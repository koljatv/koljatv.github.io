#!/usr/bin/env python3
"""Hand fixes to catalog/titles.json (the same as editing the JSON line on GitHub's web editor).

  python3 tools/fix.py ID --url URL [--dur SECONDS]   put a new copy first (its length is probed when not given)
  python3 tools/fix.py ID --drop URL                   remove a dead copy
  python3 tools/fix.py ID --off | --on                 pull a title from the air (kept on record) or put it back

Then commit and push: the workflow rebuilds schedule.json within a minute or two.
"""
import argparse, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TP = os.path.join(ROOT, "catalog", "titles.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--url")
    ap.add_argument("--dur", type=int)
    ap.add_argument("--drop")
    ap.add_argument("--off", action="store_true")
    ap.add_argument("--on", action="store_true")
    a = ap.parse_args()
    titles = json.load(open(TP, encoding="utf-8"))
    t = next((t for t in titles if t["id"] == a.id), None)
    if not t: sys.exit("no title " + a.id)
    if a.url:
        d = a.dur
        if not d:
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.url],
                               capture_output=True, text=True, timeout=120)
            d = int(float(r.stdout.strip() or 0))
        if not d: sys.exit("couldn't read the copy's length: pass --dur")
        t["sources"] = [{"url": a.url, "dur": d}] + [s for s in t["sources"] if s["url"] != a.url]
        print("%s: new first copy, %d s (the slot stays %d s)" % (a.id, d, t["dur"]))
    if a.drop:
        t["sources"] = [s for s in t["sources"] if s["url"] != a.drop]
    if a.off: t["off"] = True
    if a.on: t.pop("off", None)
    with open(TP, "w", encoding="utf-8") as f: json.dump(titles, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
