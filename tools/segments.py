"""KÖLJA TV's commercial breaks: features split into parts at the places tools/breaks.py found, with a break of our
own pieces between the parts. build.py lays out each feature as one programme whose slot is its running time plus
its breaks (span), then expand() cuts it into parts and breaks, so every set pauses and resumes at the same second.

A break is always our own material. Today (Niko, 31 Oct 2026) it is only the INTERVALO card and VOLTAMOS, about ten
seconds, no trailers, no promos, no sponsor slot. grade.json's "breaks" can bring the rest back: "slot", "promos",
"trailers": true, "idents": true, and "hold" (seconds of the station card, the room the Estúdio's spots replace).

Schedule items (format 2): [start, end, id, block] as before; a feature's part adds its number (0, 1, 2...) as a
fifth element, a piece of its break adds -1. Each copy of a split title carries "cuts": where its parts start, in
ms of that copy's own file (measured, or scaled from the measured copy when that copy wasn't).
"""
import zlib

MIN = 60_000


def config(cfg):
    """grade.json's "breaks": which pieces open, close and fill a break. None when breaks are off."""
    b = cfg.get("breaks") or {}
    return b if b.get("on") else None


def ref_cuts(t, measured):
    """(cuts in ms, the copy they were measured on) for a title, or (None, None) when it plays straight."""
    for s in t.get("sources", []):
        m = measured.get(s["url"])
        if m and not m.get("error") and m.get("cuts"):
            return list(m["cuts"]), s
    return None, None


def copy_cuts(t, measured, cuts, ref):
    """Each copy's own cuts: measured when it was, else the reference's scaled to the copy's length."""
    out = {}
    for s in t["sources"]:
        m = measured.get(s["url"])
        if m and not m.get("error") and len(m.get("cuts", [])) == len(cuts):
            out[s["url"]] = list(m["cuts"])
        else:
            k = (s.get("dur") or t["dur"]) / (ref.get("dur") or t["dur"])
            out[s["url"]] = [int(round(c * k)) for c in cuts]
    return out


def parts(dur_ms, cuts):
    """Part lengths (ms) of a programme of dur_ms cut at cuts (ms of the reference copy)."""
    edges = [0] + [c for c in cuts if 0 < c < dur_ms] + [dur_ms]
    return [b - a for a, b in zip(edges, edges[1:])]


def pieces(b, ours):
    """The pieces a break can use, by role: {"open": Prog, "close": Prog, "slot": Prog, "hold": Prog, "trailers": [...],
    "promos": [...], "idents": [...]}; only what grade.json's "breaks" asks for."""
    by = {p.id: p for p in ours}
    get = lambda k: by.get(b.get(k))
    card = next((p for p in ours if p.kind == "card"), None)
    hold = type(card)(card.id, card.kind, b["hold"], card.block) if card and b.get("hold") else None
    return {"open": get("open"), "close": get("close"), "slot": get("slot"), "hold": hold,
            "trailers": [p for p in ours if p.kind == "trailer"] if b.get("trailers") else [],
            "promos": [by[i] for i in b.get("promos", []) if i in by],
            "idents": [p for p in ours if p.kind == "ident"] if b.get("idents") else []}


def lineup(pc, title_id, j):
    """Break j of a title: INTERVALO, then what the config has of trailer, promo, trailer, ANUNCIE AQUI, trailer, promo,
    ident, the station card's hold, then VOLTAMOS. The order turns with the title and the break, so it doesn't run the
    same every time."""
    r = zlib.crc32(title_id.encode()) + j
    T, P, I = pc["trailers"], pc["promos"], pc["idents"]
    at = lambda l, k: l[k % len(l)] if l else None
    seq = [pc["open"], at(T, r), at(P, r), at(T, r + 1), pc["slot"], at(T, r + 2), at(P, r + 1), at(I, r), pc["hold"], pc["close"]]
    out, seen = [], set()
    for p in seq:  # with fewer trailers than three, none twice in one break
        if p is None or p.kind == "trailer" and p.id in seen: continue
        seen.add(p.id); out.append(p)
    return out


def expand(items, splits):
    """Cuts every split programme's slot into parts and breaks. splits: id -> (part lengths ms, [break lineups])."""
    out = []
    for it in items:
        p = it[2]
        sp = splits.get(p.id) if not p.ours() else None
        if not sp or it[1] - it[0] != p.span:
            out.append(it); continue
        lens, brks = sp
        t = it[0]
        for k, L in enumerate(lens):
            out.append([t, t + L, p, it[3], k]); t += L
            if k < len(brks):
                for x in brks[k]:
                    out.append([t, t + x.dur, x, it[3], -1]); t += x.dur
        assert t == it[1], (p.id, t, it[1])
    return out
