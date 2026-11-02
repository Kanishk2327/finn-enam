"""Pull side. Primary sources only: screener tables, annual report, concall transcripts.
Cost routing: per-document extraction on FAST (cached by URL), one SMART call for synthesis."""
from . import llm, docs, fundamentals, analytics, cache
from .config import NAME

SYS = ("You are an equity research analyst. Use ONLY the material provided. Do not use outside knowledge of the company, "
       "news, or broker views. If something is not in the material write 'not stated'. Be terse, specific, numeric. "
       "Cite sources inline like [Q2 call] or [AR p.45].")

CALL_PROMPT = """From this earnings-call transcript extract JSON:
{"period":str,"guidance":[{"metric":str,"statement":str,"quantified":bool}],
"growth_claims":[str],"tone":"confident|cautious|defensive|mixed","analyst_pressure":[str],"risks_flagged":[str]}
Only explicit forward-looking statements by management count as guidance (growth, margins, capex, volumes). Max 6 per list.
TEXT:\n"""

AR_QUERIES = {
    "business": "business overview segments revenue mix products customers manufacturing",
    "risk": "risks contingent liabilities related party transactions auditor qualification emphasis of matter",
    "capex": "capital expenditure capex plans capacity expansion investment outlook",
}
AR_PROMPT = """From these annual-report excerpts extract JSON:
{"business":str,"segments":[{"name":str,"share_pct":number|null}],"capex_plans":[str],
"contingent_liabilities":str,"related_party":str,"auditor_remarks":str,"outlook":str}
Use 'not stated' for anything missing. Keep each string under 40 words.
EXCERPTS:\n"""

FINAL_PROMPT = """Company: {name} ({sym}). Build an investor research view as JSON with these keys:
business, financial, trajectory, balance_sheet, cash_quality, narrative_vs_numbers, guidance, bull_bear.
Each of the first 7 is {{"headline": one sentence verdict, "points": [2-4 short strings with numbers], "flag": "ok|watch|red"}}.
narrative_vs_numbers must also contain "table": [{{"quarter":str,"promised":str,"delivered":str,"verdict":"delivered|missed|partial|unclear"}}]
for up to the last 4 quarters, matching each call's guidance to the reported numbers of the following quarter(s).
guidance also contains "items":[{{"metric":str,"statement":str,"source":str}}].
bull_bear: {{"bull":[3 strings],"bear":[3 strings]}}.
Every number must come from COMPUTED NUMBERS or EXTRACTS below. Flag divergences between tone and numbers explicitly.

COMPUTED NUMBERS (screener standardised financials):
{nums}

CONCALL EXTRACTS (oldest to newest):
{calls}

ANNUAL REPORT EXTRACT:
{ar}
"""


def _concalls(c, n=4):
    out = []
    for cc in c["docs"]["concalls"][:n]:
        try:
            pages = docs.pdf_pages(cc["url"], max_pages=60)
            txt = "\n".join(pages)[:60000]
            ex = llm.call(CALL_PROMPT + txt, llm.FAST)
            out.append({"label": cc["label"], **ex})
        except Exception as e:
            out.append({"label": cc["label"], "error": str(e)[:80]})
    return list(reversed(out))


def _ar(c):
    if not c["docs"]["annual"]:
        return {}
    a = c["docs"]["annual"][0]
    pages = docs.pdf_pages(a["url"])
    chs = docs.chunks(pages, label=f"AR {a['label']}")
    sel = []
    for q in AR_QUERIES.values():
        sel += docs.top(chs, q, 5)
    return llm.call(AR_PROMPT + docs.fmt(sel)[:30000], llm.FAST)


def research(symbol):
    k = cache.key("research", symbol)
    hit = cache.get(k, ttl=12 * 3600)
    if hit:
        return hit
    c = fundamentals.get_company(symbol)
    nums = analytics.compute(c)
    calls = _concalls(c)
    ar = _ar(c)
    out = llm.call(FINAL_PROMPT.format(name=NAME.get(symbol, symbol), sym=symbol, nums=nums, calls=calls, ar=ar),
                   llm.SMART, system=SYS)
    out["numbers"] = nums
    out["sources"] = {"concalls": [x["label"] for x in c["docs"]["concalls"][:4]],
                      "annual_report": (c["docs"]["annual"] or [{}])[0].get("label")}
    return cache.put(k, out)


def ask(symbol, question):
    c = fundamentals.get_company(symbol)
    chs = []
    for cc in c["docs"]["concalls"][:4]:
        chs += docs.chunks(docs.pdf_pages(cc["url"], 60), label=f"call {cc['label']}")
    if c["docs"]["annual"]:
        a = c["docs"]["annual"][0]
        chs += docs.chunks(docs.pdf_pages(a["url"]), label=f"AR {a['label']}")
    sel = docs.top(chs, question, 8)
    if not sel:
        return {"answer": "Nothing in the annual report or recent calls addresses that.", "sources": []}
    p = f"Question: {question}\n\nAnswer in max 4 sentences using only the excerpts. Cite [source p.N]. If not answered, say so.\n\n{docs.fmt(sel)}"
    return {"answer": llm.call(p, llm.FAST, system=SYS, json_out=False).strip(),
            "sources": [f"{x['src']} p.{x['page']}" for x in sel[:4]]}
