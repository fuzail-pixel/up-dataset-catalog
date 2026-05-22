# UP Dataset Catalog

A pipeline to collect, clean and analyse metadata about Uttar Pradesh government datasets from India's Open Government Data platform (data.gov.in), built for the SDA Metadata Registry project.

---

## Project Overview and Objective

The State Data Authority (SDA) of Uttar Pradesh is building a Metadata Registry — a central inventory of all data assets published by UP government departments. Before departments begin formally registering their datasets, SDA wants to understand what is already publicly available on national open data platforms and how well documented it is.

This project builds a three stage pipeline:
1. Collect metadata for UP-related datasets from data.gov.in
2. Clean and standardise the raw data into a single CSV
3. Analyse patterns in coverage, freshness and quality to help SDA prioritise outreach and registry design

---

## Setup Instructions

```bash
# clone the repo
git clone https://github.com/fuzail-pixel/up-dataset-catalog.git
cd up-dataset-catalog

# install dependencies
pip install -r requirements.txt
```

Python 3.10+ required.

---

## How to Run

Run the three scripts in order:

```bash
# Step 1 - collect raw metadata from data.gov.in
python src/collect_data.py

# Step 2 - clean and consolidate into a single CSV
python src/consolidate_data.py

# Step 3 - run analysis and generate charts
python src/analyse.py
```

Each script depends on the output of the previous one. Running them out of order will throw a file not found error.



---

## Project Structure

```
up-dataset-catalog/
├── src/
│   ├── collect_data.py         # Section 1 - hits API, saves raw JSON pages
│   ├── consolidate_data.py     # Section 2 - cleans raw files, outputs CSV
│   └── analyse.py              # Section 3 - generates charts and summary
├── data/
│   ├── raw/                    # raw JSON pages from collect_data.py (200 datasets)
│   └── processed/
│       └── up_dataset_catalog.csv
├── outputs/                    # charts saved here by analyse.py
├── README.md
└── requirements.txt
```

---

## Data Collection Approach

**We used the API (Option A) — not scraping.**

### What we tried first

The assignment mentioned this CKAN endpoint:
```
GET https://data.gov.in/api/3/action/package_search?q=uttar+pradesh&rows=50&start=0
```

We tested this in Postman. It returned a 200 status code which looked promising, but the response body was HTML — the platform's web page — not JSON. So this endpoint exists on data.gov.in but does not function as a real CKAN API. It just redirects to the website.

### How we found the real API

We opened the data.gov.in platform in the browser, searched for "uttar pradesh" in the APIs section, and opened the browser DevTools network tab to watch what requests the page was actually making. That revealed the real listing API endpoint:

```
GET https://api.data.gov.in/lists
    ?format=json
    &api-key=YOUR_KEY
    &filters[active]=1
    &filters[title]=uttar pradesh
    &notfilters[source]=visualize.data.gov.in
    &sort[_score]=desc
    &limit=50
    &offset=0
```

This returns proper JSON with up to 50 records per page. Pagination works by incrementing the offset by 50 each time (0, 50, 100...).

We also found a detail API per dataset:
```
GET https://www.data.gov.in/backend/dms/v1/ogdp/node-uuid/{uuid}?_format=json
```

However the detail API returns fields like `field_keywords` and `field_file_format` as numeric target IDs (e.g. `target_id: 31`) not as readable text. Without a separate taxonomy lookup endpoint there is no way to resolve these IDs. So we rely entirely on the listing API which already gives us title, organisation, sector, description and dates in plain text.

### Why API over scraping

The listing API returns clean structured JSON with exactly the fields we need. Scraping would mean parsing HTML which breaks whenever the site layout changes. The API is more reliable and easier to work with.

### API Key

Register at https://data.gov.in and generate an API key from any dataset's API tab. The key is account-wide, not dataset-specific.

---

## Consolidation Logic and Missing Values

The raw JSON from the listing API has most fields in readable form. We extract and flatten them into one row per dataset.

**Missing value approach:**
- `dataset_id` and `title` are required — rows missing either are dropped since we cannot identify or use the record
- All other fields get an empty string `""` if not available — we never drop rows silently for optional fields
- `tags` and `formats` are empty for all rows — the listing API does not expose these as readable text, only as numeric IDs in the detail API which we cannot resolve. This is documented in the code.

**Standardisation:**
- Dates converted to YYYY-MM-DD from both ISO strings and Unix timestamps
- `organization` and `sector` are lists in the API response — stored as pipe-separated strings e.g. `"Ministry of Jal Shakti|National Water Informatics Centre"`
- All string fields stripped of leading and trailing whitespace
- Deduplication by `dataset_id` — first occurrence kept

---

## Key Insights from the Analysis

**Finding 1 — Only 7 organisations across 200 datasets, all central govt**
Every single dataset in our collection comes from central government bodies. Not one UP state department appears in the results. Ministries like Jal Shakti and Census of India dominate completely. This is the most critical gap for SDA — state departments are the primary audience for the Metadata Registry but they are not publishing on national platforms at all. Outreach to state departments should be the top priority.

**Finding 2 — Descriptions exist but quality is thin in places**
None of the 200 datasets have empty descriptions which is a good sign. However 12 datasets have descriptions under 50 characters which gives almost no useful context. For a Metadata Registry to be useful, SDA should set a minimum description length and quality standard as part of the registration requirements.

**Finding 3 — Sector coverage is too narrow**
Across 200 datasets only a handful of sectors appear, with Water Resources dominating heavily. Core UP governance areas like Education, Health and Agriculture are almost completely absent. This suggests either those departments are not publishing data at all, or their datasets are not tagged with Uttar Pradesh properly. SDA needs to address both problems — recruiting underrepresented departments and enforcing proper tagging standards.

---

## Challenges, Limitations and Assumptions

**CKAN endpoint does not work**
The endpoint mentioned in the assignment (`/api/3/action/package_search`) returns HTML not JSON on data.gov.in. We found the real API through browser DevTools. Our collection is still API-based (Option A), just using the actual working endpoint.

**Tags and formats are empty**
The listing API does not expose tags or file formats as readable text. The detail API has these fields but only as numeric IDs with no lookup table available. This is a platform limitation not a code limitation. Both fields are present in the CSV with empty values and the reason is documented in the code.

**Title-only filter**
We use `filters[title]=uttar pradesh` which only matches datasets with "Uttar Pradesh" in the title. Datasets that mention UP in the description but not the title are missed. A broader search would require a different query approach.

**Network timeouts**
The data.gov.in API can be slow depending on the time of day and connection. The collect script uses a 60 second timeout with 3 retries and exponential backoff. If timeouts persist, try running at a different time.

**200 datasets is a small sample**
Our analysis is based on 200 out of 35,111 available datasets. The findings reflect patterns in this sample. To collect all available datasets, change `TARGET = 200` to `TARGET = None` in collect_data.py. Note this will take several hours depending on connection speed.
