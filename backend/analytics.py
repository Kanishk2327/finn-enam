"""All arithmetic happens here, never in the LLM."""


def _r(t, *names):
    if not t:
        return None
    for n in names:
        if n in t["rows"]:
            return t["rows"][n]
    return None


def pct(a, b):
    return None if a is None or not b else round((a / b - 1) * 100, 1)


def cagr(a, b, yrs):
    if a is None or not b or b <= 0 or a <= 0 or yrs <= 0:
        return None
    return round(((a / b) ** (1 / yrs) - 1) * 100, 1)


def quarters(c, n=5):
    q = c["quarterly"]
    sales = _r(q, "sales", "revenue")
    opm = _r(q, "opm %", "financing margin %")
    pat = _r(q, "net profit")
    pbt = _r(q, "profit before tax")
    out = []
    L = len(q["cols"])
    for i in range(max(0, L - n), L):
        out.append({
            "q": q["cols"][i], "sales": sales[i] if sales else None,
            "sales_yoy": pct(sales[i], sales[i - 4]) if sales and i >= 4 else None,
            "sales_qoq": pct(sales[i], sales[i - 1]) if sales and i >= 1 else None,
            "opm": opm[i] if opm else None, "pbt": pbt[i] if pbt else None,
            "pat": pat[i] if pat else None,
            "pat_yoy": pct(pat[i], pat[i - 4]) if pat and i >= 4 else None,
        })
    return out


def annual(c):
    a = c["annual"]
    yrs = a["cols"]
    sales = _r(a, "sales", "revenue")
    pat = _r(a, "net profit")
    opm = _r(a, "opm %", "financing margin %")
    n = len(yrs)
    res = {"years": yrs[-6:], "sales": (sales or [])[-6:], "pat": (pat or [])[-6:], "opm": (opm or [])[-6:]}
    if sales and n > 3:
        res["sales_cagr_3y"] = cagr(sales[-1], sales[-4], 3)
    if sales and n > 5:
        res["sales_cagr5y"] = cagr(sales[-1], sales[-6], 5)
    if pat and n > 3:
        res["pat_cagr_3y"] = cagr(pat[-1], pat[-4], 3)
    if opm and n > 3:
        res["opm_change_3y_pp"] = round(opm[-1] - opm[-4], 1)
    return res


def balance(c):
    b = c.get("balance")
    if not b:
        return {}
    eq = _r(b, "equity capital")
    res_ = _r(b, "reserves")
    debt = _r(b, "borrowings")
    out = {"years": b["cols"][-5:]}
    if debt:
        out["borrowings"] = debt[-5:]
    if eq and res_ and debt:
        out["debt_to_equity"] = [round(d / (e + r), 2) if (e or 0) + (r or 0) else None
                                 for d, e, r in zip(debt[-5:], eq[-5:], res_[-5:])]
    rt = c.get("ratios")
    if rt:
        for lab, key in [("debtor days", "debtor_days"), ("inventory days", "inventory_days"),
                         ("days payable", "payable_days"), ("cash conversion cycle", "ccc"),
                         ("roce %", "roce")]:
            if lab in rt["rows"]:
                out[key] = rt["rows"][lab][-5:]
    return out


def cash(c):
    cf = c.get("cash")
    a = c["annual"]
    if not cf:
        return {}
    cfo = _r(cf, "cash from operating activity")
    cfi = _r(cf, "cash from investing activity")
    pat = _r(a, "net profit")
    out = {"years": cf["cols"][-5:], "cfo": (cfo or [])[-5:], "cfi": (cfi or [])[-5:]}
    if cfo and pat:
        n = min(5, len(cfo), len(pat))
        out["cfo_to_pat"] = [round(x / y, 2) if y else None for x, y in zip(cfo[-n:], pat[-n:])]
        out["cum_cfo_5y"] = round(sum(x for x in cfo[-n:] if x is not None), 1)
        out["cum_pat_5y"] = round(sum(x for x in pat[-n:] if x is not None), 1)
    return out


def compute(c):
    return {"quarters": quarters(c), "annual": annual(c), "balance": balance(c), "cash": cash(c)}
