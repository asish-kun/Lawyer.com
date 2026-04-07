import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = BASE_DIR / "raw_data"
CASELAW_DIR = RAW_DATA_DIR / "caselaw"
COURTLISTENER_DIR = RAW_DATA_DIR / "courtlistener"
EDGAR_DIR = RAW_DATA_DIR / "edgar"

for d in [CASELAW_DIR, COURTLISTENER_DIR, EDGAR_DIR]:
    d.mkdir(parents=True, exist_ok=True)

CASELAW_STATIC_BASE = "https://static.case.law"
COURTLISTENER_API = "https://www.courtlistener.com/api/rest/v4"
EDGAR_EFTS_API = "https://efts.sec.gov/LATEST/search-index"
EDGAR_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"

TARGET_CASELAW = 400
TARGET_COURTLISTENER = 300
TARGET_EDGAR = 300

REQUEST_DELAY = 0.5
USER_AGENT = "LegalBriefAnalyzer/1.0 (academic research; ash@lawyer.com)"
