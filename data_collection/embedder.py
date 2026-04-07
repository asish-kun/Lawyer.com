"""
Embed document chunks using OpenAI text-embedding-3-small and store as
NumPy arrays on disk with enriched metadata (jurisdiction, case_type, year).

Produces two files in vectorstore/:
  - embeddings.npy   (N x 1536 float32 matrix)
  - metadata.json    (list of N metadata dicts, same order as rows)
"""

import json
import os
import re
import numpy as np
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm
from tenacity import retry, stop_after_attempt, wait_exponential

from data_collection.config import BASE_DIR, RAW_DATA_DIR

load_dotenv(BASE_DIR / ".env")

CHUNKS_DIR = BASE_DIR / "chunks"
STORE_DIR = BASE_DIR / "vectorstore"
STORE_DIR.mkdir(parents=True, exist_ok=True)

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536
BATCH_SIZE = 128


def _get_client():
    key = os.getenv("OpenAI_API_KEY", "")
    if not key:
        raise ValueError("Set OpenAI_API_KEY in .env")
    return OpenAI(api_key=key)


def _build_raw_doc_lookup():
    """Build doc_id -> raw doc metadata for jurisdiction/state enrichment."""
    lookup = {}
    for source_dir in ["caselaw", "courtlistener", "edgar"]:
        d = RAW_DATA_DIR / source_dir
        for f in d.glob("*.json"):
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
                lookup[doc["id"]] = doc
            except Exception:
                continue
    return lookup


def _extract_jurisdiction(chunk_meta, raw_doc):
    """Derive jurisdiction string from raw doc fields."""
    source = chunk_meta.get("source", "")

    if source == "harvard_caselaw":
        return raw_doc.get("jurisdiction", "")

    if source == "courtlistener":
        court = raw_doc.get("court", "")
        court_id = raw_doc.get("court_id", "")
        if court_id.startswith("scotus"):
            return "U.S."
        return court if court else court_id

    if source == "sec_edgar":
        states = raw_doc.get("state", [])
        return states[0] if states else ""

    return ""


def _extract_year(date_str):
    """Parse year from date string like '2024-07-19' or '2022-03-10'."""
    if not date_str:
        return ""
    m = re.match(r"(\d{4})", str(date_str))
    return m.group(1) if m else ""


def _extract_case_type(source):
    if source in ("harvard_caselaw", "courtlistener"):
        return "case_law"
    if source == "sec_edgar":
        return "filing"
    return ""


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=lambda rs: rs.outcome.failed and "BadRequestError" not in str(type(rs.outcome.exception())),
)
def _embed_batch(client, texts):
    resp = client.embeddings.create(input=texts, model=EMBED_MODEL)
    return [item.embedding for item in resp.data]


def embed_and_store():
    """Embed all chunks via OpenAI and save as .npy + enriched metadata JSON."""
    chunk_files = sorted(CHUNKS_DIR.glob("*.json"))
    if not chunk_files:
        print("[embedder] No chunks found. Run chunker first.")
        return

    print("[embedder] Found %d chunks to embed." % len(chunk_files))
    print("[embedder] Building raw doc lookup for metadata enrichment...")
    raw_lookup = _build_raw_doc_lookup()
    print("[embedder] Loaded %d raw docs." % len(raw_lookup))

    client = _get_client()

    all_texts = []
    all_metadata = []

    for fpath in chunk_files:
        try:
            doc = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception:
            continue

        doc_id = doc.get("doc_id", "")
        raw_doc = raw_lookup.get(doc_id, {})
        source = doc.get("source", "")

        all_texts.append(doc["text"])
        all_metadata.append({
            "id": doc.get("id", ""),
            "doc_id": doc_id,
            "source": source,
            "title": doc.get("title", "")[:200],
            "court": doc.get("court", "")[:100],
            "date": doc.get("date", ""),
            "jurisdiction": _extract_jurisdiction(doc, raw_doc),
            "case_type": _extract_case_type(source),
            "year": _extract_year(doc.get("date", "")),
            "chunk_index": doc.get("chunk_index", 0),
            "total_chunks": doc.get("total_chunks", 1),
            "text": doc["text"][:1500],
        })

    print("[embedder] Embedding %d chunks with %s (batches of %d) ..." % (
        len(all_texts), EMBED_MODEL, BATCH_SIZE))

    all_embeddings = []
    batches = [all_texts[i:i + BATCH_SIZE] for i in range(0, len(all_texts), BATCH_SIZE)]

    for batch in tqdm(batches, desc="Embedding"):
        embs = _embed_batch(client, batch)
        all_embeddings.extend(embs)

    emb_array = np.array(all_embeddings, dtype=np.float32)

    emb_path = STORE_DIR / "embeddings.npy"
    meta_path = STORE_DIR / "metadata.json"

    np.save(str(emb_path), emb_array)
    meta_path.write_text(json.dumps(all_metadata, ensure_ascii=False), encoding="utf-8")

    print("[embedder] Saved %d embeddings -> %s  (shape: %s)" % (
        len(emb_array), emb_path, emb_array.shape))
    print("[embedder] Saved metadata     -> %s" % meta_path)

    jurisdictions = set(m["jurisdiction"] for m in all_metadata if m["jurisdiction"])
    years = set(m["year"] for m in all_metadata if m["year"])
    print("[embedder] Jurisdictions found: %d unique" % len(jurisdictions))
    print("[embedder] Year range: %s — %s" % (min(years) if years else "?", max(years) if years else "?"))
    print("[embedder] Done.")


if __name__ == "__main__":
    embed_and_store()
