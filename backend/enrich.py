"""Push-side enrichment. Cheap model only. Numbers are computed in code, not by the LLM."""
from . import llm, docs
from .config import SECTOR, DEMO

RES_PROMPT = """Extract from this Indian results filing. Use CONSOLIDATED figures if present, else standalone.
Results tables have several columns: quarter ended (current), quarter ended (previous quarter), quarter ended (same quarter last year),
and ALSO half-year / nine-month / full-year columns. ONLY use the three single-QUARTER columns. NEVER use half-year, nine-month or year columns.
Return JSON: {"entity":"consolidated|standalone","unit":"Rs crore|Rs lakh|Rs million",
"labels":{"cur":"column header as printed e.g. 30-Sep-2026","qoq":"...","yoy":"..."},
"cols":{"cur":{...},"qoq":{...},"yoy":{...}}} where each of cur (this quarter), qoq (immediately previous quarter),
yoy (same quarter last year) has numeric fields: revenue (revenue from operations only, not total income), other_income, finance_cost,
depreciation (depreciation and amortisation), pbt (profit before tax; before exceptional items if shown separately), pat (net profit after tax).
Use null when a value is not printed. Never guess, never compute, never return 0 for something not shown. Copy numbers exactly, keep sign.
TEXT:\n"""


def _num(x):
    """LLMs sometimes return '5,899.25' or '(123.4)' as text. Clean it, or give None."""
    if x is None or isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    t = str(x).strip().replace(",", "").replace("\u2212", "-")
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").strip()
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _pct(a, b):
    if a is None or b in (None, 0):
        return None
    return round((a / b - 1) * 100, 1)


def results_snapshot(item):
    if DEMO or not item.get("url"):
        from . import demo
        if item.get("demo"):
            return _with_deltas(demo.DEMO_RESULTS, demo=True)
        return {"error": "no filing attachment on this announcement"}
    pages = docs.pdf_pages(item["url"], max_pages=12)
    text = "\n".join(pages)[:24000]
    d = llm.call(RES_PROMPT + text, llm.FAST)
    bank = SECTOR.get(item["symbol"]) == "Banks"
    metrics = {k: {} for k in ("revenue", "ebitda", "pbt", "pat")}
    for col, v in (d.get("cols") or {}).items():
        v = {k: _num(x) for k, x in (v or {}).items()}
        metrics["revenue"][col] = v.get("revenue")
        metrics["pbt"][col] = v.get("pbt")
        metrics["pat"][col] = v.get("pat")
        need = (v.get("pbt"), v.get("finance_cost"), v.get("depreciation"), v.get("other_income"))
        if bank or any(x is None for x in need):  # a missing input is n/a, never silently zero
            metrics["ebitda"][col] = None
        else:  # derived, flagged as such in the UI
            metrics["ebitda"][col] = round(v["pbt"] + v["finance_cost"] + v["depreciation"] - v["other_income"], 2)
    out = _with_deltas({"entity": d.get("entity"), "unit": d.get("unit"), "metrics": metrics,
                        "ebitda_derived": True, "bank": bank, "labels": d.get("labels") or {}})
    if any(abs(m.get("yoy_pct") or 0) > 60 for m in metrics.values()):
        out["warn"] = "Large YoY swing. Check the filing before relying on it."
    return out


def _with_deltas(r, demo=False):
    for m in r["metrics"].values():
        m["qoq_pct"] = _pct(m.get("cur"), m.get("qoq"))
        m["yoy_pct"] = _pct(m.get("cur"), m.get("yoy"))
    r["demo"] = demo
    return r


PERSON_PROMPT = """From this exchange filing text, extract the person being appointed/resigning.
JSON: {"name":str|null,"role":str|null,"action":"appointed|resigned|other","effective":str|null}
TEXT:\n"""


def mgmt_bio(item):
    if item.get("demo"):
        from . import demo
        return demo.DEMO_BIO
    ext = llm.call(PERSON_PROMPT + f"{item['headline']}\n{item['text']}", llm.FAST)
    if not ext.get("name"):
        return {"error": "could not identify the person from the filing text"}
    q = (f"Professional background of {ext['name']}, {ext.get('role') or ''} at {item['symbol']} (India). "
         "Give 2 sentences on current/previous roles and employers. Then a line 'PRIOR:' with up to 3 prior employers, separated by ';'. "
         "If you cannot find a reliable match, say NOT FOUND.")
    txt = llm.call(q, llm.FAST, json_out=False, search=True)
    prior = []
    if "PRIOR:" in txt:
        txt, p = txt.split("PRIOR:", 1)
        prior = [x.strip() for x in p.split(";") if x.strip()][:3]
    return {**ext, "bio": txt.strip(), "prior": prior, "verified": False}


def one_liner(item):
    p = ("One plain sentence (max 22 words) on what this exchange filing says and why an investor might care. "
         "No hype. If it is routine, say so.\n" f"Title: {item['headline']}\nText: {item['text']}")
    return {"summary": llm.call(p, llm.FAST, json_out=False).strip()}


def enrich(item):
    c = item["category"]
    if c == "results":
        return {"kind": "results", **results_snapshot(item)}
    if c == "management_change":
        return {"kind": "mgmt", **mgmt_bio(item)}
    if item["priority"] <= 3:
        return {"kind": "summary", **one_liner(item)}
    return {"kind": "none"}
