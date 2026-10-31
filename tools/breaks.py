#!/usr/bin/env python3
"""Finds where KÖLJA TV's features can go to a commercial break: catalog/breaks.json.

A feature (a film of 40 minutes or more; shorts, cartoons and TV episodes play straight) is split in parts of
about 20 to 30 minutes. Around each even split point ffmpeg watches a few minutes of the copy, straight from its
URL (ranged reads, nothing is kept), and the break goes on the best place nearby:

  1. a fade to black (the break comes at the end of the black, the film comes back with what follows it),
  2. a scene cut in a pause of the soundtrack (away from dialogue),
  3. the strongest scene cut,
  4. nothing found: the split point itself (marked "none", worth a look by hand).

Every copy of a title is measured on its own (other prints start earlier or later), so the app can resume any
of them at the same picture. breaks.json is keyed by the copy's URL, so it survives edits to titles.json; a copy
already measured is skipped unless --redo.

  python3 tools/breaks.py [--jobs 6] [--copies N] [--redo] [--only ID ...] [--limit N]
"""
import argparse, json, os, re, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, "catalog", "breaks.json")
UA = "koljatv-grade/0.1 (break finder; stream only)"
FEATURE = 40 * 60      # seconds: from here on a film gets breaks
PART = 25 * 60         # aimed part length
WIN = 75               # seconds either side of a split point that ffmpeg watches
EDGE = 10 * 60         # no break in a film's first or last ten minutes
lock = threading.Lock()


def dump(done, path=BP):
    """breaks.json, one copy per line (the raw detections make it long otherwise)."""
    rows = [json.dumps("note") + ": " + json.dumps("Where each feature copy goes to a break (ms of file time), and what ffmpeg saw "
                                                  "around each place. Made by tools/breaks.py; build.py reads it.")]
    rows += [json.dumps(u) + ": " + json.dumps(v, ensure_ascii=False, separators=(",", ":")) for u, v in sorted(done.items()) if u != "note"]
    with open(path + ".tmp", "w", encoding="utf-8") as f: f.write("{\n" + ",\n".join(rows) + "\n}\n")
    os.replace(path + ".tmp", path)


def plan(dur):
    """The even split points (seconds) for a feature of {dur} seconds: parts of about 25 minutes."""
    if dur < FEATURE: return []
    n = max(2, round(dur / PART))
    return [dur * k / n for k in range(1, n)]


def feature(t):
    return not t.get("off") and t.get("kind") == "film" and t.get("dur", 0) >= FEATURE


def probe(url):
    r = subprocess.run(["ffprobe", "-v", "error", "-user_agent", UA, "-show_entries", "stream=codec_type:format=start_time,duration",
                        "-of", "json", url], capture_output=True, text=True, timeout=120)
    j = json.loads(r.stdout or "{}")
    kinds = {s.get("codec_type") for s in j.get("streams", [])}
    f = j.get("format", {})
    return "audio" in kinds, "video" in kinds, float(f.get("start_time") or 0), float(f.get("duration") or 0)


def watch(url, t0, length, audio):
    """Scene changes, black stretches and pauses of the sound from t0 for length seconds (file time, seconds)."""
    fc = "[0:v]scale=160:-2,split[a][b];[a]select='gt(scene,0.22)',metadata=print:file=-[o1];[b]blackdetect=d=0.12:pix_th=0.11[o2]"
    maps = ["-map", "[o1]", "-f", "null", "-", "-map", "[o2]", "-f", "null", "-"]
    if audio:
        fc += ";[0:a]silencedetect=n=-34dB:d=0.25[o3]"
        maps += ["-map", "[o3]", "-f", "null", "-"]
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-user_agent", UA, "-copyts", "-ss", "%.3f" % t0, "-t", "%.3f" % length,
           "-i", url, "-filter_complex", fc] + maps
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    cuts, blacks, quiet = [], [], []
    last = None
    for line in r.stdout.splitlines():
        m = re.match(r"frame:\d+\s+pts:\d+\s+pts_time:([\d.]+)", line)
        if m: last = float(m.group(1)); continue
        m = re.match(r"lavfi\.scene_score=([\d.]+)", line)
        if m and last is not None: cuts.append((last, float(m.group(1))))
    for m in re.finditer(r"black_start:([\d.]+) black_end:([\d.]+)", r.stderr):
        blacks.append((float(m.group(1)), float(m.group(2))))
    st = None
    for m in re.finditer(r"silence_(start|end): ([\d.]+)", r.stderr):
        if m.group(1) == "start": st = float(m.group(2))
        elif st is not None: quiet.append((st, float(m.group(2)))); st = None
    if r.returncode != 0 and not cuts and not blacks:
        raise RuntimeError("ffmpeg: " + r.stderr.strip().splitlines()[-1][:200] if r.stderr.strip() else "ffmpeg failed")
    return cuts, blacks, quiet


def choose(target, cuts, blacks, quiet, audio):
    """The best break near target: (seconds, why, score)."""
    best = None

    def offer(t, why, s):
        nonlocal best
        s -= abs(t - target) / WIN * 0.8  # closer to the even split is better, but a good place wins
        if best is None or s > best[2]: best = (t, why, s)

    blacks = sorted(blacks)
    for k, (a, b) in enumerate(blacks):  # the break comes at the end of the black: the whole fade-out, then the next act
        if b - a < 0.12: continue
        nxt = blacks[k + 1][0] if k + 1 < len(blacks) else None
        # two dark stretches a blink apart are two dark cards ("End of Act I", then "Act II") whose brightest frames
        # read as not black: the joint is where the second one starts
        offer(nxt if nxt is not None and nxt - b < 0.6 else b, "black", 3.0 + min(b - a, 2.0))
    for t, sc in cuts:
        if sc < 0.3:  # a soft cut (a dim print, a dissolve): only when there's nothing better
            if sc >= 0.22: offer(t, "soft cut", sc - 0.5)
            continue
        q = any(a - 0.15 <= t <= b + 0.15 for a, b in quiet)
        offer(t, "quiet cut" if q else ("cut" if audio else "cut (silent)"), (1.6 if q else 0.0) + min(sc, 1.0))
    if best is None: return target, "none", 0.0
    return best


def measure(url, dur, fps_hint=None):
    audio, video, start, fdur = probe(url)
    if not video: raise RuntimeError("no video stream")
    dur = fdur or dur
    picks = []
    for target in plan(dur):
        target = min(max(target, EDGE), dur - EDGE)
        t0 = max(0, target - WIN)
        cuts, blacks, quiet = watch(url, t0, 2 * WIN, audio)
        t, why, s = choose(target, cuts, blacks, quiet, audio)
        seen = {"cuts": [[round(c, 3), round(sc, 2)] for c, sc in cuts if sc >= 0.22], "blacks": [[round(a, 3), round(b, 3)] for a, b in blacks],
                "quiet": [[round(a, 2), round(b, 2)] for a, b in quiet if any(a - 0.2 <= c <= b + 0.2 for c, sc in cuts if sc >= 0.22)]}
        picks.append({"t": int(round((t - start) * 1000)), "why": why, "score": round(s, 2), "aim": int(target * 1000),
                      "start": start, "seen": seen})
    picks.sort(key=lambda p: p["t"])
    return {"dur": round(dur, 2), "audio": audio, "cuts": [p["t"] for p in picks], "picks": picks,
            "at": time.strftime("%Y-%m-%d")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--copies", type=int, default=0, help="only each title's first N copies (0: all)")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--rechoose", action="store_true", help="pick again from what was seen (no download), after a rule change")
    a = ap.parse_args()
    titles = json.load(open(os.path.join(ROOT, "catalog", "titles.json"), encoding="utf-8"))
    done = json.load(open(BP, encoding="utf-8")) if os.path.exists(BP) else {}
    if a.rechoose:
        n = 0
        for u, r in done.items():
            if u == "note" or r.get("error") or not all("seen" in p for p in r.get("picks", [])): continue
            for p in r["picks"]:
                sn = p["seen"]
                t, why, sc = choose(p["aim"] / 1000, [tuple(c) for c in sn["cuts"]], [tuple(b) for b in sn["blacks"]],
                                    [tuple(q) for q in sn["quiet"]], r.get("audio", True))
                p.update(t=int(round((t - p.get("start", 0)) * 1000)), why=why, score=round(sc, 2))
            r["picks"].sort(key=lambda p: p["t"])
            r["cuts"] = [p["t"] for p in r["picks"]]
            n += 1
        dump(done)
        print("picked again for %d copies" % n)
        return
    todo = []
    for t in titles:
        if not feature(t) or a.only and t["id"] not in a.only: continue
        for k, s in enumerate(t["sources"][:a.copies] if a.copies else t["sources"]):
            if s["url"] in done and not a.redo and not done[s["url"]].get("error"): continue
            todo.append((k, t["id"], s["url"], s.get("dur", t["dur"])))
    todo.sort(key=lambda x: x[0])  # every title's first copy before anyone's second
    if a.limit: todo = todo[:a.limit]
    print("%d copies to measure" % len(todo), flush=True)

    def save(): dump(done)

    def one(job):
        k, tid, url, dur = job
        try:
            r = measure(url, dur)
        except Exception as e:
            r = {"error": str(e)[:200], "at": time.strftime("%Y-%m-%d")}
        with lock:
            done[url] = r
            save()
            print("%s [%d] %s" % (tid, k, r.get("error") or ", ".join("%d:%02d %s" % (p["t"] // 60000, p["t"] // 1000 % 60, p["why"]) for p in r["picks"])), flush=True)

    with ThreadPoolExecutor(a.jobs) as ex:
        list(ex.map(one, todo))
    save()


if __name__ == "__main__":
    sys.exit(main())
