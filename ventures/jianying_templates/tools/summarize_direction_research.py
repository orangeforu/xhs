"""Reproduce descriptive sample statistics; never rank revenue from engagement."""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
RAW = DATA / "direction_research_20261028.json"
LABELS = DATA / "direction_content_labels_20261028.csv"
OUTPUT = DATA / "direction_summary_20261028.json"
CSV_OUTPUT = DATA / "direction_summary_20261028.csv"
LABEL_SET = {"tutorial", "template_demo", "asset_pack", "tool_promotion",
             "end_user_request", "other", "unknown"}


def unique(rows):
    return list({row["id"]: row for row in rows}.values())


def median(rows, key):
    values = [row[key] for row in rows if row.get(key) is not None]
    return statistics.median(values) if values else None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if OUTPUT.exists() or CSV_OUTPUT.exists():
        raise FileExistsError("Refusing to overwrite an existing analysis")
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    with LABELS.open(encoding="utf-8-sig", newline="") as handle:
        label_rows = list(csv.DictReader(handle))
    labels = {row["id"]: row for row in label_rows}
    all_rows = [row for query in raw["queries"] for row in query["items"]]
    all_ids = {row["id"] for row in all_rows}
    assert len(labels) == len(label_rows) and set(labels) == all_ids
    assert all(row["label"] in LABEL_SET for row in label_rows)
    rows = []
    for direction in dict.fromkeys(query["direction"] for query in raw["queries"]):
        for mode in ("综合", "最新", "合并"):
            subset = unique(row for query in raw["queries"]
                            if query["direction"] == direction
                            and (mode == "合并" or query["sort"] == mode)
                            for row in query["items"])
            counts = Counter(labels[row["id"]]["label"] for row in subset)
            rec = {
                "direction": direction, "sort": mode, "unique_notes": len(subset),
                "median_likes": median(subset, "likes"),
                "median_collects": median(subset, "collects"),
                "median_comments": median(subset, "comments"),
                "missing_titles": sum(not row["title"] for row in subset),
                "detail_checked": sum(labels[row["id"]]["evidence_basis"] == "detail_checked"
                                      for row in subset),
            }
            rec.update({label: counts[label] for label in sorted(LABEL_SET)})
            assert sum(counts.values()) == len(subset)
            rows.append(rec)
    result = {
        "source_platform": raw["platform"], "retrieved_at": raw["retrieved_at"],
        "record_count": len(all_rows), "unique_notes": len(all_ids),
        "source_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
        "labels_sha256": hashlib.sha256(LABELS.read_bytes()).hexdigest(),
        "dedup_rule": "Per direction/sort keep the last observed record for each id",
        "warning": "Convenience sample; labels describe content, not purchase intent; no earnings ranking",
        "global_labels": dict(Counter(row["label"] for row in label_rows)),
        "rows": rows,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with CSV_OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
