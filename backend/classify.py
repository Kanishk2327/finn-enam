"""Rule-first classifier. Zero LLM cost for the bulk of filings."""
import re
from .config import PRIORITY

# order matters: first match wins
RULES = [
    ("earnings_call", r"conference call|earnings call|concall|call transcript|audio recording|transcript of"),
    ("investor_meetings", r"investor meet|institutional investor|analyst.{0,20}meet|investor conference|schedule of (analyst|investor)"),
    ("results", r"financial results|quarterly results|results for the (quarter|year|half)|investor presentation|earnings (presentation|release)|results.{0,20}(newspaper|publication)|board meeting.{0,60}results"),
    ("postal_ballot", r"postal ballot"),
    ("agm_egm", r"\bagm\b|\begm\b|annual general meeting|extraordinary general meeting|e-?voting"),
    ("pledging", r"pledge|invocation|encumbrance"),
    ("insider_trading", r"insider trading|regulation 7\(2\)|sast|trading by (promoter|designated)|disposal.{0,20}shares by promoter"),
    ("management_change", r"resign|cessation|appoint(ment)? of (a )?(ceo|cfo|md|managing director|whole.?time|chief|independent director|director|additional director|key managerial)|change in (directors|key managerial|management)|retire|re-?designat"),
    ("M&A", r"acqui(re|sition)|merger|amalgamation|demerger|scheme of arrangement|joint venture|\bjv\b|subsidiary.{0,30}(incorporat|invest|stake)|sale of (stake|shares) in|divest"),
    ("fund_raise", r"rights issue|qip|qualified institutional|preferential (issue|allot)|buy-?back|commercial paper|non-convertible|ncd|fund.?raising|raising of funds"),
    ("litigation", r"litigation|court|tribunal|nclt|show.?cause|penalty|fine imposed|sebi order|insolvency|search and seizure|enforcement|gst demand|tax demand"),
    ("credit_rating", r"credit rating|crisil|icra|care ratings|india ratings|rating (action|assigned|reaffirm|upgrade|downgrade)"),
    ("dividend", r"dividend|record date.{0,40}dividend"),
    ("bonus_split", r"bonus (issue|shares)|stock split|sub-?division of (equity )?shares"),
    ("capex", r"capex|capital expenditure|new (plant|facility|unit)|capacity expansion|greenfield|brownfield|commission(ing)? of"),
    ("unclassified", r"esop|esos|employee stock|compliance certificate|regulation 74|trading window|share certificate|auditor|secretarial|voting results|scrutini[sz]er|\besg\b|brsr|reg(ulation)? 40|investor grievance|shareholding pattern"),
    ("press_release", r"press release|media release|order|contract|partnership|launch|clarification|collaborat|inaugurat"),
]
BUMP = re.compile(r"resign|downgrad|default|fraud|penalt|search and seizure|forensic|qualified opinion|fire at|shutdown", re.I)
ORDER_WIN = re.compile(r"(order|contract)s?.{0,40}(worth|valued|of rs|₹|crore|cr\b)|bagged|secures|wins", re.I)


def classify(headline, text=""):
    blob = f"{headline} {text}".lower()
    cat = "unclassified"
    for name, pat in RULES:
        if re.search(pat, blob):
            cat = name
            break
    pr = PRIORITY[cat]
    if cat == "press_release" and ORDER_WIN.search(blob):
        pr = 2
    if BUMP.search(blob):
        pr = 1
    if cat == "credit_rating" and not re.search(r"downgrad|negative|withdraw", blob):
        pr = 3
    return cat, pr
