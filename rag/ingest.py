"""PDF → cleaned page text → overlapping chunks with citation metadata."""
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pymupdf

from . import PAPERS_DIR

CHUNK_WORDS = 300
OVERLAP_WORDS = 60
MIN_CHUNK_WORDS = 40

_BAD_TITLE = re.compile(r"(^untitled$|\d+\.\.\d+$|\.pdf$|^microsoft word|^doi|^\W*$)", re.I)
_REF_HEADING = re.compile(r"^\s*(references|reference list|bibliography|literature cited)\s*:?\s*$", re.I | re.M)
_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.I)
_YEAR = re.compile(r"\b(19[89]\d|20[0-2]\d)\b")
_STAMP_LINE = re.compile(r"download|accessed|guest|protected by copyright|printed|retrieved", re.I)
OVERRIDES_FILE = Path(__file__).with_name("titles_override.json")


def _clean(text):
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)          # re-join hyphenated line breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()


def _title_from_layout(page):
    """Largest-font text block in the top 60% of page 1 (journal names are usually smaller)."""
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for s in line["spans"]:
                if s["text"].strip() and s["bbox"][1] < page.rect.height * 0.6:
                    spans.append((round(s["size"], 1), s["bbox"][1], s["text"].strip()))
    if not spans:
        return ""
    sizes = sorted({s for s, _, _ in spans}, reverse=True)
    for size in sizes[:3]:  # skip a tiny single-glyph giant (e.g. drop caps)
        parts = [t for s, _, t in sorted(spans, key=lambda x: x[1]) if abs(s - size) < 0.6]
        title = " ".join(parts)
        if len(title) >= 25:
            return re.sub(r"\s+", " ", title)[:300]
    return ""


def _tidy(title):
    title = unicodedata.normalize("NFKC", title).replace("\u2010", "-")
    title = re.sub(r"^(author manuscript|original article|review)\s+", "", title, flags=re.I)
    return re.sub(r"\s+", " ", title).strip(" '\"\u2018\u2019\u201c\u201d-.\u2010")


def _title(doc):
    meta = (doc.metadata or {}).get("title", "").strip()
    if len(meta) >= 20 and not _BAD_TITLE.search(meta):
        return _tidy(meta)
    return _tidy(_title_from_layout(doc[0]) or meta) or "Untitled document"


def _year(first_pages_text, doc):
    text = "\n".join(l for l in first_pages_text.splitlines() if not _STAMP_LINE.search(l))
    years = [int(y) for y in _YEAR.findall(text)]
    years = [y for y in years if y <= 2026]
    if years:
        top = Counter(years).most_common()
        best = max(c for _, c in top)
        return max(y for y, c in top if c == best)
    m = re.search(r"D:(\d{4})", (doc.metadata or {}).get("creationDate", ""))
    return int(m.group(1)) if m else None


def _strip_references(pages):
    """Drop everything after a 'References' heading that appears in the last 40% of the paper."""
    start = int(len(pages) * 0.6)
    for i in range(len(pages) - 1, start - 1, -1):
        m = list(_REF_HEADING.finditer(pages[i]))
        if m:
            pages[i] = pages[i][: m[0].start()]
            return pages[: i + 1]
    return pages


def read_pdf(path: Path):
    doc = pymupdf.open(path)
    pages = [_clean(p.get_text()) for p in doc]
    head = "\n".join(pages[:2])
    doi = _DOI.search(head)
    overrides = json.loads(OVERRIDES_FILE.read_text()) if OVERRIDES_FILE.exists() else {}
    info = {
        "file": path.name,
        "title": _title(doc),
        "year": _year(pages[0] if pages else "", doc),
        "doi": doi.group(1).rstrip(".,;)") if doi else None,
        "n_pages": len(pages),
    }
    info.update(overrides.get(path.name, {}))
    return info, _strip_references(pages)


def chunk_pages(pages):
    for page_no, text in enumerate(pages, start=1):
        words = text.split()
        step = CHUNK_WORDS - OVERLAP_WORDS
        for i in range(0, max(len(words), 1), step):
            piece = words[i: i + CHUNK_WORDS]
            if len(piece) < MIN_CHUNK_WORDS:
                break
            yield page_no, " ".join(piece)
            if i + CHUNK_WORDS >= len(words):
                break


def ingest(papers_dir=PAPERS_DIR, log=print):
    docs, chunks, failed, seen = [], [], [], {}
    for path in sorted(Path(papers_dir).glob("*.pdf")):
        try:
            info, pages = read_pdf(path)
        except Exception as e:  # corrupt/encrypted PDF: log and continue
            failed.append({"file": path.name, "error": str(e)})
            continue
        body = " ".join(pages)
        if len(body) < 1500:
            failed.append({"file": path.name, "error": "no extractable text (scanned PDF?)"})
            continue
        key = hashlib.sha1(re.sub(r"\W+", "", body[:20000]).lower().encode()).hexdigest()
        title_key = re.sub(r"\W+", "", info["title"]).lower()[:80]
        dup_of = seen.get(key) or seen.get(title_key)
        if dup_of:
            log(f"  duplicate: {path.name} == {dup_of}")
            continue
        seen[key] = seen[title_key] = path.name
        doc_id = len(docs)
        info["doc_id"] = doc_id
        docs.append(info)
        for page, text in chunk_pages(pages):
            chunks.append({"chunk_id": len(chunks), "doc_id": doc_id, "page": page, "text": text})
    return docs, chunks, failed
