"""PDF download, text extraction, chunking, tiny BM25-ish retrieval. All cached."""
import io, re, math, httpx
from collections import Counter
from . import cache

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def pdf_pages(url, max_pages=400):
    k = cache.key("pdf", url)
    hit = cache.get(k)
    if hit is not None:
        return hit
    from pypdf import PdfReader
    r = httpx.get(url, headers=UA, timeout=90, follow_redirects=True)
    r.raise_for_status()
    rd = PdfReader(io.BytesIO(r.content))
    pages = []
    for p in rd.pages[:max_pages]:
        try:
            pages.append(p.extract_text() or "")
        except Exception:
            pages.append("")
    return cache.put(k, pages)


def chunks(pages, size=1400, label=""):
    out = []
    for i, t in enumerate(pages, 1):
        t = re.sub(r"\s+", " ", t).strip()
        for j in range(0, len(t), size):
            seg = t[j:j + size]
            if len(seg) > 200:
                out.append({"src": label, "page": i, "text": seg})
    return out


def _tok(s):
    return re.findall(r"[a-z0-9]{3,}", s.lower())


def top(chs, query, n=6):
    q = Counter(_tok(query))
    if not chs or not q:
        return []
    df = Counter()
    toks = []
    for c in chs:
        t = Counter(_tok(c["text"]))
        toks.append(t)
        df.update(t.keys())
    N = len(chs)
    scored = []
    for c, t in zip(chs, toks):
        s = sum((1 + math.log(t[w])) * math.log(1 + N / df[w]) for w in q if w in t)
        scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    return [c for s, c in scored[:n] if s > 0]


def fmt(chs):
    return "\n\n".join(f"[{c['src']} p.{c['page']}]\n{c['text']}" for c in chs)
