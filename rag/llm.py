"""Claude client for grounded, cited answers over retrieved research passages.

Credentials: ANTHROPIC_API_KEY in the environment or in ibd_model/.env.
Without credentials every caller falls back to offline (retrieval-only) mode.
"""
import logging
import os

from dotenv import load_dotenv

from . import ROOT
from .retrieve import cite_label

load_dotenv(ROOT / ".env")
log = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM = """You are a clinical research assistant inside IBD-Risk AI, a decision-support prototype that \
estimates inflammatory bowel disease (IBD) risk in Saudi youth aged 15-30.

Rules:
- Base every factual statement only on the research documents provided in the message, and cite them. \
If the documents do not address something, say that the provided literature does not cover it.
- When the evidence is mixed, weak, observational, or conflicts with the model's direction, say so plainly.
- Write for nurses and physicians: clear, concise, plain clinical English. No headings unless asked.
- This tool supports, and never replaces, clinical judgment. Never state a diagnosis; speak about risk.
- The patient data and the ML model were built on SYNTHETIC data; model outputs reflect a synthetic \
generation formula, so frame model findings as prototype outputs, not validated clinical evidence."""


class LLMUnavailable(Exception):
    pass


def available():
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _client():
    import anthropic
    return anthropic.Anthropic(max_retries=2, timeout=120.0)


def _documents(hits):
    return [{
        "type": "document",
        "source": {"type": "text", "media_type": "text/plain", "data": h["text"]},
        "title": cite_label(h),
        "citations": {"enabled": True},
    } for h in hits]


def cited_answer(prompt, hits, max_tokens=3000):
    """Ask Claude to answer `prompt` from `hits`. Returns (text_with_markers, references).

    references: list of {n, hit, quotes}; text contains [n] markers matching them.
    """
    if not available():
        raise LLMUnavailable("No Anthropic API key configured.")
    import anthropic

    try:
        resp = _client().beta.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": "medium"},
            betas=[FALLBACK_BETA],
            fallbacks="default",
            messages=[{"role": "user", "content": _documents(hits) + [{"type": "text", "text": prompt}]}],
        )
    except anthropic.RateLimitError as e:
        raise LLMUnavailable("Claude rate limit reached; showing retrieved passages instead.") from e
    except anthropic.AuthenticationError as e:
        raise LLMUnavailable("Anthropic API key was rejected; check ANTHROPIC_API_KEY.") from e
    except anthropic.APIStatusError as e:
        raise LLMUnavailable(f"Claude API error ({e.status_code}); showing retrieved passages instead.") from e
    except anthropic.APIConnectionError as e:
        raise LLMUnavailable("Could not reach the Claude API (network); showing retrieved passages instead.") from e

    if resp.stop_reason == "refusal":
        raise LLMUnavailable("Claude declined this request; showing retrieved passages instead.")

    refs, order, parts = {}, [], []
    for block in resp.content:
        if block.type != "text":
            continue
        parts.append(block.text)
        marks = []
        for c in block.citations or []:
            i = getattr(c, "document_index", None)
            if i is None or i >= len(hits):
                continue
            if i not in refs:
                refs[i] = {"n": len(order) + 1, "hit": hits[i], "quotes": []}
                order.append(i)
            quote = (c.cited_text or "").strip()
            if quote and quote not in refs[i]["quotes"]:
                refs[i]["quotes"].append(quote[:400])
            if refs[i]["n"] not in marks:
                marks.append(refs[i]["n"])
        if marks:
            parts.append("".join(f"[{n}]" for n in marks))
    return "".join(parts).strip(), [refs[i] for i in order]
