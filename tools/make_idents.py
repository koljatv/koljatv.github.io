#!/usr/bin/env python3
"""KÖLJA TV's own on-air pieces: block vignettes, station idents, "apresenta", the looping station card and the
commercial break's pieces (intervalo, voltamos, "anuncie aqui", the KÖLJA Store and Retrotv promos).

Everything here is made from scratch: frames drawn with PIL, music synthesised with numpy, no third-party
footage, music or samples. Run with the ComfyUI venv python (it has PIL + numpy):

    ~/ComfyUI/.venv/bin/python3 tools/make_idents.py [out_dir] [name ...]

Writes 640x360 25 fps H.264 + AAC MP4s (faststart) to media/ours/ (uploaded as GitHub Release assets, not in git) and prints their durations for catalog/grade.json.
tecnicos.mp4 is the one piece inside the app: copy it to retrofone-spinoffs/tv/src/main/assets/koljatv/.
"""
import math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS, SR = 640, 360, 25, 44100
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'media', 'ours')
SUP = '/System/Library/Fonts/Supplemental/'
SYS = '/System/Library/Fonts/'
AMBER, CREAM = (255, 176, 0), (246, 236, 214)
rng = np.random.default_rng(7)
GRAIN = [np.random.default_rng(k).normal(0, 6, (H, W, 1)).astype(np.float32) for k in range(4)]


def font(path, size, index=0):
    return ImageFont.truetype(path, size, index=index)


F_LOGO = lambda s: font(SUP + 'Futura.ttc', s, 2)          # Futura Condensed ExtraBold-ish face of the set
F_DIN = lambda s: font(SUP + 'DIN Condensed Bold.ttf', s)
F_COPPER = lambda s: font(SUP + 'Copperplate.ttc', s, 2)
F_HORROR = lambda s: font(SUP + 'Herculanum.ttf', s)
F_TOON = lambda s: font(SUP + 'Phosphate.ttc', s, 1)
F_FUT = lambda s: font(SUP + 'Futura.ttc', s, 4)
F_DIDOT = lambda s: font(SUP + 'Didot.ttc', s, 1)
F_IMPACT = lambda s: font(SUP + 'Impact.ttf', s)


def ease(x):
    x = min(1, max(0, x))
    return x * x * (3 - 2 * x)


def back(x):  # overshoot ease for bouncy entries
    x = min(1, max(0, x))
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def tracked(d, xy, text, f, fill, track=0, anchor='mm'):
    """Draws text with letter spacing, centred on xy."""
    widths = [d.textlength(ch, font=f) for ch in text]
    total = sum(widths) + track * (len(text) - 1)
    x = xy[0] - total / 2 if anchor[0] == 'm' else xy[0]
    for ch, w in zip(text, widths):
        d.text((x, xy[1]), ch, font=f, fill=fill, anchor='l' + anchor[1])
        x += w + track
    return total


def logo(img, cx, cy, scale=1.0, alpha=1.0, color=CREAM):
    """KÖLJA wordmark with the amber TV plate, as on the set."""
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    f = F_LOGO(int(74 * scale))
    tw = tracked(d, (cx - 40 * scale, cy), 'KÖLJA', f, color + (255,), track=int(6 * scale))
    px = cx - 40 * scale + tw / 2 + 14 * scale
    d.rounded_rectangle([px, cy - 30 * scale, px + 74 * scale, cy + 30 * scale], radius=int(10 * scale), fill=AMBER + (255,))
    d.text((px + 37 * scale, cy + 2 * scale), 'TV', font=F_LOGO(int(48 * scale)), fill=(20, 16, 10, 255), anchor='mm')
    if alpha < 1:
        a = lay.split()[3].point(lambda v: int(v * alpha))
        lay.putalpha(a)
    img.alpha_composite(lay)


def tube(img, t, grain=10, lines=True):
    """Our CRT finish: scanlines, vignette and a little grain."""
    a = np.asarray(img.convert('RGB')).astype(np.float32)
    if lines:
        a[1::3] *= 0.82
    yy, xx = np.mgrid[0:H, 0:W]
    v = 1 - 0.55 * (((xx - W / 2) / (W / 1.6)) ** 2 + ((yy - H / 2) / (H / 1.3)) ** 2)
    a *= np.clip(v, 0.25, 1)[..., None]
    if grain:  # four fixed grain plates in turn: film-like, and cheap for the encoder
        a += GRAIN[int(t * FPS) % 4] * (grain / 10)
    return np.clip(a, 0, 255).astype(np.uint8)


# ---------------- sound ----------------

def env(n, a=0.01, r=0.4):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(r, 1e-4))
    return e


def bell(f, dur, r=0.9, amp=0.3):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * f * t + 2.2 * np.exp(-t * 3) * np.sin(2 * np.pi * f * 3.5 * t))
    s += 0.3 * np.sin(2 * np.pi * f * 2 * t)
    return amp * s * env(n, 0.003, r)


def pluck(f, dur, amp=0.25):  # Karplus-Strong, a honky-tonk piano-ish string
    n = int(dur * SR)
    p = max(2, int(SR / f))
    buf = rng.uniform(-1, 1, p)
    out = np.zeros(n)
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = 0.996 * 0.5 * (buf[i % p] + buf[(i + 1) % p])
    return amp * out


def tone(f, dur, kind='sine', amp=0.2, a=0.02, r=1.0, vib=0.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ph = 2 * np.pi * np.cumsum(f * (1 + vib * np.sin(2 * np.pi * 5.5 * t))) / SR
    if kind == 'saw':
        s = 2 * ((ph / (2 * np.pi)) % 1) - 1
        s = np.convolve(s, np.ones(18) / 18, mode='same')  # dull it like a muted horn
    elif kind == 'square':
        s = np.sign(np.sin(ph)) * 0.6
    else:
        s = np.sin(ph)
    return amp * s * env(n, a, r)


def noise(dur, amp=0.1, lp=1):
    n = int(dur * SR)
    s = rng.normal(0, 1, n)
    if lp > 1:
        s = np.convolve(s, np.ones(lp) / lp, mode='same')
    return amp * s


def mix(total, *parts):
    out = np.zeros(int(total * SR))
    for at, s in parts:
        i = int(at * SR)
        j = min(len(out), i + len(s))
        if j > i:
            out[i:j] += s[:j - i]
    fade = int(0.08 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    peak = np.max(np.abs(out)) or 1
    return out / peak * 0.8


N = lambda m: 440 * 2 ** ((m - 69) / 12)  # midi note to Hz
SIGNATURE = [(0.0, 79), (0.22, 76), (0.44, 84)]  # KÖL-JA-TV: G5 E5 C6, our three-note chime


def chime(at=0.0, amp=0.35, octave=0):
    return [(at + dt, bell(N(m + 12 * octave), 1.6, 0.8, amp)) for dt, m in SIGNATURE]


# ---------------- writing ----------------

def render(name, dur, draw, audio, loop=False):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + '.mp4')
    wav = path + '.wav'
    a = (np.clip(audio, -1, 1) * 32767).astype('<i2')
    import wave
    with wave.open(wav, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(a.tobytes())
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-i', wav, '-c:v', 'libx264', '-profile:v', 'main', '-preset', 'slow', '-crf', '30', '-maxrate', '1200k', '-bufsize', '2400k', '-pix_fmt', 'yuv420p',
           '-g', str(FPS * 2), '-c:a', 'aac', '-b:a', '96k', '-ar', str(SR), '-shortest', '-movflags', '+faststart', path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = int(round(dur * FPS))
    for i in range(frames):
        t = i / FPS
        p.stdin.write(draw(t).tobytes())
    p.stdin.close()
    p.wait()
    os.remove(wav)
    print(f'{name}\t{dur}')


def canvas(color):
    return Image.new('RGBA', (W, H), color + (255,))


# ---------------- the pieces ----------------

def ident_bars(t):
    """Station ID: our own colour bars fold into the KÖLJA TV mark."""
    img = canvas((12, 10, 9))
    d = ImageDraw.Draw(img, 'RGBA')
    k = ease((t - 0.6) / 1.2)
    cols = [(236, 232, 220), (236, 214, 40), (40, 214, 220), (40, 200, 60), (214, 40, 200), (220, 50, 40), (40, 50, 210)]
    bw = W / len(cols)
    for i, c in enumerate(cols):
        h = H * (1 - k)
        d.rectangle([i * bw, H / 2 - h / 2, (i + 1) * bw, H / 2 + h / 2], fill=c)
    if t > 1.4:
        logo(img, W / 2, H / 2 - 14, 1.0, ease((t - 1.4) / 0.6))
        sub = ease((t - 2.2) / 0.6)
        lay = ImageDraw.Draw(img, 'RGBA')
        tracked(lay, (W / 2, H / 2 + 52), 'CLÁSSICOS CULT · 24 HORAS', F_DIN(26), AMBER + (int(255 * sub),), track=4)
    if t > 5.2:  # fold to a line at the end
        k2 = ease((t - 5.2) / 0.5)
        d.rectangle([0, 0, W, H * k2 / 2], fill=(0, 0, 0))
        d.rectangle([0, H - H * k2 / 2, W, H], fill=(0, 0, 0))
    return tube(img, t)


def ident_tube(t):
    """Station ID: a tube warming up, line then picture, CANAL 1."""
    img = canvas((6, 8, 10))
    d = ImageDraw.Draw(img, 'RGBA')
    k = ease(t / 0.9)
    if t < 0.9:
        d.rectangle([W / 2 - W * k / 2, H / 2 - 2, W / 2 + W * k / 2, H / 2 + 2], fill=(220, 240, 255))
    else:
        g = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(g)
        r = 40 + 260 * ease((t - 0.9) / 1.6)
        gd.ellipse([W / 2 - r, H / 2 - r * 0.62, W / 2 + r, H / 2 + r * 0.62], fill=(30, 60, 70, 255))
        img.alpha_composite(g.filter(ImageFilter.GaussianBlur(40)))
        wob = 3 * math.sin(t * 9) * max(0, 1 - (t - 0.9) / 1.2)
        logo(img, W / 2 + wob, H / 2 - 10, 1.05, ease((t - 1.0) / 0.5))
        tracked(d, (W / 2, H / 2 + 56), 'CANAL 1', F_DIN(30), CREAM + (int(255 * ease((t - 1.8) / 0.5)),), track=10)
    if t > 4.5:
        k2 = ease((t - 4.5) / 0.5)
        d.rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * k2)))
    return tube(img, t, 14)


def presents(t):
    img = canvas((8, 8, 8))
    d = ImageDraw.Draw(img, 'RGBA')
    a = ease(t / 0.5) * (1 - ease((t - 3.0) / 0.5))
    logo(img, W / 2, H / 2 - 24, 0.8, a)
    tracked(d, (W / 2, H / 2 + 36), 'APRESENTA', F_DIN(30), AMBER + (int(255 * a),), track=14)
    return tube(img, t, 8)


def card(t):
    """The station card for the last minutes of a block: loops seamlessly every 30 s."""
    img = canvas((14, 22, 26))
    d = ImageDraw.Draw(img, 'RGBA')
    ang = 2 * math.pi * t / 30
    for i in range(12):  # slow ring of amber dots, one turn per loop
        a = ang + i * math.pi / 6
        x, y = W / 2 + 150 * math.cos(a), H / 2 - 18 + 100 * math.sin(a)
        r = 5 + 3 * math.sin(a * 2 + ang)
        d.ellipse([x - r, y - r, x + r, y + r], fill=AMBER + (90 + int(60 * (1 + math.sin(a))),))
    logo(img, W / 2, H / 2 - 18, 0.9)
    tracked(d, (W / 2, H / 2 + 112), 'A PROGRAMAÇÃO CONTINUA JÁ', F_DIN(28), CREAM + (220,), track=5)
    return tube(img, t, 6)


def card_audio(dur=30.0):
    """A soft pad that loops: every partial completes whole cycles in 30 s."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    chords = [[60, 64, 67, 71], [57, 60, 64, 67], [62, 65, 69, 72], [55, 59, 62, 67]]
    seg = n // 4
    for ci, ch in enumerate(chords):
        w = np.clip(np.minimum((t - ci * dur / 4) / 1.5 + 1, (ci * dur / 4 + dur / 4 - t) / 1.5 + 1), 0, 1)
        w = w if ci else np.maximum(w, np.clip((t - (dur - 1.5)) / 1.5, 0, 1))  # crossfade the wrap
        for m in ch:
            f = round(N(m) * dur) / dur
            out += 0.05 * w * (np.sin(2 * np.pi * f * t) + 0.2 * np.sin(2 * np.pi * 2 * f * t))
    out += 0.02 * np.sin(2 * np.pi * (round(N(36) * dur) / dur) * t)
    return out / np.max(np.abs(out)) * 0.5


# ---- Sessão Terror blood: drips that ooze from the feet of TERROR ----

class Blood:
    """Organic blood for the terror vignette. Each drip is simulated once (gravity, drag, a mass budget that the trail
    uses up, stop-and-go pauses that swell the tip, drops that detach and fall), then drawn per frame as a soft union of
    shapes at 2x, thresholded like metaballs so neighbours merge, and shaded with a wet highlight and darker edges."""
    S = 2      # supersampling for the mask
    T0 = 2.6   # the stab: blood arrives with it

    def __init__(self, seed=31):
        r = np.random.default_rng(seed)
        m = Image.new('L', (W, H), 0)
        tracked(ImageDraw.Draw(m), (W / 2, H / 2 + 34), 'TERROR', F_HORROR(92), 255, track=6)
        ink = np.asarray(m) > 100
        ys = np.where(ink.any(0), H - 1 - np.argmax(ink[::-1], 0), -1)
        foot = ys >= ys.max() - 5  # columns whose strokes stand on the baseline
        self.runs, x = [], 0
        while x < W:
            if foot[x]:
                s = x
                while x < W and foot[x]:
                    x += 1
                self.runs.append((s, x - 1))
            x += 1
        self.ys = ys.astype(np.float32)
        self.lipn = [r.uniform(0, 6.3, 3) for _ in self.runs]
        self.drips, self.drops = [], []
        for k, (a, b) in enumerate(self.runs):
            n = 2 if b - a > 12 else 1
            for j in range(n):
                x0 = r.uniform(a + 2, b - 2) if n == 1 else (a + 3 + j * (b - a - 6)) + r.uniform(-1.5, 1.5)
                self.drips.append(self._drip(r, x0, ys[int(x0)] - 1, self.T0 + 0.1 + r.uniform(0, 1.4)))
        # one pair merges: the second drip of the wide E foot slides into its neighbour
        pa, pb = self.drips[2], self.drips[3]
        pb['t0'] = pa['t0'] + 0.35
        s1 = r.uniform(14, 22)
        pb['merge'] = (pa, s1, s1 + 16)
        pb['Lmax'] = s1 + 18
        self.sim(r)
        noise = np.random.default_rng(seed + 1).normal(0, 1, (H * self.S // 6, W * self.S // 6)).astype(np.float32)
        self.grain = np.asarray(Image.fromarray(((noise * 40) + 128).clip(0, 255).astype(np.uint8)).resize(
            (W * self.S, H * self.S), Image.BICUBIC)).astype(np.float32) - 128
        self.specks = []
        for _ in range(26):
            x = r.uniform(165, 490); y = r.uniform(200, 300) if r.random() < 0.7 else r.uniform(150, 330)
            rad = min(2.6, 0.45 + r.exponential(0.55))
            ang = math.atan2(y - 232, x - 328) + r.normal(0, 0.4)
            tail = r.random() < 0.35
            self.specks.append((x, y, rad, ang, tail, self.T0 + math.hypot(x - 328, y - 232) * 0.0012))

    @staticmethod
    def _drip(r, x0, y0, t0):
        heavy = r.random() < 0.45
        return dict(x0=x0, y0=y0, t0=t0, w=r.uniform(2.6, 3.6) if not heavy else r.uniform(3.8, 5.4),
                    Lmax=r.uniform(200, 340) if heavy else r.uniform(45, 160), g=r.uniform(150, 300), k=r.uniform(2.5, 5.0),
                    pauses=sorted((r.uniform(t0 + 0.4, 6.0), r.uniform(0.25, 0.9)) for _ in range(r.integers(1, 3))),
                    detach=heavy and r.random() < 0.7, ph=r.uniform(0, 6.3, 5), wig=r.uniform(0.4, 1.6), merge=None)

    def xs(self, d, s):
        p = d['ph']
        x = d['x0'] + d['wig'] * (np.sin(s / 9.0 + p[0]) * 0.8 + np.sin(s / 3.7 + p[1]) * 0.35) + (s * 0.012 * math.sin(p[2]))
        if d['merge']:
            a, s1, s2 = d['merge']
            k = np.clip((s - s1) / (s2 - s1), 0, 1)
            x = x + (self.xs(a, s) - x) * k * k * (3 - 2 * k)
        return x

    def sim(self, r):
        dt, sub = 1 / FPS, 6
        n = int(7.2 * FPS)
        for d in self.drips:
            p = d['ph']
            d['ws'], d['tw'] = np.zeros(420, np.float32), np.zeros(420, np.float32)
            d['L'], d['rt'], d['v'] = np.zeros(n, np.float32), np.zeros(n, np.float32), np.zeros(n, np.float32)
            L = v = 0.0
            rt = d['w'] * 0.55
            was_paused = False
            for i in range(n):
                for j in range(sub):
                    h = dt / sub
                    t = (i - 1) * dt + (j + 1) * h
                    if t < d['t0']:
                        continue
                    paused = any(a <= t < a + b for a, b in d['pauses'])
                    m = max(0.0, 1 - L / d['Lmax']) ** 0.7
                    if paused and m > 0.05:
                        v *= math.exp(-14 * h)
                        rt = min(d['w'] * 1.15, rt + 2.2 * h)  # the tip gathers what is behind it
                    else:
                        if was_paused and d['detach'] and rt > d['w'] * 0.95 and L > 18:
                            yt = d['y0'] + L
                            self.drops.append(dict(x=float(self.xs(d, L)), y=yt + rt * 0.4, r=rt * 0.95, v=v + 25, t=t, d=d))
                            L -= rt * 0.9  # the stalk snaps back up
                            rt *= 0.45
                            v = 0.0
                            d['detach'] = False
                        heavy = (rt / d['w'] - 0.55) * 0.9
                        v += (d['g'] * (m + max(0, heavy)) - d['k'] * v) * h
                        v = max(v, 0.0)
                        rt += (d['w'] * (0.62 + 0.25 * m) - rt) * 1.5 * h
                    if paused and not was_paused and L > 3:  # where it stalls, it leaves a bulge
                        for s in range(max(0, int(L) - 4), int(L) + 1):
                            d['ws'][s] = max(d['ws'][s], rt * 1.25)
                    was_paused = paused
                    L0, L = L, L + v * h
                    for s in range(int(L0) + 1, min(419, int(L)) + 1):
                        nz = 0.75 + 0.2 * math.sin(s / 11.0 + p[0]) + 0.17 * math.sin(s / 4.6 + p[3]) + 0.1 * math.sin(s / 1.9 + p[4])
                        if d['tw'][s] == 0:
                            d['ws'][s] = max(1.5, d['w'] * nz / (1 + v / 90))
                            d['tw'][s] = t
                d['L'][i], d['rt'][i], d['v'][i] = L, rt, v

    def mask(self, t):
        S = self.S
        m = Image.new('L', (W * S, H * S), 0)
        dd = ImageDraw.Draw(m)
        i = min(int(round(t * FPS)), len(self.drips[0]['L']) - 1)
        grow = ease((t - self.T0) / 0.6)
        if grow <= 0:
            return None
        sag = []
        for d in self.drips:
            if t >= d['t0'] - 0.25:
                sag.append((d['x0'], d['w'] * 1.3, min(1, (t - d['t0'] + 0.25) / 0.4)))
        for (a, b), ph in zip(self.runs, self.lipn):  # the coat along each foot, sagging where a drip forms
            x = np.arange(a - 1, b + 2, 0.5)
            th = grow * (1.6 + 0.9 * np.sin(x / 3.1 + ph[0]) + 0.6 * np.sin(x / 1.7 + ph[1]))
            for sx, sw, sk in sag:
                th += 3.2 * sk * np.exp(-((x - sx) / sw) ** 2)
            yb = np.interp(x, np.arange(W), self.ys)
            top = [(xx * S, (y - 3) * S) for xx, y in zip(x, yb)]
            bot = [(xx * S, (y + max(0.3, tt)) * S) for xx, y, tt in zip(x[::-1], yb[::-1], th[::-1])]
            dd.polygon(top + bot, fill=255)
        for d in self.drips:
            L, rt, v = float(d['L'][i]), float(d['rt'][i]), float(d['v'][i])
            if t < d['t0'] or L < 0.5:
                continue
            s = np.arange(0, L + 0.01, 1.0)
            ws = d['ws'][:len(s)].copy()
            ws[0] = max(ws[0], d['w'])
            age = np.clip((t - d['tw'][:len(s)]) / 2.5, 0, 1)
            ws *= 1 - 0.2 * age  # the trail drains as the drip moves on
            ws *= 1 + 0.45 * np.exp(-s / 22.0)  # fuller near the letter
            ws += d['w'] * 0.9 * np.exp(-s / 3.0)  # flare where it leaves the letter
            ws = np.maximum(ws, 1.25)
            x = self.xs(d, s)
            y = d['y0'] + s
            left = [(a * S, b * S) for a, b in zip(x - ws / 2, y)]
            right = [(a * S, b * S) for a, b in zip((x + ws / 2)[::-1], y[::-1])]
            if len(left) > 1:
                dd.polygon(left + right, fill=255)
            tx, ty = float(self.xs(d, L)), d['y0'] + L
            ry, rx = rt * (1 + v / 140), rt * (1 - min(0.25, v / 400))
            dd.ellipse([(tx - rx) * S, (ty - ry * 0.9) * S, (tx + rx) * S, (ty + ry * 1.1) * S], fill=255)
        for dr in self.drops:
            dtm = t - dr['t']
            if dtm < 0:
                continue
            vv = dr['v'] + 900 * dtm
            y = dr['y'] + dr['v'] * dtm + 450 * dtm * dtm
            if y - dr['r'] * 3 > H:
                continue
            rx, ry = dr['r'] * 0.85, dr['r'] * (1.05 + vv / 650)
            dd.ellipse([(dr['x'] - rx) * S, (y - ry) * S, (dr['x'] + rx) * S, (y + ry * 0.8) * S], fill=255)
            if dtm < 0.09:  # the thread that lets go
                d = dr['d']
                L = float(d['L'][min(int(round(t * FPS)), len(d['L']) - 1)])
                tx, ty = float(self.xs(d, L)), d['y0'] + L
                wdt = max(1, int(S * 1.4 * (1 - dtm / 0.09)))
                dd.line([(tx * S, ty * S), (dr['x'] * S, (y - ry) * S)], fill=255, width=wdt)
        for x, y, rad, ang, tail, ts in self.specks:
            k = ease((t - ts) / 0.12)
            if k <= 0:
                continue
            rr = rad * k
            dd.ellipse([(x - rr) * S, (y - rr) * S, (x + rr) * S, (y + rr) * S], fill=255)
            if tail:
                for j, f in enumerate((0.7, 0.45, 0.3)):
                    cx, cy = x - math.cos(ang) * rad * (1.6 + j * 1.3), y - math.sin(ang) * rad * (1.6 + j * 1.3)
                    dd.ellipse([(cx - rr * f) * S, (cy - rr * f) * S, (cx + rr * f) * S, (cy + rr * f) * S], fill=255)
        f = np.asarray(m.filter(ImageFilter.GaussianBlur(0.9 * S))).astype(np.float32) + self.grain * 0.35
        a = np.clip((f - 88) / 44, 0, 1)
        return a.reshape(H, S, W, S).mean(axis=(1, 3))

    def paint(self, img, t):
        a = self.mask(t)
        if a is None:
            return img
        rows, cols = np.nonzero(a > 0.002)
        if not len(rows):
            return img
        y0, y1 = max(0, rows.min() - 4), min(H, rows.max() + 5)
        x0, x1 = max(0, cols.min() - 4), min(W, cols.max() + 5)
        a = a[y0:y1, x0:x1]
        hgt = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.8))).astype(np.float32) / 255
        gy, gx = np.gradient(hgt)
        n = np.stack([-gx * 7, -gy * 7, np.ones_like(hgt)], -1)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        lt = np.array([-0.5, -0.65, 0.57]); lt /= np.linalg.norm(lt)
        hv = lt + np.array([0, 0, 1.0]); hv /= np.linalg.norm(hv)
        dif = np.clip(n @ lt, 0, 1)[..., None]
        spec = (np.clip(n @ hv, 0, 1) ** 36)[..., None] * np.clip(hgt * 1.6, 0, 1)[..., None]
        core = np.clip((hgt - 0.15) / 0.6, 0, 1)[..., None]
        col = np.array([72, 0, 4.0]) * (1 - core) + np.array([182, 10, 12.0]) * core
        col = col * (0.6 + 0.55 * dif) + np.array([255, 190, 180.0]) * spec * 0.9
        rgb = np.asarray(img.convert('RGB')).astype(np.float32)
        aa = a[..., None]
        rgb[y0:y1, x0:x1] = rgb[y0:y1, x0:x1] * (1 - aa) + col * aa
        out = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert('RGBA')
        img.paste(out)
        return img


_BLOOD = []


def blood():
    if not _BLOOD:
        _BLOOD.append(Blood())
    return _BLOOD[0]


# ---- block vignettes ----

def v_terror(t):
    img = canvas((10, 2, 2))
    d = ImageDraw.Draw(img, 'RGBA')
    fog = Image.fromarray((np.random.default_rng(int(t * 2)).random((H // 8, W // 8)) * 150).astype(np.uint8)).resize((W, H), Image.BICUBIC)
    red = Image.new('RGBA', (W, H), (120, 10, 10, 255))
    img = Image.composite(red, img, fog.point(lambda v: int(v * (0.6 + 0.4 * math.sin(t * 2)))))
    d = ImageDraw.Draw(img, 'RGBA')
    on = 1.0 if t > 2.6 else (1.0 if (int(t * 17) % 5 in (0, 2) and t > 0.8) else 0.15)  # a failing bulb finds its feet
    if t > 2.0 and t < 2.12:
        d.rectangle([0, 0, W, H], fill=(235, 225, 225))  # lightning
    c = (200, 20, 16, int(255 * on))
    tracked(d, (W / 2, H / 2 - 30), 'SESSÃO', F_HORROR(44), (230, 220, 210, int(255 * on)), track=10)
    tracked(d, (W / 2, H / 2 + 34), 'TERROR', F_HORROR(92), c, track=6)
    blood().paint(img, t)
    logo(img, W - 92, H - 26, 0.28, 0.8)
    if t > 6.4:
        d.rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * ease((t - 6.4) / 0.6))))
    return tube(img, t, 16)


def a_terror(dur):
    low = tone(N(33), dur, 'saw', 0.25, 0.8, 9) + tone(N(34), dur, 'saw', 0.15, 1.0, 9)
    stab = sum(tone(N(m), 2.5, 'saw', 0.18, 0.005, 1.2) for m in (57, 58, 63))
    thunder = np.convolve(noise(2.5, 1.0), np.ones(60) / 60, mode='same') * env(int(2.5 * SR), 0.02, 0.8) * 2.5
    return mix(dur, (0, low), (2.0, thunder), (2.6, stab), *chime(5.6, 0.18, -1))


def v_muda(t):
    sep = (196, 170, 128)
    img = canvas((30, 24, 16))
    d = ImageDraw.Draw(img, 'RGBA')
    r = 30 + 420 * ease((t - 0.2) / 1.4)  # iris opens
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay, 'RGBA')
    ld.ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r], fill=sep + (255,))
    img.alpha_composite(lay)
    d = ImageDraw.Draw(img, 'RGBA')
    dark = (44, 32, 20)
    d.rectangle([60, 46, W - 60, H - 46], outline=dark, width=3)
    d.rectangle([70, 56, W - 70, H - 56], outline=dark, width=1)
    for cx, cy in ((70, 56), (W - 70, 56), (70, H - 56), (W - 70, H - 56)):
        d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=dark)
    a = ease((t - 1.2) / 0.6)
    tracked(d, (W / 2, H / 2 - 26), 'COMÉDIA', F_COPPER(64), dark + (int(255 * a),), track=6)
    tracked(d, (W / 2, H / 2 + 38), 'MUDA', F_COPPER(64), dark + (int(255 * a),), track=22)
    tracked(d, (W / 2, H / 2 + 92), 'KÖLJA TV', F_DIN(22), dark + (int(200 * a),), track=8)
    arr = np.asarray(img.convert('RGB')).astype(np.float32)
    jump = int(2 * math.sin(t * 31))  # gate weave
    arr = np.roll(arr, jump, axis=0)
    for _ in range(3):  # scratches and dust
        x = int(rng.integers(0, W))
        arr[:, x:x + 1] *= 0.55
    flick = 1 + 0.06 * math.sin(t * 47)
    arr *= flick
    if t > 6.3:
        arr *= 1 - ease((t - 6.3) / 0.7)
    return tube(Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert('RGBA'), t, 22, lines=False)


def a_muda(dur):
    clat = np.zeros(int(dur * SR))
    for i in range(int(dur * 18)):
        j = int(i * SR / 18)
        clat[j:j + 300] += rng.normal(0, 0.05, 300) * np.linspace(1, 0, 300)
    melody = [72, 76, 79, 76, 77, 74, 71, 72, 79, 84]
    parts = [(0.9 + i * 0.32, pluck(N(m), 1.2, 0.3)) for i, m in enumerate(melody)]
    parts += [(0.9 + i * 0.64, pluck(N(m), 1.0, 0.22)) for i, m in enumerate([48, 55, 53, 55, 48])]
    return mix(dur, (0, clat), *parts, *chime(5.2, 0.15))


def v_toons(t):
    img = canvas((255, 205, 40))
    d = ImageDraw.Draw(img, 'RGBA')
    ang = t * 0.6
    for i in range(16):  # sunburst
        a0 = ang + i * math.pi / 8
        pts = [(W / 2, H / 2), (W / 2 + 900 * math.cos(a0), H / 2 + 900 * math.sin(a0)),
               (W / 2 + 900 * math.cos(a0 + math.pi / 16), H / 2 + 900 * math.sin(a0 + math.pi / 16))]
        d.polygon(pts, fill=(255, 150, 30))
    word = 'DESENHOS'
    f = F_TOON(70)
    x0 = W / 2 - 4 * 52
    colors = [(230, 40, 50), (30, 110, 220), (40, 170, 70), (150, 50, 200)]
    for i, ch in enumerate(word):
        k = back((t - 0.4 - i * 0.12) / 0.5)
        y = H / 2 - 30 - (1 - k) * 260
        d.text((x0 + i * 52 + 26 + 3, y + 4), ch, font=f, fill=(40, 20, 10), anchor='mm')
        d.text((x0 + i * 52 + 26, y), ch, font=f, fill=colors[i % 4], anchor='mm')
    k = back((t - 1.8) / 0.5)
    sz = max(1, int(40 * k))
    tracked(d, (W / 2, H / 2 + 46), 'CLÁSSICOS', F_TOON(sz), (255, 255, 255), track=6)
    d.ellipse([W / 2 - 12, H / 2 + 92, W / 2 + 12, H / 2 + 116], fill=(30, 30, 30))  # a ball that bounces off
    logo(img, W - 92, H - 26, 0.28, 0.9, (40, 20, 10))
    if t > 5.6:  # iris out, cartoon style
        r = 760 * (1 - ease((t - 5.6) / 0.8))
        m = Image.new('L', (W, H), 255)
        ImageDraw.Draw(m).ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r], fill=0)
        img.paste((0, 0, 0, 255), (0, 0), m)
    return tube(img, t, 4)


def a_toons(dur):
    run = [(0.4 + i * 0.12, bell(N(m), 0.6, 0.25, 0.25)) for i, m in enumerate([72, 74, 76, 77, 79, 81, 83, 84])]
    n = int(0.6 * SR)
    tt = np.arange(n) / SR
    boing = 0.3 * np.sin(2 * np.pi * np.cumsum(300 + 200 * np.sin(tt * 40) * np.exp(-tt * 4)) / SR) * env(n, 0.005, 0.25)
    oom = [(1.8 + i * 0.5, tone(N(m), 0.4, 'square', 0.12, 0.005, 0.15)) for i, m in enumerate([48, 55, 48, 55, 48, 55])]
    return mix(dur, *run, (1.8, boing), *oom, *chime(4.8, 0.2, 1))


def v_ficcao(t):
    img = canvas((2, 4, 14))
    d = ImageDraw.Draw(img, 'RGBA')
    st = np.random.default_rng(3).random((140, 3))
    for x, y, z in st:  # stars fly out of the middle
        zz = (z - t * 0.12) % 1 + 0.02
        sx, sy = W / 2 + (x - 0.5) * W / zz * 0.3, H / 2 + (y - 0.5) * H / zz * 0.3
        s = max(1, 2.5 * (1 - zz))
        d.ellipse([sx - s, sy - s, sx + s, sy + s], fill=(200, 220, 255))
    px = W / 2 + 180 - 20 * t
    d.ellipse([px - 46, 70, px + 46, 162], fill=(170, 90, 50))
    d.arc([px - 90, 98, px + 90, 134], 160, 380, fill=(230, 200, 150), width=4)
    a = ease((t - 1.0) / 0.8)
    f = F_FUT(84)
    grad = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    tracked(gd, (W / 2, H / 2 + 20), 'FICÇÃO', f, (255, 255, 255, int(255 * a)), track=int(30 - 20 * a))
    ch = np.asarray(grad).astype(np.float32)
    yy = np.linspace(0, 1, H)[:, None]
    ch[..., 0] *= 0.55 + 0.45 * yy; ch[..., 1] *= 0.75 + 0.25 * yy  # chrome: cool top, warm bottom
    img.alpha_composite(Image.fromarray(ch.astype(np.uint8)))
    d = ImageDraw.Draw(img, 'RGBA')
    tracked(d, (W / 2, H / 2 + 84), 'CIENTÍFICA', F_DIN(30), (120, 220, 255, int(255 * ease((t - 1.8) / 0.6))), track=16)
    logo(img, W - 92, H - 26, 0.28, 0.8)
    if t > 6.3:
        d.rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * ease((t - 6.3) / 0.7))))
    return tube(img, t, 6)


def a_ficcao(dur):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    glide = N(76) * 2 ** (np.interp(tt, [0, 1.2, 2.4, 3.6, 5, dur], [-12, 0, 3, -2, 7, 7]) / 12)
    ther = 0.25 * np.sin(2 * np.pi * np.cumsum(glide * (1 + 0.012 * np.sin(2 * np.pi * 6 * tt))) / SR) * np.clip(tt / 0.6, 0, 1)
    pad = tone(N(45), dur, 'sine', 0.2, 1.0, 9) + tone(N(52), dur, 'sine', 0.12, 1.5, 9)
    return mix(dur, (0, ther), (0, pad), *chime(5.4, 0.15, 1))


def v_noir(t):
    img = canvas((14, 14, 16))
    d = ImageDraw.Draw(img, 'RGBA')
    off = (t * 18) % 40
    for i in range(-2, 12):  # light through the blinds, slanted
        y = i * 40 + off
        d.polygon([(0, y), (W, y - 120), (W, y - 100), (0, y + 20)], fill=(70, 70, 74))
    img = img.filter(ImageFilter.GaussianBlur(2))
    d = ImageDraw.Draw(img, 'RGBA')
    a = ease((t - 0.8) / 1.0)
    d.text((W / 2, H / 2 - 8), 'Noir', font=F_DIDOT(130), fill=(240, 240, 236, int(255 * a)), anchor='mm')
    tracked(d, (W / 2, H / 2 + 74), 'FILMES DA MEIA-LUZ', F_DIN(24), (200, 200, 196, int(255 * ease((t - 1.8) / 0.6))), track=8)
    rain = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rain)
    for x, y in np.random.default_rng(int(t * FPS)).random((90, 2)):
        rd.line([x * W, y * H, x * W - 6, y * H + 22], fill=(200, 200, 210, 70), width=1)
    img.alpha_composite(rain)
    logo(img, W - 92, H - 26, 0.28, 0.7)
    a = np.asarray(img.convert('L').convert('RGB')).astype(np.float32)
    if t > 6.3:
        a *= 1 - ease((t - 6.3) / 0.7)
    return tube(Image.fromarray(a.astype(np.uint8)).convert('RGBA'), t, 14)


def a_noir(dur):
    rain = np.convolve(noise(dur, 0.25), np.ones(4) / 4, mode='same')
    phrase = [(0.8, 63, 0.9), (1.7, 62, 0.4), (2.1, 60, 0.4), (2.5, 58, 1.4), (4.0, 55, 1.8)]
    horn = [(at, tone(N(m), d + 0.6, 'saw', 0.3, 0.06, d * 0.8, vib=0.006)) for at, m, d in phrase]
    bass = [(0.8 + i * 0.75, pluck(N(m), 0.8, 0.3)) for i, m in enumerate([36, 39, 43, 39, 36, 34, 36])]
    return mix(dur, (0, rain), *horn, *bass)


def v_cult(t):
    img = canvas((24, 6, 40))
    d = ImageDraw.Draw(img, 'RGBA')
    for i in range(20):
        y = H - i * 10
        d.line([0, y, W, y], fill=(120, 40, 200, 255 - i * 12), width=1)
    d.ellipse([W / 2 + 110, 40, W / 2 + 190, 120], fill=(230, 240, 200))
    d.ellipse([W / 2 + 128, 36, W / 2 + 206, 112], fill=(24, 6, 40))  # crescent
    a = ease((t - 0.6) / 0.6)
    gl = int(8 * math.sin(t * 13)) if 0.6 < t < 2.4 else 0
    tracked(d, (W / 2 - gl, H / 2 - 22), 'MADRUGADA', F_IMPACT(70), (60, 255, 120, int(200 * a)), track=4)
    tracked(d, (W / 2 + gl, H / 2 - 22), 'MADRUGADA', F_IMPACT(70), (255, 60, 220, int(200 * a)), track=4)
    tracked(d, (W / 2, H / 2 - 22), 'MADRUGADA', F_IMPACT(70), (250, 250, 250, int(255 * a)), track=4)
    tracked(d, (W / 2, H / 2 + 46), 'CULT', F_IMPACT(64), (255, 210, 60, int(255 * ease((t - 1.4) / 0.4))), track=30)
    arr = np.asarray(img.convert('RGB')).astype(np.float32)
    band = int((t * 90) % (H + 60)) - 30  # VHS tracking band crawling down
    if 0 <= band < H - 12:
        arr[band:band + 12] = np.roll(arr[band:band + 12], 14, axis=1) * 1.25
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert('RGBA')
    od = ImageDraw.Draw(out, 'RGBA')
    od.text((22, 20), 'PLAY', font=F_DIN(24), fill=(240, 240, 240))
    od.polygon([(80, 21), (80, 39), (94, 30)], fill=(240, 240, 240))
    logo(out, W - 92, H - 26, 0.28, 0.8)
    if t > 6.3:
        ImageDraw.Draw(out, 'RGBA').rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * ease((t - 6.3) / 0.7))))
    return tube(out, t, 18)


def a_cult(dur):
    arp = [45, 52, 57, 60, 57, 52]
    parts = [(0.3 + i * 0.18, tone(N(arp[i % 6]), 0.25, 'square', 0.16, 0.003, 0.12)) for i in range(int((dur - 1) / 0.18))]
    hiss = noise(dur, 0.04)
    return mix(dur, (0, hiss), *parts, *chime(5.4, 0.14))


def v_series(t):
    img = canvas((20, 30, 46))
    d = ImageDraw.Draw(img, 'RGBA')
    for i in range(5):  # the old test pattern circle, our own
        r = 40 + i * 34
        d.ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r], outline=(80, 110, 150), width=2)
    a = ease((t - 0.6) / 0.6)
    tracked(d, (W / 2, H / 2 - 22), 'SÉRIES', F_FUT(72), (240, 236, 220, int(255 * a)), track=8)
    tracked(d, (W / 2, H / 2 + 42), 'CLÁSSICAS', F_DIN(40), AMBER + (int(255 * ease((t - 1.2) / 0.5)),), track=14)
    logo(img, W - 92, H - 26, 0.28, 0.8)
    if t > 6.3:
        d.rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * ease((t - 6.3) / 0.7))))
    return tube(img, t, 8)


def a_series(dur):
    parts = [(0.5 + i * 0.25, bell(N(m), 1.2, 0.5, 0.22)) for i, m in enumerate([67, 72, 74, 76, 79, 76])]
    return mix(dur, *parts, *chime(5.0, 0.18))


def v_comedia(t):
    """Red stage curtains part on a lit marquee."""
    img = canvas((14, 8, 8))
    d = ImageDraw.Draw(img, 'RGBA')
    for i in range(18):  # marquee bulbs round the frame, chasing
        on = (i + int(t * 6)) % 3 != 0
        for x, y in ((40 + i * 32, 30), (40 + i * 32, H - 30)):
            if x < W - 30:
                d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(255, 214, 120, 255 if on else 70))
    a = ease((t - 1.3) / 0.6)
    tracked(d, (W / 2, H / 2 - 24), 'COMÉDIA', F_FUT(70), CREAM + (int(255 * a),), track=8)
    tracked(d, (W / 2, H / 2 + 40), 'CLÁSSICA', F_DIN(40), AMBER + (int(255 * ease((t - 1.8) / 0.5)),), track=16)
    open_ = ease((t - 0.4) / 1.3)  # the curtains part
    half = W / 2 * (1 - 0.92 * open_)
    for side in (0, 1):
        x0, x1 = (0, half) if side == 0 else (W - half, W)
        d.rectangle([x0, 0, x1, H], fill=(128, 14, 22, 255))
        for k in range(10):  # folds
            fx = x0 + (x1 - x0) * (k + 0.5) / 10
            d.line([fx, 0, fx + 4 * math.sin(t * 2 + k), H], fill=(70, 4, 10, 200), width=5)
    logo(img, W - 92, H - 26, 0.28, 0.8)
    if t > 6.3:
        d.rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * ease((t - 6.3) / 0.7))))
    return tube(img, t, 8)


def a_comedia(dur):
    melody = [67, 72, 76, 79, 77, 76, 74, 72, 79, 84]
    parts = [(0.5 + i * 0.26, pluck(N(m), 0.9, 0.3)) for i, m in enumerate(melody)]
    parts += [(0.5 + i * 0.52, pluck(N(m), 0.9, 0.22)) for i, m in enumerate([48, 55, 48, 55, 53, 55])]
    return mix(dur, *parts, *chime(5.0, 0.16))


def _title(d, top, bottom, t, t0=0.9, top_font=None, color=CREAM, color2=AMBER, y=None):
    y = H / 2 if y is None else y
    tracked(d, (W / 2, y - 24), top, top_font or F_FUT(68), color + (int(255 * ease((t - t0) / 0.6)),), track=8)
    tracked(d, (W / 2, y + 40), bottom, F_DIN(38), color2 + (int(255 * ease((t - t0 - 0.6) / 0.5)),), track=14)


def _fade(img, t, grain=8):
    logo(img, W - 92, H - 26, 0.28, 0.8)
    if t > 6.3:
        ImageDraw.Draw(img, 'RGBA').rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * ease((t - 6.3) / 0.7))))
    return tube(img, t, grain)


def v_classicos(t):
    """A red velvet frame and a spotlight sweeping a gilt proscenium."""
    img = canvas((24, 6, 8))
    d = ImageDraw.Draw(img, 'RGBA')
    for k in range(16):  # the velvet's folds
        fx = 40 + k * (W - 80) / 15
        d.line([fx, 40, fx + 3 * math.sin(t + k), H - 40], fill=(44, 8, 12), width=6)
    x = W / 2 + math.sin(t * 0.9) * W * 0.3  # a spotlight beam from above, sweeping (solid colours: the canvas is RGBA)
    d.polygon([(W / 2 - 14, 0), (W / 2 + 14, 0), (x + 120, H), (x - 120, H)], fill=(92, 40, 34))
    d.polygon([(W / 2 - 6, 0), (W / 2 + 6, 0), (x + 60, H), (x - 60, H)], fill=(112, 54, 42))
    d.rectangle([24, 24, W - 24, H - 24], outline=(196, 150, 60), width=6)
    d.rectangle([36, 36, W - 36, H - 36], outline=(120, 84, 30), width=2)
    _title(d, 'GRANDES', 'CLÁSSICOS', t, top_font=F_COPPER(62), color=(250, 226, 170))
    return _fade(img, t)


def a_classicos(dur):
    chord = [(0.4, 48), (0.4, 55), (0.4, 64), (1.6, 53), (1.6, 60), (1.6, 69), (2.8, 55), (2.8, 62), (2.8, 71), (4.0, 48), (4.0, 64), (4.0, 72)]
    return mix(dur, *[(at, tone(N(m), 1.6, 'sine', 0.12, 0.08, 1.0, 0.004)) for at, m in chord], *chime(5.4, 0.16))


def v_aventura(t):
    """A sea at sunset, a crossed-swords crest drawing itself."""
    img = canvas((40, 22, 30))
    d = ImageDraw.Draw(img, 'RGBA')
    for y in range(0, H, 6):  # a sunset sky, then the sea
        k = y / H
        d.rectangle([0, y, W, y + 6], fill=(int(250 - 160 * k), int(150 - 100 * k), int(60 + 40 * k)) if y < H * 0.62 else (20, 40, 70))
    for i in range(12):  # waves
        y = H * 0.66 + i * 10
        for x in range(-40, W + 40, 40):
            xx = x + (t * 30 + i * 13) % 40
            d.arc([xx, y, xx + 40, y + 12], 200, 340, fill=(90, 140, 180, 160), width=2)
    a = ease((t - 0.3) / 1.0)  # two sabres cross above the title, drawn hilt first
    cx, cy = W / 2, 66
    for sgn in (-1, 1):
        x0, y0 = cx - sgn * 52, cy + 40  # hilt
        x1, y1 = x0 + sgn * 104 * a, y0 - 80 * a  # tip
        d.line([x0, y0, x1, y1], fill=(225, 228, 232), width=4)
        gx, gy = x0 + sgn * 14, y0 - 11  # the guard, across the blade
        d.line([gx - 9, gy - 11 * sgn, gx + 9, gy + 11 * sgn], fill=(214, 170, 60), width=5)
    _title(d, 'AVENTURA', 'CAPA E ESPADA', t, t0=1.1, y=H / 2 + 10)
    return _fade(img, t)


def a_aventura(dur):
    fan = [60, 67, 72, 76, 72, 79]
    return mix(dur, (0, noise(dur, 0.025)), *[(0.4 + i * 0.32, tone(N(m), 0.5, 'square', 0.1, 0.01, 0.3)) for i, m in enumerate(fan)], *chime(5.2, 0.16))


def v_faroeste(t):
    """Desert at noon: mesas, a cactus, a tumbleweed rolling through."""
    img = canvas((236, 170, 96))
    d = ImageDraw.Draw(img, 'RGBA')
    d.ellipse([W * 0.72, 30, W * 0.72 + 70, 100], fill=(255, 236, 170))
    hz = H * 0.74  # the horizon, low, so the sky carries the title
    d.polygon([(0, hz), (60, H * 0.6), (190, H * 0.6), (240, hz)], fill=(170, 84, 44))
    d.polygon([(400, hz), (450, H * 0.64), (570, H * 0.64), (630, hz)], fill=(150, 74, 40))
    d.rectangle([0, hz, W, H], fill=(214, 150, 80))
    cx = 300  # a saguaro in the middle distance
    d.rounded_rectangle([cx - 6, H * 0.62, cx + 6, H * 0.86], 6, fill=(52, 96, 52))
    d.rounded_rectangle([cx - 22, H * 0.68, cx - 14, H * 0.77], 4, fill=(52, 96, 52)); d.rectangle([cx - 22, H * 0.755, cx, H * 0.77], fill=(52, 96, 52))
    d.rounded_rectangle([cx + 14, H * 0.65, cx + 22, H * 0.74], 4, fill=(52, 96, 52)); d.rectangle([cx, H * 0.725, cx + 22, H * 0.74], fill=(52, 96, 52))
    x = (t / 7.0) * (W + 120) - 60  # the tumbleweed: a tangle of twigs, rolling and bouncing
    y = H * 0.88 - abs(math.sin(t * 4)) * 18
    for k in range(14):
        a0 = t * 400 + k * 53
        rr = 12 + (k * 7) % 9
        d.arc([x - rr, y - rr, x + rr, y + rr], a0, a0 + 150, fill=(110, 72, 36), width=2)
    _title(d, 'FAROESTE', 'O VELHO OESTE', t, top_font=F_COPPER(64), color=(70, 34, 16), color2=(150, 56, 20), y=H * 0.34)
    return _fade(img, t, 10)


def a_faroeste(dur):
    whistle = [(0.5, 76, 0.7), (1.3, 81, 0.5), (1.9, 76, 0.9), (3.0, 74, 0.5), (3.6, 72, 1.0)]
    parts = [(at, tone(N(m), ln, 'sine', 0.16, 0.05, 0.4, 0.01)) for at, m, ln in whistle]
    parts += [(0.2 + i * 0.5, pluck(N(m), 0.8, 0.2)) for i, m in enumerate([40, 47, 40, 47, 38, 45, 40, 47, 40, 47, 40, 47])]
    return mix(dur, *parts, *chime(5.4, 0.14))


def v_seriados(t):
    """A matinee: 'CAPÍTULO' cards flip by, a cliffhanger rope frays."""
    img = canvas((12, 12, 14))
    d = ImageDraw.Draw(img, 'RGBA')
    n = min(12, int(t * 3) + 1)
    tracked(d, (W / 2, 46), 'CAPÍTULO %d' % n, F_IMPACT(30), (220, 210, 190, 200), track=6)
    for k in range(9):  # the rope, fraying as it goes
        y = 70 + k * 6
        if k < 9 - int(t):
            d.line([W / 2 - 3 + (k % 2) * 6, y, W / 2 + 3 - (k % 2) * 6, y + 6], fill=(190, 160, 110), width=4)
    _title(d, 'SERIADOS', 'DE MATINÊ', t, top_font=F_IMPACT(70))
    tracked(d, (W / 2, H - 52), 'CONTINUA AMANHÃ, NESTE MESMO CANAL', F_DIN(20), (220, 210, 190, int(255 * ease((t - 3.0) / 0.6))), track=6)
    return _fade(img, t, 14)


def a_seriados(dur):
    stab = [(0.3, 45), (0.3, 52), (0.3, 57), (1.2, 46), (1.2, 53), (1.2, 58), (2.1, 47), (2.1, 54), (2.1, 59), (3.0, 48), (3.0, 55), (3.0, 60)]
    return mix(dur, *[(at, tone(N(m), 0.7, 'saw', 0.09, 0.005, 0.5)) for at, m in stab], *chime(5.2, 0.16))


def v_docs(t):
    """A newsreel: a spinning globe of meridians and a ticker."""
    img = canvas((16, 18, 22))
    d = ImageDraw.Draw(img, 'RGBA')
    cx, cy, r = W / 2, H / 2 - 6, 118
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(150, 160, 170), width=2)
    for k in range(8):  # meridians turning
        ph = (t * 0.6 + k / 8) % 1.0
        w = abs(math.cos(ph * math.pi)) * r
        d.ellipse([cx - w, cy - r, cx + w, cy + r], outline=(110, 120, 130, 160), width=1)
    for k in range(1, 6):
        y = cy - r + k * 2 * r / 6
        w = math.sqrt(max(0, r * r - (y - cy) ** 2))
        d.line([cx - w, y, cx + w, y], fill=(110, 120, 130, 140))
    _title(d, 'DOCUMENTÁRIOS', 'O MUNDO DE VERDADE', t, top_font=F_FUT(56))
    tick = 'NOTÍCIAS · CIÊNCIA · HISTÓRIA · ESPAÇO · ' * 4
    tracked(d, (W / 2 - (t * 80) % 400 + 200, H - 40), tick, F_DIN(20), AMBER + (200,), track=4)
    return _fade(img, t, 12)


def a_docs(dur):
    fan = [(0.3, 60), (0.3, 64), (0.3, 67), (0.9, 62), (0.9, 65), (0.9, 69), (1.5, 64), (1.5, 67), (1.5, 72)]
    return mix(dur, (0, noise(dur, 0.03)), *[(at, tone(N(m), 0.5, 'square', 0.08, 0.01, 0.4)) for at, m in fan], *chime(4.8, 0.16))


def v_domingo(t):
    """Sunday afternoon: the sun climbing over a horizon behind the newsreel globe, and a slower ticker."""
    img = canvas((18, 22, 30))
    d = ImageDraw.Draw(img, 'RGBA')
    hz = H / 2 + 70
    for k in range(10):  # the afternoon sky in bands, warmer towards the horizon
        y0 = k * hz / 10
        c = tuple(int(a + (b - a) * k / 9) for a, b in zip((18, 24, 38), (96, 58, 30)))
        d.rectangle([0, y0, W, y0 + hz / 10 + 1], fill=c)
    sy = hz + 10 - ease(t / 2.4) * 52  # the sun rises a little, below the title
    for r, a in ((70, 40), (56, 80), (44, 255)):
        d.ellipse([W / 2 - r, sy - r, W / 2 + r, sy + r], fill=(255, 176, 60, a))
    cx, cy, r = W / 2, sy, 44
    for k in range(6):  # the globe's meridians turning across the sun
        ph = (t * 0.5 + k / 6) % 1.0
        w = abs(math.cos(ph * math.pi)) * r
        d.ellipse([cx - w, cy - r, cx + w, cy + r], outline=(120, 64, 20, 150), width=1)
    d.rectangle([0, hz, W, H], fill=(14, 16, 20))
    for k in range(7):  # the field's furrows, in perspective
        x = W / 2 + (k - 3) * 60
        d.line([W / 2 + (k - 3) * 8, hz, x + (k - 3) * 160, H], fill=(40, 42, 46), width=2)
    _title(d, 'DOMINGO', 'DOCUMENTAL', t, top_font=F_FUT(64), y=H / 2 - 96)
    tick = 'NATUREZA · VIAGENS · CIÊNCIA · ESPAÇO · CIDADES · ' * 3
    tracked(d, (W / 2 + 300 - t * 40, H - 40), tick, F_DIN(20), CREAM + (190,), track=4)
    return _fade(img, t, 12)


def a_domingo(dur):
    fan = [(0.3, 55), (0.3, 59), (0.3, 62), (1.1, 57), (1.1, 60), (1.1, 64), (1.9, 59), (1.9, 62), (1.9, 67)]
    return mix(dur, *[(at, tone(N(m), 0.8, 'sine', 0.1, 0.05, 0.7)) for at, m in fan], *chime(4.8, 0.16))


def tecnicos(t):
    """Technical problems: our bars dimmed behind a plate, a slow scan bar; loops every 12 s."""
    img = canvas((10, 10, 12))
    d = ImageDraw.Draw(img, 'RGBA')
    cols = [(150, 146, 138), (150, 136, 30), (30, 136, 140), (30, 128, 40), (136, 30, 128), (140, 36, 30), (30, 36, 134)]
    bw = W / len(cols)
    for i, c in enumerate(cols):
        d.rectangle([i * bw, 0, (i + 1) * bw, H], fill=c)
    y = (t / 12.0) * (H + 80) - 40  # one sweep per loop, so the loop point is seamless
    d.rectangle([0, y, W, y + 26], fill=(255, 255, 255, 40))
    d.rounded_rectangle([60, 92, W - 60, H - 92], radius=14, fill=(8, 8, 10, 235), outline=AMBER + (255,), width=3)
    logo(img, W / 2, 140, 0.62)
    tracked(d, (W / 2, 196), 'PROBLEMAS TÉCNICOS', F_DIN(40), CREAM + (255,), track=5)
    blink = 255 if int(t * 2) % 2 == 0 else 150
    tracked(d, (W / 2, 238), 'JÁ VOLTAMOS', F_DIN(30), AMBER + (blink,), track=12)
    return tube(img, t, 8)


def tecnicos_audio(dur=12.0):
    """A low test hum that loops: whole cycles in 12 s."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = 0.05 * np.sin(2 * np.pi * 220 * t) + 0.03 * np.sin(2 * np.pi * 330 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * t / dur))
    return out / np.max(np.abs(out)) * 0.35


# ---------------- the commercial break: our own pieces only ----------------

def _plate(d, box, fill=(8, 8, 10, 235), outline=AMBER + (255,), r=14, w=3):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=w)


def _clock(img, cx, cy, r, ang, alpha=255):
    """The break clock: an amber dial whose hand sweeps once."""
    d = ImageDraw.Draw(img, 'RGBA')
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=AMBER + (alpha,), width=4)
    for k in range(12):
        a = k * math.pi / 6
        d.line([cx + (r - 9) * math.cos(a), cy + (r - 9) * math.sin(a), cx + (r - 3) * math.cos(a), cy + (r - 3) * math.sin(a)],
               fill=CREAM + (alpha,), width=2)
    a = -math.pi / 2 + ang
    d.line([cx, cy, cx + (r - 14) * math.cos(a), cy + (r - 14) * math.sin(a)], fill=CREAM + (alpha,), width=4)
    d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=AMBER + (alpha,))


def intervalo(t):
    """Into the break: the bars slide away, INTERVALO with the clock, KÖLJA TV."""
    img = canvas((14, 12, 10))
    d = ImageDraw.Draw(img, 'RGBA')
    cols = [(236, 232, 220), (236, 214, 40), (40, 214, 220), (40, 200, 60), (214, 40, 200), (220, 50, 40), (40, 50, 210)]
    bw = W / len(cols)
    k = ease(t / 0.9)
    for i, c in enumerate(cols):  # the bars wipe off to the left, one after the other
        x = i * bw - (W + bw) * ease((t - 0.05 * i) / 0.9)
        d.rectangle([x, 0, x + bw + 1, H], fill=c)
    if t > 0.5:
        a = ease((t - 0.6) / 0.5) * (1 - ease((t - 5.4) / 0.5))
        _clock(img, 128, H / 2, 54, 2 * math.pi * ease((t - 0.8) / 4.2), int(255 * a))
        d.text((206, H / 2 - 34), 'INTERVALO', font=F_LOGO(50), fill=CREAM + (int(255 * a),), anchor='lm')
        tracked(d, (208, H / 2 + 26), 'A PROGRAMAÇÃO VOLTA JÁ', F_DIN(26), AMBER + (int(255 * a),), track=4, anchor='lm')
        logo(img, W - 120, H - 46, 0.42, a)
    if t > 5.4:
        d.rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * ease((t - 5.4) / 0.6))))
    return tube(img, t, 8)


def a_intervalo(dur):
    down = [(0.0, 84), (0.22, 76), (0.44, 79)]  # our chime, turned round: off we go
    return mix(dur, (0, noise(0.6, 0.04, 6)), *[(0.7 + dt, bell(N(m), 1.8, 0.9, 0.32)) for dt, m in down],
               *[(1.6 + 0.5 * i, tone(N(m), 0.45, 'square', 0.05, 0.01, 0.25)) for i, m in enumerate([60, 64, 67, 72, 67, 64, 60])])


def voltamos(t):
    """Out of the break: VOLTAMOS over our bars, a quick fold to the programme."""
    img = canvas((10, 10, 12))
    d = ImageDraw.Draw(img, 'RGBA')
    a = ease(t / 0.4)
    _clock(img, 128, H / 2, 54, 2 * math.pi * (0.85 + 0.15 * ease(t / 1.5)), int(255 * a))
    d.text((206, H / 2 - 34), 'VOLTAMOS', font=F_LOGO(50), fill=CREAM + (int(255 * a),), anchor='lm')
    tracked(d, (208, H / 2 + 26), 'COM A PROGRAMAÇÃO', F_DIN(26), AMBER + (int(255 * ease((t - 0.4) / 0.5)),), track=4, anchor='lm')
    logo(img, W - 120, H - 46, 0.42, a)
    if t > 3.9:  # fold to a line, like switching back to the film
        k = ease((t - 3.9) / 0.6)
        d.rectangle([0, 0, W, H * k / 2], fill=(0, 0, 0))
        d.rectangle([0, H - H * k / 2, W, H], fill=(0, 0, 0))
    return tube(img, t, 8)


def a_voltamos(dur):
    return mix(dur, *chime(0.15, 0.36), (1.2, tone(N(48), 1.6, 'sine', 0.16, 0.05, 0.8)), (3.9, noise(0.6, 0.03, 4)))


def anuncie(t):
    """The sponsor slot, for later: ANUNCIE AQUI on a tube-set test pattern, the site to ask."""
    img = canvas((18, 16, 14))
    d = ImageDraw.Draw(img, 'RGBA')
    for i in range(10):  # slow diagonal stripes of the slot, one stripe width per 15 s: a seamless loop
        x = (i * 96 + (t / 15.0) * 96) % 960 - 160
        d.polygon([(x, 0), (x + 48, 0), (x + 48 - 200, H), (x - 200, H)], fill=(30, 26, 20))
    _plate(d, [58, 64, W - 58, H - 64])
    a = ease(t / 0.6)
    tracked(d, (W / 2, 104), 'ESPAÇO PUBLICITÁRIO', F_DIN(24), AMBER + (int(255 * a),), track=8)
    pulse = 1 + 0.03 * math.sin(t * 2 * math.pi / 2.5)
    tracked(d, (W / 2, 160), 'ANUNCIE AQUI', F_LOGO(int(44 * pulse)), CREAM + (int(255 * a),), track=4)
    lines = ['SUA MARCA NOS INTERVALOS DO KÖLJA TV', 'CLÁSSICOS CULT · 24 HORAS']
    for i, s in enumerate(lines):
        tracked(d, (W / 2, 214 + 30 * i), s, F_DIN(22), CREAM + (int(220 * ease((t - 1.0 - 0.4 * i) / 0.6)),), track=3)
    tracked(d, (W / 2, H - 38), 'koljatv.github.io', F_DIN(22), AMBER + (int(255 * ease((t - 2.2) / 0.6)),), track=2)
    return tube(img, t, 8)


def a_anuncie(dur):
    n = int(dur * SR)
    bass = [48, 48, 55, 53]
    parts = [(0, noise(dur, 0.02, 8))]
    for b in range(int(dur / 2)):  # a slow lounge vamp, two seconds a bar
        m = bass[b % 4]
        parts += [(b * 2.0, tone(N(m - 12), 1.8, 'sine', 0.18, 0.02, 0.9)), (b * 2.0 + 0.5, pluck(N(m + 16), 0.8, 0.10)),
                  (b * 2.0 + 1.5, pluck(N(m + 19), 0.6, 0.08))]
    return mix(dur, *parts, *chime(dur - 2.2, 0.22))


CARTS = [('TIJOLINHO', 'GRÁTIS', (40, 160, 200)), ('COBRINHA', 'R$ 4,90', (60, 170, 70)), ('MAL DA SERRA', 'R$ 12,90', (170, 40, 30))]


def promo_loja(t):
    """KÖLJA Store: three cartridges slide in; the address at the end."""
    img = canvas((16, 14, 22))
    d = ImageDraw.Draw(img, 'RGBA')
    for y in range(0, H, 6):
        d.line([0, y, W, y], fill=(26, 22, 34), width=1)
    a = ease(t / 0.6)
    tracked(d, (W / 2, 44), 'KÖLJA STORE', F_LOGO(44), AMBER + (int(255 * a),), track=6)
    tracked(d, (W / 2, 84), 'JOGOS PARA O SEU RETROTV', F_DIN(26), CREAM + (int(255 * ease((t - 0.5) / 0.6)),), track=4)
    for i, (name, price, col) in enumerate(CARTS):  # cartridges: a label, a notch, the price under them
        k = back((t - 1.2 - 0.6 * i) / 0.7)
        cx = 120 + i * 200
        y = 128 + (1 - k) * 260
        d.rounded_rectangle([cx - 74, y, cx + 74, y + 150], radius=10, fill=(54, 52, 58))
        d.rectangle([cx - 30, y + 140, cx + 30, y + 150], fill=(30, 28, 34))
        d.rounded_rectangle([cx - 62, y + 14, cx + 62, y + 96], radius=6, fill=col)
        d.text((cx, y + 55), name, font=F_DIN(24 if len(name) < 10 else 20), fill=CREAM, anchor='mm')
        d.text((cx, y + 118), price, font=F_DIN(26), fill=AMBER, anchor='mm')
    if t > 10.0:  # the closing plate: how to buy
        k = ease((t - 10.0) / 0.6)
        d.rectangle([0, H - 64 * k, W, H], fill=(8, 8, 10, 240))
        tracked(d, (W / 2, H - 42 * k + 8), 'kolja.com.br/store  ·  PAGUE COM PIX', F_DIN(28), CREAM + (int(255 * k),), track=3)
    return tube(img, t, 8)


def a_promo_loja(dur):
    parts = [(0, noise(dur, 0.015, 6))]
    mel = [72, 76, 79, 76, 74, 77, 81, 77, 72, 76, 79, 84]
    for i in range(int(dur / 0.25)):  # a chiptune bounce, eighth notes
        m = mel[i % len(mel)] - (0 if (i // 16) % 2 == 0 else 2)
        parts.append((i * 0.25, tone(N(m), 0.2, 'square', 0.07, 0.005, 0.12)))
        if i % 4 == 0: parts.append((i * 0.25, tone(N(m - 24), 0.45, 'square', 0.09, 0.005, 0.3)))
    return mix(dur, *parts, *chime(dur - 2.0, 0.25))


def promo_retrotv(t):
    """Retrotv: three things the set does, one card each, then the KÖLJA TV mark."""
    img = canvas((10, 18, 20))
    d = ImageDraw.Draw(img, 'RGBA')
    cards = [('MENU › JOGOS', 'JOGUE NO PRÓPRIO RETROTV'), ('PASSAR PARA O COMPUTADOR', 'O KÖLJA TV NA TELA GRANDE'),
             ('REC', 'GRAVE OS CANAIS AO VIVO')]
    tracked(d, (W / 2, 46), 'NO SEU RETROTV', F_DIN(30), AMBER + (int(255 * ease(t / 0.6)),), track=8)
    for i, (head, sub) in enumerate(cards):
        t0 = 0.8 + 3.2 * i
        if not (t0 <= t < t0 + 3.4): continue
        k = ease((t - t0) / 0.5) * (1 - ease((t - t0 - 2.9) / 0.5))
        x = W / 2 + (1 - ease((t - t0) / 0.5)) * 120
        _plate(d, [x - 250, 110, x + 250, 250], fill=(8, 8, 10, int(235 * k)), outline=AMBER + (int(255 * k),))
        d.text((x, 160), head, font=F_LOGO(38 if len(head) < 16 else 24), fill=CREAM + (int(255 * k),), anchor='mm')
        tracked(d, (x, 214), sub, F_DIN(24), AMBER + (int(255 * k),), track=3)
    if t > 10.6:
        a = ease((t - 10.6) / 0.6)
        logo(img, W / 2, 180, 0.9, a)
        tracked(d, (W / 2, 262), 'CANAL 1 DO RETROTV', F_DIN(26), CREAM + (int(255 * a),), track=6)
    return tube(img, t, 8)


def a_promo_retrotv(dur):
    parts = [(0, noise(dur, 0.02, 6))]
    prog = [60, 65, 67, 60]
    for b in range(int(dur / 1.6)):
        m = prog[b % 4]
        for j, iv in enumerate([0, 4, 7]):
            parts.append((b * 1.6 + 0.08 * j, tone(N(m + iv), 1.4, 'saw', 0.06, 0.05, 0.8)))
        parts.append((b * 1.6, tone(N(m - 12), 1.5, 'sine', 0.14, 0.02, 0.9)))
    return mix(dur, *parts, *chime(10.6, 0.3))


BREAK_JOBS = [
    ('intervalo', 6.0, intervalo, a_intervalo),
    ('voltamos', 4.48, voltamos, a_voltamos),
    ('anuncie', 15.0, anuncie, a_anuncie),
    ('promo_loja', 16.0, promo_loja, a_promo_loja),
    ('promo_retrotv', 14.0, promo_retrotv, a_promo_retrotv),
]


if __name__ == '__main__':
    only = set(sys.argv[2:])
    jobs = [
        ('ident_barras', 5.8, ident_bars, lambda d: mix(d, (0.6, tone(N(48), 1.4, 'sine', 0.2, 0.3, 0.6)), *chime(1.5, 0.35))),
        ('ident_tubo', 5.0, ident_tube, lambda d: mix(d, (0, tone(60, d, 'sine', 0.06, 0.2, 4)), (0, noise(0.9, 0.05)), *chime(1.0, 0.35))),
        ('apresenta', 3.6, presents, lambda d: mix(d, *[(0.2 + i * 0.3, bell(N(m), 1.4, 0.6, 0.25)) for i, m in enumerate([72, 79])])),
        ('vinheta_terror', 7.0, v_terror, a_terror),
        ('vinheta_muda', 7.0, v_muda, a_muda),
        ('vinheta_desenhos', 6.4, v_toons, a_toons),
        ('vinheta_ficcao', 7.0, v_ficcao, a_ficcao),
        ('vinheta_noir', 7.0, v_noir, a_noir),
        ('vinheta_cult', 7.0, v_cult, a_cult),
        ('vinheta_series', 7.0, v_series, a_series),
        ('vinheta_comedia', 7.0, v_comedia, a_comedia),
        ('vinheta_classicos', 7.0, v_classicos, a_classicos),
        ('vinheta_aventura', 7.0, v_aventura, a_aventura),
        ('vinheta_faroeste', 7.0, v_faroeste, a_faroeste),
        ('vinheta_seriados', 7.0, v_seriados, a_seriados),
        ('vinheta_docs', 7.0, v_docs, a_docs),
        ('vinheta_domingo', 7.0, v_domingo, a_domingo),
    ]
    jobs += BREAK_JOBS  # the commercial break: intervalo, voltamos, the sponsor slot, the Store and Retrotv promos
    for name, dur, draw, aud in jobs:
        if not only or name in only:
            render(name, dur, draw, aud(dur))
    if not only or 'cartao' in only:
        render('cartao', 30.0, card, card_audio(30.0), loop=True)
    if not only or 'tecnicos' in only:
        render('tecnicos', 12.0, tecnicos, tecnicos_audio(12.0), loop=True)
