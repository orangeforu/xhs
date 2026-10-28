"""Export the hand-copied native template observations to a comparison CSV.

Reads only the saved evidence JSON; no network, no login, no writes outside data/.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
SOURCE = DATA / "native_template_samples_20261028.json"
OUTPUT = DATA / "native_template_comparison_20261028.csv"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT.name}")
    import json

    evidence = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = [s for s in evidence["samples"] if s["batch"] == "user_six_links"]
    if len(rows) != 6:
        raise ValueError(f"Expected 6 comparison samples, found {len(rows)}")
    fields = ["direction_label_by_user", "title", "author", "used_count_raw",
              "used_count_approx", "paid_status", "published_at", "material_count",
              "template_id", "observed_at", "source_url", "caption_claims_unverified"]
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            record = {key: row.get(key) for key in fields}
            record["caption_claims_unverified"] = "; ".join(
                row.get("caption_claims_unverified") or []) or "无"
            writer.writerow(record)
    print(f"Wrote {OUTPUT} with {len(rows)} rows; missing paid/date/material fields kept blank.")


if __name__ == "__main__":
    main()
