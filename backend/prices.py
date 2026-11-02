"""EOD prices via yfinance. One batched download, cached 3h."""
from . import cache
from .config import SYMBOLS


def _live(symbols):
    import yfinance as yf
    tk = [s + ".NS" for s in symbols]
    df = yf.download(tk, period="3mo", group_by="ticker", threads=True, progress=False, auto_adjust=False)
    out = {}
    for s in symbols:
        d = df[s + ".NS"].dropna(subset=["Close"])
        if len(d) < 22:
            continue
        out[s] = {"close": d["Close"].round(2).tolist(), "volume": d["Volume"].astype(float).tolist(),
                  "dates": [x.strftime("%Y-%m-%d") for x in d.index]}
    if not out:
        raise RuntimeError("no price data")
    return out


def raw(symbols=SYMBOLS):
    k = cache.key("px", ",".join(symbols))
    hit = cache.get(k, ttl=3 * 3600)
    if hit:
        return hit, "live"
    from .config import DEMO
    if DEMO:
        from . import demo
        return demo.prices(symbols), "demo"
    try:
        return cache.put(k, _live(symbols)), "live"
    except Exception:
        from . import demo
        return demo.prices(symbols), "demo"


def snapshot(symbols=SYMBOLS):
    data, src = raw(symbols)
    rows = []
    for s, d in data.items():
        c, v = d["close"], d["volume"]
        avg = sum(v[-21:-1]) / 20 or 1
        rows.append({
            "symbol": s, "close": c[-1], "chg_pct": round((c[-1] / c[-2] - 1) * 100, 2),
            "vol_ratio": round(v[-1] / avg, 2), "spark": c[-30:], "date": d["dates"][-1],
            "chg_5d": round((c[-1] / c[-6] - 1) * 100, 1),
        })
    return rows, src


def price_alerts(rows, vol_mult=2.0, move_pct=3.0):
    out = []
    for r in rows:
        if r["vol_ratio"] >= vol_mult:
            out.append({"symbol": r["symbol"], "kind": "volume", "value": r["vol_ratio"],
                        "text": f"Volume {r['vol_ratio']}x its 20-day average", "chg_pct": r["chg_pct"], "date": r["date"]})
        if abs(r["chg_pct"]) >= move_pct:
            out.append({"symbol": r["symbol"], "kind": "price", "value": r["chg_pct"],
                        "text": f"{'+' if r['chg_pct']>0 else ''}{r['chg_pct']}% on the day", "chg_pct": r["chg_pct"], "date": r["date"]})
    return sorted(out, key=lambda a: -abs(a["value"]))
