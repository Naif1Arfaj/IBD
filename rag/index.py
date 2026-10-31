"""Build and load the hybrid (dense + BM25) search index."""
import json
import re
from functools import lru_cache

import numpy as np

from . import EMBED_MODEL, INDEX_DIR
from .ingest import ingest

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text):
    return _TOKEN.findall(text.lower())


@lru_cache(maxsize=1)
def embedder():
    from fastembed import TextEmbedding
    return TextEmbedding(EMBED_MODEL)


def build(log=print):
    INDEX_DIR.mkdir(exist_ok=True)
    docs, chunks, failed = ingest(log=log)
    log(f"Embedding {len(chunks)} chunks from {len(docs)} documents …")
    emb = np.array(list(embedder().passage_embed([c["text"] for c in chunks], batch_size=64)), dtype=np.float32)
    emb /= np.linalg.norm(emb, axis=1, keepdims=True)
    np.save(INDEX_DIR / "embeddings.npy", emb)
    (INDEX_DIR / "docs.json").write_text(json.dumps(docs, indent=1, ensure_ascii=False))
    (INDEX_DIR / "failed.json").write_text(json.dumps(failed, indent=1))
    with open(INDEX_DIR / "chunks.jsonl", "w") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    load.cache_clear()
    return {"documents": len(docs), "chunks": len(chunks), "failed": failed}


class Index:
    def __init__(self):
        from rank_bm25 import BM25Okapi
        self.docs = {d["doc_id"]: d for d in json.loads((INDEX_DIR / "docs.json").read_text())}
        with open(INDEX_DIR / "chunks.jsonl") as f:
            self.chunks = [json.loads(line) for line in f]
        self.emb = np.load(INDEX_DIR / "embeddings.npy")
        self.bm25 = BM25Okapi([tokenize(c["text"]) for c in self.chunks])
        failed = INDEX_DIR / "failed.json"
        self.failed = json.loads(failed.read_text()) if failed.exists() else []

    def stats(self):
        return {"documents": len(self.docs), "chunks": len(self.chunks), "failed": self.failed}


def exists():
    return all((INDEX_DIR / f).exists() for f in ("docs.json", "chunks.jsonl", "embeddings.npy"))


@lru_cache(maxsize=1)
def load():
    if not exists():
        raise FileNotFoundError("Research index not built yet: run `python manage.py build_index`.")
    return Index()
