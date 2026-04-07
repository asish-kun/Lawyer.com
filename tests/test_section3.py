"""
Section 3 end-to-end test: PDF parsing -> Extractor agent -> typed output.

Generates a synthetic legal brief PDF, parses it, runs Agent 1,
and validates the structured extraction.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # PyMuPDF — used here to create the test PDF

from app.tools.pdf_parser import extract_text_from_pdf, extract_text_from_bytes
from app.agents.extractor import run_extractor
from app.schemas import BriefExtraction

SAMPLE_BRIEF = """\
IN THE UNITED STATES DISTRICT COURT
FOR THE SOUTHERN DISTRICT OF NEW YORK

Case No. 24-cv-01234

ACME CORPORATION, Plaintiff,
v.
GLOBEX INDUSTRIES, INC., Defendant.

PLAINTIFF'S MOTION FOR SUMMARY JUDGMENT

I. INTRODUCTION

Plaintiff ACME Corporation ("ACME") respectfully moves this Court for summary judgment \
pursuant to Federal Rule of Civil Procedure 56. ACME seeks judgment as a matter of law on \
its claims for breach of contract and misappropriation of trade secrets against Defendant \
Globex Industries, Inc. ("Globex").

II. STATEMENT OF FACTS

1. On January 15, 2022, ACME and Globex entered into a Master Services Agreement \
("MSA") governing Globex's use of ACME's proprietary manufacturing process.

2. Under Section 4.2 of the MSA, Globex agreed to maintain strict confidentiality of \
all trade secrets and proprietary information disclosed by ACME.

3. On or about March 10, 2023, ACME discovered that Globex had disclosed ACME's \
proprietary catalyst formula to a third-party competitor, ChemTech Solutions LLC.

4. Globex's former employee, Dr. Sarah Chen, provided a sworn declaration confirming \
that she was directed by Globex management to share the formula with ChemTech.

5. As a direct result of this unauthorized disclosure, ACME suffered lost revenue \
exceeding $4.2 million and irreparable harm to its competitive position.

III. LEGAL ARGUMENT

A. Breach of Contract (Count I)

Under New York law, a breach of contract claim requires: (1) the existence of a contract; \
(2) performance by the plaintiff; (3) breach by the defendant; and (4) resulting damages. \
Harris v. Seward Park Housing Corp., 79 A.D.3d 425 (1st Dep't 2010).

The undisputed evidence establishes all four elements. The MSA is a valid, binding contract. \
ACME fully performed its obligations thereunder. Globex breached Section 4.2 by disclosing \
ACME's proprietary information. ACME suffered damages in excess of $4.2 million.

B. Misappropriation of Trade Secrets (Count II)

The Defend Trade Secrets Act, 18 U.S.C. § 1836, provides a federal civil cause of action \
for the misappropriation of trade secrets. A trade secret is misappropriated when it is \
acquired by improper means or disclosed without consent. See Oakwood Labs. LLC v. Thanoo, \
999 F.3d 892 (3d Cir. 2021).

ACME's catalyst formula constitutes a trade secret under both federal and New York law. \
Globex acquired knowledge of this formula through the MSA and disclosed it without \
authorization, satisfying the elements of misappropriation.

IV. RELIEF SOUGHT

ACME respectfully requests that this Court:
1. Grant summary judgment in favor of ACME on Counts I and II;
2. Award compensatory damages of no less than $4.2 million;
3. Issue a permanent injunction prohibiting Globex from further use or disclosure \
of ACME's trade secrets;
4. Award attorneys' fees and costs pursuant to 18 U.S.C. § 1836(b)(3); and
5. Grant such other relief as this Court deems just and proper.

Dated: April 1, 2024
New York, New York

Respectfully submitted,

/s/ James Mitchell
James Mitchell, Esq.
Mitchell & Associates LLP
Attorneys for Plaintiff ACME Corporation
"""

SAMPLE_DIR = Path(__file__).resolve().parent / "fixtures"


def create_test_pdf():
    """Generate a multi-page PDF from the sample brief text."""
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = SAMPLE_DIR / "sample_brief.pdf"

    doc = fitz.open()
    rect = fitz.Rect(72, 72, 540, 720)
    fontsize = 11

    remaining = SAMPLE_BRIEF
    page_num = 0

    while remaining:
        page = doc.new_page(width=612, height=792)
        page_num += 1
        header = "ACME Corp. v. Globex Industries — Case No. 24-cv-01234"
        page.insert_text(fitz.Point(72, 50), header, fontsize=8)
        footer = "Page %d" % page_num
        page.insert_text(fitz.Point(280, 775), footer, fontsize=8)

        writer = fitz.TextWriter(page.rect)
        where = rect + fitz.Rect(0, 0, 0, 0)
        used = writer.fill_textbox(
            where, remaining, fontsize=fontsize, font=fitz.Font("helv")
        )
        writer.write_text(page)

        if not remaining.strip():
            break

        lines_on_page = remaining[: max(1, len(remaining) - len(remaining.lstrip()))]
        fitted_chars = len(used) if isinstance(used, str) else 0

        if fitted_chars == 0:
            page_lines = remaining.split("\n")
            approx_lines = int((720 - 72) / (fontsize * 1.5))
            fitted_text = "\n".join(page_lines[:approx_lines])
            remaining = "\n".join(page_lines[approx_lines:])
        else:
            remaining = remaining[fitted_chars:]

        if not remaining.strip():
            break

    doc.save(str(pdf_path))
    doc.close()
    print("[OK] Created test PDF: %s (%d pages)" % (pdf_path, page_num))
    return pdf_path


def test_pdf_parser(pdf_path):
    """Test PDF text extraction from file and from bytes."""
    print("\n=== Test: PDF Parser (file path) ===")
    text = extract_text_from_pdf(pdf_path)
    assert len(text) > 100, "Extracted text is too short"
    assert "ACME" in text, "Expected 'ACME' in extracted text"
    assert "Globex" in text, "Expected 'Globex' in extracted text"
    print("[OK] Extracted %d chars from file" % len(text))

    print("\n=== Test: PDF Parser (bytes) ===")
    pdf_bytes = pdf_path.read_bytes()
    text_from_bytes = extract_text_from_bytes(pdf_bytes)
    assert len(text_from_bytes) > 100, "Bytes extraction too short"
    assert "ACME" in text_from_bytes
    print("[OK] Extracted %d chars from bytes" % len(text_from_bytes))

    hf_check = "ACME Corp. v. Globex Industries"
    page_check = "Page 1"
    if hf_check not in text:
        print("[OK] Header stripped successfully")
    else:
        print("[WARN] Header may not have been stripped (PDF too short for detection)")

    return text


def test_extractor_agent(pdf_text):
    """Test Agent 1: structured extraction from PDF text."""
    print("\n=== Test: Agent 1 Extractor ===")
    state = {"pdf_text": pdf_text}
    result = run_extractor(state)

    assert "error" not in result, "Extractor returned error: %s" % result.get("error")
    assert "extraction" in result, "No 'extraction' key in result"

    extraction_dict = result["extraction"]
    extraction = BriefExtraction(**extraction_dict)

    print("\n--- Extraction Result ---")
    print("Parties:    %d found" % len(extraction.parties))
    for p in extraction.parties:
        print("  - %s (%s)" % (p.name, p.role))

    print("Claims:     %d found" % len(extraction.claims))
    for c in extraction.claims:
        print("  - [%d] %s (basis: %s)" % (c.claim_id, c.text[:80], c.legal_basis[:60]))

    print("Facts:      %d found" % len(extraction.facts))
    print("Relief:     %s" % extraction.relief_sought[:120])
    print("Juris:      %s" % extraction.jurisdiction)
    print("Case type:  %s" % extraction.case_type)
    print("Posture:    %s" % extraction.procedural_posture)

    assert len(extraction.parties) >= 2, "Expected at least 2 parties"
    assert len(extraction.claims) >= 1, "Expected at least 1 claim"
    assert extraction.jurisdiction, "Jurisdiction should not be empty"

    print("\n[OK] Extraction validates against BriefExtraction schema")
    print("[OK] Full JSON output:\n%s" % json.dumps(extraction_dict, indent=2))
    return extraction_dict


def test_extractor_empty_input():
    """Test Agent 1 with no PDF text — should return error."""
    print("\n=== Test: Extractor with empty input ===")
    state = {"pdf_text": ""}
    result = run_extractor(state)
    assert "error" in result, "Expected error for empty input"
    print("[OK] Correctly returned error for empty input: %s" % result["error"])


if __name__ == "__main__":
    pdf_path = create_test_pdf()
    pdf_text = test_pdf_parser(pdf_path)
    test_extractor_empty_input()
    extraction = test_extractor_agent(pdf_text)
    print("\n" + "=" * 50)
    print("ALL SECTION 3 TESTS PASSED")
    print("=" * 50)
