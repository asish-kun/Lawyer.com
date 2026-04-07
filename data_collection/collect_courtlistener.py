"""
Collect court opinions from CourtListener REST API v4.
Works without auth (throttled) or with token for higher limits.
"""

import json
import os
import time
import requests
from pathlib import Path

from data_collection.config import (
    COURTLISTENER_DIR, COURTLISTENER_API, TARGET_COURTLISTENER,
    REQUEST_DELAY, USER_AGENT,
)

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

token = os.getenv("COURTLISTENER_API_TOKEN", "")
if token:
    session.headers["Authorization"] = "Token %s" % token

SEARCH_QUERIES = [
    "breach of contract",
    "negligence",
    "due process",
    "first amendment",
    "fourth amendment",
    "equal protection",
    "habeas corpus",
    "summary judgment",
    "class action",
    "intellectual property",
    "employment discrimination",
    "securities fraud",
    "antitrust",
    "wrongful termination",
    "product liability",
    "medical malpractice",
    "tort",
    "criminal procedure",
    "civil rights",
    "constitutional law",
]


def fetch_opinion_text(opinion_id):
    """Fetch full opinion text from the detail endpoint."""
    url = "%s/opinions/%s/" % (COURTLISTENER_API, opinion_id)
    try:
        resp = session.get(url, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return (
                data.get("plain_text", "")
                or data.get("html_with_citations", "")
                or data.get("html", "")
                or ""
            )
        elif resp.status_code == 429:
            print("    Rate limited, sleeping 60s...")
            time.sleep(60)
    except Exception as e:
        print("    Opinion fetch error: %s" % e)
    return ""


def search_opinions(query, max_results=20):
    """Search CourtListener for opinions matching a query."""
    url = "%s/search/" % COURTLISTENER_API
    params = {
        "q": query,
        "type": "o",
        "order_by": "score desc",
        "page_size": min(max_results, 20),
    }
    try:
        resp = session.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("results", [])
        elif resp.status_code == 429:
            print("    Rate limited, sleeping 60s...")
            time.sleep(60)
    except Exception as e:
        print("    Search error for '%s': %s" % (query, e))
    return []


def collect_courtlistener(target=TARGET_COURTLISTENER):
    """Pull opinions from CourtListener search API."""
    collected = 0
    existing = len(list(COURTLISTENER_DIR.glob("*.json")))
    if existing >= target:
        print("[courtlistener] Already have %d opinions, skipping." % existing)
        return existing

    seen_ids = set()
    per_query = max(target // len(SEARCH_QUERIES), 10)

    print("[courtlistener] Collecting ~%d opinions from CourtListener API ..." % target)

    for query in SEARCH_QUERIES:
        if collected >= target:
            break

        print("  Searching: '%s' ..." % query)
        results = search_opinions(query, max_results=per_query)
        time.sleep(REQUEST_DELAY * 2)

        for result in results:
            if collected >= target:
                break

            cluster_id = result.get("cluster_id", "")
            if not cluster_id or cluster_id in seen_ids:
                continue
            seen_ids.add(cluster_id)

            body_text = ""

            opinions = result.get("opinions", [])
            if opinions and isinstance(opinions[0], dict):
                opinion_id = opinions[0].get("id", "")
                snippet = opinions[0].get("snippet", "")

                if opinion_id:
                    body_text = fetch_opinion_text(opinion_id)
                    time.sleep(REQUEST_DELAY)

                if not body_text:
                    body_text = snippet

            if len(body_text) < 100:
                continue

            import re
            body_text = re.sub(r"<[^>]+>", " ", body_text)
            body_text = re.sub(r"\s{3,}", "  ", body_text)

            doc = {
                "id": "cl_%s" % cluster_id,
                "source": "courtlistener",
                "title": result.get("caseName", ""),
                "court": result.get("court", ""),
                "court_id": result.get("court_id", ""),
                "date": result.get("dateFiled", ""),
                "docket_number": result.get("docketNumber", ""),
                "citation": result.get("citation", []),
                "judge": result.get("judge", ""),
                "search_query": query,
                "text": body_text,
            }

            out_path = COURTLISTENER_DIR / ("cl_%s.json" % cluster_id)
            out_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            collected += 1
            print("    Collected: %s (%d total)" % (result.get("caseName", "")[:60], collected))

    print("[courtlistener] Collected %d opinions." % collected)
    return collected


if __name__ == "__main__":
    collect_courtlistener()
