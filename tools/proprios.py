"""KÖLJA TV's own material on top of the block layout, as the Estúdio KÖLJA TV app writes it:

- catalog/programas.json: our own programmes. Each has recurring slots ("seg-sex 20:00"), its own opening and
  closing vignette, and episodes (GitHub Release assets or other hosted files). "substituir" airs the newest
  episode at every slot; "playlist" plays them in turn, one per slot, from the programme's first date.
- catalog/grade_manual.json: one-off edits of a date: "inserir" puts a title (or an extra showing of a programme)
  at a time, "remover" takes a title (or a programme's showing) off that date. A removed title stays at the head of
  its block's tape, so it airs the next day instead.
- catalog/anuncios.json: paid spots. An active campaign gets its insertions a day (anywhere, or so many per block)
  in the commercial breaks of the features, spread over the day, between its "inicio" and "fim" dates (then it drops
  out by itself). The spot takes the place of our own pieces in that break; when it is longer than they are, the
  break grows and the rest of the slot takes the time from the station card that closes the slot, so the next slot
  still starts on time. A spot never airs twice in one break nor in two breaks in a row.

A date with none of these is laid out exactly as before (build.py's slot numbers don't move).
"""
import datetime as dt

MIN = 60_000


def load_extra(load):
    """The three files, through build.py's load()."""
    return {"programas": (load("catalog/programas.json", {}) or {}).get("programas", []),
            "manual": load("catalog/grade_manual.json", {}) or {},
            "anuncios": (load("catalog/anuncios.json", {}) or {}).get("anuncios", [])}


def hm(s):
    return int(s[:2]) * 60 + int(s[3:5])


def iso(d):
    return (dt.date(1970, 1, 1) + dt.timedelta(days=d)).isoformat()


def day_no(s):
    return (dt.date.fromisoformat(s) - dt.date(1970, 1, 1)).days


def media(x, local):
    """A piece's address: its published URL, or (in the Estúdio's preview) a local stand-in."""
    if x.get("url"): return x["url"]
    return "local:" + x.get("file", "") if local and x.get("file") else None


class Own:
    """What build.py's Grade needs to know about our programmes, the date edits and the ads."""

    def __init__(self, g, extra, Prog, local=False):
        extra = extra or {}
        self.g, self.local = g, local
        self.progs, self.ours, self.titles, self.blocks, self.ads = {}, [], {}, {}, []
        for pr in extra.get("programas", []):
            if pr.get("ativo") is False: continue
            blk = "prog-" + pr["id"]
            eps = []
            for e in pr.get("episodios", []):
                u = media(e, local)
                if not u or not e.get("dur"): continue
                p = Prog("prog_%s_%s" % (pr["id"], e["id"]), "tv", e["dur"], blk,
                         title="%s · %s" % (pr["nome"], e.get("titulo") or e["id"]))
                eps.append(p)
                self.titles[p.id] = {"title": p.title, "year": int((e.get("enviado") or "0")[:4] or 0), "country": "BR",
                                     "block": blk, "kind": "tv", "dur": e["dur"], "synopsis": pr.get("descricao", ""),
                                     "sources": [{"url": u, "dur": e["dur"]}]}
            if not eps: continue
            vin = {}
            for k, kind in (("abertura", "vignette"), ("encerramento", "closing")):
                v = pr.get(k) or {}
                u = media(v, local)
                if u and v.get("dur"):
                    vin[k] = Prog("prog_%s_%s" % (pr["id"], k), kind, v["dur"], blk)
                    self.ours.append({"id": vin[k].id, "kind": kind, "block": blk, "dur": v["dur"],
                                      "title": "%s · %s" % (pr["nome"], k), "url": u})
            self.blocks[blk] = {"pt": pr["nome"].upper(), "en": pr["nome"]}
            self.progs[pr["id"]] = dict(pr, _eps=eps, _vin=vin, _blk=blk)
        for a in extra.get("anuncios", []):
            u = media(a, local)
            if a.get("ativo") is False or not u or not a.get("dur"): continue
            p = Prog("ad_" + a["id"], "ad", a["dur"], None, title=a.get("nome", a["id"]))
            self.ads.append((a, p))
            self.ours.append({"id": p.id, "kind": "ad", "dur": a["dur"], "title": a.get("nome", a["id"]), "url": u})
        self.ads.sort(key=lambda x: x[0]["id"])
        m = extra.get("manual") or {}
        self.inserts, self.removes = {}, {}
        for x in m.get("inserir", []):
            self.inserts.setdefault(x["data"], []).append(x)
        for x in m.get("remover", []):
            self.removes.setdefault(x["data"], []).append(x)

    def raw(self):
        """Episodes as build.py's raw titles, so the health check and the stand-ins treat them like any title."""
        return {k: {"sources": v["sources"]} for k, v in self.titles.items()}

    # ---- programmes ----
    def _slots(self, pr, d):
        """The programme's start minutes on day d (0 = Monday)."""
        if pr.get("desde") and d < day_no(pr["desde"]): return []
        if pr.get("ate") and d > day_no(pr["ate"]): return []
        wd = (dt.date(1970, 1, 1) + dt.timedelta(days=d)).weekday()
        return sorted({hm(h["at"]) for h in pr.get("horarios", []) if wd in h.get("dias", [])})

    def episode(self, pr, d, m):
        """substituir: the newest episode. playlist: one per showing in turn, counted from the programme's first date."""
        eps = pr["_eps"]
        if pr.get("modo") != "playlist" or len(eps) == 1: return eps[-1]
        d0 = day_no(pr["desde"]) if pr.get("desde") else min(d, self.g.epoch)
        k = sum(len(self._aired(pr, x)) for x in range(d0, d)) + sum(1 for s in self._aired(pr, d) if s < m)
        return eps[k % len(eps)]

    def _aired(self, pr, d):
        """Its showings on day d that weren't taken off the date (a removed showing doesn't use up an episode)."""
        gone = [r for r in self.removes.get(iso(d), []) if r["id"] == "prog:" + pr["id"]]
        return [m for m in self._slots(pr, d) if not any(not r.get("at") or hm(r["at"]) == m for r in gone)]

    def span(self, pr, ep):
        return sum(x.dur for x in (pr["_vin"].get("abertura"), ep, pr["_vin"].get("encerramento")) if x)

    def events(self, d):
        """[start ms, end ms, what] for day d: the programmes' showings and the date's inserts. Overlaps: the first wins."""
        base, end = self.g.midnight(d), self.g.midnight(d + 1)
        date = iso(d)
        gone = self.removes.get(date, [])
        ev = []
        for pid, pr in self.progs.items():
            for m in self._slots(pr, d):
                if any(r["id"] == "prog:" + pid and (not r.get("at") or hm(r["at"]) == m) for r in gone): continue
                ep = self.episode(pr, d, m)
                ev.append([base + m * MIN, base + m * MIN + self.span(pr, ep), ("prog", pr, ep)])
        for x in self.inserts.get(date, []):
            t = base + hm(x["at"]) * MIN
            if x["id"].startswith("prog:"):
                pr = self.progs.get(x["id"][5:])
                if pr:
                    ep = self.episode(pr, d, hm(x["at"]))
                    ev.append([t, t + self.span(pr, ep), ("prog", pr, ep)])
                continue
            p = self.g.titles.get(x["id"])
            if p: ev.append([t, t + self.g.intro(0).dur + getattr(p, "span", p.dur) + self.g.outro(0), ("title", p, None)])
        ev.sort(key=lambda e: e[0])
        out = []
        for e in ev:
            if e[1] > end or out and e[0] < out[-1][1]: continue  # past midnight, or on top of another: dropped
            out.append(e)
        return out

    def banned(self, d):
        return {r["id"] for r in self.removes.get(iso(d), []) if not r["id"].startswith("prog:")}

    def plan(self, d, segs):
        """build.py's slots of a day ([from ms, to ms, block, pin, slot no]) with the day's events cut in."""
        for e in self.events(d):
            new = []
            for s in segs:
                if s[1] <= e[0] or s[0] >= e[1]:
                    new.append(s); continue
                if s[0] < e[0]: new.append([s[0], e[0]] + s[2:])
                if s[1] > e[1]: new.append([e[1], s[1], s[2], [], s[4]])  # the block goes on after it
            new.append([e[0], e[1], None, e[2], None])
            segs = sorted(new, key=lambda s: s[0])
        return segs

    def air(self, out, seg):
        frm, to, _, (what, x, ep), _ = seg
        if what == "prog":
            t = frm
            for p in (x["_vin"].get("abertura"), ep, x["_vin"].get("encerramento")):
                if p: out.append([t, t + p.dur, p, x["_blk"]]); t += p.dur
        else:
            self.g.air(out, frm, x, x.block, 0)
            if x.block in self.g.shelves:  # aired ahead: its turn on the tape is passed over
                i, ahead = self.g._pos.get(x.block, (0, frozenset()))
                self.g._pos[x.block] = (i, frozenset(ahead) | {x.id})

    # ---- ads ----
    def place_ads(self, items, d, brk):
        """Puts the day's spots in the features' breaks (items as segments.expand made them)."""
        date = iso(d)
        live = [(a, p) for a, p in self.ads if a.get("inicio", "0000") <= date <= a.get("fim", "9999")]
        if not live or not brk: return items
        breaks, k = [], 0  # [first index, last index] of each break: consecutive pieces with part -1
        while k < len(items):
            if len(items[k]) > 4 and items[k][4] == -1:
                j = k
                while j + 1 < len(items) and len(items[j + 1]) > 4 and items[j + 1][4] == -1: j += 1
                breaks.append([k, j]); k = j + 1
            else: k += 1
        if not breaks: return items
        cap = [self._room(items, b, brk) for b in breaks]
        # A spot longer than its break's room may still go in: the break grows, and the rest of the slot moves on
        # into the station card that closes the slot, which gets that much shorter (the next slot starts on time).
        card, spare = [self._spare(items, b) for b in breaks], {}
        for k in card:
            if k is not None: spare[k] = items[k][1] - items[k][0]
        def fits(i, p):
            if cap[i] >= p.dur: return True
            return card[i] is not None and spare[card[i]] - (p.dur - max(0, cap[i])) >= 0
        put = [[] for _ in breaks]
        for a, p in live:
            for blocks, n in quotas(a):
                ok = [i for i, b in enumerate(breaks) if blocks is None or items[b[0]][3] in blocks]
                for q in range(min(n, len(ok))):
                    want = int((q + 0.5) * len(ok) / n)
                    for step in range(len(ok)):  # the nearest break that still has room for it
                        for i in (want + step, want - step):
                            if not 0 <= i < len(ok): continue
                            b = ok[i]  # never the same spot twice in a break, nor in two breaks in a row
                            if p in put[b] or (b > 0 and p in put[b - 1]) or (b + 1 < len(put) and p in put[b + 1]): continue
                            if fits(b, p):
                                grow = max(0, p.dur - max(0, cap[b]))
                                if grow: spare[card[b]] -= grow
                                put[b].append(p); cap[b] -= p.dur
                                break
                        else: continue
                        break
        out, last, shift = [], 0, 0
        def moved(seg):  # pieces after a grown break, up to the slot's closing card (which absorbs the shift)
            nonlocal shift
            for it in seg:
                if shift and len(it) == 4 and it[2] is self.g.card:
                    if it[1] - (it[0] + shift) > 0: out.append([it[0] + shift] + it[1:])
                    shift = 0
                else: out.append([it[0] + shift, it[1] + shift] + it[2:])
        for i, (b, ads) in enumerate(zip(breaks, put)):
            moved(items[last:b[0]])
            seg = [[it[0] + shift, it[1] + shift] + it[2:] for it in items[b[0]:b[1] + 1]]
            if ads:
                grow = max(0, -cap[i])
                out.extend(self._rebuild(seg, ads, brk, grow)); shift += grow
            else: out.extend(seg)
            last = b[1] + 1
        moved(items[last:])
        assert shift == 0, shift
        return out

    def _spare(self, items, b):
        """Index of the station card that closes the slot a break is in (its spare time), or None."""
        block = items[b[0]][3]
        for k in range(b[1] + 1, len(items)):
            it = items[k]
            if it[3] != block: return None
            if len(it) == 4 and it[2] is self.g.card: return k
        return None

    def _room(self, items, b, brk):
        pieces = items[b[0]:b[1] + 1]
        keep = sum(it[1] - it[0] for it in pieces if it[2].id in (brk.get("open"), brk.get("close")))
        return (pieces[-1][1] - pieces[0][0]) - keep

    def _rebuild(self, pieces, ads, brk, grow=0):
        """A break with spots: the opening bumper, the spots, as many of our pieces as still fit, the closing bumper.
        grow: ms the break is made longer by (taken from the slot's closing station card)."""
        t0, t1, block = pieces[0][0], pieces[-1][1] + grow, pieces[0][3]
        head = [it[2] for it in pieces[:1] if it[2].id == brk.get("open")]
        tail = [it[2] for it in pieces[-1:] if it[2].id == brk.get("close")]
        room = (t1 - t0) - sum(p.dur for p in head + tail) - sum(p.dur for p in ads)
        mid = list(ads)
        for it in pieces[len(head):len(pieces) - len(tail)]:
            if it[2].dur <= room and it[2].id != brk.get("slot"): mid.append(it[2]); room -= it[2].dur
        out, t = [], t0
        for p in head + mid:
            out.append([t, t + p.dur, p, block, -1]); t += p.dur
        if room >= 3000 and self.g.card: out.append([t, t + room, self.g.card, block, -1]); t += room
        elif out: out[-1][1] += room; t += room
        for p in tail:
            out.append([t, t + p.dur, p, block, -1]); t += p.dur
        assert t == t1, (t, t1)
        return out


def quotas(a):
    """[(blocks or None for any, insertions a day)] of a campaign."""
    pb = a.get("por_bloco") or {}
    if pb: return [({b}, int(n)) for b, n in sorted(pb.items()) if int(n) > 0]
    return [(None, int(a.get("por_dia", 0)))] if int(a.get("por_dia", 0)) > 0 else []
