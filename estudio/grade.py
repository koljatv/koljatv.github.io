"""The grade as the Estúdio shows it: tools/build.py run here, offline, on the files as they are now (published or
not), for any day; the week by programme; what's on at a given second; the spots' report."""
import datetime as dt, importlib, json, os, sys

import canal

sys.path.insert(0, os.path.join(canal.REPO, "tools"))
import build, proprios  # noqa: E402

DAY = 86_400_000


def make(local=True):
    importlib.reload(proprios); importlib.reload(build)  # an update of the generator is picked up without a restart
    load = lambda p, d=None: build.load(p, d)
    g = build.Grade(canal.cfg(), canal.titulos(), build.load("state/health.json", {}) or {}, canal.breaks(),
                    proprios.load_extra(load), local=local)
    return g


def day_of(date):
    return (dt.date.fromisoformat(date) - dt.date(1970, 1, 1)).days


def preview(days=1, start=None, local=True, g=None):
    g = g or make(local)
    d0 = day_of(start) if start else g.day_of(int(dt.datetime.now().timestamp() * 1000))
    items = []
    for d in range(d0, d0 + days):
        items += g.items(d)[0]
    return {"g": g, "items": items, "d0": d0}


def name_of(g, p):
    if p.id in g.own.titles: return g.own.titles[p.id]["title"]
    if p.id in g.raw and "title" in g.raw[p.id]: return g.raw[p.id]["title"]
    o = next((o for o in canal.cfg()["ours"] if o["id"] == p.id), None) or next((o for o in g.own.ours if o["id"] == p.id), None)
    return (o or {}).get("title", p.id)


def hhmm(g, t):
    return dt.datetime.fromtimestamp(t / 1000, g.tz).strftime("%H:%M")


def week(start, days=7):
    """Day by day, programme by programme: a feature with its breaks is one entry, our programme (opening, episode,
    closing) is one entry, the short pieces between programmes are left out."""
    r = preview(days, start)
    g, items = r["g"], r["items"]
    blocks = canal.cfg()["blocks"] | g.own.blocks
    m = canal.manual()
    ins = {(x["data"], x["at"]): x for x in m["inserir"]}
    out = []
    for d in range(r["d0"], r["d0"] + days):
        date = proprios.iso(d)
        base, end = g.midnight(d), g.midnight(d + 1)
        rows, cur = [], None
        for it in items:
            if not (base <= it[0] < end): continue
            p, blk = it[2], it[3]
            part = it[4] if len(it) > 4 else None
            if blk.startswith("prog-"):
                if cur and cur["bloco"] == blk and cur["tipo"] == "prog" and it[0] == cur["fim_ms"]:
                    cur["fim_ms"] = it[1]
                    if p.kind == "tv": cur.update(id=p.id, titulo=name_of(g, p))
                    continue
                cur = {"ini_ms": it[0], "fim_ms": it[1], "id": p.id, "titulo": name_of(g, p), "bloco": blk, "tipo": "prog",
                       "prog": blk[5:]}
                rows.append(cur); continue
            if p.ours() and p.kind != "card":
                if part == -1 and cur:  # a piece of a feature's break
                    cur["fim_ms"] = max(cur["fim_ms"], it[1])
                    if p.kind == "ad": cur["anuncios"] = cur.get("anuncios", 0) + 1
                continue
            if part is not None and part > 0 and cur and cur["id"] == p.id:
                cur["fim_ms"] = it[1]; cur["intervalos"] = cur.get("intervalos", 0) + 1
                continue
            cur = {"ini_ms": it[0], "fim_ms": it[1], "id": p.id, "titulo": name_of(g, p), "bloco": blk,
                   "tipo": "card" if p.kind == "card" else p.kind}
            rows.append(cur)
        for x in rows:
            x["ini"], x["fim"] = hhmm(g, x["ini_ms"]), hhmm(g, x["fim_ms"])
            x["bloco_nome"] = blocks.get(x["bloco"], {}).get("pt", x["bloco"])
            x["inserido"] = (date, x["ini"]) in ins or any(k[0] == date and abs(day_ms(g, d, k[1]) - x["ini_ms"]) < 60_000 for k in ins)
        rows = [x for x in rows if not (x["tipo"] == "card" and x["fim_ms"] - x["ini_ms"] < 60_000)]
        out.append({"data": date, "dia": canal.DIAS[dt.date.fromisoformat(date).weekday()], "itens": rows,
                    "removidos": [x for x in m["remover"] if x["data"] == date]})
    return out


def day_ms(g, d, at):
    return g.midnight(d) + (int(at[:2]) * 60 + int(at[3:5])) * 60_000


def at(when):
    """What's on at a moment ('2026-11-02T21:15'): the piece, how far into it, and a way to watch it here."""
    g = make(True)
    t = int(dt.datetime.fromisoformat(when).replace(tzinfo=g.tz).timestamp() * 1000)
    d = g.day_of(t)
    items = g.items(d)[0]
    for k, it in enumerate(items):
        if it[0] <= t < it[1]:
            p = it[2]
            off = t - it[0]
            url = None
            if p.id in g.own.titles: url = g.own.titles[p.id]["sources"][0]["url"]
            elif not p.ours():
                src = (g.raw.get(p.id) or {}).get("sources") or []
                if src:
                    url = src[0]["url"]
                    if len(it) > 4 and it[4] > 0:  # a later part of a feature: the file goes on from its cut
                        cuts = (g.cuts.get(p.id) or {}).get(url) or []
                        if it[4] - 1 < len(cuts): off += cuts[it[4] - 1]
            else:
                o = next((o for o in g.own.ours if o["id"] == p.id), None)
                url = o["url"] if o else "local:ours/" + next((x["file"] for x in canal.cfg()["ours"] if x["id"] == p.id), "")
            nxt, seen = [], {p.id}
            for x in items[k + 1:]:  # the next programmes (not the idents and trailers between them)
                if len(nxt) >= 5: break
                if x[2].id in seen or x[2].ours() and x[2].kind not in ("vignette",) or x[2].kind == "vignette" and not x[3].startswith("prog-"): continue
                seen.add(x[2].id)
                nxt.append({"ini": hhmm(g, x[0]), "titulo": blocks_name(x[3]) if x[2].kind == "vignette" else name_of(g, x[2])})
            return {"titulo": name_of(g, p), "id": p.id, "tipo": p.kind, "bloco": it[3], "ini": hhmm(g, it[0]),
                    "fim": hhmm(g, it[1]), "offset": off / 1000, "url": url, "parte": it[4] if len(it) > 4 else None,
                    "seguintes": nxt}
    return {"titulo": "(nada)", "seguintes": []}


def blocks_name(b):
    pr = canal.programa(b[5:]) if b.startswith("prog-") else None
    return pr["nome"] if pr else canal.cfg()["blocks"].get(b, {}).get("pt", b)


def ad_report(aid):
    """Day by day: insertions asked for, insertions the grade has, by block, and the value."""
    a = next((x for x in canal.anuncios() if x["id"] == aid), None)
    if not a: raise RuntimeError("Anúncio não encontrado.")
    g = make(True)
    blocks = canal.cfg()["blocks"]
    d0, d1 = day_of(a.get("inicio") or dt.date.today().isoformat()), day_of(a.get("fim") or dt.date.today().isoformat())
    d1 = min(d1, d0 + 92)
    want = sum(n for _, n in proprios.quotas(a))
    rows, total, falta = [], 0, 0
    for d in range(d0, d1 + 1):
        items = g.items(d)[0]
        by = {}
        for it in items:
            if it[2].id == "ad_" + aid:
                by[it[3]] = by.get(it[3], 0) + 1
        n = sum(by.values())
        total += n; falta += max(0, want - n)
        rows.append({"data": proprios.iso(d), "pedidas": want, "na_grade": n,
                     "blocos": {blocks.get(b, {}).get("pt", b): k for b, k in sorted(by.items())}})
    preco = float(a.get("valor_insercao") or 0)
    return {"nome": a.get("nome"), "cliente": a.get("cliente", ""), "dias": rows, "total": total, "faltaram": falta,
            "valor": round(total * preco, 2), "preco": preco,
            "aviso": "Faltaram %d inserções: não houve intervalos suficientes nos blocos escolhidos (só filmes de 40 min ou mais têm intervalo)." % falta if falta else ""}


def blocks_info():
    c = canal.cfg()
    titles = canal.titulos()
    n = {}
    for t in titles:
        if not t.get("off"): n[t["block"]] = n.get(t["block"], 0) + 1
    return {"blocos": [{"id": k, "nome": v["pt"], "titulos": n.get(k, 0)} for k, v in c["blocks"].items()],
            "dia": c["day"]}


def save_day(slots):
    """The day's layout: [{"at": "HH:MM", "block": "id" or "a|b"}], from midnight."""
    c = canal.cfg()
    ok = set(c["blocks"])
    clean = []
    for s in slots:
        at, b = s.get("at", ""), s.get("block", "")
        if len(at) != 5 or at[2] != ":" or not at.replace(":", "").isdigit() or int(at[:2]) > 23 or int(at[3:]) > 59:
            raise RuntimeError("Horário inválido: %s" % at)
        if not b or any(x not in ok for x in b.split("|")): raise RuntimeError("Bloco desconhecido: %s" % b)
        clean.append({"at": at, "block": b})
    clean.sort(key=lambda s: s["at"])
    if not clean or clean[0]["at"] != "00:00": raise RuntimeError("O primeiro bloco do dia precisa começar às 00:00.")
    if len({s["at"] for s in clean}) != len(clean): raise RuntimeError("Dois blocos no mesmo horário.")
    c["day"] = clean
    canal.write("grade.json", c)
