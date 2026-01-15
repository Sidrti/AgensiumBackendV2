"""
Market Basket & Sequence Agent

Finds product co-purchase rules (within basket) and next-purchase sequences
(cross transaction) to support bundling, promotions, and intent prediction.

Input: CSV file (primary)
Output: Frequent itemsets, association rules, sequence transitions, alerts/issues,
        recommendations following Agensium agent response standard.
"""

import io
import time
from datetime import datetime
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter, defaultdict

import numpy as np
import polars as pl

from .agent_utils import normalize_column_names, validate_required_parameters


def _convert_numpy_types(obj: Any) -> Any:
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def _resolve_column(requested: Optional[str], available: List[str]) -> Optional[str]:
    if not requested:
        return None
    if requested in available:
        return requested
    normalized = normalize_column_names([requested], available, case_sensitive=False)
    return normalized[0] if normalized else None


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


def _safe_float(value: Any, default: float, min_value: Optional[float] = None, max_value: Optional[float] = None) -> float:
    try:
        if value is None:
            return default
        v = float(value)
        if np.isnan(v) or np.isinf(v):
            return default
    except Exception:
        return default
    if min_value is not None:
        v = max(min_value, v)
    if max_value is not None:
        v = min(max_value, v)
    return v


def _cap_list(items: List[Dict[str, Any]], limit: int = 1000) -> List[Dict[str, Any]]:
    return items[:limit] if len(items) > limit else items


def _unique_sorted(items: List[str]) -> List[str]:
    return sorted({i for i in items if i is not None and str(i).strip() != ""})


def _format_itemset(items: Tuple[str, ...]) -> List[str]:
    return [str(i) for i in items]


def _parse_datetime_series(expr: pl.Expr) -> pl.Expr:
    return (
        expr.cast(pl.Utf8, strict=False)
        .str.strip_chars()
        .str.to_datetime(strict=False)
    )


def execute_market_basket_sequence_agent(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Execute Market Basket & Sequence analysis."""

    start_time = time.time()
    parameters = parameters or {}

    # ----------------------------
    # Parse parameters (defaults aligned to analyze_my_data_tool.json)
    # ----------------------------
    industry = (parameters.get("industry") or "").strip()
    mode = (parameters.get("mode") or "within_basket").strip().lower()
    algorithm = (parameters.get("algorithm") or "fp_growth").strip().lower()

    support = _safe_float(parameters.get("support"), 0.02, 0.0, 1.0)
    confidence = _safe_float(parameters.get("confidence"), 0.3, 0.0, 1.0)
    lift = _safe_float(parameters.get("lift"), 1.2, 0.0, 100.0)

    gap_days = _safe_int(parameters.get("gap_days"), 14, 0, 365)
    top_n_rules = _safe_int(parameters.get("top_n_rules"), 50, 1, 500)

    transaction_id_column = parameters.get("transaction_id_column")
    product_id_column = parameters.get("product_id_column")
    customer_id_column = parameters.get("customer_id_column")
    timestamp_column = parameters.get("timestamp_column")

    min_items_per_transaction = _safe_int(parameters.get("min_items_per_transaction"), 1, 1, 100)
    max_itemset_length = _safe_int(parameters.get("max_itemset_length"), 3, 2, 10)

    excellent_threshold = _safe_int(parameters.get("excellent_threshold"), 90, 0, 100)
    good_threshold = _safe_int(parameters.get("good_threshold"), 75, 0, 100)

    agent_id = "market-basket-sequence-agent"
    agent_name = "Market Basket & Sequence Agent"

    try:
        # ----------------------------
        # Input validation
        # ----------------------------
        if not filename.lower().endswith(".csv"):
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": f"Unsupported file format: {filename}. Only CSV is supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        if mode not in {"within_basket", "cross_transaction"}:
            mode = "within_basket"

        if algorithm not in {"apriori", "fp_growth"}:
            algorithm = "fp_growth"

        required_params = ["product_id_column"]
        if mode == "within_basket":
            required_params.append("transaction_id_column")
        else:
            required_params.extend(["customer_id_column", "timestamp_column"])

        required_error = validate_required_parameters(parameters, required_params)
        if required_error:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": required_error,
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        # ----------------------------
        # Load CSV
        # ----------------------------
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
                "error": "File is empty or has no columns",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        # Resolve columns (case-insensitive)
        txn_col = _resolve_column(transaction_id_column, df.columns)
        product_col = _resolve_column(product_id_column, df.columns)
        customer_col = _resolve_column(customer_id_column, df.columns) if customer_id_column else None
        timestamp_col = _resolve_column(timestamp_column, df.columns) if timestamp_column else None

        missing_cols = []
        if mode == "within_basket":
            if txn_col is None:
                missing_cols.append("transaction_id_column")
        if product_col is None:
            missing_cols.append("product_id_column")
        if mode == "cross_transaction":
            if customer_col is None:
                missing_cols.append("customer_id_column")
            if timestamp_col is None:
                missing_cols.append("timestamp_column")

        if missing_cols:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": f"Selected column(s) not found in dataset: {', '.join(missing_cols)}",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        # ----------------------------
        # Standardize required fields
        # ----------------------------
        select_cols = []
        if txn_col:
            select_cols.append(pl.col(txn_col).alias("transaction_id_raw"))
        select_cols.append(pl.col(product_col).alias("product_id_raw"))
        if customer_col:
            select_cols.append(pl.col(customer_col).alias("customer_id_raw"))
        if timestamp_col:
            select_cols.append(pl.col(timestamp_col).alias("timestamp_raw"))

        working = df.select(select_cols).with_row_index("row_index")

        # Cast to strings
        if "transaction_id_raw" in working.columns:
            working = working.with_columns(
                pl.col("transaction_id_raw").cast(pl.Utf8, strict=False).str.strip_chars().alias("transaction_id")
            )
        else:
            working = working.with_columns(pl.lit(None).alias("transaction_id"))

        working = working.with_columns(
            pl.col("product_id_raw").cast(pl.Utf8, strict=False).str.strip_chars().alias("product_id")
        )

        if "customer_id_raw" in working.columns:
            working = working.with_columns(
                pl.col("customer_id_raw").cast(pl.Utf8, strict=False).str.strip_chars().alias("customer_id")
            )
        else:
            working = working.with_columns(pl.lit(None).alias("customer_id"))

        if "timestamp_raw" in working.columns:
            parsed_ts = _parse_datetime_series(pl.col("timestamp_raw"))
            working = working.with_columns(parsed_ts.alias("timestamp"))
        else:
            working = working.with_columns(pl.lit(None).alias("timestamp"))

        # ----------------------------
        # Row-level issues
        # ----------------------------
        row_level_issues: List[Dict[str, Any]] = []

        if mode == "within_basket":
            missing_txn = working.filter(pl.col("transaction_id").is_null() | (pl.col("transaction_id") == ""))
            for r in missing_txn.select(["row_index", "transaction_id_raw"]).head(400).iter_rows(named=True):
                row_level_issues.append({
                    "row_index": int(r["row_index"]),
                    "column": txn_col,
                    "issue_type": "missing_transaction_id",
                    "severity": "high",
                    "message": "Missing transaction identifier",
                    "value": r.get("transaction_id_raw"),
                })

        missing_product = working.filter(pl.col("product_id").is_null() | (pl.col("product_id") == ""))
        for r in missing_product.select(["row_index", "product_id_raw"]).head(400).iter_rows(named=True):
            row_level_issues.append({
                "row_index": int(r["row_index"]),
                "column": product_col,
                "issue_type": "missing_product_id",
                "severity": "high",
                "message": "Missing product identifier",
                "value": r.get("product_id_raw"),
            })

        if mode == "cross_transaction":
            missing_customer = working.filter(pl.col("customer_id").is_null() | (pl.col("customer_id") == ""))
            for r in missing_customer.select(["row_index", "customer_id_raw"]).head(400).iter_rows(named=True):
                row_level_issues.append({
                    "row_index": int(r["row_index"]),
                    "column": customer_col,
                    "issue_type": "missing_customer_id",
                    "severity": "high",
                    "message": "Missing customer identifier",
                    "value": r.get("customer_id_raw"),
                })

            bad_timestamp = working.filter(pl.col("timestamp").is_null() & pl.col("timestamp_raw").is_not_null())
            for r in bad_timestamp.select(["row_index", "timestamp_raw"]).head(400).iter_rows(named=True):
                row_level_issues.append({
                    "row_index": int(r["row_index"]),
                    "column": timestamp_col,
                    "issue_type": "invalid_timestamp",
                    "severity": "high",
                    "message": "Timestamp could not be parsed",
                    "value": str(r.get("timestamp_raw")),
                })

        # ----------------------------
        # Filter valid rows
        # ----------------------------
        base_filter = pl.col("product_id").is_not_null() & (pl.col("product_id") != "")
        if mode == "within_basket":
            base_filter = base_filter & pl.col("transaction_id").is_not_null() & (pl.col("transaction_id") != "")
        else:
            base_filter = (
                base_filter &
                pl.col("customer_id").is_not_null() & (pl.col("customer_id") != "") &
                pl.col("timestamp").is_not_null()
            )

        valid = working.filter(base_filter)

        total_rows = working.height
        valid_rows = valid.height
        invalid_rows = total_rows - valid_rows

        if valid_rows == 0:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": "No valid rows after parsing required fields",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        # ----------------------------
        # Analysis
        # ----------------------------
        data: Dict[str, Any] = {
            "analysis": {
                "mode": mode,
                "algorithm": algorithm,
                "industry": industry,
                "parameters": {
                    "support": support,
                    "confidence": confidence,
                    "lift": lift,
                    "gap_days": gap_days,
                    "top_n_rules": top_n_rules,
                    "min_items_per_transaction": min_items_per_transaction,
                    "max_itemset_length": max_itemset_length,
                },
                "columns_used": {
                    "transaction_id_column": txn_col,
                    "product_id_column": product_col,
                    "customer_id_column": customer_col,
                    "timestamp_column": timestamp_col,
                },
            }
        }

        alerts: List[Dict[str, Any]] = []
        issues: List[Dict[str, Any]] = []
        recommendations: List[Dict[str, Any]] = []

        # Parameter sanity issues
        if support < 0.001:
            issues.append({
                "issue_id": "issue_support_too_low",
                "agent_id": agent_id,
                "field_name": "support",
                "issue_type": "parameter_warning",
                "severity": "low",
                "message": "Support threshold is very low and may produce noisy rules.",
            })

        if confidence < 0.1:
            issues.append({
                "issue_id": "issue_confidence_too_low",
                "agent_id": agent_id,
                "field_name": "confidence",
                "issue_type": "parameter_warning",
                "severity": "low",
                "message": "Confidence threshold is very low and may produce weak rules.",
            })

        # Quality score
        invalid_rate = (invalid_rows / total_rows * 100.0) if total_rows > 0 else 0.0
        quality_score = max(0.0, 100.0 - invalid_rate)
        if quality_score >= excellent_threshold:
            quality_status = "excellent"
        elif quality_score >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"

        if invalid_rate > 10:
            alerts.append({
                "alert_id": "alert_market_basket_invalid_rows",
                "severity": "high" if invalid_rate <= 25 else "critical",
                "category": "data_quality",
                "message": f"{invalid_rate:.1f}% of rows were invalid for analysis (missing required identifiers).",
                "affected_fields_count": 2,
                "recommendation": "Fix missing IDs or timestamps and re-run analysis for reliable insights.",
            })

        if mode == "within_basket":
            baskets = (
                valid.select(["transaction_id", "product_id"])
                .group_by("transaction_id")
                .agg(pl.col("product_id").alias("products"))
            )

            # Convert to list of unique product lists
            baskets_list = [
                _unique_sorted(row["products"]) for row in baskets.iter_rows(named=True)
            ]

            # Filter by min_items_per_transaction
            baskets_list = [b for b in baskets_list if len(b) >= min_items_per_transaction]
            total_transactions = len(baskets_list)

            if total_transactions == 0:
                return {
                    "status": "error",
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "error": "No transactions meet the minimum items per transaction requirement",
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                }

            item_counts: Counter = Counter()
            itemset_counts: Counter = Counter()

            for items in baskets_list:
                if not items:
                    continue
                for item in items:
                    item_counts[(item,)] += 1
                max_len = min(max_itemset_length, len(items))
                for size in range(2, max_len + 1):
                    for combo in combinations(items, size):
                        itemset_counts[combo] += 1

            all_counts = Counter()
            all_counts.update(item_counts)
            all_counts.update(itemset_counts)

            frequent_itemsets = []
            for itemset, count in all_counts.items():
                support_value = count / float(total_transactions)
                if support_value + 1e-12 >= support:
                    frequent_itemsets.append({
                        "items": _format_itemset(itemset),
                        "size": len(itemset),
                        "count": int(count),
                        "support": round(float(support_value), 6),
                    })

            frequent_itemsets.sort(key=lambda x: (x["support"], x["count"]), reverse=True)

            rules = []
            for itemset, count in itemset_counts.items():
                size = len(itemset)
                if size < 2:
                    continue
                support_itemset = count / float(total_transactions)
                if support_itemset + 1e-12 < support:
                    continue
                for consequent in itemset:
                    antecedent = tuple(sorted(i for i in itemset if i != consequent))
                    antecedent_count = all_counts.get(antecedent, 0)
                    consequent_count = all_counts.get((consequent,), 0)
                    if antecedent_count <= 0 or consequent_count <= 0:
                        continue

                    confidence_value = support_itemset / (antecedent_count / float(total_transactions))
                    lift_value = confidence_value / (consequent_count / float(total_transactions))

                    if confidence_value + 1e-12 < confidence:
                        continue
                    if lift_value + 1e-12 < lift:
                        continue

                    rules.append({
                        "antecedent": list(antecedent),
                        "consequent": [consequent],
                        "support": round(float(support_itemset), 6),
                        "confidence": round(float(confidence_value), 6),
                        "lift": round(float(lift_value), 6),
                    })

            rules.sort(key=lambda x: (x["lift"], x["confidence"], x["support"]), reverse=True)
            rules = rules[:top_n_rules]

            unique_products = len(item_counts)

            data["within_basket"] = {
                "transactions": int(total_transactions),
                "unique_products": int(unique_products),
                "frequent_itemsets": frequent_itemsets[:max(100, top_n_rules)],
                "association_rules": rules,
            }

            if total_transactions < 50:
                alerts.append({
                    "alert_id": "alert_market_basket_low_volume",
                    "severity": "medium",
                    "category": "data_volume",
                    "message": f"Only {total_transactions} transactions available for basket analysis. Rules may be unstable.",
                    "affected_fields_count": 0,
                    "recommendation": "Use more transactions or a longer timeframe for more stable rules.",
                })

            if len(rules) == 0:
                recommendations.append({
                    "recommendation_id": "rec_market_basket_thresholds",
                    "agent_id": agent_id,
                    "field_name": "parameters",
                    "priority": "high",
                    "recommendation": "No association rules met the thresholds. Consider lowering support/confidence or increasing max_itemset_length.",
                    "timeline": "immediate",
                })

            top_rule = rules[0] if rules else None
            top_lift = float(top_rule.get("lift", 0.0)) if top_rule else 0.0

            executive_summary = [
                {
                    "summary_id": "exec_market_transactions",
                    "title": "Transactions Analyzed",
                    "value": str(total_transactions),
                    "status": "good" if total_transactions >= 50 else "warning",
                    "description": f"Processed {total_transactions} transactions for within-basket analysis.",
                },
                {
                    "summary_id": "exec_market_rules",
                    "title": "Association Rules",
                    "value": str(len(rules)),
                    "status": "excellent" if len(rules) >= 10 else "good" if len(rules) >= 3 else "warning",
                    "description": "Number of rules meeting support/confidence/lift thresholds.",
                },
                {
                    "summary_id": "exec_market_top_lift",
                    "title": "Top Lift",
                    "value": f"{top_lift:.2f}",
                    "status": "excellent" if top_lift >= 2 else "good" if top_lift >= 1.5 else "fair",
                    "description": "Highest lift among valid rules.",
                },
            ]

            ai_analysis_text = "\n".join([
                "MARKET BASKET ANALYSIS RESULTS:",
                f"- Transactions analyzed: {total_transactions}",
                f"- Unique products: {unique_products}",
                f"- Rules generated: {len(rules)} (support >= {support}, confidence >= {confidence}, lift >= {lift})",
                f"- Data quality score: {quality_score:.1f}/100 ({quality_status}), invalid rows: {invalid_rate:.1f}%",
            ])

            summary_metrics = {
                "total_rows_processed": int(valid_rows),
                "total_transactions": int(total_transactions),
                "unique_products": int(unique_products),
                "rules_generated": int(len(rules)),
                "invalid_rows": int(invalid_rows),
            }

        else:
            # Cross-transaction sequence mining
            events = valid.select(["customer_id", "timestamp", "product_id"])
            baskets = (
                events.group_by(["customer_id", "timestamp"])
                .agg(pl.col("product_id").alias("products"))
                .sort(["customer_id", "timestamp"])
            )

            total_baskets = baskets.height
            customers = baskets.get_column("customer_id").unique().to_list() if total_baskets > 0 else []

            transition_counts: Counter = Counter()
            antecedent_counts: Counter = Counter()
            consequent_counts: Counter = Counter()
            gap_sums: defaultdict = defaultdict(float)

            total_transition_steps = 0

            # Group by customer for sequential processing
            grouped = baskets.partition_by("customer_id", as_dict=True, maintain_order=True)
            for _, group in grouped.items():
                rows = list(group.iter_rows(named=True))
                for idx in range(len(rows) - 1):
                    current = rows[idx]
                    nxt = rows[idx + 1]
                    t1 = current.get("timestamp")
                    t2 = nxt.get("timestamp")
                    if t1 is None or t2 is None:
                        continue
                    gap = (t2 - t1).days
                    if gap > gap_days:
                        continue

                    items_a = _unique_sorted(current.get("products", []))
                    items_b = _unique_sorted(nxt.get("products", []))
                    if not items_a or not items_b:
                        continue

                    total_transition_steps += 1
                    for a in items_a:
                        antecedent_counts[a] += 1
                    for b in items_b:
                        consequent_counts[b] += 1

                    for a in items_a:
                        for b in items_b:
                            transition_counts[(a, b)] += 1
                            gap_sums[(a, b)] += float(gap)

            if total_transition_steps == 0:
                return {
                    "status": "error",
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "error": "No valid cross-transaction transitions found within gap_days",
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                }

            sequence_rules = []
            for (a, b), count in transition_counts.items():
                support_value = count / float(total_transition_steps)
                if support_value + 1e-12 < support:
                    continue
                denom = antecedent_counts.get(a, 0)
                if denom <= 0:
                    continue
                confidence_value = count / float(denom)
                if confidence_value + 1e-12 < confidence:
                    continue
                consequent_support = consequent_counts.get(b, 0) / float(total_transition_steps)
                lift_value = confidence_value / consequent_support if consequent_support > 0 else 0.0
                if lift_value + 1e-12 < lift:
                    continue

                avg_gap = gap_sums[(a, b)] / max(1, count)
                sequence_rules.append({
                    "from_item": a,
                    "to_item": b,
                    "count": int(count),
                    "support": round(float(support_value), 6),
                    "confidence": round(float(confidence_value), 6),
                    "lift": round(float(lift_value), 6),
                    "avg_gap_days": round(float(avg_gap), 2),
                })

            sequence_rules.sort(key=lambda x: (x["lift"], x["confidence"], x["support"]), reverse=True)
            sequence_rules = sequence_rules[:top_n_rules]

            # Next purchase predictions (top consequents)
            next_purchase = []
            for product, count in consequent_counts.most_common(20):
                support_value = count / float(total_transition_steps)
                next_purchase.append({
                    "product": product,
                    "support": round(float(support_value), 6),
                })

            unique_products = len(set(antecedent_counts.keys()).union(set(consequent_counts.keys())))

            data["cross_transaction"] = {
                "customers": int(len(customers)),
                "transactions": int(total_baskets),
                "total_transitions": int(total_transition_steps),
                "unique_products": int(unique_products),
                "sequence_rules": sequence_rules,
                "next_purchase_predictions": next_purchase,
            }

            if total_transition_steps < 50:
                alerts.append({
                    "alert_id": "alert_sequence_low_transitions",
                    "severity": "medium",
                    "category": "data_volume",
                    "message": f"Only {total_transition_steps} transitions found for sequence analysis. Results may be unstable.",
                    "affected_fields_count": 0,
                    "recommendation": "Increase the time window or reduce gap_days to capture more transitions.",
                })

            if len(sequence_rules) == 0:
                recommendations.append({
                    "recommendation_id": "rec_sequence_thresholds",
                    "agent_id": agent_id,
                    "field_name": "parameters",
                    "priority": "high",
                    "recommendation": "No sequence rules met the thresholds. Consider lowering support/confidence or increasing gap_days.",
                    "timeline": "immediate",
                })

            top_rule = sequence_rules[0] if sequence_rules else None
            top_lift = float(top_rule.get("lift", 0.0)) if top_rule else 0.0

            executive_summary = [
                {
                    "summary_id": "exec_sequence_transitions",
                    "title": "Transitions Analyzed",
                    "value": str(total_transition_steps),
                    "status": "good" if total_transition_steps >= 50 else "warning",
                    "description": f"Analyzed {total_transition_steps} customer transitions across transactions.",
                },
                {
                    "summary_id": "exec_sequence_rules",
                    "title": "Sequence Rules",
                    "value": str(len(sequence_rules)),
                    "status": "excellent" if len(sequence_rules) >= 10 else "good" if len(sequence_rules) >= 3 else "warning",
                    "description": "Number of sequence rules meeting thresholds.",
                },
                {
                    "summary_id": "exec_sequence_top_lift",
                    "title": "Top Lift",
                    "value": f"{top_lift:.2f}",
                    "status": "excellent" if top_lift >= 2 else "good" if top_lift >= 1.5 else "fair",
                    "description": "Highest lift among sequence rules.",
                },
            ]

            ai_analysis_text = "\n".join([
                "SEQUENCE ANALYSIS RESULTS:",
                f"- Customers analyzed: {len(customers)}",
                f"- Transactions: {total_baskets}",
                f"- Transitions analyzed: {total_transition_steps}",
                f"- Sequence rules generated: {len(sequence_rules)} (support >= {support}, confidence >= {confidence}, lift >= {lift})",
                f"- Data quality score: {quality_score:.1f}/100 ({quality_status}), invalid rows: {invalid_rate:.1f}%",
            ])

            summary_metrics = {
                "total_rows_processed": int(valid_rows),
                "total_transactions": int(total_baskets),
                "unique_products": int(unique_products),
                "sequences_generated": int(len(sequence_rules)),
                "invalid_rows": int(invalid_rows),
            }

        # Recommendations common
        recommendations.append({
            "recommendation_id": "rec_market_basket_activation",
            "agent_id": agent_id,
            "field_name": "insights",
            "priority": "medium",
            "recommendation": "Use top rules to create bundles, cross-sell offers, or on-site recommendations.",
            "timeline": "1-2 weeks",
        })

        # Issue summary aggregation
        row_level_issues = _cap_list(row_level_issues, 1000)
        issue_summary = {
            "total_issues": len(row_level_issues),
            "by_type": {},
            "by_severity": {},
            "affected_rows": len(set(i.get("row_index") for i in row_level_issues if i.get("row_index") is not None)),
            "affected_columns": sorted(list(set(i.get("column") for i in row_level_issues if i.get("column")))),
        }

        for issue in row_level_issues:
            t = issue.get("issue_type", "unknown")
            s = issue.get("severity", "info")
            issue_summary["by_type"][t] = issue_summary["by_type"].get(t, 0) + 1
            issue_summary["by_severity"][s] = issue_summary["by_severity"].get(s, 0) + 1

        # Convert data to JSON-safe
        def _convert_obj(val: Any) -> Any:
            if isinstance(val, dict):
                return {k: _convert_obj(v) for k, v in val.items()}
            if isinstance(val, list):
                return [_convert_obj(v) for v in val]
            return _convert_numpy_types(val)

        data = _convert_obj(data)

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

    except Exception as e:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }
