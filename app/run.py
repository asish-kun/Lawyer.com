"""
CLI entry point for the Legal Brief Analyzer.

Usage:
    python -m app.run path/to/brief.pdf
    python -m app.run --text "raw brief text..."
"""

import json
import sys
from pathlib import Path

from app.tools.pdf_parser import extract_text_from_pdf, extract_text_from_bytes
from app.graph import app_graph


def analyze_pdf(pdf_path):
    """Run the full analysis DAG on a PDF file. Returns the final state dict."""
    text = extract_text_from_pdf(pdf_path)
    return analyze_text(text)


def analyze_bytes(pdf_bytes, filename="upload.pdf"):
    """Run the full analysis DAG on in-memory PDF bytes. Returns the final state dict."""
    text = extract_text_from_bytes(pdf_bytes, filename)
    return analyze_text(text)


def analyze_text(text):
    """Run the full analysis DAG on raw text. Returns the final state dict."""
    if not text or not text.strip():
        return {"error": "Empty input text."}

    initial_state = {"pdf_text": text}
    result = app_graph.invoke(initial_state)
    return result


def _print_result(result):
    """Pretty-print the analysis result to stdout."""
    if result.get("error"):
        print("\n[ERROR] %s" % result["error"])
        return

    print("\n" + "=" * 60)
    print("LEGAL BRIEF ANALYSIS COMPLETE")
    print("=" * 60)

    extraction = result.get("extraction", {})
    if extraction:
        print("\n--- Extraction ---")
        print("Parties: %s" % ", ".join(
            "%s (%s)" % (p["name"], p["role"]) for p in extraction.get("parties", [])
        ))
        print("Claims:  %d found" % len(extraction.get("claims", [])))
        for c in extraction.get("claims", []):
            print("  [%d] %s" % (c["claim_id"], c["text"][:100]))
        print("Jurisdiction: %s" % extraction.get("jurisdiction", ""))
        print("Case type:    %s" % extraction.get("case_type", ""))
        print("Posture:      %s" % extraction.get("procedural_posture", ""))

    weaknesses = result.get("weaknesses", [])
    if weaknesses:
        print("\n--- Weakness Analysis ---")
        for w in weaknesses:
            print("  Claim %d: score=%.2f — %s" % (
                w["claim_id"], w["weakness_score"], w["reasoning"][:120]
            ))

    counterarguments = result.get("counterarguments", [])
    if counterarguments:
        print("\n--- Counterarguments ---")
        for ca in counterarguments:
            print("  Claim %d [%s]: %s" % (
                ca["claim_id"], ca["severity"], ca["predicted_rebuttal"][:120]
            ))

    strategy = result.get("strategy", {})
    if strategy:
        print("\n--- Strategy ---")
        print("Overall: %s" % strategy.get("overall_assessment", ""))
        for a in strategy.get("actions", []):
            print("  [P%d] %s" % (a["priority"], a["action"][:120]))
        if strategy.get("key_risks"):
            print("Risks: %s" % "; ".join(strategy["key_risks"]))

    print("\n--- Full JSON ---")
    safe = {k: v for k, v in result.items() if k != "pdf_text"}
    print(json.dumps(safe, indent=2))


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m app.run <path/to/brief.pdf>")
        print("       python -m app.run --text \"raw text...\"")
        sys.exit(1)

    if sys.argv[1] == "--text":
        text = " ".join(sys.argv[2:])
        result = analyze_text(text)
    else:
        pdf_path = Path(sys.argv[1])
        if not pdf_path.exists():
            print("File not found: %s" % pdf_path)
            sys.exit(1)
        result = analyze_pdf(pdf_path)

    _print_result(result)


if __name__ == "__main__":
    main()
