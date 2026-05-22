"""
consolidate_data.py
-------------------
Section 2: Data Consolidation & Transformation

Reads all raw JSON files from data/raw/, extracts and flattens fields into
one row per dataset, cleans and standardises them, deduplicates by dataset_id,
and writes the final output to data/processed/up_dataset_catalog.csv.

Missing value strategy:
- dataset_id : REQUIRED — rows without one are dropped (cannot deduplicate)
- title       : REQUIRED — rows without a title are dropped (unusable record)
- All others  : filled with "" (empty string) — never silently dropped.
  Analysis code treats "" as missing rather than NaN.

To run and get the result files:
    python src/consolidate_data.py
"""

import os
import json
import csv
import logging
from datetime import datetime, timezone

#Configuration
RAW_DIR       = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
OUTPUT_FILE   = os.path.join(PROCESSED_DIR, "up_dataset_catalog.csv")

COLUMNS = [
    "dataset_id",
    "title",
    "organization",
    "sector",
    "tags",
    "formats",
    "num_resources",
    "metadata_created",
    "metadata_modified",
    "description",
    "source_url",
]

#Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

#Helpers for parsing dates, joining lists, extracting formats, and flattening records.
def parse_date(raw) -> str:
    """
    Convert a date value to YYYY-MM-DD format.
    Handles:
- Unix timestamps (int or float)
    """
    if not raw:
        return ""

    # Unix timestamp (int or float)
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(raw, tz=timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            return ""

    # ISO string
    raw = str(raw).strip()
    if not raw:
        return ""

    formats_to_try = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats_to_try:
        try:
            return datetime.strptime(raw[:19], fmt[:len(fmt)]).strftime("%Y-%m-%d")
        except ValueError:
            continue

    log.debug("Could not parse date: '%s'", raw)
    return raw[:10] if len(raw) >= 10 else raw


def join_list(value, sep="|") -> str:
    """
    Convert a list of strings to a pipe-separated string.if already return stripped.
    """
    if isinstance(value, list):
        return sep.join(str(v).strip() for v in value if str(v).strip())
    if isinstance(value, str):
        return value.strip()
    return ""


def extract_formats(fields: list) -> str:
    """
    The listing API returns a 'field' array describing dataset columns.
    Each field has a 'type' (keyword, double ,etc) — not a file format.
    Since the listing API does not expose file formats directly, we return it 
    and note this limitation. The detail API would be needed to resolve this,
    but it only returns target_ids without a lookup table.
    """
    # If any field name hints at a format, capture it
    # Otherwise return empty — honest about the limitation
    return ""


def flatten_record(record: dict) -> dict:
    """
    Convert one raw listing API record into a flat row matching COLUMNS.
    """
    fields = record.get("field", [])

    # Build source URL from path alias or index_name
    index_name = (record.get("index_name") or "").strip()
    source_url = f"https://www.data.gov.in/resource/{index_name}" if index_name else ""

    row = {
        "dataset_id":        index_name,
        "title":             (record.get("title") or "").strip(),
        "organization":      join_list(record.get("org", [])),
        "sector":            join_list(record.get("sector", [])),
        "tags":              "",          # not available in listing API
        "formats":           extract_formats(fields),
        "num_resources":     str(len(fields)) if fields else "0",
        "metadata_created":  parse_date(record.get("created_date") or record.get("created")),
        "metadata_modified": parse_date(record.get("updated_date") or record.get("updated")),
        "description":       (record.get("desc") or "").strip(),
        "source_url":        source_url,
    }
    return row


#Main pipeline steps:
def load_raw_files() -> list:
    """Read all page_*.json files and return a flat list of records."""
    all_records = []
    raw_files = sorted(
        f for f in os.listdir(RAW_DIR)
        if f.startswith("page_") and f.endswith(".json")
    )

    if not raw_files:
        log.error("No raw files found in %s. Run collect_data.py first.", RAW_DIR)
        return []

    for filename in raw_files:
        filepath = os.path.join(RAW_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            records = data.get("records", [])
            all_records.extend(records)
            log.info("Loaded %s — %d records", filename, len(records))
        except (json.JSONDecodeError, KeyError) as e:
            log.warning("Skipping %s — could not parse: %s", filename, e)

    log.info("Total raw records loaded: %d", len(all_records))
    return all_records


def consolidate():
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    # Step 1: Load
    records = load_raw_files()
    if not records:
        return

    # Step 2: Flatten
    rows = []
    dropped_no_id    = 0
    dropped_no_title = 0

    for rec in records:
        row = flatten_record(rec)

        if not row["dataset_id"]:
            dropped_no_id += 1
            continue
        if not row["title"]:
            dropped_no_title += 1
            continue

        rows.append(row)

    log.info("Rows after flattening   : %d", len(rows))
    log.info("Dropped (no dataset_id) : %d", dropped_no_id)
    log.info("Dropped (no title)      : %d", dropped_no_title)

    # Step 3: Deduplicate by dataset_id — keep first occurrence
    seen        = set()
    unique_rows = []
    for row in rows:
        did = row["dataset_id"]
        if did not in seen:
            seen.add(did)
            unique_rows.append(row)

    log.info("Duplicates removed      : %d", len(rows) - len(unique_rows))
    log.info("Final unique rows       : %d", len(unique_rows))

    # Step 4: Write CSV
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(unique_rows)

    log.info("── Consolidation complete ──")
    log.info("Output saved to: %s", os.path.abspath(OUTPUT_FILE))

    # Step 5: Quick preview
    log.info("── Preview (first 3 rows) ──")
    for row in unique_rows[:3]:
        log.info("  %s | %s | %s | %s",
                 row["dataset_id"][:8],
                 row["title"][:40],
                 row["organization"][:30],
                 row["metadata_created"])


if __name__ == "__main__":
    consolidate()