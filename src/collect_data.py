"""
collect_data.py
Section 1: Data Collection
This script fetches metadata for UP-related datasets from India's Open Government Data.
Fetches metadata for UP-related datasets from (data.gov.in) using the real listing API.

API used:
    https://api.data.gov.in/lists?format=json
        &notfilters[source]=visualize.data.gov.in
        &filters[active]=1
        &filters[title]=uttar pradesh
        &limit=50
        &offset=0
        &sort[_score]=desc

Each page of results is saved as data/raw/page_001.json, page_002.json, 

To run and get the result files:
    python src/collect_data.py
"""

import requests
import json
import os
import time
import logging

#Configuration:

BASE_URL  = "https://api.data.gov.in/lists"
API_KEY   = "579b464db66ec23bdd0000019140842a91fd4420699e7603ccf4a7af"
LIMIT     = 50       # results per page
TARGET    = 200      # Amount of datasets we want to collect
RAW_DIR   = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

# Fixed params that be contant across pages
BASE_PARAMS = {
    "format":                    "json",
    "notfilters[source]":        "visualize.data.gov.in",
    "filters[active]":           "1",
    "filters[title]":            "uttar pradesh",
    "sort[_score]":              "desc",
    "limit":                     LIMIT,
    "api-key":                   API_KEY,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; UP-Metadata-Collector/1.0)",
    "Accept":     "application/json",
}

#Logging configuration:

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

#Helpers:

def ensure_dirs():
    os.makedirs(RAW_DIR, exist_ok=True)


def fetch_page(offset: int, retries: int = 3) -> dict | None:
    """
    Fetch one page of results from the listing API.

    Parameters
    ----------
    offset  : pagination offset (0, 50, 100, ...)
    retries : number of retry attempts on failure

    Returns
    -------
    Parsed JSON dict on success, None on total failure.
    """
    params = {**BASE_PARAMS, "offset": offset}

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                BASE_URL,
                params=params,
                headers=HEADERS,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                log.warning("API returned status != ok for offset=%d: %s", offset, data.get("message"))
                return None

            return data

        except requests.exceptions.Timeout:
            log.warning("Attempt %d/%d timed out (offset=%d). Retrying...", attempt, retries, offset)
        except requests.exceptions.HTTPError as e:
            log.warning("HTTP error on attempt %d/%d (offset=%d): %s", attempt, retries, offset, e)
        except requests.exceptions.RequestException as e:
            log.warning("Request failed on attempt %d/%d (offset=%d): %s", attempt, retries, offset, e)
        except json.JSONDecodeError:
            log.warning("Could not parse JSON on attempt %d/%d (offset=%d)", attempt, retries, offset)

        if attempt < retries:
            time.sleep(2 * attempt)   # back-off: 2s then 4s

    log.error("All %d attempts failed for offset=%d. Skipping.", retries, offset)
    return None


def save_page(data: dict, page_num: int):
    """Save raw API response to data/raw/page_NNN.json"""
    filename = os.path.join(RAW_DIR, f"page_{page_num:03d}.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info("Saved → %s", filename)

#Main collection loop

def collect():
    ensure_dirs()

    total_collected = 0
    total_available = None
    page_num        = 1
    offset          = 0

    log.info("Starting data collection from api.data.gov.in")
    log.info("Query: 'uttar pradesh' | limit per page: %d | target: %d+", LIMIT, TARGET)

    while True:
        log.info("Fetching page %d (offset %d)...", page_num, offset)

        data = fetch_page(offset)

        if data is None:
            log.error("Failed to fetch page %d — stopping early.", page_num)
            break

        records         = data.get("records", [])
        count_this_page = len(records)
        total_available = int(data.get("total", 0))

        if count_this_page == 0:
            log.info("No more results — collection complete.")
            break

        save_page(data, page_num)

        total_collected += count_this_page
        log.info(
            "Page %d done — %d records this page | %d total so far | %d available on platform",
            page_num, count_this_page, total_collected, total_available,
        )

        # Stop once we have enough
        if total_collected >= total_available:
            log.info("Fetched all available records (%d).", total_collected)
            break

        if total_collected >= TARGET:
            log.info("Reached target of %d datasets. Stopping.", TARGET)
            break

        offset   += LIMIT
        page_num += 1
        time.sleep(1)   

    log.info("── Collection finished ──")
    log.info("Total datasets collected : %d", total_collected)
    log.info("Raw files saved to       : %s", os.path.abspath(RAW_DIR))

    if total_collected < TARGET:
        log.warning(
            "Only %d datasets collected (target was %d). "
            "Check your API key or network connection.",
            total_collected, TARGET,
        )

    return total_collected


if __name__ == "__main__":
    collect()
