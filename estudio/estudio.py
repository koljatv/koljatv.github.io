#!/usr/bin/env python3
"""Estúdio KÖLJA TV: the channel's control room, for one person, with no AI anywhere in it.

A local web app: this server (Python standard library only) on 127.0.0.1, the page in the browser. Editing works
offline; only Publicar, Saúde and finding new copies of films need the internet.

  python3 estudio/estudio.py [--porta 8799] [--sem-navegador]
"""
import argparse, datetime as dt, json, mimetypes, os, re, secrets, shutil, socket, subprocess, sys, threading, time, urllib.parse, uuid, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import canal, grade, midia, publicar  # noqa: E402

VERSION = open(os.path.join(HERE, "VERSION")).read().strip()
WEB = os.path.join(HERE, "web")
TOKEN = secrets.token_urlsafe(18)
PORT = 8799


class Fail(Exception):
    """An error to show as it is (already in plain Portuguese)."""


# ---------------- handlers ----------------

def estado(q):
    tok, onde = publicar.token()
    c = publicar.conf()
    last = publicar.history()[:1]
    return {"versao": VERSION, "repo": canal.REPO, "pendentes": canal.pendentes(), "videos_pendentes": len(publicar.pending_media()),
            "ffmpeg": os.path.exists(midia.FFMPEG), "desenhista": bool(midia.pil_python()), "chave": onde,
            "destino": c.get("destino"), "ultima": last[0] if last else None, "teste": bool(c.get("teste")),
            "jobs": [j for j in midia.jobs() if j["estado"] == "rodando"]}


def programas_get(q):
    l = canal.programas()
    for p in l:
        p["quando"] = canal.quando(p)
        p["vinhetas_velhas"] = midia.vinhetas_velhas(p)
        p["problemas"] = canal.check_programa(p, l)
    return {"programas": l, "estilos": ["ambar", "noite", "vermelho", "verde", "roxo", "creme"]}


def programas_save(b):
    p = b["programa"]
    with canal.LOCK:
        l = canal.programas()
        old = next((x for x in l if x["id"] == p.get("id")), None) if p.get("id") else None
        if not old:
            pid = canal.slug(p.get("nome", ""))
            while any(x["id"] == pid for x in l): pid += "-2"
            old = {"id": pid, "episodios": [], "criado": canal.now_iso()}
            l.append(old)
        for k in ("nome", "descricao", "modo", "horarios", "desde", "ate", "estilo", "ativo"):
            if k in p: old[k] = p[k]
        old["nome"] = old.get("nome", "").strip()
        old.setdefault("modo", "substituir"); old.setdefault("estilo", "ambar")
        if not old.get("desde"): old["desde"] = dt.date.today().isoformat()
        errs = canal.check_programa(old, l)
        hard = [e for e in errs if "nome" in e or "inválido" in e or "pelo menos" in e]
        if hard: raise Fail(" ".join(hard))
        canal.save_programas(l)
    job = None
    if midia.vinhetas_velhas(old) and midia.pil_python():
        job = midia.run("Vinhetas de " + old["nome"], midia.vinhetas, old["id"]).id
    return {"id": old["id"], "avisos": errs, "job": job}


def programas_del(b):
    with canal.LOCK:
        l = [x for x in canal.programas() if x["id"] != b["id"]]
        canal.save_programas(l)
        m = canal.manual()
        m["inserir"] = [x for x in m["inserir"] if x["id"] != "prog:" + b["id"]]
        m["remover"] = [x for x in m["remover"] if x["id"] != "prog:" + b["id"]]
        canal.save_manual(m)
    return {}


def programas_vinhetas(b):
    return {"job": midia.run("Vinhetas", midia.vinhetas, b["id"]).id}


def episodio_edit(b):
    with canal.LOCK:
        l = canal.programas()
        pr = next(x for x in l if x["id"] == b["prog"])
        eps = pr["episodios"]
        k = next(i for i, e in enumerate(eps) if e["id"] == b["ep"])
        if b.get("acao") == "apagar":
            e = eps.pop(k)
            f = os.path.join(canal.MEDIA, e.get("file", "-"))
            if os.path.exists(f) and not e.get("url"): os.remove(f)  # published ones keep their file: undo may need it
        elif b.get("acao") == "subir" and k > 0: eps[k - 1], eps[k] = eps[k], eps[k - 1]
        elif b.get("acao") == "descer" and k < len(eps) - 1: eps[k + 1], eps[k] = eps[k], eps[k + 1]
        elif b.get("acao") == "titulo": eps[k]["titulo"] = b.get("titulo", "").strip() or eps[k]["titulo"]
        canal.save_programas(l)
    return {}


def upload(h, q):
    tipo, oid = q.get("tipo"), q.get("id")
    n = int(h.headers.get("Content-Length") or 0)
    if n <= 0: raise Fail("Arquivo vazio.")
    free = shutil.disk_usage(canal.MEDIA if os.path.exists(canal.MEDIA) else canal.REPO).free
    if free < n * 2.2: raise Fail("Pouco espaço no disco do Mac para receber e converter este vídeo.")
    os.makedirs(midia.INBOX, exist_ok=True)
    ext = os.path.splitext(q.get("nome", ""))[1][:6] or ".mp4"
    dst = os.path.join(midia.INBOX, uuid.uuid4().hex + ext)
    left = n
    with open(dst, "wb") as f:
        while left:
            b = h.rfile.read(min(left, 1 << 20))
            if not b: break
            f.write(b); left -= len(b)
    if left: os.remove(dst); raise Fail("O envio foi interrompido.")
    if tipo == "episodio":
        j = midia.run("Episódio novo", midia.episodio, oid, dst, q.get("titulo", ""))
    elif tipo == "anuncio":
        j = midia.run("Vídeo do anúncio", midia.anuncio, oid, dst)
    else:
        os.remove(dst); raise Fail("Tipo de envio desconhecido.")
    return {"job": j.id}


def semana(q):
    start = q.get("inicio") or dt.date.today().isoformat()
    return {"dias": grade.week(start, int(q.get("dias", 7)))}


def agora(q):
    return grade.at(q.get("quando") or dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))


def grade_inserir(b):
    if not re.fullmatch(r"\d{4}-\d\d-\d\d", b.get("data", "")) or not re.fullmatch(r"\d\d:\d\d", b.get("at", "")):
        raise Fail("Data ou horário inválido.")
    ids = {t["id"] for t in canal.titulos()} | {"prog:" + p["id"] for p in canal.programas()}
    if b["id"] not in ids: raise Fail("Título não encontrado.")
    with canal.LOCK:
        m = canal.manual()
        m["inserir"] = [x for x in m["inserir"] if not (x["data"] == b["data"] and x["at"] == b["at"])]
        m["inserir"].append({"data": b["data"], "at": b["at"], "id": b["id"]})
        if b.get("de"):  # moved: it comes off where it was
            de = b["de"]
            if de.get("inserido"):
                m["inserir"] = [x for x in m["inserir"] if not (x["data"] == de["data"] and x["at"] == de["at"] and x["id"] == b["id"])]
            else:
                m["remover"].append({"data": de["data"], "id": b["id"], **({"at": de["at"]} if b["id"].startswith("prog:") else {})})
        canal.save_manual(m)
    return aviso_conflito(b["data"], b["at"], b["id"])


def aviso_conflito(data, at, pid):
    """Did it make it into the grade? (an insert on top of a programme or past midnight is dropped)."""
    g = grade.make(True)
    d = grade.day_of(data)
    ev = g.own.events(d)
    t = grade.day_ms(g, d, at)
    if not any(e[0] == t for e in ev):
        return {"aviso": "Não coube nesse horário (passaria da meia-noite ou bate com outro programa). Escolha outro horário."}
    return {}


def grade_remover(b):
    with canal.LOCK:
        m = canal.manual()
        if b.get("inserido"):
            m["inserir"] = [x for x in m["inserir"] if not (x["data"] == b["data"] and x["at"] == b["at"])]
        else:
            x = {"data": b["data"], "id": b["id"]}
            if b["id"].startswith("prog:"): x["at"] = b["at"]
            m["remover"].append(x)
        canal.save_manual(m)
    return {}


def grade_cancelar(b):
    with canal.LOCK:
        m = canal.manual()
        k = b["lista"]
        m[k] = [x for i, x in enumerate(m[k]) if i != int(b["indice"])]
        canal.save_manual(m)
    return {}


def grade_mudancas(q):
    m = canal.manual()
    names = {t["id"]: t["title"] for t in canal.titulos()} | {"prog:" + p["id"]: p["nome"] for p in canal.programas()}
    for x in m["inserir"] + m["remover"]: x["nome"] = names.get(x["id"], x["id"])
    return m


def grade_gerar(b):
    def go(job):
        job.say("Gerando a grade dos próximos 7 dias...", 10)
        t = time.time()
        r = grade.preview(7)
        progs = sorted({i[3] for i in r["items"] if i[3].startswith("prog-")})
        ads = sum(1 for i in r["items"] if i[2].kind == "ad")
        job.say("Pronto em %.1f s: %d itens, %d programas próprios, %d inserções de anúncios." % (time.time() - t, len(r["items"]), len(progs), ads), 100)
        return {"itens": len(r["items"])}
    return {"job": midia.run("Gerar grade", go).id}


def filmes(q):
    termo = canal.slug(q["q"]).replace("-", " ") if q.get("q", "").strip() else ""
    bloco, estado_ = q.get("bloco", ""), q.get("estado", "")
    health = grade.build.load("state/health.json", {}) or {}
    brk = canal.breaks()
    out = []
    for t in canal.titulos():
        if bloco and t["block"] != bloco: continue
        if estado_ == "fora" and not t.get("off"): continue
        if estado_ == "no_ar" and t.get("off"): continue
        hay = canal.slug("%s %s %s" % (t["title"], t["id"], t.get("year", ""))).replace("-", " ")
        if termo and not all(w in hay for w in termo.split()): continue
        bad = sum(1 for s in t["sources"] if not health.get(s["url"], {}).get("ok", True))
        out.append({"id": t["id"], "titulo": t["title"], "ano": t.get("year"), "bloco": t["block"], "tipo": t["kind"],
                    "dur": t["dur"], "fora": bool(t.get("off")), "copias": len(t["sources"]), "ruins": bad,
                    "intervalos": len((brk.get(t["sources"][0]["url"]) or {}).get("cuts", [])) if t["sources"] else 0,
                    "sinopse": t.get("synopsis_pt", ""), "fontes": t["sources"], "pd": t.get("pd", {}),
                    "estudio": bool(t.get("estudio"))})
    out.sort(key=lambda x: x["titulo"].lower())
    return {"filmes": out[:300], "total": len(out), "blocos": grade.blocks_info()["blocos"]}


def filmes_novo(b):
    t = b["filme"]
    if not b.get("confirmo_dp"): raise Fail("Confirme que o filme é de domínio público (e diga por quê).")
    if not t.get("titulo") or not t.get("url") or not t.get("bloco"): raise Fail("Preencha título, bloco e o endereço do vídeo.")
    if not str(t.get("url")).startswith("https://"): raise Fail("O endereço do vídeo precisa começar com https://")
    dur = int(float(t.get("dur") or 0))
    if not dur:
        try: dur = int(midia.probe(t["url"])["dur"])
        except Exception: raise Fail("Não consegui medir a duração pelo endereço (sem internet?). Digite a duração em minutos.")
    with canal.LOCK:
        l = canal.titulos()
        tid = canal.slug("%s-%s" % (t["titulo"], t.get("ano") or ""))
        while any(x["id"] == tid for x in l): tid += "-2"
        l.append({"id": tid, "title": t["titulo"].strip(), "year": int(t.get("ano") or 0), "country": t.get("pais", ""),
                  "block": t["bloco"], "kind": t.get("tipo", "film"), "dur": dur, "synopsis_pt": t.get("sinopse", ""),
                  "pd": {"basis": t.get("dp", "").strip(), "source": t.get("dp_fonte", ""), "caveat": ""},
                  "sources": [{"url": t["url"].strip(), "dur": dur}], "estudio": canal.now_iso()})
        canal.save_titulos(l)
    return {"id": tid}


def filmes_editar(b):
    with canal.LOCK:
        l = canal.titulos()
        t = next((x for x in l if x["id"] == b["id"]), None)
        if not t: raise Fail("Título não encontrado.")
        a = b.get("acao")
        if a == "tirar": t["off"] = True
        elif a == "voltar": t.pop("off", None)
        elif a == "apagar":
            if not t.get("estudio"): raise Fail("Só dá para apagar títulos que você mesmo incluiu. Use 'Tirar do ar'.")
            l.remove(t)
        elif a == "copia_topo":
            s = next(s for s in t["sources"] if s["url"] == b["url"])
            t["sources"] = [s] + [x for x in t["sources"] if x is not s]
        elif a == "copia_remover":
            if len(t["sources"]) <= 1: raise Fail("É a única cópia: inclua outra antes, ou tire o título do ar.")
            t["sources"] = [x for x in t["sources"] if x["url"] != b["url"]]
        elif a == "copia_nova":
            u = b["url"].strip()
            if not u.startswith("https://"): raise Fail("O endereço precisa começar com https://")
            d = int(float(b.get("dur") or 0))
            if not d:
                try: d = int(midia.probe(u)["dur"])
                except Exception: raise Fail("Não consegui medir a cópia (sem internet?).")
            t["sources"] = [{"url": u, "dur": d}] + [x for x in t["sources"] if x["url"] != u]
        elif a == "dados":
            for k_in, k in (("titulo", "title"), ("sinopse", "synopsis_pt"), ("bloco", "block")):
                if b.get(k_in): t[k] = b[k_in]
        canal.save_titulos(l)
    return {}


def intervalos_get(q):
    t = next((x for x in canal.titulos() if x["id"] == q["id"]), None)
    if not t: raise Fail("Título não encontrado.")
    brk = canal.breaks()
    return {"titulo": t["title"], "dur": t["dur"], "copias": [{"url": s["url"], "dur": s["dur"],
            "cortes": (brk.get(s["url"]) or {}).get("cuts", []), "manual": (brk.get(s["url"]) or {}).get("manual", False)} for s in t["sources"]]}


def intervalos_set(b):
    cuts = sorted(int(c) for c in b.get("cortes", []))
    with canal.LOCK:
        brk = canal.breaks()
        if cuts:
            old = brk.get(b["url"]) or {}
            brk[b["url"]] = {"dur": old.get("dur") or b.get("dur"), "cuts": cuts, "manual": True, "at": dt.date.today().isoformat()}
        else:
            brk.pop(b["url"], None)
        canal.save_breaks(brk)
    return {}


def filmes_detectar(b):
    def go(job):
        job.say("Procurando os pontos de intervalo (assiste trechos do filme pela internet; leva alguns minutos)...", 10)
        r = subprocess.run([sys.executable, os.path.join(canal.REPO, "tools", "breaks.py"), "--redo", "--only", b["id"]],
                           capture_output=True, text=True, timeout=3600, cwd=canal.REPO)
        if r.returncode: raise RuntimeError((r.stderr or r.stdout).strip()[-300:] or "falhou")
        job.say("Pronto. " + (r.stdout.strip().splitlines() or [""])[-1][:200], 100)
    return {"job": midia.run("Intervalos automáticos", go).id}


def filmes_procurar(b):
    t = next((x for x in canal.titulos() if x["id"] == b["id"]), None)

    def go(job):
        try: import find_sources
        except ImportError: raise RuntimeError("A busca de cópias só funciona neste Mac (pasta koljatv-private).")
        job.say("Procurando cópias no Internet Archive...", 10)
        c = (t["id"], t["title"], t.get("year", 0), t.get("country", ""), t["block"], t["kind"], max(1, t["dur"] // 60), "", "", "", None)
        _, r = find_sources.find(c)
        if r.get("error"): raise RuntimeError("O Internet Archive não respondeu (%s)." % r["error"][:100])
        have = {s["url"] for s in t["sources"]}
        novas = [s for s in r.get("sources", []) if s["url"] not in have]
        job.say("Achei %d cópia(s) nova(s)." % len(novas), 100)
        return {"copias": novas, "id": t["id"]}
    return {"job": midia.run("Procurar cópias: " + t["title"], go).id}


def anuncios_get(q):
    g = grade.make(True)
    return {"anuncios": canal.anuncios(), "blocos": grade.blocks_info()["blocos"], "intervalos": bool(g.brk)}


def anuncios_save(b):
    a = b["anuncio"]
    if not a.get("nome", "").strip(): raise Fail("Dê um nome ao anúncio.")
    if a.get("inicio") and a.get("fim") and a["fim"] < a["inicio"]: raise Fail("A data final vem antes da inicial.")
    with canal.LOCK:
        l = canal.anuncios()
        old = next((x for x in l if x["id"] == a.get("id")), None) if a.get("id") else None
        if not old:
            aid = canal.slug(a["nome"])
            while any(x["id"] == aid for x in l): aid += "-2"
            old = {"id": aid, "criado": canal.now_iso()}
            l.append(old)
        for k in ("nome", "cliente", "inicio", "fim", "por_dia", "por_bloco", "valor_insercao", "ativo", "obs"):
            if k in a: old[k] = a[k]
        if old.get("por_bloco"): old["por_bloco"] = {k: int(v) for k, v in old["por_bloco"].items() if int(v or 0) > 0}
        old["por_dia"] = int(old.get("por_dia") or 0)
        canal.save_anuncios(l)
    return {"id": old["id"]}


def anuncios_del(b):
    with canal.LOCK:
        canal.save_anuncios([x for x in canal.anuncios() if x["id"] != b["id"]])
    return {}


def relatorio(q):
    return grade.ad_report(q["id"])


def saude_get(q):
    health = grade.build.load("state/health.json", {}) or {}
    titles = canal.titulos()
    soon = set()
    try:
        r = grade.preview(2)
        soon = {i[2].id for i in r["items"]}
    except Exception:
        pass
    out, checked, last = [], 0, 0
    for t in titles:
        st = [health.get(s["url"]) for s in t["sources"]]
        checked += sum(1 for x in st if x)
        last = max([last] + [x.get("at", 0) for x in st if x])
        bad = [s for s, x in zip(t["sources"], st) if x and not x.get("ok", True)]
        if not bad: continue
        out.append({"id": t["id"], "titulo": t["title"], "bloco": t["block"], "fora": bool(t.get("off")),
                    "todas_ruins": len(bad) == len(t["sources"]), "em_breve": t["id"] in soon,
                    "ruins": [{"url": s["url"], "porque": health[s["url"]].get("why", "")} for s in bad],
                    "boas": [s["url"] for s in t["sources"] if s not in bad]})
    out.sort(key=lambda x: (not x["em_breve"], not x["todas_ruins"], x["titulo"]))
    return {"problemas": out, "verificadas": checked, "ultima": dt.datetime.fromtimestamp(last / 1000).strftime("%d/%m %H:%M") if last else None}


def saude_verificar(b):
    tudo = b.get("escopo") == "tudo"

    def go(job):
        import check
        health_p = canal.path("state", "health.json")
        health = json.load(open(health_p)) if os.path.exists(health_p) else {}
        titles = {t["id"]: t for t in canal.titulos() if not t.get("off")}
        if tudo: ids = list(titles)
        else:
            r = grade.preview(2)
            ids = list(dict.fromkeys(i[2].id for i in r["items"] if i[2].id in titles))
        urls = [s["url"] for i in ids for s in titles[i]["sources"]]
        job.say("Testando %d cópias de %d títulos..." % (len(urls), len(ids)), 2)
        from concurrent.futures import ThreadPoolExecutor
        done, bad = 0, 0
        if urls and not check.probe("https://archive.org/download/Nosferatu1922/Nosferatu.mp4")[0] and not check.probe(urls[0])[0]:
            raise RuntimeError("Sem internet (ou o Internet Archive está fora do ar). Tente mais tarde.")
        with ThreadPoolExecutor(6) as ex:
            for u, (ok, why) in zip(urls, ex.map(check.probe, urls)):
                h = health.get(u, {})
                fails = 0 if ok else h.get("fails", 0) + 1
                health[u] = {"ok": ok or fails < 2, "fails": fails, "at": int(time.time() * 1000), "why": why}
                if not ok:  # a check by hand: one failure is enough to show it (the robot online asks twice)
                    health[u]["ok"] = False; bad += 1
                done += 1
                job.say("Testando... %d de %d (%d com problema)" % (done, len(urls), bad), 2 + 96 * done / len(urls))
        os.makedirs(os.path.dirname(health_p), exist_ok=True)
        json.dump(health, open(health_p, "w"), indent=1)
        job.say("Pronto: %d cópias testadas, %d com problema." % (len(urls), bad), 100)
    return {"job": midia.run("Verificar links" + (" (acervo inteiro)" if tudo else ""), go).id}


def publicar_get(q):
    errs, warns = publicar.validate()
    tok, onde = publicar.token()
    return {"resumo": publicar.summary(), "erros": errs, "avisos": warns, "chave": onde, "conf": publicar.conf(),
            "ia": bool(publicar.secret("ia_access"))}


def publicar_post(b):
    return {"job": midia.run("Ensaio da publicação" if b.get("ensaio") else "Publicar", publicar.publish, bool(b.get("ensaio"))).id}


def config_post(b):
    if "github" in b: publicar.set_secret("github", b["github"].strip())
    if "ia_access" in b: publicar.set_secret("ia_access", b["ia_access"].strip())
    if "ia_secret" in b: publicar.set_secret("ia_secret", b["ia_secret"].strip())
    if "destino" in b:
        c = publicar.conf(); c["destino"] = "ia" if b["destino"] == "ia" else "github"; publicar.save_conf(c)
    return {}


def config_testar(q):
    tok, onde = publicar.token()
    ok, msg = publicar.check_token(tok, publicar.conf()["repo"])
    return {"ok": ok, "msg": msg, "onde": onde}


def historico(q):
    return {"publicacoes": publicar.history()}


def desfazer(b):
    return {"job": midia.run("Desfazer", publicar.rollback, b["tag"]).id}


def descartar(b):
    publicar.discard()
    return {}


GET = {"/api/estado": estado, "/api/programas": programas_get, "/api/grade/semana": semana, "/api/grade/agora": agora,
       "/api/grade/mudancas": grade_mudancas, "/api/grade/blocos": lambda q: grade.blocks_info(), "/api/filmes": filmes,
       "/api/filmes/intervalos": intervalos_get, "/api/anuncios": anuncios_get, "/api/anuncios/relatorio": relatorio,
       "/api/saude": saude_get, "/api/publicar": publicar_get, "/api/config/testar": config_testar, "/api/historico": historico,
       "/api/aovivo": lambda q: publicar.live(), "/api/jobs": lambda q: {"jobs": midia.jobs()}}
POST = {"/api/programas": programas_save, "/api/programas/apagar": programas_del, "/api/programas/vinhetas": programas_vinhetas,
        "/api/programas/episodio": episodio_edit, "/api/grade/inserir": grade_inserir, "/api/grade/remover": grade_remover,
        "/api/grade/cancelar": grade_cancelar, "/api/grade/blocos": lambda b: (grade.save_day(b["dia"]), {})[1],
        "/api/grade/gerar": grade_gerar, "/api/filmes/novo": filmes_novo, "/api/filmes/editar": filmes_editar,
        "/api/filmes/intervalos": intervalos_set, "/api/filmes/detectar": filmes_detectar, "/api/filmes/procurar": filmes_procurar,
        "/api/anuncios": anuncios_save, "/api/anuncios/apagar": anuncios_del, "/api/saude/verificar": saude_verificar,
        "/api/publicar": publicar_post, "/api/config": config_post, "/api/desfazer": desfazer, "/api/descartar": descartar}


# ---------------- the server ----------------

class H(BaseHTTPRequestHandler):
    server_version = "EstudioKoljaTV/" + VERSION

    def log_message(self, *a): pass

    def ok_host(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD": self.wfile.write(data)

    def authed(self, q):
        return secrets.compare_digest(self.headers.get("X-Estudio", "") or q.get("k", ""), TOKEN)

    def route(self, table, arg):
        try:
            return self.send(200, table(arg))
        except Fail as e:
            return self.send(400, {"erro": str(e)})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self.send(500, {"erro": "Algo deu errado: %s" % e})

    def do_GET(self):
        if not self.ok_host(): return self.send(403, {"erro": "host"})
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if u.path == "/api/ping": return self.send(200, {"estudio": True, "versao": VERSION})
        if u.path in ("/", "/index.html"):
            html = open(os.path.join(WEB, "index.html"), encoding="utf-8").read().replace("{{TOKEN}}", TOKEN).replace("{{VERSAO}}", VERSION)
            return self.send(200, html.encode(), "text/html; charset=utf-8")
        if u.path.startswith("/web/"):
            return self.file(os.path.join(WEB, u.path[5:]), WEB)
        if u.path.startswith("/media/"):
            if not self.authed(q): return self.send(403, {"erro": "token"})
            return self.file(os.path.join(canal.MEDIA, urllib.parse.unquote(u.path[7:])), canal.MEDIA)
        if not self.authed(q): return self.send(403, {"erro": "Recarregue a página do Estúdio."})
        if u.path in GET: return self.route(GET[u.path], q)
        return self.send(404, {"erro": "não existe"})

    def do_HEAD(self): self.do_GET()

    def do_POST(self):
        if not self.ok_host(): return self.send(403, {"erro": "host"})
        u = urllib.parse.urlparse(self.path)
        if not self.authed({}): return self.send(403, {"erro": "Recarregue a página do Estúdio."})
        n = int(self.headers.get("Content-Length") or 0)
        try: b = json.loads(self.rfile.read(n) or b"{}")
        except ValueError: return self.send(400, {"erro": "pedido inválido"})
        if u.path in POST: return self.route(POST[u.path], b)
        return self.send(404, {"erro": "não existe"})

    def do_PUT(self):
        if not self.ok_host(): return self.send(403, {"erro": "host"})
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if not self.authed({}): return self.send(403, {"erro": "Recarregue a página do Estúdio."})
        if u.path == "/api/upload": return self.route(lambda q: upload(self, q), q)
        return self.send(404, {"erro": "não existe"})

    def file(self, p, root):
        p = os.path.realpath(p)
        if not p.startswith(os.path.realpath(root) + os.sep) or not os.path.isfile(p): return self.send(404, {"erro": "arquivo"})
        size = os.path.getsize(p)
        ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
        rng = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
        a, b = 0, size - 1
        if rng:
            if rng.group(1): a = int(rng.group(1)); b = int(rng.group(2)) if rng.group(2) else size - 1
            else: a = max(0, size - int(rng.group(2)))
            b = min(b, size - 1)
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(b - a + 1))
        if rng: self.send_header("Content-Range", "bytes %d-%d/%d" % (a, b, size))
        self.end_headers()
        if self.command == "HEAD": return
        with open(p, "rb") as f:
            f.seek(a)
            left = b - a + 1
            try:
                while left > 0:
                    chunk = f.read(min(left, 1 << 16))
                    if not chunk: break
                    self.wfile.write(chunk); left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass


def running(port):
    try:
        import urllib.request
        return json.load(urllib.request.urlopen("http://127.0.0.1:%d/api/ping" % port, timeout=2)).get("estudio")
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, default=int(os.environ.get("KTV_PORT", PORT)))
    ap.add_argument("--sem-navegador", action="store_true")
    a = ap.parse_args()
    url = "http://127.0.0.1:%d/" % a.porta
    if running(a.porta):  # already open: just show it
        if not a.sem_navegador: webbrowser.open(url)
        return
    os.makedirs(canal.MEDIA, exist_ok=True)
    midia.limpar_entrada()
    srv = ThreadingHTTPServer(("127.0.0.1", a.porta), H)
    srv.daemon_threads = True
    print("Estúdio KÖLJA TV %s em %s (repo %s)" % (VERSION, url, canal.REPO), flush=True)
    if not a.sem_navegador: threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    if not publicar.conf().get("teste"):
        threading.Thread(target=lambda: print("sincronizar:", publicar.sync(), flush=True), daemon=True).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass


if __name__ == "__main__":
    main()
