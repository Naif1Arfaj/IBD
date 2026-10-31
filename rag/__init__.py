"""Retrieval-augmented generation over the team's research library (Full text article/)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPERS_DIR = ROOT / "Full text article"
INDEX_DIR = ROOT / "rag_index"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
