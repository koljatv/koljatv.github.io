#!/usr/bin/env python3
"""KÖLJA TV's PREVISÃO DO TEMPO segment: a 72-second video drawn from state/tempo/previsao.json (tools/tempo.py).

The opening, Brazil with the main cities, the five regions with all their capitals (two days each, with the chance
of rain), Brazil for the next day, and the closing with the time of the forecast. Frames are drawn with PIL in the
station's look (the site's colours and fonts, tools/meteo/), the music bed is our own (tools/meteo/trilha.py), and
ffmpeg puts them together. Also writes the weather icons the site's page uses.

  python3 tools/tempo_video.py [--out FILE] [--icons DIR] [--still SECONDS ...]
"""
import argparse, datetime as dt, json, math, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tempo
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1280, 720, 25
HERE = os.path.dirname(os.path.abspath(__file__))
M = os.path.join(HERE, "meteo")
BG, S1, S2, S3 = (11, 10, 9), (19, 17, 16), (27, 24, 21), (36, 32, 28)
FG, FG2, FG3 = (244, 234, 214), (207, 197, 179), (148, 139, 125)
AMBER, AMBER2, RAIN = (255, 176, 0), (255, 198, 64), (120, 186, 255)
LINE, LINE2 = (38, 35, 32), (64, 60, 54)  # the site's --line and --line2 on the dark ground

_fonts = {}


def font(name, size):
    k = (name, size)
    if k not in _fonts: _fonts[k] = ImageFont.truetype(os.path.join(M, "fonts", name + ".ttf"), size)
    return _fonts[k]


COND = lambda s: font("barlowc-700", s)
COND6 = lambda s: font("barlowc-600", s)
SANS = lambda s: font("jost-500", s)
SANSB = lambda s: font("jost-700", s)

DOW = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
DOW3 = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]
MES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def day_long(d):
    return "%s, %s de %s" % (DOW[d.weekday()], "1º" if d.day == 1 else d.day, MES[d.month - 1])


def day_short(d): return "%s %d/%02d" % (DOW3[d.weekday()], d.day, d.month)


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


# ---------------- icons ----------------

_icons = {}


def _cloud(d, ox, oy, s, fill):
    """A cloud with a flat bottom, in a box of size s at (ox, oy)."""
    for cx, cy, r in ((0.30, 0.62, 0.17), (0.50, 0.47, 0.23), (0.71, 0.60, 0.16)):
        d.ellipse([ox + (cx - r) * s, oy + (cy - r) * s, ox + (cx + r) * s, oy + (cy + r) * s], fill=fill)
    d.rounded_rectangle([ox + 0.20 * s, oy + 0.55 * s, ox + 0.84 * s, oy + 0.78 * s], radius=0.11 * s, fill=fill)


def _sun(d, cx, cy, r, rays=True):
    if rays:
        for k in range(8):
            a = k * math.pi / 4
            x0, y0 = cx + math.cos(a) * r * 1.45, cy + math.sin(a) * r * 1.45
            x1, y1 = cx + math.cos(a) * r * 1.95, cy + math.sin(a) * r * 1.95
            d.line([x0, y0, x1, y1], fill=AMBER, width=max(2, int(r * 0.32)))
            for x, y in ((x0, y0), (x1, y1)):
                w = r * 0.16
                d.ellipse([x - w, y - w, x + w, y + w], fill=AMBER)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=AMBER)


def _drops(d, s, n, oy, color=RAIN, dots=False):
    xs = [0.36, 0.52, 0.68][:n] if n == 3 else [0.42, 0.62]
    for x in xs:
        if dots:
            for k in range(2):
                w = 0.035 * s
                cx, cy = (x - 0.03 * k) * s, (oy + 0.09 * k) * s
                d.ellipse([cx - w, cy - w, cx + w, cy + w], fill=color)
        else:
            d.line([x * s, oy * s, (x - 0.07) * s, (oy + 0.16) * s], fill=color, width=max(2, int(0.055 * s)))


def icon(name, size):
    """A weather icon (RGBA), drawn 4x and scaled down."""
    k = (name, size)
    if k in _icons: return _icons[k]
    s = size * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if name == "sol":
        _sun(d, s * 0.5, s * 0.5, s * 0.2)
    elif name == "sol-nuvens":
        _sun(d, s * 0.38, s * 0.36, s * 0.15)
        _cloud(d, s * 0.08, s * 0.14, s * 0.9, FG)
    elif name == "nublado":
        _cloud(d, s * 0.16, s * -0.04, s * 0.78, FG3)
        _cloud(d, 0, s * 0.12, s * 0.92, FG2)
    elif name in ("chuva", "garoa", "pancadas", "trovoada"):
        if name == "pancadas": _sun(d, s * 0.36, s * 0.26, s * 0.13)
        _cloud(d, s * 0.02, s * -0.10, s * 0.96, FG3 if name == "trovoada" else (FG if name == "pancadas" else FG2))
        if name == "trovoada":
            b = [(0.55, 0.60), (0.40, 0.80), (0.50, 0.80), (0.42, 0.98), (0.66, 0.72), (0.55, 0.72), (0.63, 0.60)]
            d.polygon([(x * s, y * s) for x, y in b], fill=AMBER2)
            _drops(d, s, 2, 0.68)
        else:
            _drops(d, s, 3, 0.72, dots=name == "garoa")
    elif name == "nevoeiro":
        _cloud(d, s * 0.04, s * -0.12, s * 0.92, FG3)
        for k, y in enumerate((0.62, 0.74, 0.86)):
            d.rounded_rectangle([s * (0.14 + 0.06 * k), s * y, s * (0.86 - 0.04 * k), s * (y + 0.06)], radius=s * 0.03, fill=FG2)
    elif name == "neve":
        _cloud(d, s * 0.02, s * -0.10, s * 0.96, FG2)
        for x in (0.34, 0.52, 0.70):
            cx, cy, r = x * s, 0.82 * s, 0.06 * s
            for a in range(3):
                t = a * math.pi / 3
                d.line([cx - math.cos(t) * r, cy - math.sin(t) * r, cx + math.cos(t) * r, cy + math.sin(t) * r], fill=FG, width=int(0.025 * s))
    else:
        _cloud(d, 0, 0, s, FG2)
    out = im.resize((size, size), Image.LANCZOS)
    _icons[k] = out
    return out


def drop(size, color=RAIN):
    s = size * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([s * 0.2, s * 0.38, s * 0.8, s * 0.98], fill=color)
    d.polygon([(s * 0.5, 0), (s * 0.24, s * 0.56), (s * 0.76, s * 0.56)], fill=color)
    return im.resize((size, size), Image.LANCZOS)


# ---------------- the map ----------------

BR = json.load(open(os.path.join(M, "brasil.json")))["uf"]
UF_REGION = {"AM": "N", "PA": "N", "RO": "N", "AC": "N", "RR": "N", "AP": "N", "TO": "N",
             "MA": "NE", "PI": "NE", "CE": "NE", "RN": "NE", "PB": "NE", "PE": "NE", "AL": "NE", "SE": "NE", "BA": "NE",
             "DF": "CO", "GO": "CO", "MT": "CO", "MS": "CO", "SP": "SE", "RJ": "SE", "MG": "SE", "ES": "SE",
             "PR": "S", "SC": "S", "RS": "S"}
K = math.cos(math.radians(15))  # equirectangular, true to scale at 15° S


class Proj:
    def __init__(self, ufs, box, pad=0.04):
        xs = [x for u in ufs for r in BR[u] for x, _ in r]
        ys = [y for u in ufs for r in BR[u] for _, y in r]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        bw, bh = (x1 - x0) * K, (y1 - y0)
        bx0, by0, bx1, by1 = box
        sc = min((bx1 - bx0) / bw, (by1 - by0) / bh) * (1 - pad * 2)
        self.sc, self.x0, self.y1 = sc, x0, y1
        self.ox = bx0 + ((bx1 - bx0) - bw * sc) / 2
        self.oy = by0 + ((by1 - by0) - bh * sc) / 2

    def __call__(self, lon, lat):
        return self.ox + (lon - self.x0) * K * self.sc, self.oy + (self.y1 - lat) * self.sc


def draw_map(img, proj, hi=None, alpha=1.0, ss=2, clip=None):
    """Brazil's states: the region `hi` lit, the rest dim, inside `clip` (a box) when given. Drawn 2x for smooth edges."""
    lay = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for u, rings in BR.items():
        lit = hi in (None, "*") or UF_REGION[u] == hi
        fill = (52, 45, 36, 255) if (hi and lit) else ((36, 32, 28, 255) if lit else (24, 21, 19, 255))
        for r in rings:
            d.polygon([(proj(x, y)[0] * ss, proj(x, y)[1] * ss) for x, y in r], fill=fill)
    for u, rings in BR.items():
        lit = hi in (None, "*") or UF_REGION[u] == hi
        col = (255, 176, 0, 120) if (hi and lit) else ((244, 234, 214, 60) if lit else (244, 234, 214, 26))
        if hi == "*": col = (255, 176, 0, 90)
        for r in rings:
            d.line([(proj(x, y)[0] * ss, proj(x, y)[1] * ss) for x, y in r] + [(proj(*r[0])[0] * ss, proj(*r[0])[1] * ss)], fill=col, width=ss)
    lay = lay.resize((W, H), Image.LANCZOS)
    if alpha < 1: lay.putalpha(lay.getchannel("A").point(lambda v: int(v * alpha)))
    if clip:
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).rounded_rectangle(clip, radius=14, fill=255)
        lay.putalpha(Image.composite(lay.getchannel("A"), m, m))
    img.alpha_composite(lay)


# ---------------- the frame ----------------

LOGO = Image.open(os.path.join(M, "logo.png")).convert("RGBA")
LOGO = LOGO.crop(LOGO.getbbox())


def logo(h):
    return LOGO.resize((int(LOGO.width * h / LOGO.height), h), Image.LANCZOS)


def text(d, xy, s, f, fill, anchor="la", spacing=0):
    if spacing:
        x, y = xy
        if anchor[0] == "r": x -= sum(f.getlength(c) + spacing for c in s) - spacing
        for c in s:
            d.text((x, y), c, font=f, fill=fill, anchor="l" + anchor[1]); x += f.getlength(c) + spacing
    else:
        d.text(xy, s, font=f, fill=fill, anchor=anchor)


def frame_base(title, sub, stamp):
    """The ground every scene shares: header with the logo and the scene's name, footer with the forecast's time."""
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))  # a faint warm light from the top
    dg = ImageDraw.Draw(glow)
    for y in range(0, 520):
        dg.line([(0, y), (W, y)], fill=(255, 176, 0, int(12 * (1 - y / 520))))
    img.alpha_composite(glow)
    lg = logo(30)
    img.alpha_composite(lg, (56, 40))
    x = 56 + lg.width + 22
    d.line([(x, 38), (x, 72)], fill=LINE2, width=2)
    text(d, (x + 22, 56), "PREVISÃO DO TEMPO", COND(30), AMBER, "lm", spacing=2)
    text(d, (W - 56, 50), title, COND(34), FG, "rm", spacing=1)
    if sub: text(d, (W - 56, 80), sub, SANS(17), FG3, "rm")
    d.line([(56, 98), (W - 56, 98)], fill=LINE, width=1)
    d.line([(56, 668), (W - 56, 668)], fill=LINE, width=1)
    text(d, (56, 690), stamp, SANS(17), FG3, "lm")
    text(d, (W - 56, 690), "tv.kolja.com.br/tempo", COND6(20), FG3, "rm", spacing=1)
    return img


class Scene:
    def __init__(self, dur, base, sprites=(), fade=0.5):
        self.dur, self.base, self.sprites, self.fade = dur, base, list(sprites), fade  # sprite: (img, x, y, t)

    def render(self, tau, cache):
        """The scene at tau seconds; sprites rise and fade in at their time."""
        key = id(self)
        st = cache.get(key)
        if st is None: st = cache[key] = [self.base.copy(), set()]
        settled, done = st
        img = None
        for i, (sp, x, y, t) in enumerate(self.sprites):
            if i in done: continue
            a = ease((tau - t) / 0.4)
            if a >= 1:
                settled.alpha_composite(sp, (int(x), int(y))); done.add(i); continue
            if a <= 0: continue
            if img is None: img = settled.copy()
            s = sp.copy()
            s.putalpha(s.getchannel("A").point(lambda v: int(v * a)))
            img.alpha_composite(s, (int(x), int(y + (1 - a) * 16)))
        return img if img is not None else settled


def chip(c, day, d0):
    """A city on the national map: name, icon, max and min."""
    e = next((x for x in c["dias"] if x["data"] == day.isoformat()), None)
    w, h = 158, 66
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=10, fill=(19, 17, 16, 236), outline=(244, 234, 214, 40))
    text(d, (10, 13), c["nome"].upper(), COND6(17), FG2, "lm", spacing=1)
    if e:
        im.alpha_composite(icon(e["icone"], 40), (6, 23))
        text(d, (54, 45), "%d°" % e["max"], COND(31), AMBER, "lm")
        text(d, (106, 47), "%d°" % e["min"], COND6(24), FG3, "lm")
    else:
        text(d, (54, 45), "—", COND(28), FG3, "lm")
    return im


# the national map: chips in a column each side of the map (west and east, north to south), and the middle on the map
WEST = ["boa-vista", "manaus", "porto-velho", "cuiaba", "campo-grande", "curitiba", "porto-alegre"]
EAST = ["sao-luis", "fortaleza", "recife", "salvador", "belo-horizonte", "rio-de-janeiro", "sao-paulo"]
MID = {"belem": (-79, -96), "palmas": (-79, -84), "brasilia": (-79, 18)}  # chip's top-left from the dot


def national(P, day, stamp):
    base = frame_base("BRASIL", day_long(day), stamp)
    proj = Proj(list(BR), (330, 108, 950, 662), pad=0.02)
    draw_map(base, proj)
    lines = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lines)
    by = {c["id"]: c for c in P["cidades"]}
    sprites, place = [], {}
    for col, x0 in ((WEST, 150), (EAST, W - 150 - 158)):
        top, step = 116, (650 - 116 - 66) / (len(col) - 1)
        for i, cid in enumerate(col): place[cid] = (x0, top + i * step)
    for cid, (dx, dy) in MID.items():
        x, y = proj(by[cid]["lon"], by[cid]["lat"]); place[cid] = (x + dx, y + dy)
    order = sorted(place, key=lambda c: (-by[c]["lat"], by[c]["lon"]))  # north to south, as a weatherman reads it
    for k, cid in enumerate(order):
        c = by[cid]
        x, y = proj(c["lon"], c["lat"])
        cx, cy = place[cid]
        ch = chip(c, day, None)
        ends = {"w": (cx + 158, cy + 40), "e": (cx, cy + 40)}.get("w" if cid in WEST else "e" if cid in EAST else "", None)
        x0, y0 = int(min(cx, x)) - 6, int(min(cy, y)) - 6
        sp = Image.new("RGBA", (int(max(cx + 158, x)) - x0 + 7, int(max(cy + 66, y)) - y0 + 7), (0, 0, 0, 0))
        ds = ImageDraw.Draw(sp)
        if ends: ds.line([(ends[0] - x0, ends[1] - y0), (x - x0, y - y0)], fill=(255, 176, 0, 130), width=1)
        sp.alpha_composite(ch, (int(cx) - x0, int(cy) - y0))
        sprites.append((sp, x0, y0, 0.5 + k * 0.17))
    for cid in place:
        x, y = proj(by[cid]["lon"], by[cid]["lat"])
        d.ellipse([x - 4.5, y - 4.5, x + 4.5, y + 4.5], fill=AMBER, outline=BG + (255,))
    base.alpha_composite(lines)
    return base, sprites


def region(P, rid, rname, days, stamp):
    base = frame_base(rname.upper(), "%s e %s" % (day_long(days[0]).split(",")[0], day_long(days[1]).split(",")[0].lower()), stamp)
    ufs = [u for u, r in UF_REGION.items() if r == rid]
    box = (56, 112, 560, 650)
    ImageDraw.Draw(base).rounded_rectangle(box, radius=14, fill=S1)
    proj = Proj(ufs, box, pad=0.07)
    draw_map(base, proj, hi=rid, clip=box)
    d = ImageDraw.Draw(base)
    d.rounded_rectangle(box, radius=14, outline=LINE)
    cities = sorted([c for c in P["cidades"] if c["regiao"] == rid], key=lambda c: (-c["lat"], c["lon"]))
    taken = []  # the names' boxes, so no two overlap
    for c in cities:
        x, y = proj(c["lon"], c["lat"])
        if not (box[0] < x < box[2] and box[1] < y < box[3]): continue
        taken.append((x - 6, y - 6, x + 6, y + 6))
    for c in cities:
        x, y = proj(c["lon"], c["lat"])
        if not (box[0] < x < box[2] and box[1] < y < box[3]): continue
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=AMBER, outline=BG, width=2)
        w = SANS(15).getlength(c["nome"])
        tries = [("lm", x + 10, y), ("rm", x - 10, y), ("lm", x + 6, y - 15), ("lm", x + 6, y + 15), ("rm", x - 6, y - 15), ("rm", x - 6, y + 15)]
        for anc, tx, ty in tries:
            r = (tx, ty - 9, tx + w, ty + 9) if anc == "lm" else (tx - w, ty - 9, tx, ty + 9)
            inside = r[0] > box[0] + 6 and r[2] < box[2] - 6
            if inside and not any(r[0] < q[2] and q[0] < r[2] and r[1] < q[3] and q[1] < r[3] for q in taken): break
        taken.append(r)
        text(d, (tx, ty), c["nome"], SANS(15), FG2, anc)
    # the table: city | day 1 | day 2
    X0, X1 = 600, W - 56
    cols = [X0 + 226, X0 + 226 + 198]
    n = len(cities)
    rh = min(62, (640 - 132 - 36) // max(1, n))
    hl = n <= 5  # a short table: the day's highlights under it
    top = 132 if not hl else int(132 + max(0, (640 - 132 - 26 - n * rh - 150) / 2 - 10))
    for j, dd in enumerate(days):
        text(d, (cols[j] + 4, top), day_short(dd), COND(24), AMBER if j == 0 else FG2, "lm", spacing=1)
    text(d, (X0 + 16, top), "CAPITAL", COND6(18), FG3, "lm", spacing=2)
    sprites = []
    for i, c in enumerate(cities):
        y0 = top + 26 + i * rh
        row = Image.new("RGBA", (X1 - X0, rh), (0, 0, 0, 0))
        r = ImageDraw.Draw(row)
        if i % 2 == 0: r.rounded_rectangle([0, 2, X1 - X0 - 1, rh - 3], radius=8, fill=(244, 234, 214, 9))
        cy = rh // 2
        text(r, (16, cy - 7), c["nome"], SANSB(22 if rh >= 50 else 20), FG, "lm")
        text(r, (16, cy + 15), c["uf"], COND6(15), FG3, "lm", spacing=2)
        for j, dd in enumerate(days):
            e = next((x for x in c["dias"] if x["data"] == dd.isoformat()), None)
            x = cols[j] - X0
            if not e:
                text(r, (x + 50, cy), "—", COND(26), FG3, "lm"); continue
            isz = min(44, rh - 8)
            row.alpha_composite(icon(e["icone"], isz), (x, cy - isz // 2))
            text(r, (x + isz + 8, cy), "%d°" % e["max"], COND(30), AMBER if j == 0 else FG, "lm")
            text(r, (x + isz + 56, cy + 1), "%d°" % e["min"], COND6(23), FG3, "lm")
            if e.get("chuva") is not None:
                row.alpha_composite(drop(13, RAIN if e["chuva"] >= 30 else FG3), (x + isz + 98, cy - 8))
                text(r, (x + isz + 114, cy + 1), "%d%%" % e["chuva"], COND6(19), RAIN if e["chuva"] >= 30 else FG3, "lm")
        sprites.append((row, X0, y0, 0.45 + i * 0.16))
    if hl:
        sprites.append((highlights(cities, days[0], X1 - X0), X0, top + 26 + n * rh + 24, 0.45 + n * 0.16 + 0.5))
    return base, sprites


def highlights(cities, day, width):
    """Three tiles: the hottest afternoon, the coolest night and the likeliest rain of the region that day."""
    es = [(c, next((x for x in c["dias"] if x["data"] == day.isoformat()), None)) for c in cities]
    es = [(c, e) for c, e in es if e]
    im = Image.new("RGBA", (width, 118), (0, 0, 0, 0))
    if not es: return im
    d = ImageDraw.Draw(im)
    hot = max(es, key=lambda ce: ce[1]["max"])
    cool = min(es, key=lambda ce: ce[1]["min"])
    wet = max(es, key=lambda ce: ce[1].get("chuva") or 0)
    tiles = [("MÁXIMA MAIS ALTA", hot[0]["nome"], "%d°" % hot[1]["max"], AMBER),
             ("MÍNIMA MAIS BAIXA", cool[0]["nome"], "%d°" % cool[1]["min"], FG),
             ("MAIS CHANCE DE CHUVA", wet[0]["nome"], "%d%%" % (wet[1].get("chuva") or 0), RAIN)]
    tw = (width - 2 * 14) // 3
    for k, (lab, name, val, col) in enumerate(tiles):
        x = k * (tw + 14)
        d.rounded_rectangle([x, 0, x + tw, 117], radius=10, fill=(27, 24, 21, 255), outline=(244, 234, 214, 30))
        text(d, (x + 14, 22), lab, COND6(16), FG3, "lm")
        text(d, (x + 14, 64), val, COND(42), col, "lm")
        text(d, (x + 14, 98), name, SANS(17), FG2, "lm")
    return im


def opener(day, stamp):
    img = Image.new("RGBA", (W, H), BG + (255,))
    proj = Proj(list(BR), (640, 40, 1260, 700), pad=0.02)
    draw_map(img, proj, hi="*")
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))  # fade the map into the dark at its left
    ds = ImageDraw.Draw(sh)
    for x in range(640, 900):
        ds.line([(x, 0), (x, H)], fill=BG + (int(255 * (1 - (x - 640) / 260)),))
    img.alpha_composite(sh)
    d = ImageDraw.Draw(img)
    lg = logo(52)
    sprites = [(lg, 96, 214, 0.15)]
    t = Image.new("RGBA", (760, 120), (0, 0, 0, 0))
    text(ImageDraw.Draw(t), (0, 60), "PREVISÃO DO TEMPO", COND(96), AMBER, "lm", spacing=3)
    sprites.append((t, 90, 282, 0.45))
    s = Image.new("RGBA", (760, 60), (0, 0, 0, 0))
    text(ImageDraw.Draw(s), (2, 30), day_long(day), SANS(32), FG, "lm")
    sprites.append((s, 94, 404, 0.8))
    s2 = Image.new("RGBA", (760, 40), (0, 0, 0, 0))
    text(ImageDraw.Draw(s2), (2, 20), "As capitais de todo o Brasil", SANS(22), FG3, "lm")
    sprites.append((s2, 94, 452, 1.05))
    return img, sprites


def closing(P, when, stamp):
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    sprites = []
    lg = logo(64)
    sprites.append((lg, (W - lg.width) // 2, 196, 0.1))
    lines = [("Previsão atualizada às %s de %s" % (when.strftime("%H:%M"), when.strftime("%d/%m")), SANS(30), FG, 312),
             ("horário de Brasília", SANS(22), FG3, 352),
             ("Dados: Open-Meteo.com", COND6(24), FG2, 420),
             ("A previsão completa em tv.kolja.com.br/tempo", SANS(22), AMBER, 470)]
    for k, (s, f, col, y) in enumerate(lines):
        t = Image.new("RGBA", (W, 50), (0, 0, 0, 0))
        text(ImageDraw.Draw(t), (W // 2, 25), s, f, col, "mm")
        sprites.append((t, 0, y - 25, 0.35 + k * 0.25))
    return img, sprites


def scenes(P):
    when = dt.datetime.fromtimestamp(P["gerado"] / 1000, tempo.TZ)
    today = when.date()
    first = today + dt.timedelta(days=1) if when.hour >= 17 else today  # in the evening: tomorrow and the day after
    days = [first, first + dt.timedelta(days=1)]
    stamp = "Previsão Open-Meteo.com · atualizada às %s de %s (horário de Brasília)" % (when.strftime("%H:%M"), when.strftime("%d/%m"))
    out = [Scene(4.0, *opener(first, stamp), fade=0.0)]
    out.append(Scene(10.0, *national(P, days[0], stamp)))
    for (rid, name), dur in zip(tempo.REGIONS, (9.0, 11.0, 8.0, 8.0, 7.0)):
        out.append(Scene(dur, *region(P, rid, name, days, stamp)))
    out.append(Scene(9.0, *national(P, days[1], stamp)))
    out.append(Scene(tempo.DUR - sum(s.dur for s in out), *closing(P, when, stamp)))
    return out


def frames(sc):
    """(rgb bytes) for every frame: each scene fades in over the one before."""
    cache, prev = {}, None
    n = int(round(tempo.DUR * FPS))
    starts, acc = [], 0.0
    for s in sc: starts.append(acc); acc += s.dur
    k = 0
    for f in range(n):
        t = f / FPS
        while k + 1 < len(sc) and t >= starts[k + 1]: k += 1
        s = sc[k]
        tau = t - starts[k]
        img = s.render(tau, cache)
        if k > 0 and tau < s.fade:
            last = sc[k - 1].render(sc[k - 1].dur, cache)
            img = Image.blend(last, img, ease(tau / s.fade))
        if t > tempo.DUR - 0.6:  # out to black
            img = Image.blend(img, Image.new("RGBA", (W, H), (0, 0, 0, 255)), (t - (tempo.DUR - 0.6)) / 0.6)
        yield img


def render(P, out):
    tmp = out + ".part.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", os.path.join(M, "trilha.m4a"), "-map", "0:v", "-map", "1:a", "-t", str(tempo.DUR),
           "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p", "-g", "50", "-profile:v", "main",
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for img in frames(scenes(P)): p.stdin.write(img.convert("RGB").tobytes())
    p.stdin.close()
    if p.wait() != 0: raise SystemExit("ffmpeg failed")
    os.replace(tmp, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(tempo.STATE, "previsao.json"))
    ap.add_argument("--out", default=os.path.join(tempo.STATE, tempo.ID + ".mp4"))
    ap.add_argument("--icons", help="write the site's icons (PNG) here and stop")
    ap.add_argument("--still", type=float, nargs="*", help="write PNG stills at these seconds (next to --out) and stop")
    a = ap.parse_args()
    if a.icons:
        os.makedirs(a.icons, exist_ok=True)
        for n in ("sol", "sol-nuvens", "nublado", "nevoeiro", "garoa", "chuva", "pancadas", "trovoada", "neve"):
            icon(n, 128).save(os.path.join(a.icons, n + ".png"), optimize=True)
        return
    P = json.load(open(a.data, encoding="utf-8"))
    if a.still is not None:
        want = {int(round(s * FPS)): s for s in a.still}
        for f, img in enumerate(frames(scenes(P))):
            if f in want: img.convert("RGB").save(os.path.splitext(a.out)[0] + "-%05.1f.png" % want[f])
            if f > max(want): break
        return
    render(P, a.out)
    tempo.rendered(P["gerado"])
    print("rendered", a.out, "from the forecast of", P.get("gerado_brt"))


if __name__ == "__main__":
    main()
