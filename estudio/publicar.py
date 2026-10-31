"""Publishing: the token in the macOS Keychain, our videos up as GitHub Release assets (or to the Internet Archive),
the catalogue committed and pushed to koljatv/koljatv.github.io, a pub-* tag per publication, and going back to
an earlier one. The only part of the Estúdio that needs the internet."""
import datetime as dt, http.client, json, os, re, shutil, ssl, subprocess, sys, tempfile, time, urllib.parse, urllib.request

import canal, grade

SUPPORT = os.path.expanduser("~/Library/Application Support/Estudio KOLJA TV")
CONF = os.path.join(SUPPORT, "config.json")
KEY = "Estudio KOLJA TV"
UA = "estudio-koljatv/1.0"
RELEASE = "estudio-midia"  # our programmes' episodes, their vignettes and the spots live in this release


def conf():
    c = {"repo": "koljatv/koljatv.github.io", "branch": "main", "destino": "github", "remote": "origin"}
    try: c.update(json.load(open(CONF)))
    except Exception: pass
    if os.environ.get("KTV_TEST_UPLOAD_DIR"): c["teste"] = True
    return c


def save_conf(c):
    os.makedirs(SUPPORT, exist_ok=True)
    json.dump({k: v for k, v in c.items() if k != "teste"}, open(CONF, "w"), indent=1)


# ---------------- Keychain ----------------

def secret(name):
    r = subprocess.run(["security", "find-generic-password", "-s", KEY, "-a", name, "-w"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def set_secret(name, value):
    subprocess.run(["security", "delete-generic-password", "-s", KEY, "-a", name], capture_output=True)
    if value:
        r = subprocess.run(["security", "add-generic-password", "-s", KEY, "-a", name, "-w", value, "-U"], capture_output=True, text=True)
        if r.returncode: raise RuntimeError("Não consegui guardar no Chaveiro do Mac: " + r.stderr.strip())


def token():
    t = secret("github")
    if t: return t, "chaveiro"
    gh = shutil.which("gh") or "/opt/homebrew/bin/gh"
    if os.path.exists(gh):
        r = subprocess.run([gh, "auth", "token"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip(): return r.stdout.strip(), "gh"
    return "", ""


# ---------------- GitHub API ----------------

def api(method, url, tok, body=None, ctype="application/json", timeout=60):
    if not url.startswith("http"): url = "https://api.github.com" + url
    data = json.dumps(body).encode() if isinstance(body, (dict, list)) else body
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json", "User-Agent": UA,
        "X-GitHub-Api-Version": "2022-11-28", **({"Content-Type": ctype} if data is not None else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            t = r.read()
            return r.status, json.loads(t) if t else {}
    except urllib.error.HTTPError as e:
        t = e.read()
        try: return e.code, json.loads(t)
        except Exception: return e.code, {"message": t[:200].decode(errors="replace")}


def check_token(tok, repo):
    """(ok, message in plain words)."""
    if not tok: return False, "Nenhuma chave do GitHub guardada ainda."
    try:
        s, j = api("GET", "/repos/" + repo, tok, timeout=20)
    except Exception:
        return False, "Sem internet (ou o GitHub não respondeu). Para editar não precisa; para publicar, sim."
    if s == 401: return False, "A chave do GitHub não vale mais (expirou ou foi apagada). Cole uma nova."
    if s == 404: return False, "A chave não enxerga o repositório %s. Dê acesso a ele quando criar a chave." % repo
    if s != 200: return False, "GitHub respondeu %s: %s" % (s, j.get("message"))
    if not j.get("permissions", {}).get("push"):
        return False, "A chave só lê. Ela precisa de 'Contents: Read and write' no repositório %s." % repo
    return True, "Chave do GitHub ok (pode publicar em %s)." % repo


class GitHubRelease:
    def __init__(self, tok, repo):
        self.tok, self.repo, self.rel = tok, repo, None

    def release(self):
        if self.rel: return self.rel
        s, j = api("GET", "/repos/%s/releases/tags/%s" % (self.repo, RELEASE), self.tok)
        if s == 404:
            s, j = api("POST", "/repos/%s/releases" % self.repo, self.tok, {
                "tag_name": RELEASE, "name": "Estúdio: programas e anúncios",
                "body": "Episódios dos programas próprios, suas vinhetas e os anúncios, enviados pelo Estúdio KÖLJA TV. "
                        "Não apague: a grade aponta para estes arquivos."})
        if s not in (200, 201): raise RuntimeError("Não consegui abrir a área de vídeos no GitHub (%s: %s)." % (s, j.get("message")))
        self.rel = j
        return j

    def put(self, job, f, name, lo, hi):
        rel = self.release()
        for a in rel.get("assets", []):
            if a["name"] == name and a.get("size") == os.path.getsize(f):
                return a["browser_download_url"]  # already up (an earlier publication stopped halfway)
        size = os.path.getsize(f)
        host = "uploads.github.com"
        path = "/repos/%s/releases/%d/assets?name=%s" % (self.repo, rel["id"], urllib.parse.quote(name))
        c = http.client.HTTPSConnection(host, timeout=300, context=ssl.create_default_context())
        c.putrequest("POST", path)
        for k, v in {"Authorization": "Bearer " + self.tok, "Content-Type": "video/mp4", "Content-Length": str(size),
                     "Accept": "application/vnd.github+json", "User-Agent": UA}.items():
            c.putheader(k, v)
        c.endheaders()
        sent = 0
        with open(f, "rb") as fh:
            for b in iter(lambda: fh.read(1 << 20), b""):
                c.send(b); sent += len(b)
                job.say("Enviando %s... %d%%" % (name, 100 * sent / size), lo + (hi - lo) * sent / size)
        r = c.getresponse()
        t = r.read()
        if r.status == 422 and b"already_exists" in t:
            self.rel = None
            for a in self.release().get("assets", []):
                if a["name"] == name: return a["browser_download_url"]
        if r.status not in (200, 201): raise RuntimeError("O GitHub recusou o envio de %s (%s)." % (name, r.status))
        return json.loads(t)["browser_download_url"]


class InternetArchive:
    """Our own uploads to archive.org (S3-like API), with Niko's own keys (archive.org/account/s3.php)."""

    def __init__(self, access, secret_):
        self.auth = "LOW %s:%s" % (access, secret_)

    def put(self, job, f, name, lo, hi, item, title):
        size = os.path.getsize(f)
        c = http.client.HTTPSConnection("s3.us.archive.org", timeout=600, context=ssl.create_default_context())
        c.putrequest("PUT", "/%s/%s" % (item, urllib.parse.quote(name)))
        for k, v in {"authorization": self.auth, "x-amz-auto-make-bucket": "1", "x-archive-meta-mediatype": "movies",
                     "x-archive-meta-collection": "opensource_movies", "x-archive-meta-title": title.encode("utf-8").decode("latin-1", "replace"),
                     "x-archive-meta-creator": "KOLJA TV", "x-archive-queue-derive": "0", "Content-Length": str(size),
                     "Content-Type": "video/mp4"}.items():
            c.putheader(k, v)
        c.endheaders()
        sent = 0
        with open(f, "rb") as fh:
            for b in iter(lambda: fh.read(1 << 20), b""):
                c.send(b); sent += len(b)
                job.say("Enviando %s ao Internet Archive... %d%%" % (name, 100 * sent / size), lo + (hi - lo) * sent / size)
        r = c.getresponse(); r.read()
        if r.status not in (200, 201): raise RuntimeError("O Internet Archive recusou o envio (%s). Confira as chaves." % r.status)
        return "https://archive.org/download/%s/%s" % (item, urllib.parse.quote(name))


class Folder:
    """Tests only (KTV_TEST_UPLOAD_DIR): 'uploads' are copies into a folder."""

    def __init__(self, d): self.d = d

    def put(self, job, f, name, lo, hi, *a):
        os.makedirs(self.d, exist_ok=True)
        shutil.copy(f, os.path.join(self.d, name))
        job.say("(teste) copiado %s" % name, hi)
        return os.environ.get("KTV_TEST_UPLOAD_URL", "http://127.0.0.1:8798/midia/") + urllib.parse.quote(name)


# ---------------- what goes up ----------------

def pending_media():
    """[(kind, owner, key, item dict)] of our videos with no address yet."""
    out = []
    for pr in canal.programas():
        for k in ("abertura", "encerramento"):
            v = pr.get(k)
            if v and not v.get("url"): out.append(("vinheta", pr, k, v))
        for e in pr.get("episodios", []):
            if not e.get("url"): out.append(("episodio", pr, e["id"], e))
    for a in canal.anuncios():
        if a.get("file") and not a.get("url"): out.append(("anuncio", a, a["id"], a))
    return out


def asset_name(kind, owner, key, x):
    return re.sub(r"[^a-z0-9]+", "-", "%s-%s-%s" % (kind, owner["id"], key.lower())).strip("-")[:90] + "-" + (x.get("sha") or "0")[:8] + ".mp4"


def validate(local=True):
    """Problems that would stop a publication, in plain words, and a few warnings."""
    errs, warns = [], []
    for name in canal.FILES:
        try:
            if os.path.exists(canal.path(name)): json.load(open(canal.path(name), encoding="utf-8"))
        except Exception as e:
            errs.append("O arquivo %s está com defeito (%s)." % (name, e))
    if errs: return errs, warns
    progs = canal.programas()
    for pr in progs:
        for e in canal.check_programa(pr, progs): errs.append("%s: %s" % (pr["nome"], e))
        if pr.get("ativo") is not False and not pr.get("episodios"): warns.append("\"%s\" ainda não tem episódio: não vai ao ar." % pr["nome"])
        if pr.get("episodios") and not pr.get("abertura"): warns.append("\"%s\" está sem vinhetas (vai ao ar sem abertura)." % pr["nome"])
    for kind, owner, key, x in pending_media():
        if not os.path.exists(os.path.join(canal.MEDIA, x.get("file", "-"))):
            errs.append("Falta o arquivo de vídeo de %s \"%s\" (%s). Envie de novo." % (kind, owner.get("nome", owner["id"]), key))
    for a in canal.anuncios():
        if not a.get("file"): warns.append("O anúncio \"%s\" ainda não tem vídeo." % a.get("nome", a["id"]))
    try:
        r = grade.preview(1, local=local)
        if not r["items"]: errs.append("A grade ficou vazia.")
    except Exception as e:
        errs.append("O gerador da grade falhou: %s" % e)
    return errs, warns


def summary():
    """What a publication would send: the files changed, the videos to upload, commits made outside the Estúdio."""
    c = conf()
    ahead = canal.git("log", "--oneline", "%s/%s..HEAD" % (c["remote"], c["branch"])).stdout.splitlines()
    return {"arquivos": canal.pendentes(), "videos": [{"tipo": k, "de": o.get("nome", o["id"]), "item": key,
                                                         "mb": round(os.path.getsize(os.path.join(canal.MEDIA, x["file"])) / 1e6, 1)
                                                         if os.path.exists(os.path.join(canal.MEDIA, x.get("file", "-"))) else 0}
                                                        for k, o, key, x in pending_media()],
            "commits_de_fora": ahead}


def git_env(tok):
    if not tok: return {}
    return {"KTV_TOKEN": tok, "GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "credential.helper", "GIT_CONFIG_VALUE_0": "",
            "GIT_CONFIG_KEY_1": "credential.helper",
            "GIT_CONFIG_VALUE_1": '!f() { echo username=x-access-token; echo "password=$KTV_TOKEN"; }; f'}


def ident():
    return ["-c", "user.name=KÖLJA TV Estúdio", "-c", "user.email=koljatv-estudio@users.noreply.github.com"]


def publish(job, ensaio=False, motivo=""):
    c = conf()
    job.say("Conferindo tudo antes de publicar...", 2)
    errs, warns = validate()
    for w in warns: job.say("Aviso: " + w)
    if errs: raise RuntimeError(" ".join(errs))
    s = summary()
    if not s["arquivos"] and not s["videos"] and not s["commits_de_fora"]:
        job.say("Não há nada novo para publicar.", 100)
        return {"nada": True}
    tok, onde = token()
    if not ensaio and not c.get("teste"):
        ok, msg = check_token(tok, c["repo"])
        if not ok: raise RuntimeError(msg)
        job.say(msg, 5)
    if ensaio:
        for v in s["videos"]: job.say("Enviaria: %s de \"%s\" (%s MB)" % (v["tipo"], v["de"], v["mb"]))
        for a in s["arquivos"]: job.say("Publicaria: " + a["nome"])
        for x in s["commits_de_fora"]: job.say("Iria junto (feito fora do Estúdio): " + x)
        job.say("Ensaio concluído: tudo certo, nada foi enviado.", 100)
        return {"ensaio": True, **s}
    # 1. our videos
    up = Folder(os.environ["KTV_TEST_UPLOAD_DIR"]) if c.get("teste") else GitHubRelease(tok, c["repo"])
    ia = None
    if c.get("destino") == "ia" and not c.get("teste"):
        acc, sec = secret("ia_access"), secret("ia_secret")
        if not acc or not sec: raise RuntimeError("Escolheu o Internet Archive mas faltam as chaves dele (Publicar > Configurar).")
        ia = InternetArchive(acc, sec)
    todo = pending_media()
    for n, (kind, owner, key, x) in enumerate(todo):
        lo, hi = 8 + 70 * n / max(1, len(todo)), 8 + 70 * (n + 1) / max(1, len(todo))
        f = os.path.join(canal.MEDIA, x["file"])
        name = asset_name(kind, owner, key, x)
        if kind == "episodio" and ia:
            item = owner.get("ia_item") or "koljatv-%s-%s" % (owner["id"], time.strftime("%Y%m%d"))
            url = ia.put(job, f, name, lo, hi, item, "KÖLJA TV - %s - %s" % (owner["nome"], x.get("titulo", key)))
            set_url("programa", owner["id"], key, url, ia_item=item)
        else:
            url = up.put(job, f, name, lo, hi)
            set_url("anuncio" if kind == "anuncio" else "programa", owner["id"], key, url)
    # 2. "substituir": the newest published episode replaces the older ones
    with canal.LOCK:
        l = canal.programas()
        for pr in l:
            if pr.get("modo", "substituir") == "substituir":
                live = [e for e in pr.get("episodios", []) if e.get("url")]
                if len(live) > 1: pr["episodios"] = [e for e in pr["episodios"] if e is live[-1] or not e.get("url")]
        canal.save_programas(l)
    job.say("Conferindo a grade com os endereços novos...", 80)
    errs, _ = validate(local=False)
    if errs: raise RuntimeError(" ".join(errs))
    # 3. commit + push
    msg = "Estúdio: " + (motivo or describe(s))
    return push(job, c, tok, msg)


def set_url(kind, oid, key, url, ia_item=None):
    with canal.LOCK:
        if kind == "anuncio":
            l = canal.anuncios()
            next(a for a in l if a["id"] == oid)["url"] = url
            canal.save_anuncios(l)
            return
        l = canal.programas()
        pr = next(p for p in l if p["id"] == oid)
        if ia_item: pr["ia_item"] = ia_item
        if key in ("abertura", "encerramento"): pr[key]["url"] = url
        else: next(e for e in pr["episodios"] if e["id"] == key)["url"] = url
        canal.save_programas(l)


def describe(s):
    n = [a["nome"].lower() for a in s["arquivos"]]
    return ", ".join(n) or "atualização"


def push(job, c, tok, msg):
    env = git_env(tok)
    R, B = c["remote"], c["branch"]
    job.say("Buscando a versão do canal no GitHub...", 84)
    r = canal.git("fetch", "--tags", R, B, env=env, timeout=180)
    if r.returncode: raise RuntimeError("Não consegui falar com o GitHub (sem internet?). Nada foi publicado; tente de novo.")
    first = not [t for t in canal.git("tag", "-l", "pub-*").stdout.split() if t]
    if canal.git("diff", "--quiet", "--", "public/grade/schedule.json").returncode:
        canal.git("checkout", "--", "public/grade/schedule.json")  # a local rebuild; the channel's own robot remakes it
    tracked = set(canal.git("ls-tree", "-r", "--name-only", "HEAD", "--", *canal.FILES).stdout.split())
    files = [f for f in canal.FILES if os.path.exists(canal.path(f)) or f in tracked]  # a deleted one goes as a deletion
    canal.git("add", "-A", "--", *files)
    if canal.git("diff", "--cached", "--quiet").returncode:
        canal.git(*ident(), "commit", "-m", msg, "--", *files, check=True)
    r = canal.git(*ident(), "rebase", "--autostash", "%s/%s" % (R, B), timeout=180)
    if r.returncode:
        canal.git("rebase", "--abort")
        raise RuntimeError("Alguém mudou os mesmos arquivos no GitHub ao mesmo tempo. Nada foi publicado. "
                           "Abra Publicar > 'Ver detalhes' ou peça ajuda; suas mudanças continuam aqui.")
    tag = "pub-" + time.strftime("%Y%m%d-%H%M%S")
    tags = [tag]
    if first:  # the channel as it was before the Estúdio's first publication, so it can be gone back to
        canal.git("tag", "-f", tag + "-antes", "%s/%s" % (R, B))
        tags.insert(0, tag + "-antes")
    canal.git(*ident(), "tag", "-a", tag, "-m", msg, check=True)
    job.say("Publicando...", 90)
    r = canal.git("push", R, "HEAD:" + B, *["refs/tags/" + t for t in tags], env=env, timeout=300)
    if r.returncode:
        for t in tags: canal.git("tag", "-d", t)
        raise RuntimeError("O GitHub recusou a publicação: " + (r.stderr.strip().splitlines() or ["?"])[-1][:200])
    job.say("Publicado! O canal se atualiza sozinho em 1 a 3 minutos.", 100)
    return {"tag": tag, "commit": canal.git("rev-parse", "--short", "HEAD").stdout.strip()}


# ---------------- going back ----------------

def history():
    r = canal.git("for-each-ref", "--sort=-creatordate", "--format=%(refname:short)|%(creatordate:iso)|%(contents:subject)", "refs/tags/pub-*")
    out = []
    for line in r.stdout.splitlines():
        t, when, subj = (line.split("|", 2) + ["", ""])[:3]
        w = when[:16]
        w = "%s/%s/%s %s" % (w[8:10], w[5:7], w[:4], w[11:16]) if len(w) == 16 else w
        out.append({"tag": t, "quando": w, "o_que": "Como o canal estava antes da primeira publicação pelo Estúdio" if t.endswith("-antes") else subj.replace("Estúdio: ", "")})
    return out


def rollback(job, tag):
    c = conf()
    if canal.pendentes(): raise RuntimeError("Há mudanças ainda não publicadas. Publique ou descarte antes de voltar atrás.")
    tok, _ = token()
    if not c.get("teste"):
        ok, msg = check_token(tok, c["repo"])
        if not ok: raise RuntimeError(msg)
    if canal.git("rev-parse", "-q", "--verify", "refs/tags/" + tag).returncode: raise RuntimeError("Publicação %s não encontrada." % tag)
    job.say("Voltando os arquivos da grade para %s..." % tag, 30)
    canal.git("fetch", "--tags", c["remote"], c["branch"], env=git_env(tok), timeout=180)
    canal.git("checkout", tag, "--", "catalog/", check=True)
    for f in canal.FILES:  # files the Estúdio made after that publication go too
        if canal.git("cat-file", "-e", "%s:%s" % (tag, f)).returncode and os.path.exists(canal.path(f)):
            canal.git("rm", "-q", "--cached", "--ignore-unmatch", f); os.remove(canal.path(f))
    when = next((h["quando"] for h in history() if h["tag"] == tag), tag)
    return push(job, c, tok, "Estúdio: desfazer, a grade volta a ser a de %s" % when)


def discard():
    """Throws away the changes not yet published (the files go back to the last commit)."""
    canal.git("checkout", "--", "catalog/")
    for line in canal.git("status", "--porcelain", "--", "catalog/").stdout.splitlines():
        if line.startswith("??"): os.remove(canal.path(line[3:].strip().strip('"')))


def sync():
    """At start-up, when online: bring in what changed on GitHub (the robot's schedule, fixes). Offline: nothing."""
    c = conf()
    tok, _ = token()
    r = canal.git("fetch", c["remote"], c["branch"], env=git_env(tok), timeout=25)
    if r.returncode: return "offline"
    if canal.git("diff", "--quiet", "--", "public/grade/schedule.json").returncode:
        canal.git("checkout", "--", "public/grade/schedule.json")
    r = canal.git(*ident(), "rebase", "--autostash", "%s/%s" % (c["remote"], c["branch"]), timeout=60)
    if r.returncode:
        canal.git("rebase", "--abort")
        return "conflito"
    return "ok"


# ---------------- checking the live channel ----------------

def live(site="https://koljatv.github.io/"):
    """What the channel has on the internet right now, and whether our programmes are in it."""
    try:
        req = urllib.request.Request(site + "grade/schedule.json?t=%d" % time.time(), headers={"User-Agent": UA, "Cache-Control": "no-cache"})
        s = json.load(urllib.request.urlopen(req, timeout=30))
    except Exception as e:
        return {"ok": False, "msg": "Não consegui abrir %sgrade/schedule.json (%s)." % (site, e)}
    ids = {i[2] for i in s.get("items", [])}
    progs = []
    for pr in canal.programas():
        mine = [i for i in ids if i.startswith("prog_%s_" % pr["id"])]
        progs.append({"nome": pr["nome"], "no_ar": bool(mine)})
    ads = [{"nome": a.get("nome", a["id"]), "no_ar": ("ad_" + a["id"]) in ids} for a in canal.anuncios()]
    return {"ok": True, "rev": s.get("rev"), "itens": len(s.get("items", [])), "programas": progs, "anuncios": ads,
            "msg": "O canal no ar tem %d itens nos próximos dias." % len(s.get("items", []))}
