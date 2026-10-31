#!/usr/bin/env python3
"""How long KÖLJA TV goes without a rerun: lays out the next days with build.py's own Grade and reports, for the
whole channel and for each block, the first day on which a programme airs that already aired on an earlier day.

  python3 tools/rotation.py [--days 120] [--from YYYY-MM-DD]
"""
import argparse, datetime as dt, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--from", dest="start", help="first day (default: today, São Paulo)")
    a = ap.parse_args()
    cfg = build.load("catalog/grade.json")
    titles = build.load("catalog/titles.json", [])
    g = build.Grade(cfg, titles, {})
    d0 = g.day_of(dt.datetime.now(dt.timezone.utc).timestamp() * 1000) if not a.start else \
        (dt.date.fromisoformat(a.start) - dt.date(1970, 1, 1)).days
    seen, first_rerun, block_rerun = {}, None, {}
    plugs, plug_first, plug_rerun = {}, {}, {}
    special = set(cfg.get("special", {}))
    for k in range(a.days):
        d = d0 + k
        date = dt.date(1970, 1, 1) + dt.timedelta(days=d)
        if date.strftime("%m-%d") in special: continue  # a special night's pinned line-up repeats on purpose
        for it in g.build(d):
            p = it[2]
            if p.ours(): continue
            if it[3] != p.block:  # a short plugging a gap in another block: counted apart
                plugs[p.id] = plugs.get(p.id, 0) + 1
                plug_rerun.setdefault(p.id, k) if plugs[p.id] > 1 and plug_first.get(p.id, k) < k else None
                plug_first.setdefault(p.id, k)
                continue
            if p.id in seen and seen[p.id] < k:
                if first_rerun is None: first_rerun = (k, p.id)
                block_rerun.setdefault(it[3], (k, p.id))
            seen.setdefault(p.id, k)
    on = [t for t in titles if not t.get("off") and t.get("sources")]
    hours = sum(t["dur"] for t in on) / 3600
    print("%d titles on the shelf, %.0f hours" % (len(on), hours))
    print("first rerun of a programme in its own block on day %s (%s)" % ((first_rerun[0] + 1, first_rerun[1]) if first_rerun else (">%d" % a.days, "-")))
    per = {}
    for t in on: per.setdefault(t["block"], []).append(t["dur"])
    daily = {b: ms / 3_600_000 for b, ms in g.daily.items()}
    print("%-10s %6s %7s %8s %s" % ("block", "titles", "hours", "h/day", "days before a rerun"))
    for b in sorted(per, key=lambda b: -sum(per[b])):
        r = block_rerun.get(b)
        print("%-10s %6d %7.1f %8.1f %s" % (b, len(per[b]), sum(per[b]) / 3600, daily.get(b, 0),
                                           ("%d (%s)" % (r[0], r[1])) if r else ">%d" % a.days))
    if plug_rerun: print("gap fillers (shorts aired outside their block): %d airings; the first one aired again on day %d"
                         % (sum(plugs.values()), min(plug_rerun.values()) + 1))
    never = [t["id"] for t in on if t["id"] not in seen]
    print("never aired in %d days: %d titles%s" % (a.days, len(never), (" (" + ", ".join(never[:8]) + "...)") if never else ""))


if __name__ == "__main__":
    main()
