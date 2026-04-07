"""
Collect SEC EDGAR filings (10-K, 10-Q, 8-K, contracts) via the
free EFTS full-text search API. No authentication required.
"""

import json
import re
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path

from data_collection.config import (
    EDGAR_DIR, EDGAR_EFTS_API, TARGET_EDGAR,
    REQUEST_DELAY, USER_AGENT,
)

session = requests.Session()
session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
})

SEARCH_QUERIES = [
    ("breach of contract", "10-K"),
    ("indemnification agreement", "10-K"),
    ("merger agreement", "8-K"),
    ("employment agreement", "10-K"),
    ("securities litigation", "10-K"),
    ("settlement agreement", "8-K"),
    ("license agreement", "10-K"),
    ("non-compete agreement", "10-K"),
    ("intellectual property dispute", "10-K"),
    ("class action settlement", "10-K"),
    ("regulatory compliance", "10-K"),
    ("shareholder derivative", "10-K"),
    ("fiduciary duty", "10-K"),
    ("material contract", "8-K"),
    ("arbitration clause", "10-K"),
]


def search_edgar(query, form_type, start=0, size=20):
    """Search EDGAR EFTS for filings matching the query."""
    payload = {
        "q": f'"{query}"',
        "dateRange": "custom",
        "startdt": "2022-01-01",
        "enddt": "2024-12-31",
        "forms": form_type,
        "from": start,
        "size": size,
    }

    try:
        resp = session.get(EDGAR_EFTS_API, params=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("hits", {}).get("hits", [])
    except Exception as e:
        print(f"    EDGAR search error: {e}")
    return []


def download_filing_text(adsh: str, filename: str, cik: str) -> str:
    """Download the actual filing document text from SEC archives."""
    adsh_clean = adsh.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh_clean}/{filename}"

    try:
        resp = session.get(url, timeout=60)
        if resp.status_code != 200:
            url_alt = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh}/{filename}"
            resp = session.get(url_alt, timeout=60)

        if resp.status_code == 200:
            content = resp.text
            if "<html" in content.lower() or "<body" in content.lower():
                soup = BeautifulSoup(content, "lxml")
                for tag in soup(["script", "style", "meta", "link"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
            else:
                text = content

            text = re.sub(r"\n{3,}", "\n\n", text)
            text = re.sub(r"[ \t]{2,}", " ", text)
            return text.strip()
    except Exception:
        pass
    return ""


def collect_edgar(target: int = TARGET_EDGAR) -> int:
    """Pull filings from SEC EDGAR and save as JSON."""
    collected = 0
    existing = len(list(EDGAR_DIR.glob("*.json")))
    if existing >= target:
        print(f"[edgar] Already have {existing} filings, skipping.")
        return existing

    seen_ids = set()
    per_query = max(target // len(SEARCH_QUERIES), 10)

    print(f"[edgar] Collecting ~{target} filings from SEC EDGAR ...")

    for query, form_type in SEARCH_QUERIES:
        if collected >= target:
            break

        print(f"  Searching: '{query}' ({form_type}) ...")
        hits = search_edgar(query, form_type, size=min(per_query, 40))
        time.sleep(REQUEST_DELAY)

        for hit in hits:
            if collected >= target:
                break

            source = hit.get("_source", {})
            adsh = source.get("adsh", "")
            if not adsh or adsh in seen_ids:
                continue
            seen_ids.add(adsh)

            ciks = source.get("ciks", [])
            cik = ciks[0].lstrip("0") if ciks else ""
            if not cik:
                continue

            file_id = hit.get("_id", "")
            filename = file_id.split(":")[-1] if ":" in file_id else ""
            if not filename:
                continue

            print(f"    Downloading {adsh} / {filename} ...")
            text = download_filing_text(adsh, filename, cik)
            time.sleep(REQUEST_DELAY)

            if len(text) < 500:
                continue

            max_chars = 100_000
            if len(text) > max_chars:
                text = text[:max_chars]

            display_names = source.get("display_names", [])
            doc = {
                "id": f"edgar_{adsh}",
                "source": "sec_edgar",
                "title": display_names[0] if display_names else adsh,
                "form_type": source.get("form", form_type),
                "filing_date": source.get("file_date", ""),
                "period_ending": source.get("period_ending", ""),
                "company": display_names,
                "sic_codes": source.get("sics", []),
                "state": source.get("biz_states", []),
                "search_query": query,
                "text": text,
            }

            safe_adsh = adsh.replace("/", "_")
            out_path = EDGAR_DIR / f"edgar_{safe_adsh}.json"
            out_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            collected += 1

    print(f"[edgar] Collected {collected} filings.")
    return collected


if __name__ == "__main__":
    collect_edgar()
