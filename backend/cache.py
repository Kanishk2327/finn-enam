import os, json, time, hashlib, pathlib

D = pathlib.Path(os.getenv("FINN_CACHE", ".cache"))
D.mkdir(exist_ok=True)


def key(*parts):
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()


def get(k, ttl=None):
    p = D / f"{k}.json"
    if not p.exists():
        return None
    try:
        o = json.loads(p.read_text())
    except Exception:
        return None
    if ttl and time.time() - o["t"] > ttl:
        return None
    return o["v"]


def put(k, v):
    (D / f"{k}.json").write_text(json.dumps({"t": time.time(), "v": v}))
    return v
