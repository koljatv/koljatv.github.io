#!/usr/bin/env python3
"""Writes public/tv/reserva.json: the shorts the player puts on when a programme won't start (programação alternativa).

The player falls back to a short from the same part of the day while it keeps trying the programme. A fallback has to
start fast, so only copies that answer quickly and are "faststart" (the index, moov, at the front of the file, so the
first picture comes after a few hundred KB instead of after the whole index at the end) go in. Each copy gets one
ranged GET of the first 64 KB; the top-level boxes say where moov is.

  python3 tools/reserva.py [--max 900] [--toons 120]
"""
import argparse, json, os, random, re, struct, subprocess, time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "koljatv-grade/0.1 (fallback check; stream only)"
OUT = os.path.join(ROOT, "public", "tv", "reserva.json")


def head(url):
    t0 = time.time()
    r = subprocess.run(["curl", "-fsL", "--max-filesize", "1048576", "-r", "0-65535", "-m", "20", "--connect-timeout", "8", "-A", UA, url],
                       capture_output=True)
    return (r.stdout if r.returncode == 0 else b""), time.time() - t0


def faststart(b):
    """True: moov comes before mdat. None: can't tell from the first bytes."""
    i = 0
    while i + 8 <= len(b):
        size, kind = struct.unpack(">I4s", b[i:i + 8])
        if size == 1 and i + 16 <= len(b): size = struct.unpack(">Q", b[i + 8:i + 16])[0]
        if kind == b"moov": return True
        if kind == b"mdat": return False
        if size < 8: return None
        i += size
    return None


def save_reserve(items, path=OUT):
    if not items:
        print("No verified copies: keeping the last good reserve")
        return False
    temp=path+".tmp"
    with open(temp,"w",encoding="utf-8") as f:
        json.dump({"format":1,"at":int(time.time()*1000),"items":items},f,ensure_ascii=False,separators=(",",":"))
    os.replace(temp,path)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=900, help="longest short, seconds")
    ap.add_argument("--toons", type=int, default=120, help="cartoons to check (there are hundreds)")
    ap.add_argument("--daily",action="store_true",help="skip if last verified reserve is under 24 hours old")
    ap.add_argument("--limit",type=int,default=0,help="bound network probes; 0 checks all candidates")
    a = ap.parse_args()
    if a.daily:
        try:
            old=json.load(open(OUT,encoding="utf-8"))
            if old.get("items") and 0 <= time.time()*1000-old.get("at",0) < 86400000:
                print("Last good reserve is under 24 hours old");return
        except (OSError,ValueError,TypeError):pass
    S = json.load(open(os.path.join(ROOT, "public", "grade", "schedule2.json"), encoding="utf-8"))
    shorts = {k: p for k, p in S["titles"].items() if 60 <= (p.get("dur") or 0) <= a.max
              and not re.search(r"-s\d+e\d+$", k)}  # a serial's chapter out of the blue says nothing: shorts that stand alone
    toons = [k for k, p in shorts.items() if p["block"] == "toons"]
    random.seed(7)
    keep = set(random.sample(toons, min(a.toons, len(toons)))) | {k for k, p in shorts.items() if p["block"] != "toons"}
    todo = [(k, s["url"], s.get("dur") or shorts[k]["dur"]) for k in sorted(keep) for s in shorts[k]["sources"]]

    if a.limit > 0:
        random.Random(int(time.time()//86400)).shuffle(todo)
        todo=todo[:a.limit]

    def one(x):
        k, u, d = x
        b, secs = head(u)
        return k, u, d, faststart(b) if len(b) > 30000 else None, secs

    out = {}
    with ThreadPoolExecutor(6) as ex:
        for k, u, d, fs, secs in ex.map(one, todo):
            if fs and secs < 6:
                p = shorts[k]
                e = out.setdefault(k, {"id": k, "title": p["title"], "block": p["block"], "dur": round(d), "copies": []})
                e["copies"].append(u)
    items = sorted(out.values(), key=lambda e: (e["block"], e["id"]))
    save_reserve(items)
    by = {}
    for e in items: by[e["block"]] = by.get(e["block"], 0) + 1
    print("checked %d copies of %d shorts: %d fast titles %s" % (len(todo), len(keep), len(items), by))


if __name__ == "__main__":
    main()
