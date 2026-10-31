"""Hybrid retrieval: dense cosine + BM25, merged with reciprocal-rank fusion."""
from collections import defaultdict

import numpy as np

from .index import embedder, load, tokenize

RRF_K = 60


def search(query, k=8, candidates=30, max_per_doc=2):
    idx = load()
    q = np.array(next(iter(embedder().query_embed([query]))), dtype=np.float32)
    q /= np.linalg.norm(q)
    dense = np.argsort(-(idx.emb @ q))[:candidates]
    bm = np.argsort(-idx.bm25.get_scores(tokenize(query)))[:candidates]

    fused = defaultdict(float)
    for ranking in (dense, bm):
        for rank, i in enumerate(ranking):
            fused[int(i)] += 1.0 / (RRF_K + rank + 1)

    out, per_doc = [], defaultdict(int)
    for i, score in sorted(fused.items(), key=lambda kv: -kv[1]):
        c = idx.chunks[i]
        if per_doc[c["doc_id"]] >= max_per_doc:
            continue
        per_doc[c["doc_id"]] += 1
        d = idx.docs[c["doc_id"]]
        out.append({**c, "score": round(score, 5), "title": d["title"], "year": d["year"],
                    "doi": d["doi"], "file": d["file"]})
        if len(out) == k:
            break
    return out


def cite_label(hit):
    year = f" ({hit['year']})" if hit.get("year") else ""
    return f"{hit['title']}{year}, p. {hit['page']}"
