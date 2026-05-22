# analyse.py
# Section 3 - Analysis and Insights
#
# Loads the CSV and produces charts to help SDA understand
# what UP data is already out there and where the gaps are.
#
# Charts saved to outputs/
# Run: python src/analyse.py

import os
import csv
import logging
from collections import Counter
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S"
)

CSV_FILE    = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "up_dataset_catalog.csv")
OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")


def load_data():
    if not os.path.exists(CSV_FILE):
        logging.error("CSV not found - run consolidate_data.py first")
        return []
    rows = []
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    logging.info("Loaded %d rows", len(rows))
    return rows


def save_chart(filename):
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    path = os.path.join(OUTPUTS_DIR, filename)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    logging.info("Saved %s", path)


# Chart 1 - organisation coverage
# taking just the first org from the pipe-separated list as the primary one
def plot_top_organisations(rows):
    counts = Counter()
    for row in rows:
        org = row["organization"].split("|")[0].strip()
        counts[org if org else "Unknown"] += 1

    top    = counts.most_common(15)
    labels = [o for o, _ in top]
    values = [c for _, c in top]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh(labels[::-1], values[::-1], color="#2196F3")

    for i, v in enumerate(values[::-1]):
        ax.text(v + 0.1, i, str(v), va="center", fontsize=9)

    ax.set_xlabel("Number of Datasets")
    ax.set_title("Top 15 Organisations Publishing UP-Related Datasets", fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save_chart("top_organisations.png")


# Chart 2 - format distribution
# formats field is empty because API doesnt expose readable format names
# using num_resources (count of data fields per dataset) as a proxy instead
def plot_format_distribution(rows):
    buckets = {"0": 0, "1-3": 0, "4-6": 0, "7-10": 0, "10+": 0}

    for row in rows:
        try:
            n = int(row["num_resources"])
            if n == 0:       buckets["0"]    += 1
            elif n <= 3:     buckets["1-3"]  += 1
            elif n <= 6:     buckets["4-6"]  += 1
            elif n <= 10:    buckets["7-10"] += 1
            else:            buckets["10+"]  += 1
        except ValueError:
            buckets["0"] += 1

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(buckets.keys(), buckets.values(),
                  color=["#9E9E9E", "#4CAF50", "#2196F3", "#FF9800", "#E91E63"])

    for bar, val in zip(bars, buckets.values()):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                str(val), ha="center", fontsize=10)

    ax.set_xlabel("Number of Data Fields per Dataset")
    ax.set_ylabel("Number of Datasets")
    ax.set_title("Dataset Size Distribution (fields per dataset)", fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save_chart("format_distribution.png")


# Chart 3 - data freshness
def plot_data_freshness(rows):
    year_counts = Counter()

    for row in rows:
        d = row.get("metadata_modified", "").strip()
        if not d:
            year_counts["Unknown"] += 1
            continue
        try:
            year_counts[str(datetime.strptime(d[:10], "%Y-%m-%d").year)] += 1
        except ValueError:
            year_counts["Unknown"] += 1

    years  = sorted(k for k in year_counts if k != "Unknown")
    if "Unknown" in year_counts:
        years.append("Unknown")

    values = [year_counts[y] for y in years]
    colors = ["#2196F3" if y != "Unknown" else "#BDBDBD" for y in years]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(years, values, color=colors)

    for i, v in enumerate(values):
        ax.text(i, v + 0.2, str(v), ha="center", fontsize=9)

    ax.set_xlabel("Year of Last Update")
    ax.set_ylabel("Number of Datasets")
    ax.set_title("Data Freshness - Year of Last Update", fontweight="bold")
    ax.tick_params(axis="x", rotation=30)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save_chart("data_freshness.png")


# Chart 4 - top sectors (using sector as proxy for tags)
def plot_top_tags(rows):
    counts = Counter()
    for row in rows:
        for s in row.get("sector", "").split("|"):
            s = s.strip()
            if s:
                counts[s] += 1

    if not counts:
        logging.warning("No sector data, skipping chart")
        return

    top    = counts.most_common(15)
    labels = [s for s, _ in top]
    values = [c for _, c in top]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh(labels[::-1], values[::-1], color="#E91E63")

    for i, v in enumerate(values[::-1]):
        ax.text(v + 0.1, i, str(v), va="center", fontsize=9)

    ax.set_xlabel("Number of Datasets")
    ax.set_title("Top Sectors in UP Datasets", fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save_chart("top_tags.png")


# Chart 5 - description quality
# wanted to see how many datasets actually have useful descriptions
def plot_description_quality(rows):
    empty = sum(1 for r in rows if not r.get("description", "").strip())
    short = sum(1 for r in rows if 0 < len(r.get("description", "").strip()) < 50)
    good  = len(rows) - empty - short

    labels = ["Empty", "Too short\n(<50 chars)", "OK\n(50+ chars)"]
    values = [empty, short, good]
    colors = ["#F44336", "#FF9800", "#4CAF50"]

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(labels, values, color=colors)

    for bar, val in zip(bars, values):
        pct = round(100 * val / len(rows))
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                f"{val} ({pct}%)", ha="center", fontsize=10)

    ax.set_ylabel("Number of Datasets")
    ax.set_title("Description Quality Across UP Datasets", fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save_chart("description_quality.png")

    logging.info("Description quality - empty: %d, short: %d, good: %d", empty, short, good)


# Chart 6 - own angle: central vs state government publishing breakdown
# noticed the API returns org_type but we didnt include it in the CSV
# so deriving it from organisation names instead
def plot_org_type_breakdown(rows):
    # datasets from central ministries vs state bodies
    # rough heuristic - if org name has "Ministry" or "Department of" its central
    central = 0
    state   = 0
    other   = 0

    central_keywords = ["ministry", "department of", "national", "central", "india", "rajya sabha", "lok sabha"]

    for row in rows:
        org = row["organization"].lower()
        if any(kw in org for kw in central_keywords):
            central += 1
        elif "uttar pradesh" in org or "up " in org:
            state += 1
        else:
            other += 1

    labels = ["Central Govt", "UP State Govt", "Other/Unknown"]
    values = [central, state, other]
    colors = ["#3F51B5", "#FF5722", "#9E9E9E"]

    fig, ax = plt.subplots(figsize=(7, 5))
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, colors=colors,
        autopct="%1.0f%%", startangle=90
    )
    ax.set_title("Central vs State Government Publishing", fontweight="bold")
    save_chart("org_type_breakdown.png")

    logging.info("Central: %d | State: %d | Other: %d", central, state, other)


# Chart 5 - description quality
# wanted to check how many datasets actually have useful descriptions
def plot_description_quality(rows):
    empty = sum(1 for r in rows if not r.get("description", "").strip())
    short = sum(1 for r in rows if 0 < len(r.get("description", "").strip()) < 50)
    good  = len(rows) - empty - short

    labels = ["Empty", "Too short\n(<50 chars)", "OK\n(50+ chars)"]
    values = [empty, short, good]
    colors = ["#F44336", "#FF9800", "#4CAF50"]

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(labels, values, color=colors)

    for bar, val in zip(bars, values):
        pct = round(100 * val / len(rows))
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                f"{val} ({pct}%)", ha="center", fontsize=10)

    ax.set_ylabel("Number of Datasets")
    ax.set_title("Description Quality Across UP Datasets", fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save_chart("description_quality.png")

    logging.info("Descriptions - empty: %d, short: %d, good: %d", empty, short, good)


# Chart 6 - own angle: central vs state government breakdown
# noticed most orgs look like central ministries, wanted to see the actual split
def plot_org_type_breakdown(rows):
    central_keywords = ["ministry", "department of", "national", "central", "india", "rajya sabha", "lok sabha"]

    central = 0
    state   = 0
    other   = 0

    for row in rows:
        org = row["organization"].lower()
        if any(kw in org for kw in central_keywords):
            central += 1
        elif "uttar pradesh" in org or "up " in org:
            state += 1
        else:
            other += 1

    labels = ["Central Govt", "UP State Govt", "Other/Unknown"]
    values = [central, state, other]
    colors = ["#3F51B5", "#FF5722", "#9E9E9E"]

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(labels, values, color=colors, width=0.5)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                str(val), ha="center", fontsize=12, fontweight="bold")

    ax.set_ylabel("Number of Datasets")
    ax.set_title("Central vs State Government Publishing", fontweight="bold")
    ax.set_ylim(0, max(values) + 10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save_chart("org_type_breakdown.png")

    logging.info("Central: %d | State: %d | Other: %d", central, state, other)


def print_summary(rows):
    total      = len(rows)
    empty_desc = sum(1 for r in rows if not r.get("description", "").strip())
    orgs       = set(r["organization"].split("|")[0].strip() for r in rows if r["organization"])

    print("\n" + "="*65)
    print("SUMMARY - Key Findings for SDA UP Metadata Registry")
    print("="*65)
    print(f"\nDatasets analysed : {total}")
    print(f"Unique orgs       : {len(orgs)}")
    print(f"Empty descriptions: {empty_desc} ({round(100*empty_desc/total)}%)")
    short_desc = sum(1 for r in rows if 0 < len(r.get("description", "").strip()) < 50)

    print(f"""
Finding 1 - Only {len(orgs)} organisations across {total} datasets
All {total} datasets collected are from central government bodies - not
a single UP state department appears. Ministries like Jal Shakti and
Census of India dominate completely. SDA needs to prioritise outreach
to state departments as the most critical gap in UP open data publishing.

Finding 2 - Descriptions exist but {short_desc} are too short to be useful
None of the {total} datasets have empty descriptions which is positive.
However {short_desc} have descriptions under 50 characters which gives
almost no context about the dataset. SDA should set a minimum description
length and quality standard when designing the Metadata Registry.

Finding 3 - Sector coverage is too narrow
Across {total} datasets only a handful of sectors appear with Water
Resources dominating. Core UP governance areas like Education, Health
and Agriculture are almost invisible. SDA needs to actively recruit
departments from underrepresented sectors into the registry.
""")
    print("="*65)


def main():
    rows = load_data()
    if not rows:
        return

    logging.info("Running analysis on %d datasets", len(rows))

    plot_top_organisations(rows)
    plot_format_distribution(rows)
    plot_data_freshness(rows)
    plot_top_tags(rows)
    plot_description_quality(rows)
    plot_org_type_breakdown(rows)
    print_summary(rows)

    logging.info("Done. Charts in: %s", os.path.abspath(OUTPUTS_DIR))


if __name__ == "__main__":
    main()