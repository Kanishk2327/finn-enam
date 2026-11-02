import os

DEMO = os.getenv("FINN_DEMO", "0") == "1"

# 18 names, mixed sector and size. Banks are included on purpose:
# EBITDA does not apply to them and the results parser must handle that.
PORTFOLIO = [
    ("RELIANCE", "Reliance Industries", "Conglomerate"),
    ("TCS", "TCS", "IT Services"),
    ("HDFCBANK", "HDFC Bank", "Banks"),
    ("ICICIBANK", "ICICI Bank", "Banks"),
    ("INFY", "Infosys", "IT Services"),
    ("PERSISTENT", "Persistent Systems", "IT Services"),
    ("ITC", "ITC", "FMCG"),
    ("TITAN", "Titan", "Consumer"),
    ("TRENT", "Trent", "Retail"),
    ("LT", "Larsen & Toubro", "Capital Goods"),
    ("POLYCAB", "Polycab India", "Capital Goods"),
    ("DIXON", "Dixon Technologies", "Electronics"),
    ("BHARTIARTL", "Bharti Airtel", "Telecom"),
    ("SUNPHARMA", "Sun Pharma", "Pharma"),
    ("MARUTI", "Maruti Suzuki", "Auto"),
    ("ASIANPAINT", "Asian Paints", "Paints"),
    ("TATASTEEL", "Tata Steel", "Metals"),
    ("CDSL", "CDSL", "Capital Markets"),
]
RESEARCH_DEMO = ["DIXON", "PERSISTENT", "TITAN", "CDSL"]

SECTOR = {s: sec for s, _, sec in PORTFOLIO}
NAME = {s: n for s, n, _ in PORTFOLIO}
SYMBOLS = [s for s, _, _ in PORTFOLIO]

# priority 1 = look now, 4 = collapsed noise
PRIORITY = {
    "results": 1, "M&A": 1, "management_change": 1, "litigation": 1, "fund_raise": 1,
    "credit_rating": 2, "dividend": 2, "capex": 2, "bonus_split": 2, "pledging": 2,
    "insider_trading": 3, "earnings_call": 3, "press_release": 3, "investor_meetings": 4,
    "postal_ballot": 4, "agm_egm": 4, "unclassified": 4,
}
