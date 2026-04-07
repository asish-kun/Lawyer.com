"""
NumPy-backed vector store with OpenAI query embeddings and metadata filtering.

Usage:
    from data_collection.vector_store import VectorStore

    vs = VectorStore()
    results = vs.search("breach of contract damages", top_k=10)
    results = vs.search("fiduciary duty", jurisdiction="U.S.", case_type="case_law", top_k=5)
"""

import json
import os
import warnings
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List

warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*encountered in matmul.*")

from dotenv import load_dotenv
from openai import OpenAI

_BASE_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_STORE = _BASE_DIR / "vectorstore"

load_dotenv(_BASE_DIR / ".env")

EMBED_MODEL = "text-embedding-3-small"


class VectorStore:
    def __init__(self, store_dir=None):
        store_dir = Path(store_dir) if store_dir else _DEFAULT_STORE

        emb_path = store_dir / "embeddings.npy"
        meta_path = store_dir / "metadata.json"

        if not emb_path.exists() or not meta_path.exists():
            raise FileNotFoundError(
                "Run `python3 -m data_collection.embedder` first to generate "
                "embeddings.npy and metadata.json in %s" % store_dir
            )

        self.embeddings = np.load(str(emb_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        key = os.getenv("OpenAI_API_KEY", "")
        if not key:
            raise ValueError("Set OpenAI_API_KEY in .env for query embedding")
        self._client = OpenAI(api_key=key)

        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-10)
        self._normed = (self.embeddings / norms).astype(np.float32)
        self._normed = np.nan_to_num(self._normed, nan=0.0, posinf=0.0, neginf=0.0)

        self._jurisdiction_arr = np.array([m.get("jurisdiction", "") for m in self.metadata])
        self._case_type_arr = np.array([m.get("case_type", "") for m in self.metadata])
        self._year_arr = np.array([m.get("year", "") for m in self.metadata])
        self._source_arr = np.array([m.get("source", "") for m in self.metadata])

        print("[VectorStore] Loaded %d vectors (dim=%d)" % self.embeddings.shape)

    def _embed_query(self, query):
        resp = self._client.embeddings.create(input=[query], model=EMBED_MODEL)
        emb = np.array(resp.data[0].embedding, dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        return emb

    def search(
        self,
        query,
        top_k=10,
        source_filter=None,
        jurisdiction=None,
        case_type=None,
        year_min=None,
        year_max=None,
    ):
        # type: (...) -> List[Tuple[float, dict]]
        """
        Cosine similarity search with optional metadata filters.

        Args:
            query:          natural language query string
            top_k:          number of results to return
            source_filter:  "harvard_caselaw", "courtlistener", or "sec_edgar"
            jurisdiction:   e.g. "U.S.", "Tennessee", "TX"
            case_type:      "case_law" or "filing"
            year_min:       e.g. "2020" — include this year and later
            year_max:       e.g. "2024" — include this year and earlier
        """
        q_emb = self._embed_query(query).reshape(1, -1)
        scores = (self._normed @ q_emb.T).flatten()

        mask = np.ones(len(scores), dtype=bool)

        if source_filter:
            mask &= self._source_arr == source_filter
        if jurisdiction:
            mask &= np.char.lower(self._jurisdiction_arr) == jurisdiction.lower()
        if case_type:
            mask &= self._case_type_arr == case_type
        if year_min:
            mask &= self._year_arr >= str(year_min)
        if year_max:
            mask &= self._year_arr <= str(year_max)

        filtered_scores = np.where(mask, scores, -1.0)
        top_indices = np.argsort(filtered_scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if filtered_scores[idx] <= 0:
                break
            results.append((float(filtered_scores[idx]), self.metadata[idx]))
        return results

    @property
    def count(self):
        return len(self.metadata)

    @property
    def dimension(self):
        return self.embeddings.shape[1]

    @property
    def jurisdictions(self):
        return sorted(set(j for j in self._jurisdiction_arr if j))

    @property
    def years(self):
        return sorted(set(y for y in self._year_arr if y))
