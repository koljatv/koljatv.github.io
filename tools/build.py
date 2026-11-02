#!/usr/bin/env python3
"""Builds KÖLJA TV's schedule: public/grade/schedule.json (the next few days, item by item) and public/grade/now.json.

The layout of a day comes from the date alone (block by block, each filled from its own shelf of titles with our
vignettes, idents and trailers in the gaps), so it is the same every time it is built. Then state/health.json is
applied: a title none of whose copies answers is swapped, in its slot, for a playable one of the same block that
fits (the longest first), and the station card covers what is left. Copies that failed go to the back of their
title's list. Last, every feature with break points (catalog/breaks.json, from tools/breaks.py) is cut into parts
with a commercial break of our own pieces between them (tools/segments.py): its slot was laid out as its running
time plus its breaks, so the rest of the day doesn't move. The app only shows what this file says.

  python3 tools/build.py [--ours URL] [--out DIR] [--now EPOCH_SECONDS] [--days N]
"""
import argparse, datetime as dt, hashlib, json, os, sys, zlib
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proprios, segments, tempo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN = 60_000
WEEK = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # grade.json "week" keys, date.weekday() order
DAY = 86_400_000


def load(p, default=None):
    p = os.path.join(ROOT, p)
    if not os.path.exists(p): return default
    with open(p, encoding="utf-8") as f: return json.load(f)


class Prog:
    def __init__(self, id, kind, dur, block=None, **kw):
        self.id, self.kind, self.dur, self.block = id, kind, int(round(dur * 1000)), block
        self.span = self.dur  # its slot: the running time, plus its commercial breaks when it has them
        self.__dict__.update(kw)

    def ours(self): return self.kind not in ("film", "short", "cartoon", "tv")


NONE = Prog("-", "none", 0)


def family(p):
    """superman, popeye, chaplin...; an episode's family is its series (bonanza-s1e19 -> bonanza)."""
    return p.id.rsplit("-s", 1)[0] if p.kind == "tv" else p.id.split("-")[0]


def interleave(progs):
    """Round-robin across families, each in a fixed shuffle; episodes and chapters stay in their own order, so the
    series take turns (Bonanza 1, Dragnet 1, Buscapé 1, Bonanza 2...) like a matinee running several serials."""
    fam = {}
    for p in sorted(progs, key=lambda p: (p.id, 0) if p.kind == "tv" else ("", zlib.crc32(p.id.encode()))):
        fam.setdefault(family(p), []).append(p)
    groups = sorted(fam.values(), key=lambda g: (-len(g), g[0].id))
    out = []
    while any(groups):
        for g in groups:
            if g: out.append(g.pop(0))
    return out


def cleared(t, today):
    """What grade.json's commercial_mode allows on the air: a title's "rights" (us, br)."""
    r = t.get("rights") or {}
    us = r.get("us", False)
    br = r["br"] if "br" in r else bool(t.get("year")) and today.year >= t["year"] + 71
    return bool(us and br)


class Grade:
    def __init__(self, cfg, titles, health, measured=None, extra=None, local=False):
        self.tz = ZoneInfo(cfg.get("tz", "America/Sao_Paulo"))
        hm = lambda day: [(int(s["at"][:2]) * 60 + int(s["at"][3:]), s["block"], s.get("pin", [])) for s in day]
        self.slots = hm(cfg["day"])
        self.special = {k: hm(v) for k, v in cfg.get("special", {}).items()}
        self.week = {k: hm(v) for k, v in cfg.get("week", {}).items()}  # a weekday of its own ("sat": Kung Fu de Sábado)
        self.week_from = {k: dt.date.fromisoformat(v) for k, v in cfg.get("week_from", {}).items()}  # a weekday's own line-up starts on this date
        self.vignettes, self.idents, self.presents, self.trailers = {}, [], [], []
        self.card = None
        for o in cfg["ours"]:
            p = Prog(o["id"], o["kind"], o["dur"], o.get("block"))
            {"vignette": lambda: self.vignettes.__setitem__(p.block, p), "ident": lambda: self.idents.append(p),
             "presents": lambda: self.presents.append(p), "trailer": lambda: self.trailers.append(p),
             "card": lambda: setattr(self, "card", p)}.get(p.kind, lambda: None)()
        self.health = health
        by = {o["id"]: Prog(o["id"], o["kind"], o["dur"], o.get("block")) for o in cfg["ours"]}
        # a block of shorts with a short break of its own every few programmes (DESENHOS: INTERVALO + VOLTAMOS)
        self.pauses = {b: (int(v.get("every", 3)), [by[i] for i in (v.get("open"), v.get("close")) if i in by])
                       for b, v in (cfg.get("block_breaks") or {}).items() if v.get("every")}
        self._slot = None  # [block, slot end, programmes aired in this slot]
        self.titles, self.shelves, self.fillers = {}, {}, []
        stay = set(cfg.get("stay_home", []))  # blocks whose shorts don't fill other blocks' slots (the cartoons stay in the morning)
        home = set(cfg.get("keep_home", []))  # blocks whose shorts never leave their own slots (Domingo Documental keeps its shorts for Sunday)
        self.guests, self.hosts = [], set(cfg.get("stay_home_guests", []))  # ...except, last, the slots of these blocks (the matinee)
        self.commercial = bool(cfg.get("commercial_mode"))
        self.today = dt.date.today()
        brk = segments.config(cfg)
        pc = segments.pieces(brk, [Prog(o["id"], o["kind"], o["dur"], o.get("block")) for o in cfg["ours"]]) if brk else None
        self.splits, self.cuts = {}, {}  # id -> (part lengths, break line-ups); id -> {url: that copy's cuts}
        for t in titles:
            if t.get("off") or not t.get("sources"): continue
            if self.commercial and not cleared(t, self.today): continue  # commercial mode: cleared titles only
            p = Prog(t["id"], t["kind"], t["dur"], t["block"])
            cuts, ref = segments.ref_cuts(t, measured or {}) if pc and t["kind"] in brk.get("kinds", ["film"]) else (None, None)
            if cuts:
                lens = segments.parts(p.dur, cuts)
                lines = [segments.lineup(pc, p.id, j) for j in range(len(lens) - 1)]
                if len(lens) > 1 and all(lines):
                    self.splits[p.id] = (lens, lines)
                    self.cuts[p.id] = segments.copy_cuts(t, measured, cuts, ref)
                    p.span = p.dur + sum(x.dur for l in lines for x in l)
            self.titles[p.id] = p
            self.shelves.setdefault(p.block, []).append(p)
            if p.dur <= 25 * MIN and p.kind != "tv" and p.id not in self.splits and p.block not in home:  # never an episode out of its order
                (self.guests if p.block in stay else self.fillers).append(p)  # a "stay_home" block's shorts only close the guests' slots
        for b, l in self.shelves.items():  # families take turns (no 4 Supermen in a row), episodes in order
            l.sort(key=lambda p: p.id)
            l[:] = interleave(l)
        self.fillers = interleave(self.fillers)
        self.guests = interleave(self.guests)
        self.raw = {t["id"]: t for t in titles}
        self.brk = brk
        self.own = proprios.Own(self, extra, Prog, local)  # our programmes, a date's edits, the ads (Estúdio KÖLJA TV)
        self.tempo = tempo.Tempo(self, Prog, [] if local else None)  # the weather forecast's airings (tools/tempo.py)
        self.raw.update(self.own.raw())
        self._ban, self._pos = set(), {}
        # Each block plays its shelf like a tape, and the fillers have a tape of their own. The tapes are wound
        # from day to day starting at the epoch, so every title of a block airs once before the first rerun, none
        # is skipped (a title that doesn't fit opens the block's next slot), and a date always gets the same layout.
        self.epoch = (dt.date.fromisoformat(cfg.get("epoch", "2026-10-31")) - dt.date(1970, 1, 1)).days
        self._at = None  # (day, {block: tape index}, [filler tape index]) at the start of that day
        self.daily = {}  # each block's average air time a day (tools/rotation.py); "a|b" alternates blocks by day
        for wd in WEEK:
            slots = self.week.get(wd, self.slots)
            for s, (m, b, _) in enumerate(slots):
                end = slots[s + 1][0] if s + 1 < len(slots) else 1440
                for x in b.split("|"): self.daily[x] = self.daily.get(x, 0) + (end - m) * MIN / len(b.split("|")) / 7

    # ---- the clock ----
    def midnight(self, d):
        day = dt.date(1970, 1, 1) + dt.timedelta(days=d)
        return int(dt.datetime(day.year, day.month, day.day, tzinfo=self.tz).timestamp() * 1000)

    def day_of(self, t):
        return (dt.datetime.fromtimestamp(t / 1000, self.tz).date() - dt.date(1970, 1, 1)).days

    # ---- one day ----
    def build(self, d):
        """Day d, with the tapes wound forward from the epoch (a few milliseconds a day)."""
        start = min(d, self.epoch)
        if self._at is None or self._at[0] > d or self._at[0] < start: self._at = (start, {}, [len(self.fillers) // 2, len(self.guests) // 2])
        while self._at[0] < d: self._day(self._at[0])
        return self._day(d)

    def _day(self, d):
        day, pos, fpos = self._at
        pos, fpos = dict(pos), list(fpos)
        out, today = [], set()
        base, end = self.midnight(d), self.midnight(d + 1)
        date = dt.date(1970, 1, 1) + dt.timedelta(days=d)
        wd = WEEK[date.weekday()]
        own = self.week.get(wd) if date >= self.week_from.get(wd, dt.date.min) else None
        slots = self.special.get(date.strftime("%m-%d")) or own or self.slots  # a date of its own (Halloween...), then a weekday
        segs = []
        for s, (m, block, pin) in enumerate(slots):
            opts = block.split("|")
            block = opts[d % len(opts)]  # "faroeste|aventura": faroeste on even days, aventura on odd
            frm = base + m * MIN
            to = base + slots[s + 1][0] * MIN if s + 1 < len(slots) else end
            segs.append([frm, to, block, pin, s])
        self._ban, self._pos = self.own.banned(d), pos
        self.tempo.slots[d] = []
        for frm, to, block, pin, s in self.own.plan(d, segs):  # our programmes and the date's inserts cut in
            if block is None: self.own.air(out, [frm, to, block, pin, s])
            else:
                r = self.tempo.reserve(d, frm, to, block)  # the forecast's time, from tempo.FROM on
                self.fill(out, frm, to - r, block, (d * 7 + s * 3) % 1000, pin, pos, fpos, today)
                if r: self.tempo.pad(out, to - r, to, block)
        self._ban = set()
        self._at = (d + 1, pos, fpos)
        return out

    def intro(self, gap): return self.presents[gap % len(self.presents)] if self.presents else NONE

    def outro(self, gap):
        n = self.idents[gap % len(self.idents)].dur if self.idents else 0
        if self.trailers and gap % 2: n += self.trailers[(gap // 2) % len(self.trailers)].dur
        return n

    def air(self, out, t, p, block, gap):
        i = self.intro(gap)
        if i.dur: out.append([t, t + i.dur, i, block]); t += i.dur
        out.append([t, t + p.span, p, block]); t += p.span
        if self.idents:
            x = self.idents[gap % len(self.idents)]; out.append([t, t + x.dur, x, block]); t += x.dur
        if self.trailers and gap % 2:
            x = self.trailers[(gap // 2) % len(self.trailers)]; out.append([t, t + x.dur, x, block]); t += x.dur
        sl = self._slot
        if sl and sl[0] == block and block in self.pauses:
            sl[2] += 1
            every, pcs = self.pauses[block]
            n = sum(x.dur for x in pcs)
            if pcs and sl[2] % every == 0 and t + n <= sl[1] - 4 * MIN:  # not right before the slot ends
                for x in pcs: out.append([t, t + x.dur, x, block]); t += x.dur
        return t

    LOOK = 8  # how far down its tape a block may look for a title that fits the end of a slot

    def fill(self, out, frm, to, block, gaps, pin, pos, fpos, today):
        """One slot: the block's vignette, a special night's pinned titles, then the block's tape from where it
        stopped. When the next title doesn't fit, the longest of the next few that does airs instead; it is marked
        as aired ahead and passed over when the tape gets to it, so nothing is skipped or shown twice in a lap.
        The next title that doesn't fit opens the block's next slot. Fillers from their own tape close the slot."""
        t = frm
        self._slot = [block, to, 0]
        v = self.vignettes.get(block)
        if v and t + v.dur <= to: out.append([t, t + v.dur, v, block]); t += v.dur
        room = to - t
        pinned = [self.titles[i] for i in pin if i in self.titles and i not in self._ban]  # a special night's own line-up, in order
        for p in pinned:
            if t + self.intro(gaps).dur + p.span + self.outro(gaps) <= to:
                t = self.air(out, t, p, block, gaps); gaps += 1; today.add(p.id)
        shelf = self.shelves.get(block, [])
        n = len(shelf)
        if n:
            i, ahead = pos.get(block, (0, frozenset()))
            i, ahead = i % n, set(ahead)
            need = lambda p: self.intro(gaps).dur + p.span + self.outro(gaps)
            here = set()  # aired in this slot: a small shelf (Kung Fu de Sábado) must not come round twice in one slot
            for _ in range(2 * n):
                p = shelf[i]
                if p.id in here and p.id not in ahead: break  # the tape came round
                if p.id in ahead or p in pinned or need(p) > room:  # aired ahead, aired tonight, or longer than the slot
                    ahead.discard(p.id); i = (i + 1) % n
                    continue
                if t + need(p) <= to and p.id not in self._ban:  # a title taken off this date keeps its turn for the next
                    t = self.air(out, t, p, block, gaps); gaps += 1; today.add(p.id); here.add(p.id)
                    i = (i + 1) % n
                    continue
                fits, waiting = [], {family(p)} if p.kind == "tv" else set()
                for m in range(1, min(self.LOOK, n - 1) + 1):  # never an episode before an earlier one of its series
                    q = shelf[(i + m) % n]
                    if q.id in ahead or q in pinned or q.id in here or q.id in self._ban: continue
                    if q.kind == "tv" and family(q) in waiting: continue
                    if t + need(q) <= to: fits.append(q)
                    if q.kind == "tv": waiting.add(family(q))  # only a series' next episode may be picked
                if not fits: break
                q = max(fits, key=lambda q: q.span)
                t = self.air(out, t, q, block, gaps); gaps += 1; today.add(q.id); here.add(q.id)
                ahead.add(q.id)
            pos[block] = (i, frozenset(ahead))
        nf = len(self.fillers)  # shorts of the other blocks, on their own tape, never twice in a day
        j = fpos[0] % nf if nf else 0
        for k in range(nf):
            if to - t < 4 * MIN: break
            p = self.fillers[(j + k) % nf]
            if p.block == block or p.id in today or p.id in self._ban or t + self.intro(gaps).dur + p.span + self.outro(gaps) > to: continue
            t = self.air(out, t, p, block, gaps); gaps += 1; today.add(p.id)
            fpos[0] = (j + k + 1) % nf
        ng = len(self.guests) if block in self.hosts else 0  # then the morning's cartoons, on their own tape, for the matinee
        j = fpos[1] % ng if ng else 0
        for k in range(ng):
            if to - t < 4 * MIN: break
            p = self.guests[(j + k) % ng]
            if p.block == block or p.id in today or p.id in self._ban or t + self.intro(gaps).dur + p.span + self.outro(gaps) > to: continue
            t = self.air(out, t, p, block, gaps); gaps += 1; today.add(p.id)
            fpos[1] = (j + k + 1) % ng
        if t < to and self.card: out.append([t, to, self.card, block])
        self._slot = None

    def items(self, d):
        """Day d as it goes on the air: laid out, stand-ins for dead titles, features cut by their breaks, the spots."""
        day, sw = self.patch(self.build(d))
        return self.own.place_ads(self.tempo.place(segments.expand(day, self.splits), d), d, self.brk), sw

    # ---- health ----
    def bad(self, url):
        h = self.health.get(url)
        return bool(h and not h.get("ok", True))

    def playable(self, pid):
        t = self.raw.get(pid)
        return bool(t) and any(not self.bad(s["url"]) for s in t["sources"])

    def substitute(self, block, room, skip):
        best = None
        for p in self.shelves.get(block, []):
            if p.span <= room and p.id not in skip and self.playable(p.id) and (best is None or p.span > best.span): best = p
        if best and best.span > room / 2: return best
        short = None
        for p in self.fillers:
            if p.span > room or p.id in skip or not self.playable(p.id): continue
            r = (DAY if p.block == block else 0) + p.span
            if short is None or r > (DAY if short.block == block else 0) + short.span: short = p
        return best or short

    def patch(self, items):
        """A programme nothing of which answers: stand-ins of its block for its slot, then the card."""
        out, swaps = [], []
        for it in items:
            p = it[2]
            if p.ours() or self.playable(p.id):
                out.append(it); continue
            t, end, skip = it[0], it[1], {p.id}
            while end - t > 2 * MIN:
                s = self.substitute(it[3], end - t, skip)
                if not s: break
                out.append([t, t + s.span, s, it[3]]); t += s.span; skip.add(s.id)
                swaps.append((p.id, s.id, it[0]))
            if t < end and self.card: out.append([t, end, self.card, it[3]])
        return out, swaps


def sources(t, g):
    good = [s for s in t["sources"] if not g.bad(s["url"])]
    return good + [s for s in t["sources"] if g.bad(s["url"])]  # the broken ones stay at the back, for a retry


def lay(cfg, titles, health, measured, now, days):
    """The days from today's: (grade, items, stand-ins). Features are cut into parts and breaks when cfg has them on."""
    g = Grade(cfg, titles, health, measured, proprios.load_extra(load))
    d0 = g.day_of(now)
    items, swaps = [], []
    for d in range(d0, d0 + days):
        day, sw = g.items(d)
        items += day; swaps += sw
    return g, items, swaps


def schedule(g, items, cfg, titles, base, fmt):
    """schedule.json's content for these items: format 1 (no breaks, what Retrotv 0.3.0 reads) or 2 (with them)."""
    used = {i[2].id for i in items}
    ours = {}
    for o in cfg["ours"]:
        if o["id"] in used or o["kind"] == "card":
            ours[o["id"]] = {k: v for k, v in o.items() if k not in ("id", "file")} | {"url": base + o["file"]}
    for o in g.own.ours:  # our programmes' vignettes and the spots: each carries its own address
        if o["id"] in used: ours[o["id"]] = {k: v for k, v in o.items() if k != "id"}
    if g.tempo.prog.id in used: ours[g.tempo.prog.id] = g.tempo.ours()  # the weather forecast: a video on the site itself
    tl = {}
    for t in titles:
        if t.get("off") or t["id"] not in g.titles: continue  # every title on air, so the app can find stand-ins too
        cuts = g.cuts.get(t["id"]) if fmt >= 2 else None
        tl[t["id"]] = {"title": t["title"], "year": t.get("year", 0), "country": t.get("country", ""), "block": t["block"],
                       "kind": t["kind"], "dur": t["dur"], "synopsis": t.get("synopsis_pt", ""),
                       "sources": [dict({"url": s["url"], "dur": s["dur"]}, **({"cuts": cuts[s["url"]]} if cuts else {}))
                                   for s in sources(t, g)]}
    tl.update({k: v for k, v in g.own.titles.items() if k in used})  # our programmes' episodes on the air
    body = {"blocks": cfg["blocks"] | g.own.blocks, "ours": ours, "titles": tl,
            **({"dayparts": cfg["dayparts"]} if cfg.get("dayparts") else {}),
            "items": [[i[0], i[1], i[2].id, i[3]] + (i[4:] if fmt >= 2 else []) for i in items]}
    rev = hashlib.sha1(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    note = "KÖLJA TV. Times are milliseconds since 1970 (UTC). items: [start, end, id, block]; id is a key of titles or ours."
    if fmt >= 2:
        note = ("KÖLJA TV. Times are milliseconds since 1970 (UTC). items: [start, end, id, block(, part)]; id is a key of titles or "
                "ours. part: a feature's part number (0, 1...) or -1 for a piece of its commercial break; a split title's copies "
                "carry cuts, where in that copy's file each later part starts (ms).")
    return {"format": fmt, "rev": rev, "tz": cfg.get("tz"), "from": items[0][0], "to": items[-1][1], "note": note, **body}


def write(out, name, sched):
    """Writes out/name when its rev changed; returns the rev it had before."""
    sp = os.path.join(out, name)
    old = json.load(open(sp, encoding="utf-8")).get("rev") if os.path.exists(sp) else None
    if old != sched["rev"]:
        with open(sp, "w", encoding="utf-8") as f: json.dump(sched, f, ensure_ascii=False, separators=(",", ":"))
    return old


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ours", help="where our pieces are served (default: grade.json's ours_base, the GitHub release)")
    ap.add_argument("--out", default=os.path.join(ROOT, "public", "grade"))
    ap.add_argument("--now", type=float)
    ap.add_argument("--days", type=int, help="how many days (default: grade.json's days); the APK's seed copy uses 7")
    a = ap.parse_args()
    cfg = load("catalog/grade.json")
    titles = load("catalog/titles.json", [])
    health = load("state/health.json", {})
    measured = load("catalog/breaks.json", {})
    base = (a.ours or cfg["ours_base"]).rstrip("/") + "/"
    now = int((a.now or dt.datetime.now(dt.timezone.utc).timestamp()) * 1000)
    days = a.days or int(cfg.get("days", 3))
    # schedule2.json: the grade (format 2, features with their commercial breaks), what Retrotv 0.3.1+ plays.
    # schedule.json: the same shelves laid out without breaks (format 1), so Retrotv 0.3.0 sets keep working.
    g, items, swaps = lay(cfg, titles, health, measured, now, days)
    g1, items1, _ = lay(dict(cfg, breaks=dict(cfg.get("breaks") or {}, on=False)), titles, health, measured, now, days)
    s2, s1 = schedule(g, items, cfg, titles, base, 2), schedule(g1, items1, cfg, titles, base, 1)
    os.makedirs(a.out, exist_ok=True)
    old = write(a.out, "schedule2.json", s2)
    write(a.out, "schedule.json", s1)
    rev, ours = s2["rev"], s2["ours"]
    cur = next((k for k, i in enumerate(items) if i[0] <= now < i[1]), 0)
    while cur > 0 and len(items[cur]) > 4 and (items[cur][4] == -1 or items[cur][4] > 0): cur -= 1  # in a feature: from its first part
    nxt = []
    for k, i in enumerate(items[cur:], cur):
        if len(nxt) >= 8: break
        if len(i) > 4 and i[4] != 0: continue  # a later part or a break: part of the feature already listed
        if len(i) > 4:  # a feature's first part: the entry runs to the end of its last
            e = k
            while e + 1 < len(items) and len(items[e + 1]) > 4 and (items[e + 1][4] == -1 or items[e + 1][4] > 0 and items[e + 1][2] is i[2]): e += 1
            i = [i[0], items[e][1], i[2], i[3]]
        p = i[2]
        name = p.__dict__.get("title") or (g.raw.get(p.id, {}).get("title") if not p.ours() else ours.get(p.id, {}).get("title", p.id))
        nxt.append({"start": i[0], "end": i[1], "id": p.id, "block": i[3], "title": name, "programme": not p.ours()})
    nowj = {"format": 1, "rev": s1["rev"], "generated": now, "schedule": "schedule.json",
            "rev2": rev, "schedule2": "schedule2.json",  # 0.3.1+: the grade with commercial breaks
            "on_air": dict(nxt[0], offset=now - nxt[0]["start"]) if nxt else None, "next": nxt[1:],
            "stand_ins": [{"was": w, "now": s, "slot": at} for w, s, at in swaps if at + DAY > now][:30]}
    with open(os.path.join(a.out, "now.json"), "w", encoding="utf-8") as f: json.dump(nowj, f, ensure_ascii=False, indent=1)
    print("rev %s%s (without breaks: %s), %d items, %d titles, %d features with breaks, %d stand-ins; on air: %s" % (
        rev, "" if old != rev else " (unchanged)", s1["rev"], len(items), len(s2["titles"]), len(g.splits), len(swaps),
        nxt[0]["id"] if nxt else "-"))


if __name__ == "__main__":
    sys.exit(main())
