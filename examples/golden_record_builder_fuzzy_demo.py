"""Golden Record Builder – Fuzzy Matching Demo

Run this file to understand whether fuzzy matching is working and what it does.

What it demonstrates:
- strict clustering (exact match keys) vs fuzzy clustering (weighted similarity)
- per-cluster fuzzy match details: similarity_score + field_scores
- survivorship rules resolving conflicts into a golden record
- writes the mastered (golden) CSV output decoded from the agent response

Usage (from backend/):
  python examples/golden_record_builder_fuzzy_demo.py

Notes:
- Fuzzy matching requires rapidfuzz + jellyfish; both are already listed in backend/requirements.txt.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from typing import Any, Dict

# Ensure backend/ is on sys.path when executed from repo root
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from agents.golden_record_builder import execute_golden_record_builder  # noqa: E402


def _pretty(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, default=str)


def _load_demo_csv_bytes() -> bytes:
    csv_path = os.path.join(os.path.dirname(__file__), "demo_golden_records_fuzzy.csv")
    with open(csv_path, "rb") as f:
        return f.read()


def _base_params() -> Dict[str, Any]:
    """"Perfect" parameters for this demo.

    Key ideas:
    - match_key_columns define which columns participate in similarity when fuzzy is enabled.
    - match_key_weights controls relative importance across columns.
    - fuzzy_threshold is the minimum weighted score (0-100) to join an existing cluster.
    - survivorship_rules resolve conflicts once rows are clustered.
    """

    return {
        # Similarity inputs
        "match_key_columns": ["first_name", "last_name", "email", "phone", "address", "zip"],
        "match_key_weights": {
            "email": 35,
            "phone": 25,
            "last_name": 15,
            "first_name": 10,
            "address": 10,
            "zip": 5,
        },

        # Cluster behavior
        "enable_fuzzy_matching": True,
        "fuzzy_threshold": 83.0,

        # Survivorship behavior
        "source_column": "source_system",
        "timestamp_column": "updated_at",
        "source_priority": {
            "CRM": 1,
            "Support": 2,
            "Ecommerce": 3,
        },
        "default_survivorship_rule": "most_complete",
        "survivorship_rules": {
            "email": "source_priority",
            "phone": "most_recent",
            "address": "most_complete",
            "updated_at": "most_recent",
            "loyalty_tier": "source_priority",
        },

        # Reporting
        "min_trust_score": 0.75,
        "excellent_threshold": 90,
        "good_threshold": 75,
    }


def _print_cluster_details(result: Dict[str, Any], *, label: str) -> None:
    print("\n" + "=" * 88)
    print(f"{label}")
    print("=" * 88)

    if result.get("status") != "success":
        print("ERROR:")
        print(_pretty(result))
        return

    stats = (result.get("data") or {}).get("statistics") or {}
    print("Statistics:")
    print(_pretty(stats))

    golden_records = ((result.get("data") or {}).get("golden_records")) or []
    print(f"\nGolden records returned in response: {len(golden_records)}")

    for gr in golden_records:
        cluster_id = gr.get("cluster_id")
        count = gr.get("source_record_count")
        trust = gr.get("trust_score")
        print("\n---")
        print(f"Cluster: {cluster_id} | source_record_count={count} | trust_score={trust}")
        print(f"Source row indices: {gr.get('source_row_indices')}")

        # Fuzzy diagnostics (only present when fuzzy matching is enabled AND actually used)
        if "fuzzy_match_details" in gr:
            details = gr.get("fuzzy_match_details") or []
            print(f"Fuzzy match details (new rows matched to representative): {len(details)}")
            for d in details:
                row_idx = d.get("row_index")
                sim = d.get("similarity_score")
                field_scores = d.get("field_scores") or {}

                # Show top 3 contributing fields by score (rough heuristic)
                top_fields = sorted(field_scores.items(), key=lambda kv: kv[1], reverse=True)[:3]
                print(f"  row_index={row_idx} similarity_score={sim:.2f} top_field_scores={top_fields}")
        else:
            print("(No fuzzy_match_details on this cluster in this run)")

        # Print compact golden record (without dumping huge)
        golden = gr.get("golden_record") or {}
        compact = {k: golden.get(k) for k in [
            "first_name", "last_name", "email", "phone", "address", "zip", "source_system", "updated_at", "loyalty_tier", "__trust_score__"
        ] if k in golden}
        print("Golden record (selected fields):")
        print(_pretty(compact))

    # Show a few field resolutions to see conflict handling
    field_resolutions = ((result.get("data") or {}).get("field_resolutions")) or []
    if field_resolutions:
        print("\nField resolutions (first 10):")
        print(_pretty(field_resolutions[:10]))


def _write_mastered_csv(result: Dict[str, Any], out_name: str) -> None:
    if result.get("status") != "success":
        return

    cleaned = result.get("cleaned_file") or {}
    b64 = cleaned.get("content")
    if not b64:
        print("No cleaned_file.content found; nothing to write")
        return

    out_path = os.path.join(os.path.dirname(__file__), out_name)
    raw = base64.b64decode(b64)
    with open(out_path, "wb") as f:
        f.write(raw)

    print(f"\nWrote mastered CSV: {out_path} ({len(raw)} bytes)")

    # Print first few lines as a quick peek
    try:
        preview = raw.decode("utf-8", errors="replace").splitlines()[:8]
        print("Preview (first 8 lines):")
        for line in preview:
            print("  " + line)
    except Exception:
        pass


def main() -> None:
    csv_bytes = _load_demo_csv_bytes()
    filename = "demo_golden_records_fuzzy.csv"

    # 1) Strict (non-fuzzy) run for comparison
    strict_params = _base_params()
    strict_params["enable_fuzzy_matching"] = False

    strict_result = execute_golden_record_builder(
        file_contents=csv_bytes,
        filename=filename,
        parameters=strict_params,
    )

    # 2) Fuzzy run
    fuzzy_params = _base_params()
    fuzzy_result = execute_golden_record_builder(
        file_contents=csv_bytes,
        filename=filename,
        parameters=fuzzy_params,
    )

    _print_cluster_details(strict_result, label="STRICT RUN (enable_fuzzy_matching=False)")
    _print_cluster_details(fuzzy_result, label="FUZZY RUN (enable_fuzzy_matching=True)")

    # Write mastered output from fuzzy run
    _write_mastered_csv(fuzzy_result, out_name="out_mastered_demo_golden_records_fuzzy.csv")

    print("\nDone. If fuzzy is working, the FUZZY RUN should show:")
    print("- fewer clusters than the strict run (higher compression ratio)")
    print("- fuzzy_match_details with similarity_score/field_scores for merged rows")


if __name__ == "__main__":
    main()
