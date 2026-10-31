#!/usr/bin/env python3
"""Abertura and encerramento of one of our programmes, in the channel's own style (tools/make_idents.py: frames
drawn with PIL, music synthesised with numpy, nothing third-party). Needs a python with PIL + numpy.

  python3 estudio/vinheta.py OUT_DIR PROG_ID "Nome do programa" [--quando "SEG A SEX · 20H"] [--estilo ambar]

Writes OUT_DIR/prog_<id>_abertura.mp4 (6 s) and OUT_DIR/prog_<id>_encerramento.mp4 (5 s), 640x360 25 fps, and
prints their lengths as JSON.
"""
import argparse, json, math, os, sys, zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
_argv, sys.argv = sys.argv, sys.argv[:1]  # make_idents reads its out dir from argv when imported
import make_idents as mi  # noqa: E402
sys.argv = _argv
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

W, H = mi.W, mi.H
ESTILOS = {  # fundo, cor do nome, cor de destaque, cor das faixas
    "ambar": ((18, 14, 10), mi.CREAM, mi.AMBER, (70, 46, 10)),
    "noite": ((10, 16, 34), (230, 236, 250), (110, 180, 255), (26, 44, 90)),
    "vermelho": ((30, 6, 8), (250, 232, 220), (255, 90, 70), (90, 16, 18)),
    "verde": ((8, 24, 16), (230, 246, 230), (120, 230, 140), (20, 70, 40)),
    "roxo": ((22, 10, 32), (244, 232, 250), (210, 140, 255), (60, 26, 90)),
    "creme": ((236, 226, 204), (34, 26, 18), (190, 90, 20), (210, 190, 150)),
}


def fit(d, text, maxw, sizes=(64, 56, 48, 42, 36, 30)):
    """The largest size the name fits in one line, else two lines."""
    for s in sizes:
        f = mi.F_FUT(s)
        if d.textlength(text, font=f) + len(text) * 4 <= maxw: return [text], f
    words = text.split()
    best = None
    for k in range(1, len(words)):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        w = max(len(a), len(b))
        if best is None or w < best[0]: best = (w, a, b)
    lines = [best[1], best[2]] if best else [text]
    for s in sizes:
        f = mi.F_FUT(s)
        if all(d.textlength(l, font=f) + len(l) * 4 <= maxw for l in lines): return lines, f
    return lines, mi.F_FUT(26)


def make(out, pid, nome, quando="", estilo="ambar"):
    bg, fg, acc, band = ESTILOS.get(estilo, ESTILOS["ambar"])
    nome = nome.upper()
    seed = zlib.crc32(nome.encode())
    melody = [72 + [0, 2, 4, 5, 7, 9, 11, 12][(seed >> (3 * i)) % 8] for i in range(5)]  # its own little tune

    def name(d, t, t0, y, alpha=1.0):
        lines, f = fit(d, nome, W - 90)
        gap = f.size + 8
        y0 = y - gap * (len(lines) - 1) / 2
        a = mi.ease((t - t0) / 0.6) * alpha
        if a < 0.01: return
        for k, l in enumerate(lines):
            mi.tracked(d, (W / 2, y0 + k * gap), l, f, fg + (int(255 * a),), track=4)

    def abertura(t):
        img = mi.canvas(bg)
        d = ImageDraw.Draw(img, "RGBA")
        for k in range(7):  # bands sweep across, then settle as a frame for the name
            x = (t * 260 + k * 120) % (W + 240) - 120
            d.polygon([(x, 0), (x + 60, 0), (x - 60, H), (x - 120, H)], fill=band + (120,))
        open_ = mi.ease((t - 0.3) / 0.9)
        d.rectangle([0, H / 2 - 92 * open_, W, H / 2 + 92 * open_], fill=bg + (230,))
        d.line([60, H / 2 - 92 * open_, W - 60, H / 2 - 92 * open_], fill=acc + (255,), width=3)
        d.line([60, H / 2 + 92 * open_, W - 60, H / 2 + 92 * open_], fill=acc + (255,), width=3)
        a = mi.ease((t - 0.6) / 0.4) * (1 - mi.ease((t - 1.9) / 0.3))
        if a > 0.01:  # (PIL draws text given alpha 0 as opaque)
            mi.tracked(d, (W / 2, H / 2 - 8), "KÖLJA TV APRESENTA", mi.F_DIN(28), acc + (int(255 * a),), track=8)
        if t > 2.0:
            name(d, t, 2.0, H / 2 - 6)
        if t > 5.3:
            d.rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * mi.ease((t - 5.3) / 0.7))))
        mi.logo(img, W - 92, H - 26, 0.28, 0.8)
        return mi.tube(img, t, 8)

    def encerramento(t):
        img = mi.canvas(bg)
        d = ImageDraw.Draw(img, "RGBA")
        g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        r = 120 + 30 * math.sin(t * 1.6)
        ImageDraw.Draw(g).ellipse([W / 2 - r * 1.8, H / 2 - r, W / 2 + r * 1.8, H / 2 + r], fill=band + (255,))
        img.alpha_composite(g.filter(ImageFilter.GaussianBlur(50)))
        fade = 1 - mi.ease((t - 4.2) / 0.5)
        name(d, t, 0.2, H / 2 - 40, fade)
        if quando and t > 0.8 and fade > 0.01:
            mi.tracked(d, (W / 2, H / 2 + 36), quando.upper(), mi.F_DIN(30), acc + (int(255 * mi.ease((t - 0.8) / 0.5) * fade),), track=8)
        mi.logo(img, W / 2, H / 2 + 100, 0.5, mi.ease((t - 1.2) / 0.5) * fade)
        if t > 4.5:
            d.rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * mi.ease((t - 4.5) / 0.5))))
        return mi.tube(img, t, 8)

    def a_abertura(dur):
        parts = [(2.0 + i * 0.22, mi.bell(mi.N(m), 1.2, 0.6, 0.22)) for i, m in enumerate(melody)]
        parts += [(2.0, mi.tone(mi.N(melody[0] - 24), 2.4, "sine", 0.12, 0.05, 1.4))]
        return mi.mix(dur, (0.0, mi.noise(0.5, 0.04)), *parts, *mi.chime(0.6, 0.22))

    def a_encerramento(dur):
        parts = [(0.3 + i * 0.3, mi.bell(mi.N(m), 1.2, 0.6, 0.2)) for i, m in enumerate(melody[::-1][:3])]
        return mi.mix(dur, *parts, *mi.chime(1.4, 0.3))

    mi.OUT = out
    os.makedirs(out, exist_ok=True)
    res = {}
    for k, dur, draw, aud in (("abertura", 6.0, abertura, a_abertura), ("encerramento", 5.0, encerramento, a_encerramento)):
        mi.render("prog_%s_%s" % (pid, k), dur, draw, aud(dur))
        res[k] = {"file": "prog_%s_%s.mp4" % (pid, k), "dur": dur}
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("id"); ap.add_argument("nome")
    ap.add_argument("--quando", default=""); ap.add_argument("--estilo", default="ambar")
    a = ap.parse_args()
    _stdout, sys.stdout = sys.stdout, sys.stderr  # render() prints its own lines: keep stdout for the JSON
    r = make(a.out, a.id, a.nome, a.quando, a.estilo)
    sys.stdout = _stdout
    print(json.dumps(r))
