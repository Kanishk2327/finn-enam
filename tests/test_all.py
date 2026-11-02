import os, json, sys
os.environ["FINN_DEMO"] = "1"
import tempfile
os.environ["FINN_CACHE"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fastapi.testclient import TestClient
from backend import classify, fundamentals, analytics, llm, docs, research, enrich
from backend.app import app

c = TestClient(app)


def test_classifier():
    f = classify.classify
    assert f("Outcome of Board Meeting", "approved unaudited financial results for the quarter")[0] == "results"
    assert f("Appointment of Auditor", "statutory auditors")[0] == "unclassified"
    assert f("Resignation of CFO", "")[0] == "management_change" and f("Resignation of CFO", "")[1] == 1
    assert f("Press Release", "bagged order worth Rs 500 crore")[1] == 2
    assert f("Earnings call transcript", "Q2")[0] == "earnings_call"
    assert f("Postal Ballot Notice", "appointment of independent director")[0] == "postal_ballot"
    assert f("ESOP allotment", "employee stock option")[0] == "unclassified"


def test_demo_endpoints():
    d = c.get("/api/digest?hours=24").json()
    assert d["meta"]["source"] == "demo" and d["items"][0]["priority"] == 1
    assert d["meta"]["counts"]["4"] if "4" in d["meta"]["counts"] else True
    px = c.get("/api/prices").json()["rows"]
    assert len(px) == 18
    a = c.get("/api/alerts?vol=2&move=3").json()
    syms = {x["symbol"] for x in a["price"]}
    assert "DIXON" in syms and "CDSL" in syms
    a2 = c.get("/api/alerts?vol=9&move=20&cats=").json()
    assert a2["price"] == [] and a2["announcements"] == []
    wide = c.get("/api/digest?hours=72").json()["items"]
    assert len(wide) > len(d["items"])


def test_enrich_demo():
    d = c.get("/api/digest?hours=72").json()["items"]
    res = next(i for i in d if i["category"] == "results")
    e = c.get(f"/api/enrich/{res['id']}").json()
    assert e["kind"] == "results" and abs(e["metrics"]["revenue"]["yoy_pct"] - 27.2) < 0.1
    mg = next(i for i in d if i["category"] == "management_change")
    assert c.get(f"/api/enrich/{mg['id']}").json()["kind"] == "mgmt"


def test_research_demo():
    r = c.get("/api/research/DIXON").json()
    assert r["demo"] and "narrative_vs_numbers" in r


HTML = """<html><h1>Test Co</h1>
<section id="quarters"><table><thead><tr><th></th><th>Sep 24</th><th>Dec 24</th><th>Mar 25</th><th>Jun 25</th><th>Sep 25</th></tr></thead><tbody>
<tr><td class="text">Sales&nbsp;+</td><td>100</td><td>110</td><td>120</td><td>130</td><td>150</td></tr>
<tr><td class="text">OPM %</td><td>10%</td><td>10%</td><td>11%</td><td>11%</td><td>12%</td></tr>
<tr><td class="text">Net Profit&nbsp;+</td><td>8</td><td>9</td><td>10</td><td>11</td><td>14</td></tr></tbody></table></section>
<section id="profit-loss"><table><thead><tr><th></th><th>Mar 21</th><th>Mar 22</th><th>Mar 23</th><th>Mar 24</th><th>Mar 25</th><th>TTM</th></tr></thead><tbody>
<tr><td>Sales +</td><td>100</td><td>130</td><td>170</td><td>220</td><td>300</td><td>320</td></tr>
<tr><td>OPM %</td><td>8%</td><td>9%</td><td>9%</td><td>10%</td><td>11%</td><td>11%</td></tr>
<tr><td>Net Profit +</td><td>5</td><td>8</td><td>10</td><td>14</td><td>20</td><td>22</td></tr></tbody></table></section>
<section id="cash-flow"><table><thead><tr><th></th><th>Mar 22</th><th>Mar 23</th><th>Mar 24</th><th>Mar 25</th></tr></thead><tbody>
<tr><td>Cash from Operating Activity +</td><td>2</td><td>4</td><td>5</td><td>8</td></tr>
<tr><td>Cash from Investing Activity +</td><td>-5</td><td>-6</td><td>-9</td><td>-10</td></tr></tbody></table></section>
<section id="documents"><div><h3>Annual reports</h3><ul><li><a href="http://x/ar.pdf">Financial Year 2025</a></li></ul></div>
<div><h3>Concalls</h3><ul><li>Aug 2025 <a href="http://x/t1.pdf">Transcript</a><a href="http://x/p.pdf">PPT</a></li><li>May 2025 <a href="http://x/t2.pdf">Transcript</a></li></ul></div></section></html>"""


def test_screener_parse_and_analytics():
    co = fundamentals.parse(HTML)
    assert co["quarterly"]["rows"]["sales"][-1] == 150 and co["quarterly"]["rows"]["opm %"][-1] == 12
    assert [x["label"] for x in co["docs"]["concalls"]] == ["Aug 2025", "May 2025"]
    n = analytics.compute(co)
    assert n["quarters"][-1]["sales_yoy"] == 50.0 and n["quarters"][-1]["sales_qoq"] == 15.4
    assert n["annual"]["sales_cagr_3y"] == round(((300 / 130) ** (1 / 3) - 1) * 100, 1)
    assert n["cash"]["cfo_to_pat"][-1] == 0.4


def test_research_pipeline_routing(monkeypatch=None):
    co = fundamentals.parse(HTML)
    co["symbol"] = "TESTCO"
    fundamentals.get_company = lambda s: co
    docs.pdf_pages = lambda url, max_pages=400: [f"Page text about margins guidance revenue growth capex segments. {url} " * 20]
    seen = {"fast": 0, "smart": 0}

    def mock(prompt, model, system):
        if model == llm.SMART:
            seen["smart"] += 1
            return json.dumps({k: {"headline": "h", "points": ["p"], "flag": "ok"} for k in
                               ["business", "financial", "trajectory", "balance_sheet", "cash_quality", "narrative_vs_numbers", "guidance"]} |
                              {"bull_bear": {"bull": ["a"], "bear": ["b"]}})
        seen["fast"] += 1
        if "earnings-call" in prompt:
            return json.dumps({"period": "Q1", "guidance": [], "growth_claims": [], "tone": "mixed", "analyst_pressure": [], "risks_flagged": []})
        return json.dumps({"business": "b", "segments": [], "capex_plans": [], "contingent_liabilities": "not stated", "related_party": "not stated", "auditor_remarks": "not stated", "outlook": "x"})
    llm.MOCK = mock
    out = research.research("TESTCO")
    assert seen["smart"] == 1 and seen["fast"] == 3  # 2 calls + 1 AR, one expensive call total
    assert out["numbers"]["quarters"]
    research.research("TESTCO")
    assert seen["smart"] == 1  # cached
    llm.MOCK = None


def test_results_extraction_math():
    llm.MOCK = lambda p, m, s: json.dumps({"entity": "consolidated", "unit": "Rs crore", "cols": {
        "cur": {"revenue": 1000, "pbt": 120, "finance_cost": 10, "depreciation": 30, "other_income": 15, "pat": 90},
        "qoq": {"revenue": 900, "pbt": 100, "finance_cost": 10, "depreciation": 30, "other_income": 10, "pat": 75},
        "yoy": {"revenue": 800, "pbt": 80, "finance_cost": 12, "depreciation": 28, "other_income": 8, "pat": 60}}})
    os.environ["FINN_DEMO"] = "0"
    import backend.enrich as E
    E.DEMO = False
    docs.pdf_pages = lambda u, max_pages=12: ["x"]
    r = E.results_snapshot({"url": "http://x", "symbol": "DIXON"})
    assert r["metrics"]["ebitda"]["cur"] == 145 and r["metrics"]["revenue"]["yoy_pct"] == 25.0
    b = E.results_snapshot({"url": "http://x2", "symbol": "HDFCBANK"})
    assert b["metrics"]["ebitda"]["cur"] is None
    llm.MOCK = None
