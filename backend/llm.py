"""Thin Gemini client with disk cache and two-tier routing.
FAST  = bulk extraction/classification (cheap).
SMART = cross-source reasoning (only the final research synthesis)."""
import os, re, json, time, httpx
from . import cache

FAST = os.getenv("FINN_FAST_MODEL", "gemini-2.5-flash-lite")
SMART = os.getenv("FINN_SMART_MODEL", "gemini-2.5-flash")
_RESOLVED = False
BASE = "https://generativelanguage.googleapis.com/v1beta"


def _ver(name):
    import re as _re
    m = _re.search(r"gemini-(\d+(?:\.\d+)?)", name)
    return float(m.group(1)) if m else 0.0


def resolve_models():
    """Ask Google which models this key can call, unless the user pinned them via env.
    Picks the newest stable flash-lite (FAST) and flash (SMART)."""
    global FAST, SMART, _RESOLVED
    _RESOLVED = True
    key = os.getenv("GEMINI_API_KEY")
    if not key or (os.getenv("FINN_FAST_MODEL") and os.getenv("FINN_SMART_MODEL")):
        return
    try:
        r = httpx.get(f"{BASE}/models", headers={"x-goog-api-key": key}, params={"pageSize": 200}, timeout=30)
        r.raise_for_status()
        names = [m["name"].split("/")[-1] for m in r.json().get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
    except Exception:
        return

    def pick(pred):
        c = [n for n in names if n.startswith("gemini-") and pred(n)
             and not any(x in n for x in ("image", "tts", "live", "audio", "embedding", "thinking", "robotics", "computer", "learnlm", "gemma"))]
        stable = [n for n in c if not any(x in n for x in ("preview", "exp", "-latest"))]
        pool = stable or c
        return sorted(pool, key=lambda n: (_ver(n), -len(n)), reverse=True)[0] if pool else None

    if not os.getenv("FINN_FAST_MODEL"):
        FAST = pick(lambda n: "flash-lite" in n) or pick(lambda n: "flash" in n) or FAST
    if not os.getenv("FINN_SMART_MODEL"):
        SMART = pick(lambda n: "flash" in n and "lite" not in n) or FAST
    print(f"[finn] models: fast={FAST} smart={SMART}")
MOCK = None  # tests set this to fn(prompt, model, system) -> str
STATS = {"calls": 0, "cache_hits": 0, "fast": 0, "smart": 0}


def enabled():
    return bool(os.getenv("GEMINI_API_KEY")) or MOCK is not None


def _parse(t):
    t = re.sub(r"^```(?:json)?|```$", "", t.strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"[\[{].*[\]}]", t, re.S)
        return json.loads(m.group(0)) if m else None


def call(prompt, model=None, system="", json_out=True, search=False):
    global _RESOLVED
    if not _RESOLVED and not MOCK:
        resolve_models()
    model = model or FAST
    k = cache.key("llm", model, system, prompt, search)
    hit = cache.get(k)
    if hit is not None:
        STATS["cache_hits"] += 1
        return hit
    if MOCK:
        out = MOCK(prompt, model, system)
    else:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY not set")
        body = {"contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if search:
            body["tools"] = [{"google_search": {}}]  # cannot combine with json mime
        elif json_out:
            body["generationConfig"]["responseMimeType"] = "application/json"
        url = f"{BASE}/models/{model}:generateContent"
        for i in range(4):
            r = httpx.post(url, headers={"x-goog-api-key": key}, json=body, timeout=120)
            if r.status_code in (429, 503):
                time.sleep(2 ** i * 2)
                continue
            if r.status_code >= 400:  # never echo the URL: keep secrets out of errors
                raise RuntimeError(f"Gemini {r.status_code} on model '{model}': {r.text[:160]}")
            break
        else:
            raise RuntimeError("LLM rate limited, retry in a minute")
        parts = r.json()["candidates"][0]["content"]["parts"]
        out = "".join(p.get("text", "") for p in parts)
    STATS["calls"] += 1
    STATS["smart" if model == SMART else "fast"] += 1
    res = _parse(out) if json_out else out
    if res is None:
        raise ValueError("LLM returned unparseable output")
    return cache.put(k, res)
