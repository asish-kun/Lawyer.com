from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# --- LLM ---
OPENAI_API_KEY = os.getenv("OpenAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("Anthropic_API_KEY", "")
LLM_MODEL = os.getenv("MODEL_NAME_OPENAI", "gpt-4o-mini")

# --- Embeddings ---
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# --- Paths ---
VECTORSTORE_DIR = BASE_DIR / "vectorstore"
RAW_DATA_DIR = BASE_DIR / "raw_data"
CHUNKS_DIR = BASE_DIR / "chunks"
