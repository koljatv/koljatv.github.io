#!/usr/bin/env python3
"""Checks the copies of what airs soon and writes state/health.json, so build.py can route round dead links.

For every title airing in the next HOURS (default 8), each copy in turn gets a small ranged GET (64 KB, following
redirects). A copy is marked bad after failing twice in a row, and good again the
first time it answers. Titles further ahead are checked a few at a time, oldest check first, so the whole shelf
is seen at least once a day.

  python3 tools/check.py [--hours 8] [--extra 60]
"""
import argparse, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "koljatv-grade/0.1 (link check; stream only)"
HP = os.path.join(ROOT, "state", "health.json")


def probe(url):
    r = subprocess.run(["curl", "-sL", "-r", "0-65535", "-m", "25", "--connect-timeout", "10", "-A", UA, "-o", "/dev/null",
                        "-w", "%{http_code} %{content_type} %{size_download} %{time_total}", url], capture_output=True, text=True)
    p = r.stdout.split()
    if len(p) != 4: return False, "no answer"
    code, ctype, size, secs = p[0], p[1], int(float(p[2])), float(p[3])
    if code not in ("200", "206"): return False, "HTTP " + code
    if ctype.startswith("text") or "html" in ctype: return False, "not video (%s)" % ctype
    if size < 30000: return False, "too short (%d bytes)" % size
    return True, "%s %.1fs" % (code, secs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=8)
    ap.add_argument("--extra", type=int, default=60, help="titles further ahead to check per run")
    a = ap.parse_args()
    titles = {t["id"]: t for t in json.load(open(os.path.join(ROOT, "catalog", "titles.json"), encoding="utf-8")) if not t.get("off")}
    sp = os.path.join(ROOT, "public", "grade", "schedule2.json")  # the grade with breaks (schedule.json: the same without)
    if not os.path.exists(sp): sp = os.path.join(ROOT, "public", "grade", "schedule.json")
    health = json.load(open(HP)) if os.path.exists(HP) else {}
    now = time.time() * 1000
    soon = []
    if os.path.exists(sp):
        for it in json.load(open(sp, encoding="utf-8"))["items"]:  # [start, end, id, block(, part)]
            s, e, pid = it[:3]
            if e > now and s < now + a.hours * 3600_000 and pid in titles and pid not in soon: soon.append(pid)
    rest = sorted((t for t in titles if t not in soon),
                  key=lambda t: min((health.get(s["url"], {}).get("at", 0) for s in titles[t]["sources"]), default=0))
    todo = soon + rest[:a.extra]
    urls = [s["url"] for t in todo for s in titles[t]["sources"]]

    def one(u):
        ok, why = probe(u)
        if not ok:
            time.sleep(4)
            ok, why = probe(u)  # once more: hosts hiccup
        return u, ok, why

    bad = 0
    with ThreadPoolExecutor(4) as ex:
        for u, ok, why in ex.map(one, urls):
            h = health.get(u, {})
            fails = 0 if ok else h.get("fails", 0) + 1
            health[u] = {"ok": ok or fails < 2, "fails": fails, "at": int(time.time() * 1000), "why": why}
            if not health[u]["ok"]: bad += 1; print("BAD", u, why)
    known = {s["url"] for t in titles.values() for s in t["sources"]}
    health = {u: v for u, v in sorted(health.items()) if u in known}
    os.makedirs(os.path.dirname(HP), exist_ok=True)
    with open(HP, "w") as f: json.dump(health, f, indent=1)
    print("checked %d copies of %d titles (%d airing in %gh), %d bad" % (len(urls), len(todo), len(soon), a.hours, bad))


if __name__ == "__main__":
    sys.exit(main())
