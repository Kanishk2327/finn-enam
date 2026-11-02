"""SAMPLE DATA ONLY. Generated so the app runs offline. Never real prices or filings."""
import random, hashlib, datetime as dt
from .classify import classify
from .config import SYMBOLS

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def prices(symbols=SYMBOLS):
    out = {}
    today = dt.date.today()
    dates = []
    d = today
    while len(dates) < 62:
        if d.weekday() < 5:
            dates.append(d)
        d -= dt.timedelta(days=1)
    dates.reverse()
    for s in symbols:
        rnd = random.Random(s)
        p, c, v = rnd.uniform(300, 4000), [], []
        for _ in dates:
            p *= 1 + rnd.gauss(0.0003, 0.012)
            c.append(round(p, 2))
            v.append(rnd.uniform(0.8, 1.2) * 1_000_000)
        out[s] = {"close": c, "volume": v, "dates": [x.isoformat() for x in dates]}
    # force a few anomalies on the last day so alerts are demonstrable
    for s, mv, vm in [("DIXON", 0.062, 2.8), ("CDSL", -0.041, 3.4), ("TRENT", 0.012, 2.3), ("TATASTEEL", -0.034, 1.1)]:
        if s in out:
            out[s]["close"][-1] = round(out[s]["close"][-2] * (1 + mv), 2)
            out[s]["volume"][-1] = out[s]["volume"][-2] * vm * 1.0
    return out


_RAW = [
    ("DIXON", 2, "Outcome of Board Meeting", "Board approved unaudited financial results for the quarter and half year ended September 30"),
    ("DIXON", 3, "Press Release", "Company secures new manufacturing contract worth Rs 1,200 crore"),
    ("TCS", 5, "Appointment of Chief Financial Officer", "Board approved appointment of Mr. Sample Person as Chief Financial Officer effective December 1"),
    ("PERSISTENT", 4, "Analysts/Institutional Investor Meet", "Schedule of analyst meet in Mumbai"),
    ("PERSISTENT", 6, "Earnings call transcript", "Transcript of Q2 conference call"),
    ("CDSL", 1, "Credit Rating", "CRISIL reaffirms AAA stable rating"),
    ("TITAN", 7, "Dividend", "Board declared interim dividend, record date November 14"),
    ("RELIANCE", 8, "Acquisition", "Company to acquire 51% stake in a renewable energy subsidiary"),
    ("ITC", 9, "Disclosure under Regulation 74(5)", "Certificate under SEBI Depositories and Participants regulations"),
    ("ITC", 10, "ESOP allotment", "Allotment of equity shares under employee stock option scheme"),
    ("LT", 11, "Postal Ballot Notice", "Postal ballot notice for appointment of independent director"),
    ("MARUTI", 12, "Newspaper Publication", "Newspaper publication of audited financial results"),
    ("HDFCBANK", 14, "Analysts/Institutional Investor Meet", "Meeting with institutional investors"),
    ("TATASTEEL", 15, "Fund raising", "Board approves raising Rs 3,000 crore via non-convertible debentures"),
    ("POLYCAB", 16, "Announcement under Regulation 30 (LODR)", "Show cause notice received from tax authority, demand of Rs 45 crore"),
    ("SUNPHARMA", 20, "Trading Window", "Intimation of closure of trading window"),
    ("INFY", 22, "Appointment of Auditor", "Appointment of statutory auditors for FY27"),
    ("BHARTIARTL", 30, "Press Release", "Launch of new enterprise product suite"),
    ("TRENT", 50, "Capex", "Board approves new distribution facility, capex Rs 400 crore"),
]


def announcements(hours=24):
    now = dt.datetime.now(IST)
    out = []
    for sym, ago, head, text in _RAW:
        if ago > hours:
            continue
        ts = now - dt.timedelta(hours=ago)
        cat, pr = classify(head, text)
        out.append({"id": hashlib.sha1(f"{sym}{head}".encode()).hexdigest()[:12], "symbol": sym, "ts": ts.isoformat(),
                    "headline": head, "text": text, "url": "", "category": cat, "priority": pr, "demo": True})
    return sorted(out, key=lambda x: x["ts"], reverse=True)


DEMO_RESULTS = {  # shape of the real output, fake numbers
    "entity": "consolidated", "unit": "Rs crore", "ebitda_derived": True,
    "metrics": {
        "revenue": {"cur": 4120.0, "qoq": 3890.0, "yoy": 3240.0},
        "ebitda": {"cur": 215.0, "qoq": 198.0, "yoy": 160.0},
        "pbt": {"cur": 170.0, "qoq": 152.0, "yoy": 118.0},
        "pat": {"cur": 128.0, "qoq": 115.0, "yoy": 90.0},
    },
}
DEMO_BIO = {"name": "Mr. Sample Person", "role": "Chief Financial Officer", "effective": "December 1",
            "bio": "Demo text. In live mode this comes from a grounded web search and is labelled unverified.",
            "prior": ["Sample Corp (CFO)", "Another Ltd (VP Finance)"], "verified": False}
