"""
Collect US court cases from Harvard Caselaw Access Project (case.law).
Downloads volume ZIP files from static.case.law (no auth required).
"""

import json
import time
import zipfile
import io
import requests
from pathlib import Path
from bs4 import BeautifulSoup

from data_collection.config import (
    CASELAW_DIR, CASELAW_STATIC_BASE, TARGET_CASELAW,
    REQUEST_DELAY, USER_AGENT,
)

REPORTERS = [
    ("us", 490, 520),
    ("f3d", 50, 80),
    ("f-supp-3d", 300, 340),
    ("cal-4th", 1, 20),
    ("ny3d", 30, 42),
    ("ill-2d", 180, 200),
    ("tex", 750, 770),
    ("mass", 460, 480),
    ("pa", 560, 580),
    ("so-3d", 200, 220),
    ("ohio-st-3d", 130, 150),
    ("a3d", 200, 230),
    ("ne3d", 100, 130),
    ("nw2d", 900, 920),
]

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def fetch_volume_cases(reporter, volume):
    """Download and extract cases from a single volume ZIP."""
    url = "%s/%s/%s.zip" % (CASELAW_STATIC_BASE, reporter, volume)
    try:
        resp = session.get(url, timeout=90)
        if resp.status_code != 200:
            return []

        cases = []
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                if name.endswith(".json"):
                    with zf.open(name) as f:
                        try:
                            case = json.loads(f.read())
                            cases.append(case)
                        except json.JSONDecodeError:
                            continue
        return cases
    except Exception as e:
        print("    Error fetching %s/%s: %s" % (reporter, volume, e))
        return []


def collect_caselaw(target=TARGET_CASELAW):
    """Pull cases from static.case.law and save as individual JSON files."""
    collected = 0
    existing = len(list(CASELAW_DIR.glob("*.json")))
    if existing >= target:
        print("[caselaw] Already have %d cases, skipping." % existing)
        return existing

    print("[caselaw] Collecting ~%d cases from static.case.law ..." % target)

    for reporter, vol_start, vol_end in REPORTERS:
        if collected >= target:
            break

        for vol in range(vol_start, vol_end):
            if collected >= target:
                break

            print("  Fetching %s/%s ..." % (reporter, vol))
            cases = fetch_volume_cases(reporter, vol)

            if not cases:
                print("    No cases or volume not found, skipping.")
                continue

            print("    Found %d cases in volume" % len(cases))

            for case_data in cases:
                if collected >= target:
                    break

                if not isinstance(case_data, dict):
                    continue

                case_id = case_data.get("id", "%s_%s_%d" % (reporter, vol, collected))
                name = case_data.get("name_abbreviation", case_data.get("name", ""))

                body_text = ""
                casebody = case_data.get("casebody", {})
                if isinstance(casebody, dict):
                    opinions = casebody.get("opinions", [])
                    if opinions:
                        body_text = "\n\n".join(
                            op.get("text", "") for op in opinions if op.get("text")
                        )

                if not body_text or len(body_text) < 200:
                    continue

                court_info = case_data.get("court", {})
                court_name = court_info.get("name", "") if isinstance(court_info, dict) else str(court_info)
                jurisdiction = case_data.get("jurisdiction", {})
                jurisdiction_name = jurisdiction.get("name", "") if isinstance(jurisdiction, dict) else str(jurisdiction)

                doc = {
                    "id": "caselaw_%s" % case_id,
                    "source": "harvard_caselaw",
                    "title": name,
                    "court": court_name,
                    "date": case_data.get("decision_date", ""),
                    "jurisdiction": jurisdiction_name,
                    "citations": [
                        c.get("cite", "") for c in case_data.get("citations", [])
                        if isinstance(c, dict)
                    ],
                    "docket_number": case_data.get("docket_number", ""),
                    "text": body_text,
                }

                out_path = CASELAW_DIR / ("caselaw_%s.json" % case_id)
                out_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
                collected += 1

            time.sleep(REQUEST_DELAY)

    print("[caselaw] Collected %d cases." % collected)
    return collected


if __name__ == "__main__":
    collect_caselaw()
