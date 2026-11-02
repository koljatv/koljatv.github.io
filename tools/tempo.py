#!/usr/bin/env python3
"""KÖLJA TV's weather forecast (PREVISÃO DO TEMPO): the 27 state capitals, today and the next days, from Open-Meteo
(free, no key). It airs at fixed times of the day as a short segment of its own, a video made from the latest
forecast (tools/tempo_video.py), and the site has a page with the same forecast (public/tempo/).

  python3 tools/tempo.py due        prints "yes" when the forecast should be fetched again now (and the video redone)
  python3 tools/tempo.py fetch      fetches it into state/tempo/previsao.json
  python3 tools/tempo.py publish    copies the forecast and its video into public/ (the site), when they're fresh
  python3 tools/tempo.py svg        writes public/tempo/mapa.svg (the page's map; in git)

The workflow runs these every 20 minutes. The forecast is fetched again every few hours, and shortly before each
airing when it is more than an hour old. state/ is kept between runs in the Actions cache, not in git.

In the schedule (build.py): from FROM on, every slot of the day that has an airing time in it is laid out
DUR shorter, and its station card covers the time that's left; then the forecast goes in at the nearest point
between two programmes (or in a cartoon block's INTERVALO, or in the card), and the rest of the slot moves on into
the card, so the next slot starts on time. An airing only goes in when a video from a forecast at most MAX_AGE old
was published before it; otherwise the station card stays (no old weather on the air). This depends only on the
date and on when forecasts were rendered, so a slot never changes once it has the forecast in it.
"""
import datetime as dt, hashlib, json, os, shutil, sys, urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "state", "tempo")
TZ = ZoneInfo("America/Sao_Paulo")
MIN, HOUR = 60_000, 3_600_000

ID = "previsao-tempo"  # a hyphen: Retrotv keeps only [a-z0-9_].mp4 pieces on the phone, so it always streams this one fresh
DUR = 72.0             # seconds; tempo_video.py makes it exactly this long
TITLE = "Previsão do tempo"
URL = "https://tv.kolja.com.br/tv/ours/" + ID + ".mp4"
FROM = "2026-11-02"    # first date laid out with the forecast's time (earlier dates keep their layout)
AT = ["07:00", "12:55", "18:55", "23:55"]
MAX_AGE = 12 * HOUR    # an airing needs a forecast at most this old
REFRESH = 150 * MIN    # fetch again after this long...
BEFORE = 75 * MIN      # ...or, when an airing is this close,
FRESH = 55 * MIN       # if the forecast is older than this
API = "https://api.open-meteo.com/v1/forecast"
DAYS = 4

# id, name, state, region, lat, lon, on the national map
CITIES = [
    ("manaus", "Manaus", "AM", "N", -3.119, -60.022, True),
    ("belem", "Belém", "PA", "N", -1.456, -48.490, True),
    ("porto-velho", "Porto Velho", "RO", "N", -8.762, -63.904, True),
    ("rio-branco", "Rio Branco", "AC", "N", -9.975, -67.810, False),
    ("boa-vista", "Boa Vista", "RR", "N", 2.820, -60.672, True),
    ("macapa", "Macapá", "AP", "N", 0.035, -51.070, False),
    ("palmas", "Palmas", "TO", "N", -10.184, -48.333, True),
    ("sao-luis", "São Luís", "MA", "NE", -2.530, -44.303, True),
    ("teresina", "Teresina", "PI", "NE", -5.089, -42.802, False),
    ("fortaleza", "Fortaleza", "CE", "NE", -3.732, -38.527, True),
    ("natal", "Natal", "RN", "NE", -5.795, -35.209, False),
    ("joao-pessoa", "João Pessoa", "PB", "NE", -7.115, -34.864, False),
    ("recife", "Recife", "PE", "NE", -8.048, -34.877, True),
    ("maceio", "Maceió", "AL", "NE", -9.666, -35.735, False),
    ("aracaju", "Aracaju", "SE", "NE", -10.947, -37.073, False),
    ("salvador", "Salvador", "BA", "NE", -12.971, -38.501, True),
    ("brasilia", "Brasília", "DF", "CO", -15.794, -47.882, True),
    ("goiania", "Goiânia", "GO", "CO", -16.686, -49.265, False),
    ("cuiaba", "Cuiabá", "MT", "CO", -15.601, -56.097, True),
    ("campo-grande", "Campo Grande", "MS", "CO", -20.469, -54.620, True),
    ("sao-paulo", "São Paulo", "SP", "SE", -23.550, -46.633, True),
    ("rio-de-janeiro", "Rio de Janeiro", "RJ", "SE", -22.907, -43.173, True),
    ("belo-horizonte", "Belo Horizonte", "MG", "SE", -19.917, -43.935, True),
    ("vitoria", "Vitória", "ES", "SE", -20.315, -40.312, False),
    ("curitiba", "Curitiba", "PR", "S", -25.428, -49.273, True),
    ("florianopolis", "Florianópolis", "SC", "S", -27.595, -48.548, False),
    ("porto-alegre", "Porto Alegre", "RS", "S", -30.035, -51.218, True),
]
REGIONS = [("N", "Norte"), ("NE", "Nordeste"), ("CO", "Centro-Oeste"), ("SE", "Sudeste"), ("S", "Sul")]


def condition(code):
    """WMO weather code -> (icon, words)."""
    c = int(code)
    if c == 0: return "sol", "Céu claro"
    if c == 1: return "sol", "Predomínio de sol"
    if c == 2: return "sol-nuvens", "Sol entre nuvens"
    if c == 3: return "nublado", "Nublado"
    if c in (45, 48): return "nevoeiro", "Nevoeiro"
    if 51 <= c <= 57: return "garoa", "Garoa"
    if 61 <= c <= 67: return "chuva", "Chuva"
    if 71 <= c <= 77 or c in (85, 86): return "neve", "Neve"
    if 80 <= c <= 82: return "pancadas", "Pancadas de chuva"
    if c >= 95: return "trovoada", "Chuva com trovoadas"
    return "nublado", "Nublado"


def now_ms(): return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def read(p, default=None):
    if not os.path.exists(p): return default
    with open(p, encoding="utf-8") as f: return json.load(f)


def write(p, obj, pretty=False):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, **({"indent": 1} if pretty else {"separators": (",", ":")}))
    os.replace(p + ".tmp", p)


def airings(after, until):
    """The airing times (ms) in [after, until)."""
    out, d = [], dt.datetime.fromtimestamp(after / 1000, TZ).date()
    while True:
        for a in AT:
            t = int(dt.datetime(d.year, d.month, d.day, int(a[:2]), int(a[3:]), tzinfo=TZ).timestamp() * 1000)
            if t >= until: return out
            if t >= after: out.append(t)
        d += dt.timedelta(days=1)


# ---------------- the forecast ----------------

def fetch():
    q = {"latitude": ",".join(str(c[4]) for c in CITIES), "longitude": ",".join(str(c[5]) for c in CITIES),
         "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
         "timezone": "auto", "forecast_days": str(DAYS)}
    url = API + "?" + "&".join(f"{k}={v}" for k, v in q.items())
    req = urllib.request.Request(url, headers={"User-Agent": "KOLJA-TV-previsao/1 (tv.kolja.com.br)"})
    raw = json.load(urllib.request.urlopen(req, timeout=40))
    if isinstance(raw, dict): raw = [raw]
    if len(raw) != len(CITIES): raise SystemExit("open-meteo: %d answers for %d cities" % (len(raw), len(CITIES)))
    cities = []
    for c, r in zip(CITIES, raw):
        d = r["daily"]
        days = []
        for k, day in enumerate(d["time"]):
            vals = [d["weather_code"][k], d["temperature_2m_max"][k], d["temperature_2m_min"][k]]
            if any(v is None for v in vals): continue
            icon, words = condition(vals[0])
            rain = d["precipitation_probability_max"][k]
            days.append({"data": day, "cod": int(vals[0]), "icone": icon, "tempo": words,
                         "max": round(vals[1]), "min": round(vals[2]), "chuva": None if rain is None else int(rain)})
        cities.append({"id": c[0], "nome": c[1], "uf": c[2], "regiao": c[3], "lat": c[4], "lon": c[5], "mapa": c[6], "dias": days})
    if sum(len(c["dias"]) >= 2 for c in cities) < len(CITIES) - 2: raise SystemExit("open-meteo: too few days")
    t = now_ms()
    out = {"format": 1, "gerado": t, "gerado_brt": dt.datetime.fromtimestamp(t / 1000, TZ).strftime("%Y-%m-%d %H:%M"),
           "fuso": "America/Sao_Paulo", "fonte": "Open-Meteo.com", "licenca": "CC BY 4.0",
           "regioes": [{"id": k, "nome": n} for k, n in REGIONS], "cidades": cities,
           "note": "KÖLJA TV weather: daily forecast for the state capitals. gerado: when it was fetched (ms since 1970, UTC). "
                   "Each city's days are its own local dates; max/min in °C, chuva = chance of rain (%)."}
    write(os.path.join(STATE, "previsao.json"), out)
    print("fetched %d cities, %s" % (len(cities), out["gerado_brt"]))
    return out


def render_revision():
    """Invalidate a cached video when its renderer or music changes."""
    h = hashlib.sha256()
    for name in ("tempo_video.py", "meteo/trilha.m4a"):
        with open(os.path.join(ROOT, "tools", name), "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
    return h.hexdigest()[:16]


def due(t=None):
    t = t or now_ms()
    p = read(os.path.join(STATE, "previsao.json"))
    v = read(os.path.join(STATE, "video.json"))
    if not p or not v or v.get("gerado") != p.get("gerado") or not os.path.exists(os.path.join(STATE, ID + ".mp4")): return True
    if v.get("render_revision") != render_revision(): return True
    age = t - p["gerado"]
    if age >= REFRESH: return True
    return age >= FRESH and bool(airings(t, t + BEFORE))


def rendered(data_ms):
    """tempo_video.py made a video from the forecast fetched at data_ms: the schedule may use it from now on."""
    write(os.path.join(STATE, "video.json"), {"gerado": data_ms, "feito": now_ms(), "render_revision": render_revision()})
    h = read(os.path.join(STATE, "renders.json"), {"renders": []})
    r = sorted(set(h["renders"]) | {data_ms})
    write(os.path.join(STATE, "renders.json"), {"renders": [x for x in r if x > now_ms() - 5 * 24 * HOUR]})


def publish():
    """The site's copies: public/tempo/previsao.json (the page) and the segment's video, when the forecast is fresh."""
    p = read(os.path.join(STATE, "previsao.json"))
    v = read(os.path.join(STATE, "video.json"))
    mp4 = os.path.join(STATE, ID + ".mp4")
    if not p or now_ms() - p["gerado"] > MAX_AGE:
        print("tempo: no fresh forecast, nothing published"); return
    write(os.path.join(ROOT, "public", "tempo", "previsao.json"), p)
    if v and os.path.exists(mp4):
        os.makedirs(os.path.join(ROOT, "public", "tv", "ours"), exist_ok=True)
        shutil.copyfile(mp4, os.path.join(ROOT, "public", "tv", "ours", ID + ".mp4"))
    print("tempo: published the forecast of", p["gerado_brt"], "(video: %s)" % ("yes" if v and os.path.exists(mp4) else "no"))


# ---------------- in the schedule (build.py) ----------------

class Tempo:
    def __init__(self, g, Prog, renders=None):
        self.g = g
        self.prog = Prog(ID, "tempo", DUR)
        self.prog.title = TITLE
        self.start = (dt.date.fromisoformat(FROM) - dt.date(1970, 1, 1)).days
        if renders is None: renders = (read(os.path.join(STATE, "renders.json"), {}) or {}).get("renders", [])
        self.renders = sorted(renders)
        self.slots = {}  # day -> [(from, to, block)] of the slots fill() laid out

    def ours(self):
        video = read(os.path.join(STATE, "video.json"), {}) or {}
        revision = str(video.get("gerado", 0)) + "-" + video.get("render_revision", "legacy")
        return {"kind": "tempo", "dur": DUR, "title": TITLE, "url": URL + "?v=" + revision, "media_rev": revision}

    def times(self, d):
        base = self.g.midnight(d)
        return [base + (int(a[:2]) * 60 + int(a[3:])) * MIN for a in AT]

    def reserve(self, d, frm, to, block):
        """Called by _day for each slot fill() lays out: how much of it (ms) to leave for the forecast."""
        self.slots.setdefault(d, []).append((frm, to, block))
        if d < self.start: return 0
        return sum(int(DUR * 1000) for t in self.times(d) if frm <= t < to)

    def pad(self, out, frm, to, block):
        """The reserved end of a slot: the station card (the one closing the slot grows, or a new one)."""
        card = self.g.card
        if not card or to <= frm: return
        if out and out[-1][2] is card and out[-1][1] == frm and len(out[-1]) == 4: out[-1][1] = to
        else: out.append([frm, to, card, block])

    def fresh(self, t):
        return any(t - MAX_AGE <= r <= t for r in self.renders)

    def place(self, items, d):
        """Day d's items (expanded, before the spots): the forecast at each airing time with a fresh video."""
        slots = self.slots.get(d, [])
        if not slots: return items
        D, card = int(DUR * 1000), self.g.card
        for T in self.times(d):
            seg = next(((a, b, blk) for a, b, blk in slots if a <= T < b), None)
            if not seg or not card: continue
            a, b, blk = seg
            idx = [k for k, it in enumerate(items) if a <= it[0] < b and it[3] == blk]
            if not idx: continue
            last = idx[-1]
            tail = items[last]
            if not (tail[2] is card and len(tail) == 4 and tail[1] - tail[0] >= D): continue
            best = None  # (distance, time, index or None for "inside the card")
            for k in idx:
                if k == idx[0] or k > last: continue
                it, prev = items[k], items[k - 1]
                if len(it) > 4 or len(prev) > 4: continue  # never inside a feature or its commercial break
                ok = (prev[2].kind in ("ident", "trailer") and it[2].id != "intervalo") or \
                     (it[2].id == "voltamos" and prev[2].id == "intervalo")
                if ok and k < last:
                    c = (abs(it[0] - T), it[0], k)
                    if best is None or c < best: best = c
            c = min(max(T, tail[0]), tail[1] - D)
            if best is None or (abs(c - T), c) < best[:2]: best = (abs(c - T), c, None)
            if best[0] > 45 * MIN or not self.fresh(best[1]): continue
            _, at, k = best
            if k is None:  # in the station card that closes the slot
                pieces = ([[tail[0], at, card, blk]] if at > tail[0] else []) + [[at, at + D, self.prog, blk]] + \
                         ([[at + D, tail[1], card, blk]] if tail[1] > at + D else [])
                items[last:last + 1] = pieces
            else:  # between two programmes: the rest of the slot moves on into the card
                moved = [[x[0] + D, x[1] + D] + x[2:] for x in items[k:last]]
                end = [[tail[0] + D, tail[1], card, blk]] if tail[1] > tail[0] + D else []
                items[k:last + 1] = [[at, at + D, self.prog, blk]] + moved + end
        return items


def svg_map(out=None):
    """public/tempo/mapa.svg: Brazil's states, and a pin for each city of the national map (the page fills them in)."""
    import math
    br = read(os.path.join(ROOT, "tools", "meteo", "brasil.json"))["uf"]
    k = math.cos(math.radians(15))
    xs = [x for r in br.values() for ring in r for x, _ in ring]
    ys = [y for r in br.values() for ring in r for _, y in ring]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    pl, pr, pv = 60, 150, 40  # room for the labels: more on the right (the coast's cities label to the east)
    sc = (1000 - pl - pr) / ((x1 - x0) * k)
    h = round((y1 - y0) * sc + 2 * pv)
    P = lambda lon, lat: (pl + (lon - x0) * k * sc, pv + (y1 - lat) * sc)
    paths = []
    for uf, rings in sorted(br.items()):
        d = " ".join("M" + " ".join("%.1f %.1f" % P(x, y) for x, y in ring) + "Z" for ring in rings)
        paths.append('<path data-uf="%s" d="%s"/>' % (uf, d))
    pins = "".join('<g class="pin" data-id="%s" transform="translate(%.1f %.1f)"></g>' % ((c[0],) + P(c[5], c[4])) for c in CITIES if c[6])
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 %d" role="img" aria-label="Mapa do Brasil com as capitais">'
           '<g class="uf">%s</g><g class="pins">%s</g></svg>\n') % (h, "".join(paths), pins)
    out = out or os.path.join(ROOT, "public", "tempo", "mapa.svg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write(svg)
    print("wrote", out, len(svg), "bytes")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "due"
    if cmd == "due": print("yes" if due() else "no")
    elif cmd == "svg": svg_map()
    elif cmd == "fetch": fetch()
    elif cmd == "publish": publish()
    else: raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
