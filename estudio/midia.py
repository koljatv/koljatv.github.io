"""Videos: probing, converting to the channel's format, the programmes' vignettes, and the background jobs that do
the slow work while the page stays responsive."""
import glob, json, os, shutil, subprocess, threading, time, traceback, uuid

import canal

FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"

# ---------------- jobs ----------------

JOBS = {}


class Job:
    def __init__(self, titulo):
        self.id, self.titulo, self.pct, self.msg, self.estado = uuid.uuid4().hex[:10], titulo, 0, "", "rodando"
        self.log, self.inicio, self.resultado = [], time.time(), None
        JOBS[self.id] = self

    def say(self, msg, pct=None):
        self.msg = msg
        if pct is not None: self.pct = max(0, min(100, pct))
        self.log.append(time.strftime("%H:%M:%S ") + msg)

    def view(self):
        return {"id": self.id, "titulo": self.titulo, "pct": round(self.pct), "msg": self.msg, "estado": self.estado,
                "log": self.log[-40:], "resultado": self.resultado}


def run(titulo, fn, *a):
    """Runs fn(job, *a) in the background; its return value is the job's result. Errors become a plain message."""
    j = Job(titulo)

    def go():
        try:
            j.resultado = fn(j, *a)
            j.estado, j.pct = "pronto", 100
            if not j.msg or j.msg.endswith("..."): j.say("Pronto.")
        except Exception as e:
            j.estado = "erro"
            j.say("Erro: %s" % e)
            j.log.append(traceback.format_exc()[-1500:])
    threading.Thread(target=go, daemon=True).start()
    return j


def jobs():
    old = [k for k, j in JOBS.items() if j.estado != "rodando" and time.time() - j.inicio > 6 * 3600]
    for k in old: JOBS.pop(k, None)
    return [j.view() for j in sorted(JOBS.values(), key=lambda j: -j.inicio)]


# ---------------- probing and converting ----------------

def probe(p):
    """{dur, w, h, fps, audio} of a video, or raises with a plain message."""
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate",
                        "-of", "json", p], capture_output=True, text=True, timeout=120)
    if r.returncode: raise RuntimeError("Não consegui ler este vídeo (o arquivo está inteiro? é um vídeo?).")
    j = json.loads(r.stdout)
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v: raise RuntimeError("Este arquivo não tem imagem de vídeo.")
    n, d = (v.get("r_frame_rate") or "25/1").split("/")
    fps = float(n) / float(d or 1) if float(d or 1) else 25.0
    return {"dur": float(j.get("format", {}).get("duration") or 0), "w": v.get("width"), "h": v.get("height"),
            "fps": fps, "audio": any(s.get("codec_type") == "audio" for s in j.get("streams", []))}


def convert(job, src, dst, w=854, h=480, lo=0, hi=100):
    """Any video to the channel's format: H.264 up to 854x480 (letterboxed to 16:9), at most 30 fps, AAC stereo,
    loudness evened out (so it doesn't jump in volume next to the films), moov at the front for streaming."""
    info = probe(src)
    if info["dur"] < 1: raise RuntimeError("O vídeo parece vazio (menos de 1 segundo).")
    fps = info["fps"] if 0 < info["fps"] <= 30.5 else (info["fps"] / 2 if info["fps"] <= 61 else 30)
    vf = "scale=w=%d:h=%d:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=black,fps=%.3f,format=yuv420p" % (w, h, w, h, fps)
    tmp = dst + ".part.mp4"
    cmd = [FFMPEG, "-v", "error", "-y", "-i", src]
    if not info["audio"]:  # a silent track, so every piece has sound the same way
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest"]
    cmd += ["-map", "0:v:0", "-map", "0:a:0" if info["audio"] else "1:a:0", "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-maxrate", "1500k", "-bufsize", "3000k",
            "-profile:v", "main", "-g", str(int(round(fps * 2))), "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]
    if info["audio"]: cmd += ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]
    cmd += ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", tmp]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in p.stdout:
        if line.startswith("out_time_ms="):
            try: done = int(line.split("=")[1]) / 1e6
            except ValueError: continue
            job.say("Convertendo... %d%%" % min(99, 100 * done / info["dur"]), lo + (hi - lo) * min(1, done / info["dur"]))
    err = p.stderr.read()
    if p.wait():
        if os.path.exists(tmp): os.remove(tmp)
        raise RuntimeError("A conversão falhou: " + (err.strip().splitlines() or ["?"])[-1][:200])
    os.replace(tmp, dst)
    out = probe(dst)
    return round(out["dur"], 2)


# ---------------- the vignettes ----------------

def pil_python():
    """A python that has PIL and numpy (the vignettes are drawn with them)."""
    cands = [os.path.expanduser("~/Library/Application Support/Estudio KOLJA TV/venv/bin/python3"),
             os.path.expanduser("~/ComfyUI/.venv/bin/python3"), shutil.which("python3") or "", "/usr/bin/python3"]
    for c in cands:
        if c and os.path.exists(c):
            r = subprocess.run([c, "-c", "import PIL, numpy"], capture_output=True)
            if r.returncode == 0: return c
    return None


def vinhetas(job, pid):
    """Makes the programme's abertura and encerramento with its current name and slots."""
    pr = canal.programa(pid)
    if not pr: raise RuntimeError("Programa não encontrado.")
    py = pil_python()
    if not py: raise RuntimeError("Falta o desenhista das vinhetas (Python com PIL e numpy). Rode 'instalar.command' de novo.")
    out = os.path.join(canal.MEDIA, "programas", pid)
    job.say("Desenhando a abertura e o encerramento...", 10)
    r = subprocess.run([py, os.path.join(canal.HERE, "vinheta.py"), out, pid, pr["nome"], "--quando", canal.quando(pr),
                        "--estilo", pr.get("estilo", "ambar")], capture_output=True, text=True, timeout=600)
    if r.returncode: raise RuntimeError("As vinhetas falharam: " + r.stderr.strip()[-300:])
    res = json.loads(r.stdout.strip().splitlines()[-1])
    with canal.LOCK:
        l = canal.programas()
        p = next(x for x in l if x["id"] == pid)
        for k in ("abertura", "encerramento"):
            f = os.path.join(out, res[k]["file"])
            p[k] = {"file": "programas/%s/%s" % (pid, res[k]["file"]), "dur": res[k]["dur"], "sha": canal.sha(f), "url": None}
        p["vinheta_nome"], p["vinheta_quando"], p["vinheta_estilo"] = pr["nome"], canal.quando(pr), pr.get("estilo", "ambar")
        canal.save_programas(l)
    job.say("Vinhetas prontas.", 100)


def vinhetas_velhas(pr):
    """True when the name, slots or style changed since the vignettes were made."""
    return not pr.get("abertura") or (pr.get("vinheta_nome"), pr.get("vinheta_quando"), pr.get("vinheta_estilo")) != \
        (pr["nome"], canal.quando(pr), pr.get("estilo", "ambar"))


# ---------------- uploads into the Estúdio ----------------

INBOX = os.path.join(canal.MEDIA, "entrada")


def episodio(job, pid, src, titulo):
    """A new episode: convert it, put it on the programme (newest last), drop the original copy."""
    pr = canal.programa(pid)
    if not pr: raise RuntimeError("Programa não encontrado.")
    eid = "ep-" + time.strftime("%Y%m%d-%H%M%S")
    out = os.path.join(canal.MEDIA, "programas", pid)
    os.makedirs(out, exist_ok=True)
    dst = os.path.join(out, eid + ".mp4")
    job.say("Lendo o vídeo...", 2)
    dur = convert(job, src, dst, lo=3, hi=95)
    job.say("Conferindo...", 97)
    e = {"id": eid, "titulo": titulo or ("Episódio de " + time.strftime("%d/%m/%Y")), "file": "programas/%s/%s.mp4" % (pid, eid),
         "dur": dur, "sha": canal.sha(dst), "url": None, "enviado": canal.now_iso(), "mb": round(os.path.getsize(dst) / 1e6, 1)}
    with canal.LOCK:
        l = canal.programas()
        p = next(x for x in l if x["id"] == pid)
        p.setdefault("episodios", []).append(e)  # "substituir": the newest published one airs; the older go at publishing
        canal.save_programas(l)
    try: os.remove(src)
    except OSError: pass
    m, s = divmod(int(dur), 60)
    job.say("Episódio pronto: %d min %02d s." % (m, s), 100)
    return e


def anuncio(job, aid, src):
    a = next((x for x in canal.anuncios() if x["id"] == aid), None)
    if not a: raise RuntimeError("Anúncio não encontrado.")
    out = os.path.join(canal.MEDIA, "anuncios")
    os.makedirs(out, exist_ok=True)
    dst = os.path.join(out, aid + ".mp4")
    job.say("Convertendo o anúncio...", 5)
    info = probe(src)
    if info["dur"] > 120: raise RuntimeError("Um anúncio pode ter no máximo 2 minutos (este tem %d s)." % info["dur"])
    dur = convert(job, src, dst, 640, 360, 5, 95)
    with canal.LOCK:
        l = canal.anuncios()
        x = next(x for x in l if x["id"] == aid)
        x.update({"file": "anuncios/%s.mp4" % aid, "dur": dur, "sha": canal.sha(dst), "url": None})
        canal.save_anuncios(l)
    try: os.remove(src)
    except OSError: pass
    job.say("Anúncio pronto: %.1f s." % dur, 100)


def limpar_entrada():
    for f in glob.glob(os.path.join(INBOX, "*")):
        if time.time() - os.path.getmtime(f) > 24 * 3600:
            try: os.remove(f)
            except OSError: pass
