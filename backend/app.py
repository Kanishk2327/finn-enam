import os, datetime as dt
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import prices, announcements, enrich, research, llm
from .config import PORTFOLIO, RESEARCH_DEMO, SYMBOLS, NAME, SECTOR

app = FastAPI(title="FINN")
@app.on_event("startup")
def _startup():
    llm.resolve_models()


STORE = {}  # announcement id -> item, for lazy enrichment
FE = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.get("/api/config")
def config():
    return {"portfolio": [{"symbol": s, "name": n, "sector": sec} for s, n, sec in PORTFOLIO],
            "research_demo": RESEARCH_DEMO, "llm": llm.enabled()}


@app.get("/api/digest")
def digest(hours: int = 24):
    hours = max(1, min(hours, 24 * 30))
    items, src = announcements.fetch(hours)
    snaps, _ = prices.snapshot()
    moved = {r["symbol"] for r in snaps if abs(r["chg_pct"]) >= 3 or r["vol_ratio"] >= 2}
    for i in items:
        STORE[i["id"]] = i
        i["name"] = NAME.get(i["symbol"], i["symbol"])
        i["unusual_move"] = i["symbol"] in moved
        if i["unusual_move"] and i["priority"] > 1:  # price confirms the filing: lift one tier
            i["priority"] -= 1
    items.sort(key=lambda x: x["ts"], reverse=True)
    items.sort(key=lambda x: x["priority"])  # stable: newest first inside each tier
    counts = {p: sum(1 for i in items if i["priority"] == p) for p in (1, 2, 3, 4)}
    return {"meta": {"source": src, "hours": hours, "counts": counts, "total": len(items)}, "items": items}


@app.get("/api/prices")
def px():
    rows, src = prices.snapshot()
    names = {s: n for s, n, _ in PORTFOLIO}
    for r in rows:
        r["name"] = names[r["symbol"]]
        r["sector"] = SECTOR[r["symbol"]]
    return {"meta": {"source": src}, "rows": rows}


@app.get("/api/alerts")
def alerts(vol: float = 2.0, move: float = 3.0, cats: str = "results,M&A,management_change,litigation,fund_raise", hours: int = 48):
    rows, src = prices.snapshot()
    pa = prices.price_alerts(rows, vol, move)
    items, asrc = announcements.fetch(hours)
    want = {c for c in cats.split(",") if c}
    ann = [i for i in items if i["category"] in want]
    for i in ann:
        STORE[i["id"]] = i
        i["name"] = NAME.get(i["symbol"], i["symbol"])
    return {"meta": {"source": src if src == asrc else "mixed"}, "price": pa, "announcements": ann}


@app.get("/api/enrich/{aid}")
def enrich_one(aid: str):
    it = STORE.get(aid)
    if not it:
        raise HTTPException(404, "unknown id; refresh the digest")
    try:
        return enrich.enrich(it)
    except Exception as e:
        return {"kind": "error", "error": str(e)[:200]}


@app.get("/api/research/{symbol}")
def do_research(symbol: str):
    symbol = symbol.upper().strip()
    if os.getenv("FINN_DEMO") == "1" or not llm.enabled():
        import json
        p = os.path.join(os.path.dirname(__file__), "demo_research.json")
        d = json.load(open(p))
        d["demo"] = True
        d["symbol"] = symbol
        return d
    try:
        return research.research(symbol)
    except Exception as e:
        raise HTTPException(502, f"research failed: {str(e)[:200]}")


class Q(BaseModel):
    symbol: str
    question: str


@app.post("/api/ask")
def ask(q: Q):
    if not llm.enabled() or os.getenv("FINN_DEMO") == "1":
        return {"answer": "Ask needs GEMINI_API_KEY and live network. Not available in demo mode.", "sources": []}
    try:
        return research.ask(q.symbol.upper(), q.question)
    except Exception as e:
        raise HTTPException(502, str(e)[:200])


@app.get("/api/stats")
def stats():
    return llm.STATS


@app.get("/")
def index():
    return FileResponse(os.path.join(FE, "index.html"))
