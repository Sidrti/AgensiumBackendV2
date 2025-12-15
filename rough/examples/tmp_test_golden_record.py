from pathlib import Path
from agents.golden_record_builder import execute_golden_record_builder


def main() -> None:
    csv_path = Path(r"c:\Users\VIVEK BANSAL\Desktop\Agensium\Agensium-V2\backend\examples\master_my_data_inputs2\master_data_input.csv")
    file_bytes = csv_path.read_bytes()

    params = {
        "enable_fuzzy_matching": True,
        "fuzzy_threshold": 83.0,
        "match_key_columns": [
            "Email",
            "Phone",
            "FirstName",
            "LastName",
            "Address",
            "City",
            "PostalCode",
            "Country",
        ],
        "match_key_weights": {
            "Email": 40,
            "Phone": 25,
            "LastName": 12,
            "FirstName": 8,
            "Address": 8,
            "PostalCode": 4,
            "City": 2,
            "Country": 1,
        },
        "source_column": "SourceSystem",
        "source_priority": {
            "CRM": 1,
            "ERP": 2,
            "Support": 3,
            "WebPortal": 4,
            "Marketing": 5,
        },
        "default_survivorship_rule": "source_priority",
        "survivorship_rules": {
            "CustomerID": "source_priority",
            "FirstName": "most_frequent",
            "LastName": "most_frequent",
            "Email": "source_priority",
            "Phone": "source_priority",
            "Address": "most_complete",
            "City": "most_frequent",
            "State": "most_frequent",
            "PostalCode": "most_frequent",
            "Country": "most_frequent",
            "LastUpdated": "max",
        },
        "min_trust_score": 0.55,
    }

    res = execute_golden_record_builder(file_bytes, csv_path.name, params)

    print("status:", res.get("status"))
    if res.get("status") != "success":
        print("error:", res.get("error"))
        raise SystemExit(1)

    data = res["data"]
    stats = data["statistics"]

    print(
        "metrics:",
        {
            "input_records": stats.get("input_records"),
            "golden_records_created": stats.get("golden_records_created"),
            "clusters_formed": stats.get("clusters_formed"),
            "compression_ratio": stats.get("compression_ratio"),
            "average_trust_score": stats.get("average_trust_score"),
            "conflicts_resolved": stats.get("conflicts_resolved"),
        },
    )

    print(
        "fuzzy:",
        {
            "enabled": stats.get("fuzzy_matching_enabled"),
            "threshold": stats.get("fuzzy_threshold"),
            "match_key_columns_used": stats.get("match_key_columns"),
        },
    )

    clusters = data.get("golden_records", [])
    clusters_with_fuzzy_details = [c for c in clusters if "fuzzy_match_details" in c]
    merged_clusters = [c for c in clusters if c.get("source_record_count", 0) > 1]

    print(
        "cluster_counts:",
        {
            "returned_in_response": len(clusters),
            "merged_clusters": len(merged_clusters),
            "clusters_with_fuzzy_match_details_field": len(clusters_with_fuzzy_details),
        },
    )

    # Show a few merged clusters with similarity evidence
    for c in merged_clusters[:8]:
        gr = c.get("golden_record", {})
        print(
            "merged_cluster:",
            {
                "cluster_id": c.get("cluster_id"),
                "source_record_count": c.get("source_record_count"),
                "avg_similarity_score": c.get("avg_similarity_score"),
                "golden_email": gr.get("Email"),
                "golden_phone": gr.get("Phone"),
                "golden_name": f"{gr.get('FirstName')} {gr.get('LastName')}",
            },
        )
        details = c.get("fuzzy_match_details") or []
        if details:
            d0 = details[0]
            print(
                "  example_match_detail:",
                {
                    "row_index": d0.get("row_index"),
                    "similarity_score": d0.get("similarity_score"),
                    "field_scores_keys": sorted(list((d0.get("field_scores") or {}).keys())),
                },
            )


if __name__ == "__main__":
    main()
