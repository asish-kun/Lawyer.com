"""
Main orchestrator: collect -> chunk -> embed (local NumPy store).
"""

import sys
import json
from pathlib import Path

from data_collection.config import RAW_DATA_DIR, BASE_DIR


def run_collection():
    from data_collection.collect_caselaw import collect_caselaw
    from data_collection.collect_courtlistener import collect_courtlistener
    from data_collection.collect_edgar import collect_edgar

    print("=" * 60)
    print("LEGAL BRIEF ANALYZER — Data Collection Pipeline")
    print("=" * 60)

    caselaw_count = collect_caselaw()
    cl_count = collect_courtlistener()
    edgar_count = collect_edgar()

    total = caselaw_count + cl_count + edgar_count
    print(f"\n{'=' * 60}")
    print(f"Collection complete:")
    print(f"  Harvard Caselaw : {caselaw_count}")
    print(f"  CourtListener   : {cl_count}")
    print(f"  SEC EDGAR       : {edgar_count}")
    print(f"  TOTAL           : {total}")
    print(f"{'=' * 60}")
    return total


def run_chunking():
    from data_collection.chunker import chunk_all_documents

    print("\n" + "=" * 60)
    print("Chunking documents...")
    print("=" * 60)
    return chunk_all_documents()


def run_embedding():
    from data_collection.embedder import embed_and_store

    print("\n" + "=" * 60)
    print("Embedding locally (sentence-transformers + NumPy)...")
    print("=" * 60)
    embed_and_store()


def report():
    """Print summary of all collected and chunked data."""
    sources = {"caselaw": 0, "courtlistener": 0, "edgar": 0}
    for source in sources:
        source_dir = RAW_DATA_DIR / source
        sources[source] = len(list(source_dir.glob("*.json")))

    chunks_dir = BASE_DIR / "chunks"
    chunk_count = len(list(chunks_dir.glob("*.json"))) if chunks_dir.exists() else 0

    print(f"\n{'=' * 60}")
    print("DATA SUMMARY")
    print(f"{'=' * 60}")
    for source, count in sources.items():
        print(f"  {source:20s}: {count:5d} documents")
    print(f"  {'TOTAL':20s}: {sum(sources.values()):5d} documents")
    print(f"  {'Chunks':20s}: {chunk_count:5d}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"

    if stage in ("collect", "all"):
        run_collection()
    if stage in ("chunk", "all"):
        run_chunking()
    if stage in ("embed",):
        run_embedding()

    report()
