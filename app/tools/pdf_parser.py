"""
PDF text extraction via PyMuPDF.
Handles multi-column layouts, strips headers/footers/page numbers.
"""

import re
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF


def extract_text_from_pdf(pdf_path):
    """
    Extract clean text from a PDF file.

    Args:
        pdf_path: str or Path to the PDF file

    Returns:
        str: cleaned full text of the document
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError("PDF not found: %s" % pdf_path)

    doc = fitz.open(str(pdf_path))
    raw_pages = []

    for page in doc:
        raw_pages.append(page.get_text("text"))

    doc.close()

    if not raw_pages:
        return ""

    headers, footers = _detect_headers_footers(raw_pages)
    cleaned_pages = []

    for text in raw_pages:
        lines = text.split("\n")
        lines = _strip_matched_lines(lines, headers, footers)
        lines = _strip_page_numbers(lines)
        cleaned_pages.append("\n".join(lines))

    full_text = "\n\n".join(cleaned_pages)
    full_text = _normalize_whitespace(full_text)
    return full_text.strip()


def extract_text_from_bytes(pdf_bytes, filename="upload.pdf"):
    """
    Extract clean text from in-memory PDF bytes (for API uploads).

    Args:
        pdf_bytes: bytes content of the PDF
        filename:  original filename (for error messages)

    Returns:
        str: cleaned full text
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    raw_pages = []

    for page in doc:
        raw_pages.append(page.get_text("text"))

    doc.close()

    if not raw_pages:
        return ""

    headers, footers = _detect_headers_footers(raw_pages)
    cleaned_pages = []

    for text in raw_pages:
        lines = text.split("\n")
        lines = _strip_matched_lines(lines, headers, footers)
        lines = _strip_page_numbers(lines)
        cleaned_pages.append("\n".join(lines))

    full_text = "\n\n".join(cleaned_pages)
    full_text = _normalize_whitespace(full_text)
    return full_text.strip()


def _detect_headers_footers(pages, threshold=0.5):
    """
    Find lines that repeat across many pages — likely headers or footers.
    A line appearing on > threshold fraction of pages is flagged.
    """
    if len(pages) < 3:
        return set(), set()

    n = len(pages)
    min_occurrences = max(3, int(n * threshold))

    first_lines = Counter()
    last_lines = Counter()

    for text in pages:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            continue
        for line in lines[:3]:
            first_lines[line] += 1
        for line in lines[-3:]:
            last_lines[line] += 1

    headers = {line for line, count in first_lines.items()
               if count >= min_occurrences and len(line) < 120}
    footers = {line for line, count in last_lines.items()
               if count >= min_occurrences and len(line) < 120}

    return headers, footers


def _strip_matched_lines(lines, headers, footers):
    """Remove lines that match detected headers or footers."""
    return [l for l in lines if l.strip() not in headers and l.strip() not in footers]


def _strip_page_numbers(lines):
    """Remove lines that are just page numbers (standalone digits)."""
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^[-–—]?\s*\d{1,4}\s*[-–—]?$", stripped):
            continue
        if re.match(r"^Page\s+\d+\s*(of\s+\d+)?$", stripped, re.IGNORECASE):
            continue
        cleaned.append(line)
    return cleaned


def _normalize_whitespace(text):
    """Collapse excessive whitespace while preserving paragraph breaks."""
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = re.sub(r"\n ", "\n", text)
    return text
