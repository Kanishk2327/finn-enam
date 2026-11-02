"""screener.in: standardised multi-year tables + links to annual reports and concall transcripts."""
import re, httpx
from bs4 import BeautifulSoup
from . import cache

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def _num(s):
    s = s.replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _label(s):
    return re.sub(r"[\s\+\-]+$", "", s.replace("\xa0", " ")).strip().lower()


def parse_table(sec):
    t = sec.find("table") if sec else None
    if not t:
        return None
    cols = [th.get_text(strip=True) for th in t.select("thead th")][1:]
    rows = {}
    for tr in t.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        rows[_label(tds[0].get_text())] = [_num(td.get_text()) for td in tds[1:]]
    if cols and cols[-1].upper() == "TTM":  # not a fiscal year, would skew CAGRs
        cols = cols[:-1]
        rows = {k: v[:len(cols)] for k, v in rows.items()}
    return {"cols": cols, "rows": rows}


def parse_docs(soup):
    sec = soup.select_one("#documents")
    out = {"annual": [], "concalls": []}
    if not sec:
        return out
    for h in sec.find_all(["h3", "h2"]):
        title = h.get_text(strip=True).lower()
        ul = h.find_next("ul")
        if not ul:
            continue
        for li in ul.find_all("li"):
            links = li.find_all("a", href=True)
            if not links:
                continue
            if "annual" in title:
                out["annual"].append({"label": links[0].get_text(" ", strip=True), "url": links[0]["href"]})
            elif "concall" in title:
                tr = [a for a in links if "transcript" in a.get_text().lower()]
                if tr:
                    when = re.sub(r"\s+", " ", li.get_text(" ", strip=True).split("Transcript")[0]).strip()
                    out["concalls"].append({"label": when, "url": tr[0]["href"]})
    return out


def parse(html):
    soup = BeautifulSoup(html, "lxml")
    return {
        "quarterly": parse_table(soup.select_one("#quarters")),
        "annual": parse_table(soup.select_one("#profit-loss")),
        "balance": parse_table(soup.select_one("#balance-sheet")),
        "cash": parse_table(soup.select_one("#cash-flow")),
        "ratios": parse_table(soup.select_one("#ratios")),
        "docs": parse_docs(soup),
        "name": (soup.find("h1") or soup.find("title")).get_text(strip=True) if soup else "",
    }


def get_company(symbol):
    k = cache.key("screener", symbol)
    hit = cache.get(k, ttl=24 * 3600)
    if hit:
        return hit
    for path in ("consolidated/", ""):
        r = httpx.get(f"https://www.screener.in/company/{symbol}/{path}", headers=UA, timeout=30, follow_redirects=True)
        if r.status_code == 200:
            c = parse(r.text)
            if c["quarterly"] and c["annual"]:
                c["symbol"] = symbol
                return cache.put(k, c)
    raise RuntimeError(f"screener.in has no usable page for {symbol}")
