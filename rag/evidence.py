"""Evidence for model factors and free-text research questions, with offline fallback."""
from . import llm
from .queries import label, query
from .retrieve import cite_label, search


def _offline(hits, n=3, note=None):
    """Retrieval-only result: top passages as quotes with references."""
    refs = [{"n": i + 1, "hit": h, "quotes": [h["text"][:600] + ("…" if len(h["text"]) > 600 else "")]}
            for i, h in enumerate(hits[:n])]
    return {"text": "", "references": refs, "llm_used": False, "notice": note}


def _pack(text, refs, llm_used=True, notice=None):
    return {"text": text, "references": refs, "llm_used": llm_used, "notice": notice}


def serialize_refs(refs):
    """JSON-safe references for storage."""
    return [{"n": r["n"], "label": cite_label(r["hit"]), "title": r["hit"]["title"], "year": r["hit"]["year"],
             "page": r["hit"]["page"], "file": r["hit"]["file"], "doi": r["hit"]["doi"], "quotes": r["quotes"]}
            for r in refs]


def feature_evidence(feature, direction):
    """What does the literature say about `feature` and IBD risk? direction: 'raises' | 'lowers'."""
    hits = search(query(feature), k=6)
    if not llm.available():
        return _offline(hits)
    prompt = (
        f"In this synthetic prototype, the ML model found that the patient's '{label(feature)}' value "
        f"{direction} their estimated IBD risk.\n"
        f"In 3-4 sentences, summarise what the provided research says about {label(feature).lower()} and the risk "
        f"or early detection of IBD. State whether the literature supports the model's direction, and note "
        f"the strength and type of evidence (meta-analysis, cohort, case series, review)."
    )
    try:
        text, refs = llm.cited_answer(prompt, hits, max_tokens=1500)
        return _pack(text, refs)
    except llm.LLMUnavailable as e:
        return _offline(hits, note=str(e))


def answer_question(question, k=8):
    hits = search(question, k=k)
    if not llm.available():
        return _offline(hits, n=5, note="Offline mode: showing the most relevant passages (no API key configured).")
    try:
        text, refs = llm.cited_answer(
            f"Question from a clinician: {question}\n\nAnswer from the provided research with citations. "
            f"If the documents do not answer it, say so.", hits)
        return _pack(text, refs)
    except llm.LLMUnavailable as e:
        return _offline(hits, n=5, note=str(e))


def patient_narrative(summary, evidence_blocks):
    """Clinical interpretation for one assessment. evidence_blocks: list of (feature, direction, hits)."""
    hits, seen = [], set()
    for _, _, hs in evidence_blocks:
        for h in hs:
            if h["chunk_id"] not in seen:
                seen.add(h["chunk_id"])
                hits.append(h)
    hits = hits[:16]
    if not llm.available():
        return None
    prompt = (
        "Write a clinical interpretation (2 short paragraphs, ~180 words) for this IBD risk assessment, for the "
        "nurse and physician reviewing it. Paragraph 1: what the model estimated and which factors drove it, "
        "linking each factor to the provided research where it supports it. Paragraph 2: a suggested next step "
        "consistent with the risk tier (e.g. fecal calprotectin confirmation, GI referral per local protocol, or "
        "routine follow-up), phrased as decision support. Do not diagnose.\n\n"
        f"Assessment (synthetic prototype):\n{summary}"
    )
    try:
        return llm.cited_answer(prompt, hits, max_tokens=2500)
    except llm.LLMUnavailable:
        return None
