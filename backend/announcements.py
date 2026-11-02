"""NSE corporate announcements. NSE blocks bare clients, so we warm a cookie first."""
import re, hashlib, datetime as dt, httpx
from concurrent.futures import ThreadPoolExecutor
from . import cache
from .classify import classify
from .config import SYMBOLS, DEMO

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
     "Accept": "application/json,text/plain,*/*", "Accept-Language": "en-US,en;q=0.9",
     "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements"}
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def _client():
    c = httpx.Client(headers=H, timeout=25, follow_redirects=True)
    c.get("https://www.nseindia.com/")
    return c


def _norm(sym, r):
    try:
        ts = dt.datetime.strptime(r.get("an_dt") or r.get("sort_date"), "%d-%b-%Y %H:%M:%S").replace(tzinfo=IST)
    except Exception:
        ts = dt.datetime.now(IST)
    head, text = (r.get("desc") or "").strip(), (r.get("attchmntText") or "").strip()
    cat, pr = classify(head, text)
    url = r.get("attchmntFile") or ""
    return {"id": hashlib.sha1(f"{sym}{ts}{url}{head}".encode()).hexdigest()[:12], "symbol": sym,
            "ts": ts.isoformat(), "headline": head, "text": text[:600], "url": url,
            "category": cat, "priority": pr}


def _fetch_symbol(client, sym, d0, d1):
    k = cache.key("ann", sym, d0, d1)
    hit = cache.get(k, ttl=600)
    if hit is not None:
        return hit
    r = client.get("https://www.nseindia.com/api/corporate-announcements",
                   params={"index": "equities", "symbol": sym, "from_date": d0, "to_date": d1})
    r.raise_for_status()
    return cache.put(k, [_norm(sym, x) for x in r.json()])


def fetch(hours=24, symbols=SYMBOLS):
    now = dt.datetime.now(IST)
    since = now - dt.timedelta(hours=hours)
    if DEMO:
        from . import demo
        return demo.announcements(hours), "demo"
    try:
        d0, d1 = since.strftime("%d-%m-%Y"), now.strftime("%d-%m-%Y")
        client = _client()
        with ThreadPoolExecutor(4) as ex:
            res = list(ex.map(lambda s: _fetch_symbol(client, s, d0, d1), symbols))
        items = [i for sub in res for i in sub if dt.datetime.fromisoformat(i["ts"]) >= since]
        # same filing is often posted twice; collapse on symbol+headline+day
        seen, out = set(), []
        for i in sorted(items, key=lambda x: x["ts"], reverse=True):
            kk = (i["symbol"], i["headline"][:60], i["ts"][:10])
            if kk not in seen:
                seen.add(kk)
                out.append(i)
        return out, "live"
    except Exception:
        import json, os
        snap = os.path.join(os.path.dirname(__file__), "snapshot_announcements.json")
        if os.path.exists(snap):  # real filings recorded earlier; window is ignored, UI labels it
            return json.load(open(snap)), "snapshot"
        from . import demo
        return demo.announcements(hours), "demo"
