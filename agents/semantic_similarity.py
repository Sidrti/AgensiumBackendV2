"""
Semantic Similarity Agent

Node‑05: Vector Context

Uses local text embeddings to detect semantically similar invoices that may not match
exactly on fields but are meaningfully alike in description, vendor context, and notes.

Input: Single CSV file (normalized invoice table)
Output: Semantic match pairs, similarity scores, diagnostics, alerts/issues/recommendations
        following Agentsium agent response standard.
"""

import io
import time
from typing import Any, Dict, List, Optional

import numpy as np
import polars as pl
from sentence_transformers import SentenceTransformer


# ----------------------------
# Embedding model (lazy-loaded)
# ----------------------------

_EMBEDDING_MODEL: Optional[SentenceTransformer] = None


def _get_embedding_model() -> SentenceTransformer:
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        # You can swap this for any other local model you prefer
        _EMBEDDING_MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _EMBEDDING_MODEL


# ----------------------------
# Helper functions
# ----------------------------

def _safe_int(value: Any, default: int, min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
    try:
        if value is None:
            return default
        v = int(value)
    except Exception:
        return default
    if min_value is not None:
        v = max(min_value, v)
    if max_value is not None:
        v = min(max_value, v)
    return v


def _fmt_money(value: float) -> str:
    try:
        return f"${value:,.2f}"
    except Exception:
        return "$0.00"


def _cosine_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    """
    Compute cosine similarity matrix for embeddings.
    embeddings: (n, d)
    returns: (n, n) similarity matrix in [0, 1]
    """
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-12
    normalized = embeddings / norms
    return np.matmul(normalized, normalized.T)


# ----------------------------
# Main agent entrypoint
# ----------------------------

def execute_semantic_similarity_agent(
    file_contents: Optional[bytes] = None,
    filename: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    start_time = time.time()
    parameters = parameters or {}

    agent_id = "semantic-similarity-agent"
    agent_name = "Semantic Similarity Agent"

    # ----------------------------
    # Parse global parameters
    # ----------------------------
    excellent_threshold = _safe_int(parameters.get("excellent_threshold"), 90, 0, 100)
    good_threshold = _safe_int(parameters.get("good_threshold"), 75, 0, 100)

    similarity_threshold = _safe_int(parameters.get("similarity_threshold"), 85, 1, 100)
    max_pairs = _safe_int(parameters.get("max_pairs"), 500, 10, 5000)
    max_rows_for_pairs = _safe_int(parameters.get("max_rows_for_pairs"), 1000, 10, 5000)
    max_preview_rows = _safe_int(parameters.get("max_preview_rows"), 50, 1, 500)

    alerts: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    row_level_issues: List[Dict[str, Any]] = []
    recommendations: List[Dict[str, Any]] = []

    # ----------------------------
    # Input validation
    # ----------------------------
    if file_contents is None or filename is None:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": "Semantic Similarity requires a normalized invoice CSV file.",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    if not filename.lower().endswith(".csv"):
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": f"Unsupported file format: {filename}. Only CSV is supported.",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    try:
        df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000)
    except Exception as e:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": f"Failed to parse CSV: {str(e)}",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    if df.height == 0 or df.width == 0:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": "Input file is empty or has no columns.",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    df = df.with_row_index("row_index")

    # ----------------------------
    # Determine text fields to embed
    # ----------------------------
    candidate_text_fields = [
        "vendor_name",
        "description",
        "invoice_description",
        "memo",
        "notes",
        "line_description",
    ]
    embedding_fields = [f for f in candidate_text_fields if f in df.columns]

    if not embedding_fields:
        issues.append({
            "issue_id": "no_text_fields",
            "agent_id": agent_id,
            "field_name": "",
            "issue_type": "missing_field",
            "severity": "high",
            "message": "No suitable text fields found for semantic similarity (expected one of vendor_name, description, invoice_description, memo, notes, line_description).",
        })
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": "No text fields available for semantic similarity.",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "issues": issues,
        }

    # ----------------------------
    # Build text corpus per row
    # ----------------------------
    def _build_text(row: Dict[str, Any]) -> str:
        parts = []
        for f in embedding_fields:
            v = row.get(f)
            if v is not None:
                parts.append(str(v))
        return " | ".join(parts) if parts else ""

    total_rows = df.height
    if total_rows > max_rows_for_pairs:
        alerts.append({
            "alert_id": "alert_row_cap",
            "severity": "info",
            "category": "performance",
            "message": f"Row count ({total_rows}) exceeds max_rows_for_pairs ({max_rows_for_pairs}). Only first {max_rows_for_pairs} rows will be used for pairwise similarity.",
            "affected_fields_count": 1,
            "recommendation": "Increase max_rows_for_pairs if you need full coverage, at the cost of performance.",
        })

    df_subset = df.head(max_rows_for_pairs)
    rows = df_subset.to_dicts()
    texts = [_build_text(r) for r in rows]

    # ----------------------------
    # Compute embeddings
    # ----------------------------
    try:
        model = _get_embedding_model()
        embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    except Exception as e:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": f"Failed to compute embeddings: {str(e)}",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    if embeddings.shape[0] == 0:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": "No embeddings could be computed.",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    # ----------------------------
    # Pairwise cosine similarity
    # ----------------------------
    sim_matrix = _cosine_similarity_matrix(embeddings)  # [0,1]
    n = sim_matrix.shape[0]

    semantic_pairs: List[Dict[str, Any]] = []
    count = 0
    threshold_float = similarity_threshold / 100.0

    for i in range(n):
        if count >= max_pairs:
            break
        for j in range(i + 1, n):
            if count >= max_pairs:
                break
            sim = float(sim_matrix[i, j])
            if sim >= threshold_float:
                a = rows[i]
                b = rows[j]
                semantic_pairs.append({
                    "row_a": a["row_index"],
                    "row_b": b["row_index"],
                    "similarity": round(sim * 100.0, 1),
                    "text_a": texts[i],
                    "text_b": texts[j],
                })
                count += 1

    semantic_pairs_sorted = sorted(semantic_pairs, key=lambda x: -x["similarity"])
    semantic_count = len(semantic_pairs_sorted)

    # ----------------------------
    # Quality scoring
    # ----------------------------
    quality_score = 100.0

    if semantic_count == 0:
        quality_score -= 20.0

    if semantic_count > max_pairs * 0.8:
        quality_score -= 10.0

    quality_score = max(0.0, min(100.0, quality_score))

    if quality_score >= excellent_threshold:
        quality_status = "excellent"
    elif quality_score >= good_threshold:
        quality_status = "good"
    else:
        quality_status = "needs_improvement"

    # ----------------------------
    # Recommendations
    # ----------------------------
    if semantic_count > 0:
        recommendations.append({
            "recommendation_id": "rec_review_semantic_matches",
            "agent_id": agent_id,
            "field_name": "semantic_similarity",
            "priority": "high",
            "recommendation": "Review semantic match pairs. These invoices are textually similar and may represent subtle duplicates.",
            "timeline": "immediate",
        })

    if semantic_count == 0:
        recommendations.append({
            "recommendation_id": "rec_adjust_semantic_threshold",
            "agent_id": agent_id,
            "field_name": "similarity_threshold",
            "priority": "medium",
            "recommendation": "No semantic matches detected. Consider lowering similarity_threshold or expanding the text fields used.",
            "timeline": "next sprint",
        })

    # ----------------------------
    # Executive summary
    # ----------------------------
    executive_summary = [
        {
            "summary_id": "exec_rows",
            "title": "Rows Considered",
            "value": f"{df_subset.height:,}",
            "status": "info",
            "description": "Number of rows included in semantic similarity analysis.",
        },
        {
            "summary_id": "exec_semantic_pairs",
            "title": "Semantic Match Pairs",
            "value": f"{semantic_count:,}",
            "status": "warning" if semantic_count > 0 else "success",
            "description": "Number of invoice pairs exceeding the semantic similarity threshold.",
        },
        {
            "summary_id": "exec_similarity_threshold",
            "title": "Similarity Threshold",
            "value": f"{similarity_threshold}%",
            "status": "info",
            "description": "Minimum cosine similarity (scaled to %) required to flag a semantic near‑match.",
        },
        {
            "summary_id": "exec_quality",
            "title": "Semantic Match Quality",
            "value": f"{quality_score:.1f}",
            "status": quality_status,
            "description": "Overall health of semantic similarity detection.",
        },
    ]

    # ----------------------------
    # Issue summary
    # ----------------------------
    issue_summary = {
        "total_issues": len(row_level_issues),
        "by_type": {},
        "by_severity": {},
        "affected_rows": 0,
        "affected_columns": [],
    }

    # ----------------------------
    # Defaults / overrides / final parameters
    # ----------------------------
    defaults = {
        "excellent_threshold": 90,
        "good_threshold": 75,
        "similarity_threshold": 85,
        "max_pairs": 500,
        "max_rows_for_pairs": 1000,
        "max_preview_rows": 50,
    }
    overrides = {
        "excellent_threshold": parameters.get("excellent_threshold"),
        "good_threshold": parameters.get("good_threshold"),
        "similarity_threshold": parameters.get("similarity_threshold"),
        "max_pairs": parameters.get("max_pairs"),
        "max_rows_for_pairs": parameters.get("max_rows_for_pairs"),
        "max_preview_rows": parameters.get("max_preview_rows"),
    }
    final_params = {
        "excellent_threshold": excellent_threshold,
        "good_threshold": good_threshold,
        "similarity_threshold": similarity_threshold,
        "max_pairs": max_pairs,
        "max_rows_for_pairs": max_rows_for_pairs,
        "max_preview_rows": max_preview_rows,
    }

    # ----------------------------
    # Data payload
    # ----------------------------
    data = {
        "embedding_fields": embedding_fields,
        "semantic_pairs": semantic_pairs_sorted[:max_preview_rows],
        "similarity_threshold": similarity_threshold,
        "quality": {
            "plan_quality_score": round(quality_score, 1),
            "quality_status": quality_status,
        },
        "defaults": defaults,
        "overrides": overrides,
        "parameters": final_params,
    }

    # ----------------------------
    # Summary metrics
    # ----------------------------
    summary_metrics = {
        "rows_processed": total_rows,
        "rows_analyzed": df_subset.height,
        "semantic_pairs": semantic_count,
        "quality_score": round(quality_score, 1),
    }

    # ----------------------------
    # AI analysis text
    # ----------------------------
    ai_analysis_text = "\n".join([
        "SEMANTIC SIMILARITY RESULTS:",
        f"- Rows processed: {total_rows:,}",
        f"- Rows analyzed for pairs: {df_subset.height:,}",
        f"- Semantic match pairs: {semantic_count:,}",
        f"- Similarity threshold: {similarity_threshold}%",
        f"- Quality score: {quality_score:.1f} ({quality_status})",
    ])

    return {
        "status": "success",
        "agent_id": agent_id,
        "agent_name": agent_name,
        "execution_time_ms": int((time.time() - start_time) * 1000),
        "summary_metrics": summary_metrics,
        "data": data,
        "alerts": alerts,
        "issues": issues,
        "row_level_issues": row_level_issues,
        "issue_summary": issue_summary,
        "recommendations": recommendations,
        "executive_summary": executive_summary,
        "ai_analysis_text": ai_analysis_text,
    }
