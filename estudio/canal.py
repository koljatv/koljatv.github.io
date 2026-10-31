"""The channel's files, as the Estúdio reads and writes them: catalog/*.json in the repo, media/ (not in git) for
our videos. Everything here works offline."""
import datetime as dt, hashlib, json, os, re, subprocess, sys, threading, unicodedata
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("KTV_REPO") or os.path.dirname(HERE)
CAT = os.path.join(REPO, "catalog")
MEDIA = os.path.join(REPO, "media")
sys.path.insert(0, os.path.join(REPO, "tools"))
PRIV = os.environ.get("KTV_PRIVATE") or os.path.expanduser("~/Documents/Developer/koljatv-private")  # local only
EVID = os.path.join(PRIV, "catalog", "evidence.json")
if os.path.isdir(os.path.join(PRIV, "tools")): sys.path.append(os.path.join(PRIV, "tools"))
NOTES = ("pd", "pd_us", "pd_br")  # a title's notes: kept in EVID, never in the repo

LOCK = threading.RLock()  # one writer at a time (the page and the background jobs)
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def path(*p): return os.path.join(REPO, *p)


def read(name, default=None):
    p = os.path.join(CAT, name)
    if not os.path.exists(p): return default
    with open(p, encoding="utf-8") as f: return json.load(f)


def write(name, data, indent=1):
    """Atomic: a crash halfway never leaves half a file."""
    with LOCK:
        p = os.path.join(CAT, name)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        os.replace(tmp, p)


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "item"


def sha(p, n=1 << 20):
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(n), b""): h.update(b)
    return h.hexdigest()


def now_iso(): return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def cfg(): return read("grade.json")


def tz(): return ZoneInfo(cfg().get("tz", "America/Sao_Paulo"))


# ---------------- programmes ----------------

def programas():
    return (read("programas.json") or {}).get("programas", [])


def save_programas(l):
    write("programas.json", {"note": "KÖLJA TV's own programmes, kept by the Estúdio KÖLJA TV app (estudio/). Files "
                                     "are in media/ (not in git) until published; url is where the app plays them from.",
                             "programas": l})


def programa(pid):
    return next((p for p in programas() if p["id"] == pid), None)


def quando(pr):
    """'SEG A SEX · 20H' for the closing vignette, from the programme's slots."""
    out = []
    for h in pr.get("horarios", []):
        d = sorted(h.get("dias", []))
        if not d: continue
        if d == list(range(7)): dias = "TODO DIA"
        elif len(d) > 2 and d == list(range(d[0], d[-1] + 1)): dias = "%s A %s" % (DIAS[d[0]].upper(), DIAS[d[-1]].upper())
        else: dias = ", ".join(DIAS[x].upper() for x in d)
        hh, mm = h["at"].split(":")
        out.append("%s · %sH%s" % (dias, int(hh), "" if mm == "00" else mm))
    return "  ".join(out[:2])


def check_programa(pr, others):
    """Problems in plain words, or [] when it's fine."""
    err = []
    if not pr.get("nome", "").strip(): err.append("O programa precisa de um nome.")
    for h in pr.get("horarios", []):
        if not re.fullmatch(r"\d\d:\d\d", h.get("at", "")) or int(h["at"][:2]) > 23 or int(h["at"][3:]) > 59:
            err.append("Horário inválido: %s (use 20:00)." % h.get("at"))
        if not h.get("dias"): err.append("Escolha pelo menos um dia para o horário %s." % h.get("at"))
    dur = max([e.get("dur", 0) for e in pr.get("episodios", [])] or [0]) + 11
    for h in pr.get("horarios", []):
        try: m = int(h["at"][:2]) * 60 + int(h["at"][3:])
        except Exception: continue
        if m * 60 + dur > 24 * 3600: err.append("No horário %s o episódio passaria da meia-noite: escolha um horário mais cedo." % h["at"])
        for o in others:
            if o["id"] == pr.get("id") or o.get("ativo") is False: continue
            od = max([e.get("dur", 0) for e in o.get("episodios", [])] or [0]) + 11
            for oh in o.get("horarios", []):
                om = int(oh["at"][:2]) * 60 + int(oh["at"][3:])
                if set(oh.get("dias", [])) & set(h.get("dias", [])) and m * 60 < om * 60 + od and om * 60 < m * 60 + dur:
                    err.append("O horário %s bate com \"%s\" (%s)." % (h["at"], o["nome"], oh["at"]))
    return err


# ---------------- ads ----------------

def anuncios():
    return (read("anuncios.json") or {}).get("anuncios", [])


def save_anuncios(l):
    write("anuncios.json", {"note": "Paid spots in the features' commercial breaks, kept by the Estúdio KÖLJA TV app. "
                                    "por_dia: insertions a day anywhere; por_bloco: insertions a day per block.",
                            "anuncios": l})


# ---------------- one-off edits of the grade ----------------

def manual():
    m = read("grade_manual.json") or {}
    m.setdefault("inserir", []); m.setdefault("remover", [])
    return m


def save_manual(m):
    today = dt.date.today().isoformat()  # edits of days gone by are dropped: they no longer change anything
    m["inserir"] = sorted([x for x in m["inserir"] if x["data"] >= today], key=lambda x: (x["data"], x["at"]))
    m["remover"] = sorted([x for x in m["remover"] if x["data"] >= today], key=lambda x: (x["data"], x.get("at", "")))
    m["note"] = "One-off edits of a date, kept by the Estúdio KÖLJA TV app: inserir puts a title (or prog:<id>) at a time; remover takes one off that date."
    write("grade_manual.json", m)


# ---------------- titles (the films) ----------------

def _notas():
    try:
        with open(EVID, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return {}


def titulos():
    l, ev = read("titles.json", []), _notas()
    for t in l: t.update(ev.get(t["id"], {}))
    return l


def save_titulos(l):
    ev, out = _notas(), []
    for t in l:
        t = dict(t)
        e = {k: t.pop(k) for k in NOTES if k in t}
        if e:
            ev[t["id"]] = e
            r = {"us": e["pd_us"] if "pd_us" in e else bool((e.get("pd") or {}).get("basis"))}
            if "pd_br" in e: r["br"] = e["pd_br"]
            t["rights"] = r
        if "sources" in t: t["sources"] = t.pop("sources")
        out.append(t)
    if ev:
        os.makedirs(os.path.dirname(EVID), exist_ok=True)
        tmp = EVID + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(ev, f, indent=1, ensure_ascii=False)
        os.replace(tmp, EVID)
    write("titles.json", out)


def breaks():
    return read("breaks.json", {}) or {}


def save_breaks(b):
    write("breaks.json", b)


# ---------------- git (local, offline) ----------------

def git(*a, check=False, env=None, timeout=120):
    e = dict(os.environ, GIT_TERMINAL_PROMPT="0", **(env or {}))
    r = subprocess.run(["git", "-C", REPO] + list(a), capture_output=True, text=True, env=e, timeout=timeout)
    if check and r.returncode: raise RuntimeError((r.stderr or r.stdout).strip()[-600:])
    return r


FILES = ["catalog/programas.json", "catalog/anuncios.json", "catalog/grade_manual.json", "catalog/titles.json",
         "catalog/breaks.json", "catalog/grade.json"]
NOMES = {"catalog/programas.json": "Programas próprios", "catalog/anuncios.json": "Anúncios",
         "catalog/grade_manual.json": "Mudanças na grade", "catalog/titles.json": "Filmes (catálogo)",
         "catalog/breaks.json": "Intervalos dos filmes", "catalog/grade.json": "Blocos do dia"}


def pendentes():
    """What changed here since the last commit (the Estúdio publishes these)."""
    r = git("status", "--porcelain", "--", "catalog/")
    out = []
    for line in r.stdout.splitlines():
        f = line[3:].strip().strip('"')
        out.append({"arquivo": f, "nome": NOMES.get(f, f)})
    return out
