// Estúdio KÖLJA TV: the page. Talks only to the local server (127.0.0.1).
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"];
const CORES = ["#ffb000", "#79b8ff", "#ff6a5a", "#6fd38a", "#d28cff", "#ffd36b", "#5ad1c8", "#ff8fc7", "#a3e36b", "#ff9a3c", "#8fa8ff", "#e0c9a6", "#c58b5c", "#9ad0ff"];
const ESTILO_COR = { ambar: "linear-gradient(135deg,#120e0a 50%,#ffb000 50%)", noite: "linear-gradient(135deg,#0a1022 50%,#6eb4ff 50%)",
  vermelho: "linear-gradient(135deg,#1e0608 50%,#ff5a46 50%)", verde: "linear-gradient(135deg,#081810 50%,#78e68c 50%)",
  roxo: "linear-gradient(135deg,#160a20 50%,#d28cff 50%)", creme: "linear-gradient(135deg,#ece2cc 50%,#be5a14 50%)" };
const ESTILO_NOME = { ambar: "Âmbar", noite: "Noite", vermelho: "Vermelho", verde: "Verde", roxo: "Roxo", creme: "Creme" };

async function api(path, body, method) {
  const opt = { method: method || (body !== undefined ? "POST" : "GET"), headers: { "X-Estudio": TOKEN } };
  if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers["Content-Type"] = "application/json"; }
  let r;
  try { r = await fetch(path, opt); } catch (e) { throw new Error("O Estúdio parou. Abra de novo pelo ícone 'Estúdio KÖLJA TV'."); }
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.erro || ("Erro " + r.status));
  return j;
}
const qs = o => "?" + new URLSearchParams(o).toString();
function toast(msg, ruim) {
  const d = document.createElement("div"); d.textContent = msg; if (ruim) d.className = "ruim";
  $("#toast").appendChild(d); setTimeout(() => d.remove(), ruim ? 7000 : 3200);
}
async function tenta(fn) { try { return await fn(); } catch (e) { toast(e.message, true); } }
function modal(html) { $("#modal-corpo").innerHTML = html; $("#modal").hidden = false; }
function fecharModal() { $("#modal").hidden = true; $("#modal-corpo").innerHTML = ""; }
document.addEventListener("keydown", e => { if (e.key === "Escape") fecharModal(); });
const mmss = s => { s = Math.round(s); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
  return (h ? h + "h" + String(m).padStart(2, "0") : m) + "min" + (h ? "" : " " + String(x).padStart(2, "0") + "s"); };
const hoje = () => { const d = new Date(); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); };
const addDias = (iso, n) => { const d = new Date(iso + "T12:00:00"); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };
const segunda = iso => { const d = new Date(iso + "T12:00:00"); const wd = (d.getDay() + 6) % 7; return addDias(iso, -wd); };
const dataBR = iso => iso ? iso.slice(8, 10) + "/" + iso.slice(5, 7) : "";
const media = f => "/media/" + f.split("/").map(encodeURIComponent).join("/") + "?k=" + TOKEN;
function corBloco(b) { let h = 0; for (const c of b) h = (h * 31 + c.charCodeAt(0)) >>> 0; return b.startsWith("prog-") ? "#ffb000" : CORES[h % CORES.length]; }

// ---------------- background jobs ----------------
const vistos = new Set(); let jobTimer = null; const aoTerminar = {};
function seguir(id, fn) { if (fn) aoTerminar[id] = fn; vistos.add(id); pollJobs(); }
async function pollJobs() {
  clearTimeout(jobTimer);
  let j; try { j = await api("/api/jobs"); } catch (e) { jobTimer = setTimeout(pollJobs, 3000); return; }
  const box = $("#jobs"); box.innerHTML = "";
  let rodando = false;
  for (const x of j.jobs) {
    if (!vistos.has(x.id) && x.estado !== "rodando") continue;
    vistos.add(x.id);
    if (x.estado === "rodando") rodando = true;
    const d = document.createElement("div"); d.className = "job " + x.estado;
    d.innerHTML = `<div class="linha"><b>${esc(x.titulo)}</b><span class="espaco"></span>${x.estado === "rodando" ? x.pct + "%" : `<button class="pequeno" title="fechar">✕</button>`}</div>
      <div class="msg">${esc(x.msg)}</div>${x.estado === "rodando" ? `<div class="barra"><i style="width:${x.pct}%"></i></div>` : ""}`;
    const b = $("button", d); if (b) b.onclick = () => { vistos.delete(x.id); d.remove(); };
    box.appendChild(d);
    if (x.estado !== "rodando" && aoTerminar[x.id]) { const f = aoTerminar[x.id]; delete aoTerminar[x.id]; f(x); }
    if (x.estado === "pronto" && !x._lido) setTimeout(() => { if (vistos.has(x.id)) { vistos.delete(x.id); pollJobs(); } }, 8000);
  }
  if (rodando) jobTimer = setTimeout(pollJobs, 1000);
}

// ---------------- pages ----------------
const PAGINAS = {};
let ESTADO = {};
async function estado() {
  ESTADO = await api("/api/estado");
  const n = ESTADO.pendentes.length + ESTADO.videos_pendentes;
  const b = $("#badge"); b.hidden = !n; b.textContent = n;
  $("#versao").textContent = ESTADO.versao;
  $("#teste-aviso").textContent = ESTADO.teste ? "MODO DE TESTE" : "";
  for (const j of ESTADO.jobs) vistos.add(j.id);
  if (ESTADO.jobs.length) pollJobs();
  return ESTADO;
}
async function abrir() {
  const p = (location.hash || "#inicio").slice(1).split("/")[0];
  $$("nav a").forEach(a => a.classList.toggle("ativo", a.dataset.p === p));
  const main = $("#pagina");
  main.innerHTML = `<p class="apagado">Carregando...</p>`;
  try { await (PAGINAS[p] || PAGINAS.inicio)(main); } catch (e) { main.innerHTML = `<div class="erro">${esc(e.message)}</div>`; }
  estado().catch(() => {});
}
window.addEventListener("hashchange", abrir);

// ---- Início ----
PAGINAS.inicio = async main => {
  const [e, a] = await Promise.all([estado(), api("/api/grade/agora")]);
  const n = e.pendentes.length + e.videos_pendentes;
  main.innerHTML = `
    <h1>Início</h1><p class="sub">O canal, do jeito que vai ficar com o que está aqui no Estúdio.</p>
    <div class="noar">
      <div><div class="tela" id="tela"></div></div>
      <div class="cartao"><small>NO AR AGORA (${esc(a.ini || "")}–${esc(a.fim || "")})</small>
        <h3 style="font-size:20px;margin-top:4px">${esc(a.titulo)}</h3>
        <small>A SEGUIR</small>
        <table>${(a.seguintes || []).map(s => `<tr><td style="width:60px">${esc(s.ini)}</td><td>${esc(s.titulo)}</td></tr>`).join("")}</table>
      </div>
    </div>
    <div class="grade2" style="margin-top:16px">
      <div class="cartao"><small>NÃO PUBLICADO</small><div class="numero">${n}</div>
        <small>${n ? "mudança(s) esperando o botão Publicar" : "tudo o que está aqui já está no ar"}</small></div>
      <div class="cartao"><small>ÚLTIMA PUBLICAÇÃO</small><div style="font-size:18px;margin:8px 0">${e.ultima ? esc(e.ultima.quando) : "ainda nenhuma pelo Estúdio"}</div>
        <small>${e.ultima ? esc(e.ultima.o_que) : ""}</small></div>
      <div class="cartao"><small>FERRAMENTAS</small><div style="margin-top:8px">
        <span class="pilula ${e.ffmpeg ? "ok" : "ruim"}">conversor ${e.ffmpeg ? "ok" : "faltando"}</span>
        <span class="pilula ${e.desenhista ? "ok" : "ruim"}">vinhetas ${e.desenhista ? "ok" : "faltando"}</span>
        <span class="pilula ${e.chave ? "ok" : "aviso"}">chave GitHub ${e.chave ? "ok" : "não guardada"}</span></div></div>
    </div>
    <h2>O que você quer fazer?</h2>
    <div class="atalhos">
      <button onclick="location.hash='programas'">▶ Episódio novo<span>Enviar o vídeo de um programa</span></button>
      <button onclick="location.hash='grade'">▦ Mexer na grade<span>Ver a semana, tirar ou pôr títulos</span></button>
      <button onclick="location.hash='anuncios'">$ Anúncio<span>Cadastrar um anunciante e ver o relatório</span></button>
      <button onclick="location.hash='saude'">✚ Links quebrados<span>Testar e trocar cópias com defeito</span></button>
      <button onclick="location.hash='publicar'" class="${n ? "principal" : ""}">↑ Publicar<span style="color:inherit">${n ? "Mandar as mudanças para o ar" : "Nada pendente"}</span></button>
      <button onclick="location.hash='desfazer'">↶ Desfazer<span>Voltar a grade a uma publicação anterior</span></button>
    </div>`;
  tocar($("#tela"), a);
};

function tocar(tela, a) {
  if (!a || !a.url) { tela.innerHTML = `<div class="sem">${esc(a && a.titulo || "")}<br><small>(sem vídeo para mostrar)</small></div>`; return; }
  const src = a.url.startsWith("local:") ? media(a.url.slice(6)) : a.url;
  tela.innerHTML = `<video controls muted playsinline preload="metadata" src="${esc(src)}#t=${a.offset || 0}"></video>
    <div class="legenda">${esc(a.titulo)} · ${mmss(a.offset || 0)}</div>`;
  const v = $("video", tela);
  v.addEventListener("loadedmetadata", () => { try { v.currentTime = a.offset || 0; } catch (e) {} });
  v.addEventListener("error", () => { tela.innerHTML = `<div class="sem">${esc(a.titulo)}<br><small>Não deu para tocar aqui (sem internet? os filmes vêm do Internet Archive).</small></div>`; });
}

// ---- Programas ----
PAGINAS.programas = async main => {
  const r = await api("/api/programas");
  main.innerHTML = `<div class="linha"><div><h1>Programas próprios</h1><p class="sub">Os programas que você faz. Cada um tem horário fixo, abertura e encerramento.</p></div>
    <span class="espaco"></span><button class="principal grande" id="novo">+ Novo programa</button></div><div id="lista"></div>`;
  $("#novo").onclick = () => formPrograma(null, r.estilos);
  const lista = $("#lista");
  if (!r.programas.length) lista.innerHTML = `<div class="vazio">Nenhum programa ainda. Clique em <b>+ Novo programa</b>.</div>`;
  for (const p of r.programas) lista.appendChild(cartaoPrograma(p, r.estilos));
};

function cartaoPrograma(p, estilos) {
  const d = document.createElement("div"); d.className = "cartao";
  const eps = p.episodios || [];
  const naoPub = eps.filter(e => !e.url).length;
  d.innerHTML = `
    <div class="prog"><div><div class="nome">${esc(p.nome)}</div>
      <div class="apagado">${esc(p.quando || "sem horário")} · ${p.modo === "playlist" ? "lista: um episódio por vez, em ordem" : "substitui: vai ao ar o episódio mais novo"}
      ${p.ativo === false ? ` · <span class="pilula ruim">fora do ar</span>` : ""}</div>
      ${p.descricao ? `<p>${esc(p.descricao)}</p>` : ""}</div>
      <div class="linha" style="align-items:flex-start"><button class="editar">Editar</button></div></div>
    ${(p.problemas || []).map(x => `<div class="alerta">${esc(x)}</div>`).join("")}
    <h2 style="margin-top:12px">Episódios</h2>
    <div class="eps">${eps.length ? "" : `<p class="apagado">Nenhum episódio ainda.</p>`}</div>
    <div class="soltar" tabindex="0">Arraste o vídeo do episódio para cá, ou <u>clique para escolher</u>.<br>
      <small>Qualquer formato (MP4, MOV, MKV...). O Estúdio converte sozinho para o formato do canal.</small>
      <div class="linha" style="justify-content:center;margin-top:8px"><input class="titulo-ep" placeholder="Título do episódio (opcional)" style="width:320px"></div>
      <input type="file" accept="video/*,.mkv,.mov,.avi,.mp4,.m4v,.webm" hidden></div>
    <h2>Vinhetas</h2>
    <div class="vinhetas">${p.abertura ? `<div><small>ABERTURA</small><video controls preload="metadata" src="${media(p.abertura.file)}#t=3"></video></div>` : ""}
      ${p.encerramento ? `<div><small>ENCERRAMENTO</small><video controls preload="metadata" src="${media(p.encerramento.file)}#t=2.5"></video></div>` : ""}</div>
    <div class="linha" style="margin-top:8px">${p.vinhetas_velhas ? `<span class="pilula aviso">as vinhetas precisam ser refeitas</span>` : `<span class="pilula ok">vinhetas em dia</span>`}
      <button class="pequeno refazer">Refazer vinhetas</button>
      ${naoPub ? `<span class="pilula aviso">${naoPub} episódio(s) ainda não publicado(s)</span>` : ""}</div>`;
  const le = $(".eps", d);
  eps.forEach((e, i) => {
    const row = document.createElement("div"); row.className = "ep";
    const ativo = p.modo !== "playlist" ? (i === eps.length - 1 || (!eps[eps.length - 1].url && e.url && eps.filter(x => x.url).slice(-1)[0] === e)) : true;
    row.innerHTML = `<div class="t"><b>${esc(e.titulo)}</b><br><small>${mmss(e.dur)} · ${e.mb || "?"} MB · enviado ${esc(e.enviado || "")}</small></div>
      ${e.url ? `<span class="pilula ok">publicado</span>` : `<span class="pilula aviso">falta publicar</span>`}
      ${p.modo !== "playlist" && i === eps.length - 1 ? `<span class="pilula">mais novo</span>` : ""}
      <button class="pequeno" data-a="ver">Ver</button>
      ${p.modo === "playlist" ? `<button class="pequeno" data-a="subir">↑</button><button class="pequeno" data-a="descer">↓</button>` : ""}
      <button class="pequeno" data-a="titulo">Renomear</button><button class="pequeno perigo" data-a="apagar">Apagar</button>`;
    $$("button", row).forEach(b => b.onclick = () => acaoEpisodio(p, e, b.dataset.a));
    le.appendChild(row);
  });
  $(".editar", d).onclick = () => formPrograma(p, estilos);
  $(".refazer", d).onclick = () => tenta(async () => { const j = await api("/api/programas/vinhetas", { id: p.id }); seguir(j.job, () => abrir()); });
  const zona = $(".soltar", d), inp = $("input[type=file]", d);
  zona.onclick = e => { if (e.target.classList.contains("titulo-ep")) return; inp.click(); };
  inp.onchange = () => inp.files[0] && enviar(inp.files[0], "episodio", p.id, $(".titulo-ep", d).value);
  zona.ondragover = e => { e.preventDefault(); zona.classList.add("sobre"); };
  zona.ondragleave = () => zona.classList.remove("sobre");
  zona.ondrop = e => { e.preventDefault(); zona.classList.remove("sobre"); const f = e.dataTransfer.files[0]; if (f) enviar(f, "episodio", p.id, $(".titulo-ep", d).value); };
  return d;
}

async function acaoEpisodio(p, e, a) {
  if (a === "ver") { modal(`<h3>${esc(e.titulo)}</h3><div class="player"><video controls autoplay src="${media(e.file)}"></video></div>`); return; }
  if (a === "apagar" && !confirm(`Apagar o episódio "${e.titulo}"?` + (e.url ? "\n(Ele continua guardado no GitHub, para o Desfazer.)" : ""))) return;
  let titulo;
  if (a === "titulo") { titulo = prompt("Novo título do episódio:", e.titulo); if (!titulo) return; }
  await tenta(async () => { await api("/api/programas/episodio", { prog: p.id, ep: e.id, acao: a, titulo }); abrir(); });
}

function enviar(file, tipo, id, titulo) {
  return new Promise(resolve => {
    const x = new XMLHttpRequest();
    x.open("PUT", "/api/upload" + qs({ tipo, id, titulo: titulo || "", nome: file.name }));
    x.setRequestHeader("X-Estudio", TOKEN);
    const box = document.createElement("div"); box.className = "job";
    box.innerHTML = `<b>Recebendo ${esc(file.name)}</b><div class="msg">0%</div><div class="barra"><i style="width:0"></i></div>`;
    $("#jobs").prepend(box);
    x.upload.onprogress = ev => { if (ev.lengthComputable) { const p = Math.round(100 * ev.loaded / ev.total);
      $(".msg", box).textContent = p + "% de " + Math.round(ev.total / 1e6) + " MB"; $("i", box).style.width = p + "%"; } };
    x.onload = () => { box.remove(); let j = {}; try { j = JSON.parse(x.responseText); } catch (e) {}
      if (x.status !== 200) { toast(j.erro || "O envio falhou.", true); return resolve(); }
      seguir(j.job, job => { if (job.estado === "pronto") toast("Vídeo pronto!"); abrir(); }); resolve(); };
    x.onerror = () => { box.remove(); toast("O envio falhou.", true); resolve(); };
    x.send(file);
  });
}

function formPrograma(p, estilos) {
  p = p || { nome: "", descricao: "", modo: "substituir", estilo: "ambar", horarios: [{ dias: [0, 1, 2, 3, 4], at: "20:00" }], ativo: true };
  modal(`<h3>${p.id ? "Editar programa" : "Novo programa"}</h3>
    <label>Nome</label><input class="campo" id="f-nome" value="${esc(p.nome)}" placeholder="Ex.: Cine Kölja">
    <label>Descrição (aparece no guia)</label><textarea id="f-desc">${esc(p.descricao || "")}</textarea>
    <label>Horários fixos</label><div id="f-hor"></div><button class="pequeno" id="f-mais">+ outro horário</button>
    <label>Episódios</label>
    <label class="inline"><input type="radio" name="modo" value="substituir" ${p.modo !== "playlist" ? "checked" : ""}> O episódio novo substitui o anterior</label><br>
    <label class="inline"><input type="radio" name="modo" value="playlist" ${p.modo === "playlist" ? "checked" : ""}> Lista: passa um episódio por vez, em ordem, e recomeça</label>
    <label>Cor das vinhetas</label><div class="estilos">${estilos.map(s => `<label title="${ESTILO_NOME[s]}"><input type="radio" name="estilo" value="${s}" ${p.estilo === s ? "checked" : ""}><span style="background:${ESTILO_COR[s]}"></span></label>`).join("")}</div>
    <div class="linha" style="margin-top:10px"><div><label>Começa em</label><input type="date" id="f-desde" value="${esc(p.desde || hoje())}"></div>
      <div><label>Termina em (opcional)</label><input type="date" id="f-ate" value="${esc(p.ate || "")}"></div></div>
    <label class="inline" style="margin-top:12px"><input type="checkbox" id="f-ativo" ${p.ativo !== false ? "checked" : ""}> No ar</label>
    <div id="f-erro"></div>
    <div class="linha fim" style="margin-top:16px">${p.id ? `<button class="perigo" id="f-apagar">Apagar programa</button><span class="espaco"></span>` : ""}
      <button onclick="fecharModal()">Cancelar</button><button class="principal" id="f-salvar">Salvar</button></div>`);
  const hor = $("#f-hor");
  const linha = h => {
    const d = document.createElement("div"); d.className = "horario";
    d.innerHTML = `<span class="dias">${DIAS.map((n, i) => `<label><input type="checkbox" value="${i}" ${h.dias.includes(i) ? "checked" : ""}><span>${n}</span></label>`).join("")}</span>
      às <input type="time" value="${esc(h.at)}" step="300"> <button class="pequeno perigo">remover</button>`;
    $("button", d).onclick = () => d.remove();
    hor.appendChild(d);
  };
  (p.horarios || []).forEach(linha);
  $("#f-mais").onclick = () => linha({ dias: [5], at: "20:00" });
  if (p.id) $("#f-apagar").onclick = () => tenta(async () => {
    if (!confirm(`Apagar "${p.nome}" e tirar da grade? (Os vídeos já publicados continuam guardados.)`)) return;
    await api("/api/programas/apagar", { id: p.id }); fecharModal(); abrir(); });
  $("#f-salvar").onclick = () => tenta(async () => {
    const horarios = $$(".horario", hor).map(d => ({ dias: $$("input[type=checkbox]:checked", d).map(i => +i.value), at: $("input[type=time]", d).value }));
    const novo = { id: p.id, nome: $("#f-nome").value, descricao: $("#f-desc").value, horarios,
      modo: $("input[name=modo]:checked").value, estilo: ($("input[name=estilo]:checked") || {}).value || "ambar",
      desde: $("#f-desde").value, ate: $("#f-ate").value || null, ativo: $("#f-ativo").checked };
    try {
      const r = await api("/api/programas", { programa: novo });
      fecharModal();
      if (r.avisos && r.avisos.length) toast(r.avisos[0], true); else toast("Programa salvo.");
      if (r.job) seguir(r.job, () => abrir());
      abrir();
    } catch (e) { $("#f-erro").innerHTML = `<div class="erro">${esc(e.message)}</div>`; }
  });
}

// ---- Grade ----
let G = { semana: null, dia: 0, dias: [] };
PAGINAS.grade = async main => {
  G.semana = G.semana || segunda(hoje());
  if (G.semana === segunda(hoje()) && G._primeira === undefined) { G.dia = (new Date().getDay() + 6) % 7; G._primeira = true; }
  main.innerHTML = `<h1>Grade</h1><p class="sub">A semana como vai ao ar. Arraste um item para outro dia (nas abas) ou para outro horário (em cima de outro item). Clique num item para tirar, mover ou assistir.</p>
    <div class="semana-nav"><button id="g-ant">‹ semana anterior</button><b id="g-tit"></b><button id="g-prox">próxima semana ›</button>
      <span class="espaco"></span><button id="g-hoje">Hoje</button><button id="g-inserir" class="principal">+ Inserir título</button></div>
    <div class="dias-tabs" id="g-tabs"></div>
    <div class="linha" style="align-items:flex-start;gap:18px"><div class="dia-lista" id="g-dia" style="flex:1.4"></div>
      <div style="flex:1;position:sticky;top:12px">
        <div class="cartao"><h3>Ver o que passa</h3><div class="linha"><input type="date" id="g-qd"><input type="time" id="g-qh" step="60"><button id="g-ver">Ver</button></div>
          <div id="g-agora" style="margin-top:10px"></div></div>
        <div class="cartao"><h3>Mudanças desta grade</h3><div id="g-mud"></div></div>
        <div class="cartao"><h3>Ferramentas</h3><div class="linha"><button id="g-gerar">Gerar a grade de novo</button><button id="g-blocos">Blocos do dia</button></div>
          <small>A grade é refeita sozinha a cada mudança; "gerar de novo" só confere que está tudo certo.</small></div>
      </div></div>`;
  $("#g-ant").onclick = () => { G.semana = addDias(G.semana, -7); abrir(); };
  $("#g-prox").onclick = () => { G.semana = addDias(G.semana, 7); abrir(); };
  $("#g-hoje").onclick = () => { G.semana = segunda(hoje()); G.dia = (new Date().getDay() + 6) % 7; abrir(); };
  $("#g-inserir").onclick = () => formInserir(G.dias[G.dia] ? G.dias[G.dia].data : hoje(), "20:00");
  $("#g-gerar").onclick = () => tenta(async () => seguir((await api("/api/grade/gerar", {})).job));
  $("#g-blocos").onclick = formBlocos;
  $("#g-qd").value = hoje(); $("#g-qh").value = new Date().toTimeString().slice(0, 5);
  $("#g-ver").onclick = () => verAgora($("#g-qd").value + "T" + $("#g-qh").value);
  $("#g-tit").textContent = `${dataBR(G.semana)} a ${dataBR(addDias(G.semana, 6))}`;
  const r = await api("/api/grade/semana" + qs({ inicio: G.semana }));
  G.dias = r.dias;
  desenharTabs(); desenharDia(); mudancas();
};

function desenharTabs() {
  const t = $("#g-tabs"); t.innerHTML = "";
  G.dias.forEach((d, i) => {
    const b = document.createElement("button");
    b.innerHTML = `<b>${d.dia}</b>${dataBR(d.data)}`; if (i === G.dia) b.className = "ativo";
    b.onclick = () => { G.dia = i; desenharTabs(); desenharDia(); };
    b.ondragover = e => { e.preventDefault(); b.classList.add("alvo"); };
    b.ondragleave = () => b.classList.remove("alvo");
    b.ondrop = e => { e.preventDefault(); b.classList.remove("alvo"); const it = JSON.parse(e.dataTransfer.getData("text/plain")); mover(it, d.data, it.ini); };
    t.appendChild(b);
  });
}

function idDe(it) { return it.tipo === "prog" ? "prog:" + it.prog : it.id; }

function desenharDia() {
  const d = G.dias[G.dia], box = $("#g-dia");
  box.innerHTML = "";
  if (!d) return;
  for (const it of d.itens) {
    const el = document.createElement("div");
    el.className = "item " + (it.tipo === "prog" ? "prog" : it.tipo === "card" ? "card" : "");
    el.style.setProperty("--cor", corBloco(it.bloco));
    el.draggable = it.tipo !== "card";
    el.innerHTML = `<span class="hora">${it.ini}</span><div><b>${esc(it.titulo)}</b>${it.inserido ? `<span class="etq ins">inserido</span>` : ""}${it.anuncios ? `<span class="etq ad">${it.anuncios} anúncio(s)</span>` : ""}
      <div class="blk">${esc(it.bloco_nome)} · até ${it.fim}${it.intervalos ? " · " + it.intervalos + " intervalo(s)" : ""}</div></div><span class="apagado">${mmss((it.fim_ms - it.ini_ms) / 1000)}</span>`;
    el.onclick = () => menuItem(d, it);
    el.ondragstart = e => e.dataTransfer.setData("text/plain", JSON.stringify({ ...it, data: d.data, idx: idDe(it) }));
    el.ondragover = e => { e.preventDefault(); el.classList.add("alvo"); };
    el.ondragleave = () => el.classList.remove("alvo");
    el.ondrop = e => { e.preventDefault(); el.classList.remove("alvo"); const src = JSON.parse(e.dataTransfer.getData("text/plain")); mover(src, d.data, it.ini); };
    box.appendChild(el);
  }
  if (d.removidos.length) box.insertAdjacentHTML("beforeend", `<p class="apagado">Tirados deste dia: ${d.removidos.map(x => esc(x.id)).join(", ")} (veja "Mudanças desta grade" para devolver).</p>`);
}

function menuItem(d, it) {
  if (it.tipo === "card") return;
  modal(`<h3>${esc(it.titulo)}</h3><p class="apagado">${d.dia} ${dataBR(d.data)}, ${it.ini}–${it.fim} · ${esc(it.bloco_nome)}</p>
    <div class="linha"><button id="m-ver">Assistir neste horário</button><button id="m-mover">Mover para outro horário</button>
    <button class="perigo" id="m-tirar">${it.inserido ? "Desfazer a inserção" : "Tirar deste dia"}</button></div>
    <p class="apagado" style="margin-top:12px">${it.tipo === "prog" ? "Tirar um programa próprio daqui vale só para este dia; o horário fixo continua." :
      "Um título tirado não some: ele volta no dia seguinte, e outro do mesmo bloco entra no lugar."}</p>`);
  $("#m-ver").onclick = () => { fecharModal(); $("#g-qd").value = d.data; $("#g-qh").value = it.ini; verAgora(d.data + "T" + it.ini + ":30"); };
  $("#m-tirar").onclick = () => tenta(async () => { await api("/api/grade/remover", { data: d.data, id: idDe(it), at: it.ini, inserido: it.inserido }); fecharModal(); toast("Feito. Lembre de publicar."); abrir(); });
  $("#m-mover").onclick = () => {
    $("#modal-corpo").insertAdjacentHTML("beforeend", `<div class="cartao" style="margin-top:12px"><div class="linha"><input type="date" id="m-d" value="${d.data}"><input type="time" id="m-h" value="${it.ini}" step="300"><button class="principal" id="m-ok">Mover</button></div></div>`);
    $("#m-ok").onclick = () => { fecharModal(); mover({ ...it, data: d.data, idx: idDe(it) }, $("#m-d").value, $("#m-h").value); };
  };
}

async function mover(it, data, at) {
  if (it.tipo === "card") return;
  if (it.data === data && it.ini === at) return;
  if (!confirm(`Mover "${it.titulo}" para ${dataBR(data)} às ${at}?`)) return;
  await tenta(async () => {
    const r = await api("/api/grade/inserir", { data, at, id: it.idx || idDe(it), de: { data: it.data, at: it.ini, inserido: it.inserido } });
    if (r.aviso) toast(r.aviso, true); else toast("Movido. Lembre de publicar.");
    abrir();
  });
}

async function verAgora(q) {
  const box = $("#g-agora"); box.innerHTML = `<small>Procurando...</small>`;
  await tenta(async () => {
    const a = await api("/api/grade/agora" + qs({ quando: q }));
    box.innerHTML = `<b>${esc(a.titulo)}</b><br><small>${esc(a.ini || "")}–${esc(a.fim || "")}${a.parte > 0 ? " · parte " + (a.parte + 1) : ""}</small><div class="tela" style="margin-top:8px"></div>
      <small>Depois: ${(a.seguintes || []).slice(0, 3).map(s => esc(s.ini + " " + s.titulo)).join(" · ")}</small>`;
    tocar($(".tela", box), a);
  });
}

async function mudancas() {
  const m = await api("/api/grade/mudancas");
  const box = $("#g-mud");
  const l = [...m.inserir.map((x, i) => ({ ...x, lista: "inserir", i, txt: `${dataBR(x.data)} ${x.at}: entra ${x.nome}` })),
             ...m.remover.map((x, i) => ({ ...x, lista: "remover", i, txt: `${dataBR(x.data)}${x.at ? " " + x.at : ""}: sai ${x.nome}` }))];
  box.innerHTML = l.length ? "" : `<small>Nenhuma. A grade segue os blocos normais.</small>`;
  for (const x of l) {
    const d = document.createElement("div"); d.className = "linha"; d.style.margin = "4px 0";
    d.innerHTML = `<span style="flex:1">${esc(x.txt)}</span><button class="pequeno">desfazer</button>`;
    $("button", d).onclick = () => tenta(async () => { await api("/api/grade/cancelar", { lista: x.lista, indice: x.i }); abrir(); });
    box.appendChild(d);
  }
}

async function formInserir(data, at) {
  const [f, p] = await Promise.all([api("/api/filmes" + qs({ estado: "no_ar" })), api("/api/programas")]);
  modal(`<h3>Inserir na grade</h3><p class="apagado">Coloca um título num dia e hora. O que estava ali se ajusta em volta.</p>
    <div class="linha"><input type="date" id="i-d" value="${data}"><input type="time" id="i-h" value="${at}" step="300"></div>
    <label>Procure o título</label><input class="campo" id="i-q" placeholder="nome do filme, desenho, série...">
    <div id="i-res" style="max-height:320px;overflow:auto;margin-top:8px"></div>`);
  const progs = p.programas.map(x => ({ id: "prog:" + x.id, titulo: "▶ " + x.nome + " (episódio extra)", bloco: "programa próprio", dur: 0 }));
  const desenha = async () => {
    const q = $("#i-q").value;
    const r = q ? await api("/api/filmes" + qs({ q, estado: "no_ar" })) : f;
    const l = [...progs.filter(x => !q || x.titulo.toLowerCase().includes(q.toLowerCase())), ...r.filmes].slice(0, 60);
    $("#i-res").innerHTML = `<table>${l.map(x => `<tr class="clicavel" data-id="${esc(x.id)}"><td>${esc(x.titulo)} ${x.ano ? `<small>(${x.ano})</small>` : ""}</td><td><small>${esc(x.bloco)}</small></td><td><small>${x.dur ? mmss(x.dur) : ""}</small></td></tr>`).join("")}</table>`;
    $$("#i-res tr").forEach(tr => tr.onclick = () => tenta(async () => {
      const r = await api("/api/grade/inserir", { data: $("#i-d").value, at: $("#i-h").value, id: tr.dataset.id });
      fecharModal(); if (r.aviso) toast(r.aviso, true); else toast("Inserido. Lembre de publicar."); abrir(); }));
  };
  let t; $("#i-q").oninput = () => { clearTimeout(t); t = setTimeout(desenha, 250); };
  desenha();
}

async function formBlocos() {
  const r = await api("/api/grade/blocos");
  modal(`<h3>Blocos do dia</h3><p class="apagado">A divisão normal de todo dia: a partir de que hora entra cada bloco. Os títulos de cada bloco passam em ordem, sem repetir até acabar a lista. "Alterna com" troca de bloco dia sim, dia não.</p>
    <div class="blocos-ed" id="b-l"></div><button class="pequeno" id="b-mais">+ bloco</button><div id="b-erro"></div>
    <div class="linha fim" style="margin-top:14px"><button onclick="fecharModal()">Cancelar</button><button class="principal" id="b-ok">Salvar</button></div>`);
  const opts = sel => r.blocos.map(b => `<option value="${b.id}" ${b.id === sel ? "selected" : ""}>${esc(b.nome)} (${b.titulos})</option>`).join("");
  const linha = s => {
    const [a, ...alt] = s.block.split("|");
    const d = document.createElement("div"); d.className = "horario";
    d.innerHTML = `<input type="time" value="${s.at}" step="300"><select class="b1">${opts(a)}</select> alterna com
      <select class="b2"><option value="">(nenhum)</option>${opts(alt[0] || "")}</select><button class="pequeno perigo">remover</button>`;
    if (alt.length > 1) d.dataset.resto = alt.slice(1).join("|");
    $("button", d).onclick = () => d.remove();
    $("#b-l").appendChild(d);
  };
  r.dia.forEach(linha);
  $("#b-mais").onclick = () => linha({ at: "12:00", block: r.blocos[0].id });
  $("#b-ok").onclick = async () => {
    const dia = $$("#b-l .horario").map(d => ({ at: $("input", d).value,
      block: [$(".b1", d).value, $(".b2", d).value, d.dataset.resto].filter(Boolean).join("|") }));
    try { await api("/api/grade/blocos", { dia }); fecharModal(); toast("Blocos salvos. Lembre de publicar."); abrir(); }
    catch (e) { $("#b-erro").innerHTML = `<div class="erro">${esc(e.message)}</div>`; }
  };
}

// ---- Filmes ----
let F = { q: "", bloco: "", estado: "" };
PAGINAS.filmes = async main => {
  main.innerHTML = `<div class="linha"><div><h1>Filmes</h1><p class="sub">O acervo: filmes, desenhos, curtas e séries, todos em domínio público, tocados direto do Internet Archive.</p></div>
    <span class="espaco"></span><button class="principal" id="f-novo">+ Incluir título</button></div>
    <div class="linha"><input id="f-q" placeholder="Procurar..." style="flex:1" value="${esc(F.q)}"><select id="f-b"><option value="">Todos os blocos</option></select>
      <select id="f-e"><option value="">No ar e fora</option><option value="no_ar">Só no ar</option><option value="fora">Só fora do ar</option></select></div>
    <p class="apagado" id="f-n"></p><div id="f-l"></div>`;
  const r0 = await api("/api/filmes" + qs(F));
  $("#f-b").innerHTML += r0.blocos.map(b => `<option value="${b.id}">${esc(b.nome)}</option>`).join("");
  $("#f-b").value = F.bloco; $("#f-e").value = F.estado;
  const desenha = r => {
    $("#f-n").textContent = r.total + " título(s)" + (r.total > r.filmes.length ? " (mostrando " + r.filmes.length + ")" : "");
    $("#f-l").innerHTML = `<table><tr><th>Título</th><th>Bloco</th><th>Duração</th><th>Cópias</th><th>Intervalos</th><th></th></tr>
      ${r.filmes.map(x => `<tr class="clicavel" data-id="${esc(x.id)}"><td><b>${esc(x.titulo)}</b> <small>${x.ano || ""}</small></td><td><small>${esc((r0.blocos.find(b => b.id === x.bloco) || { nome: x.bloco }).nome)}</small></td>
        <td>${mmss(x.dur)}</td><td>${x.copias}${x.ruins ? ` <span class="pilula ruim">${x.ruins} ruim</span>` : ""}</td><td>${x.intervalos || "–"}</td>
        <td>${x.fora ? `<span class="pilula ruim">fora do ar</span>` : ""}</td></tr>`).join("")}</table>`;
    $$("#f-l tr[data-id]").forEach(tr => tr.onclick = () => fichaFilme(r.filmes.find(x => x.id === tr.dataset.id), r0.blocos));
  };
  desenha(r0);
  let t;
  const busca = () => { clearTimeout(t); t = setTimeout(async () => { F = { q: $("#f-q").value, bloco: $("#f-b").value, estado: $("#f-e").value };
    desenha(await api("/api/filmes" + qs(F))); }, 250); };
  $("#f-q").oninput = busca; $("#f-b").onchange = busca; $("#f-e").onchange = busca;
  $("#f-novo").onclick = () => formFilme(r0.blocos);
};

async function fichaFilme(x, blocos) {
  const iv = await api("/api/filmes/intervalos" + qs({ id: x.id }));
  const c0 = iv.copias[0] || { url: "", cortes: [] };
  modal(`<h3>${esc(x.titulo)} <small>${x.ano || ""}</small></h3><p class="apagado">${esc(x.sinopse)}</p>
    <div class="linha">${x.fora ? `<button class="principal" data-a="voltar">Pôr de volta no ar</button>` : `<button class="perigo" data-a="tirar">Tirar do ar</button>`}
      ${x.estudio ? `<button class="perigo" data-a="apagar">Apagar</button>` : ""}<button data-a="inserir">Inserir na grade...</button></div>
    <h2>Cópias</h2><p class="apagado">O canal toca a primeira; se ela falhar, a seguinte.</p>
    <table>${x.fontes.map((s, i) => `<tr><td style="word-break:break-all"><small>${esc(s.url)}</small></td><td>${mmss(s.dur)}</td>
      <td>${i ? `<button class="pequeno" data-c="copia_topo" data-u="${esc(s.url)}">usar primeiro</button>` : `<span class="pilula">primeira</span>`}</td>
      <td><button class="pequeno perigo" data-c="copia_remover" data-u="${esc(s.url)}">remover</button></td></tr>`).join("")}</table>
    <div class="linha" style="margin-top:8px"><input id="c-url" placeholder="https://archive.org/download/..." style="flex:1"><button id="c-add">Incluir cópia</button><button id="c-proc">Procurar cópias novas</button></div>
    <div id="c-res"></div>
    <h2>Intervalos comerciais</h2>
    <p class="apagado">Só filmes de 40 minutos ou mais têm intervalo. Toque o filme, pare onde deve entrar o intervalo (de preferência num escurecimento ou troca de cena) e clique em "Marcar aqui".</p>
    <div class="player"><video id="iv-v" controls preload="metadata" src="${esc(c0.url)}"></video></div>
    <div class="linha" style="margin-top:8px"><button class="principal" id="iv-marca">Marcar intervalo aqui</button><button id="iv-auto">Detectar automaticamente</button>
      <button id="iv-limpa" class="perigo">Sem intervalos</button><span class="espaco"></span><button id="iv-salva">Salvar intervalos</button></div>
    <ul class="cortes" id="iv-l"></ul>`);
  let cortes = [...c0.cortes];
  const lista = () => { $("#iv-l").innerHTML = cortes.map((c, i) => `<li>${mmss(c / 1000)} <button class="pequeno" data-i="${i}" data-a="ir">ir</button> <button class="pequeno perigo" data-i="${i}" data-a="x">tirar</button></li>`).join("") || "<li class='apagado'>Nenhum intervalo: o filme passa direto.</li>";
    $$("#iv-l button").forEach(b => b.onclick = () => { const i = +b.dataset.i; if (b.dataset.a === "x") { cortes.splice(i, 1); lista(); } else $("#iv-v").currentTime = cortes[i] / 1000; }); };
  lista();
  $("#iv-marca").onclick = () => { cortes.push(Math.round($("#iv-v").currentTime * 1000)); cortes.sort((a, b) => a - b); lista(); };
  $("#iv-limpa").onclick = () => { cortes = []; lista(); };
  $("#iv-salva").onclick = () => tenta(async () => { await api("/api/filmes/intervalos", { url: c0.url, cortes, dur: c0.dur }); toast("Intervalos salvos. Lembre de publicar."); });
  $("#iv-auto").onclick = () => tenta(async () => { const j = await api("/api/filmes/detectar", { id: x.id }); fecharModal(); seguir(j.job); });
  $$("[data-a]", $("#modal-corpo")).forEach(b => { if (!["tirar", "voltar", "apagar", "inserir"].includes(b.dataset.a)) return;
    b.onclick = () => tenta(async () => {
      if (b.dataset.a === "inserir") { fecharModal(); location.hash = "grade"; setTimeout(() => formInserirDireto(x), 400); return; }
      if (b.dataset.a === "apagar" && !confirm("Apagar este título do acervo?")) return;
      await api("/api/filmes/editar", { id: x.id, acao: b.dataset.a }); fecharModal(); toast("Feito. Lembre de publicar."); abrir(); }); });
  $$("[data-c]", $("#modal-corpo")).forEach(b => b.onclick = () => tenta(async () => {
    await api("/api/filmes/editar", { id: x.id, acao: b.dataset.c, url: b.dataset.u }); fecharModal(); toast("Feito."); abrir(); }));
  $("#c-add").onclick = () => tenta(async () => { await api("/api/filmes/editar", { id: x.id, acao: "copia_nova", url: $("#c-url").value }); fecharModal(); toast("Cópia incluída."); abrir(); });
  $("#c-proc").onclick = () => tenta(async () => { const j = await api("/api/filmes/procurar", { id: x.id }); seguir(j.job, job => mostrarCopias(x, job)); toast("Procurando... (aparece embaixo à direita)"); });
}

function mostrarCopias(x, job) {
  if (job.estado !== "pronto") return;
  const l = job.resultado.copias;
  modal(`<h3>Cópias novas de ${esc(x.titulo)}</h3>${l.length ? "" : "<p>Não achei nenhuma cópia nova.</p>"}
    <table>${l.map(s => `<tr><td><small>${esc(s.ia_title || s.ia)}<br>${esc(s.url)}</small></td><td>${mmss(s.dur)} · ${s.h}p</td>
      <td><a class="botao pequeno" href="${esc(s.url)}" target="_blank">ver</a></td><td><button class="pequeno principal" data-u="${esc(s.url)}" data-d="${s.dur}">usar</button></td></tr>`).join("")}</table>`);
  $$("button[data-u]", $("#modal-corpo")).forEach(b => b.onclick = () => tenta(async () => {
    await api("/api/filmes/editar", { id: x.id, acao: "copia_nova", url: b.dataset.u, dur: b.dataset.d }); fecharModal(); toast("Cópia incluída como primeira. Lembre de publicar."); abrir(); }));
}

function formInserirDireto(x) { formInserir(hoje(), "20:00").then(() => { $("#i-q").value = x.titulo; $("#i-q").dispatchEvent(new Event("input")); }); }

function formFilme(blocos) {
  modal(`<h3>Incluir título</h3>
    <div class="alerta">Só entra no canal o que é <b>domínio público</b>. Confira antes (veja o Manual, "Incluir filme"). Na dúvida, não inclua.</div>
    <label>Título</label><input class="campo" id="n-t">
    <div class="linha"><div><label>Ano</label><input id="n-a" type="number" style="width:100px"></div><div><label>País</label><input id="n-p" placeholder="US" style="width:80px"></div>
      <div><label>Bloco</label><select id="n-b">${blocos.map(b => `<option value="${b.id}">${esc(b.nome)}</option>`).join("")}</select></div>
      <div><label>Tipo</label><select id="n-k"><option value="film">filme</option><option value="short">curta</option><option value="cartoon">desenho</option><option value="tv">episódio de série</option></select></div></div>
    <label>Endereço do vídeo (MP4 no Internet Archive)</label><input class="campo" id="n-u" placeholder="https://archive.org/download/ITEM/ARQUIVO.mp4">
    <label>Duração em minutos (deixe vazio para medir pela internet)</label><input id="n-d" type="number" style="width:120px">
    <label>Sinopse (uma linha, em português)</label><input class="campo" id="n-s">
    <label>Por que é domínio público?</label><input class="campo" id="n-dp" placeholder="Ex.: filme americano de 1922, publicado antes de 1931">
    <label class="inline" style="margin-top:12px"><input type="checkbox" id="n-ok"> Confirmo que conferi: é domínio público.</label><div id="n-erro"></div>
    <div class="linha fim" style="margin-top:14px"><button onclick="fecharModal()">Cancelar</button><button class="principal" id="n-salva">Incluir</button></div>`);
  $("#n-salva").onclick = async () => {
    const filme = { titulo: $("#n-t").value, ano: $("#n-a").value, pais: $("#n-p").value, bloco: $("#n-b").value, tipo: $("#n-k").value,
      url: $("#n-u").value, dur: $("#n-d").value ? $("#n-d").value * 60 : 0, sinopse: $("#n-s").value, dp: $("#n-dp").value };
    try { await api("/api/filmes/novo", { filme, confirmo_dp: $("#n-ok").checked && !!filme.dp.trim() }); fecharModal(); toast("Incluído. Lembre de publicar."); abrir(); }
    catch (e) { $("#n-erro").innerHTML = `<div class="erro">${esc(e.message)}</div>`; }
  };
}

// ---- Anúncios ----
PAGINAS.anuncios = async main => {
  const r = await api("/api/anuncios");
  main.innerHTML = `<div class="linha"><div><h1>Anúncios</h1><p class="sub">Anunciantes nos intervalos dos filmes. O anúncio entra no lugar das nossas chamadas, e o intervalo continua do mesmo tamanho.</p></div>
    <span class="espaco"></span><button class="principal grande" id="a-novo">+ Novo anúncio</button></div>
    ${r.intervalos ? "" : `<div class="alerta">Os intervalos comerciais ainda não estão ligados no canal. Pode cadastrar os anúncios: eles começam a passar quando os intervalos forem ligados.</div>`}<div id="a-l"></div>`;
  $("#a-novo").onclick = () => formAnuncio(null, r.blocos);
  const l = $("#a-l");
  if (!r.anuncios.length) l.innerHTML = `<div class="vazio">Nenhum anúncio. Enquanto não houver, o intervalo mostra o "Anuncie aqui".</div>`;
  const hj = hoje();
  for (const a of r.anuncios) {
    const ativo = a.ativo !== false && (!a.inicio || a.inicio <= hj) && (!a.fim || hj <= a.fim);
    const ins = a.por_bloco && Object.keys(a.por_bloco).length ? Object.entries(a.por_bloco).map(([b, n]) => n + "× em " + (r.blocos.find(x => x.id === b) || { nome: b }).nome).join(", ") : (a.por_dia || 0) + " por dia, em qualquer bloco";
    const d = document.createElement("div"); d.className = "cartao";
    d.innerHTML = `<div class="linha"><div style="flex:1"><h3>${esc(a.nome)} ${a.cliente ? `<small>· ${esc(a.cliente)}</small>` : ""}</h3>
      <div class="apagado">${a.inicio ? dataBR(a.inicio) : "?"} a ${a.fim ? dataBR(a.fim) : "?"} · ${esc(ins)}${a.dur ? " · " + a.dur.toFixed(1) + " s" : ""}${a.valor_insercao ? " · R$ " + Number(a.valor_insercao).toFixed(2) + " por inserção" : ""}</div></div>
      ${ativo ? `<span class="pilula ok">no período</span>` : `<span class="pilula">fora do período</span>`}
      ${!a.file ? `<span class="pilula ruim">sem vídeo</span>` : a.url ? `<span class="pilula ok">publicado</span>` : `<span class="pilula aviso">falta publicar</span>`}</div>
      <div class="linha" style="margin-top:10px">${a.file ? `<button class="pequeno" data-a="ver">Ver vídeo</button>` : ""}<button class="pequeno" data-a="video">${a.file ? "Trocar vídeo" : "Enviar vídeo"}</button>
        <button class="pequeno" data-a="rel">Relatório</button><button class="pequeno" data-a="ed">Editar</button><button class="pequeno perigo" data-a="x">Apagar</button>
        <input type="file" accept="video/*" hidden></div>`;
    const inp = $("input[type=file]", d);
    inp.onchange = () => inp.files[0] && enviar(inp.files[0], "anuncio", a.id);
    $$("button", d).forEach(b => b.onclick = () => tenta(async () => {
      const k = b.dataset.a;
      if (k === "ver") modal(`<h3>${esc(a.nome)}</h3><div class="player"><video controls autoplay src="${media(a.file)}"></video></div>`);
      if (k === "video") inp.click();
      if (k === "ed") formAnuncio(a, r.blocos);
      if (k === "rel") relatorio(a);
      if (k === "x" && confirm(`Apagar o anúncio "${a.nome}"?`)) { await api("/api/anuncios/apagar", { id: a.id }); abrir(); }
    }));
    l.appendChild(d);
  }
};

function formAnuncio(a, blocos) {
  a = a || { nome: "", cliente: "", inicio: hoje(), fim: addDias(hoje(), 29), por_dia: 4, por_bloco: {}, valor_insercao: "" };
  const porBloco = a.por_bloco && Object.keys(a.por_bloco).length;
  modal(`<h3>${a.id ? "Editar anúncio" : "Novo anúncio"}</h3>
    <label>Nome do anúncio</label><input class="campo" id="a-n" value="${esc(a.nome)}" placeholder="Ex.: Padaria do Zé 30s">
    <label>Anunciante</label><input class="campo" id="a-c" value="${esc(a.cliente || "")}">
    <div class="linha"><div><label>Começa</label><input type="date" id="a-i" value="${esc(a.inicio || "")}"></div><div><label>Termina</label><input type="date" id="a-f" value="${esc(a.fim || "")}"></div>
      <div><label>R$ por inserção (para o relatório)</label><input type="number" step="0.01" id="a-v" value="${esc(a.valor_insercao || "")}" style="width:140px"></div></div>
    <label>Inserções</label>
    <label class="inline"><input type="radio" name="modo" value="dia" ${porBloco ? "" : "checked"}> Por dia, em qualquer bloco: <input type="number" id="a-pd" min="0" value="${a.por_dia || 0}" style="width:80px"></label>
    <label class="inline" style="margin-top:8px"><input type="radio" name="modo" value="bloco" ${porBloco ? "checked" : ""}> Por dia, em blocos escolhidos:</label>
    <div id="a-blocos" style="columns:2;margin-top:6px">${blocos.map(b => `<div><input type="number" min="0" data-b="${b.id}" value="${(a.por_bloco || {})[b.id] || 0}" style="width:60px"> ${esc(b.nome)}</div>`).join("")}</div>
    <p class="apagado">O vídeo do anúncio (até 2 minutos) você envia depois de salvar, no botão "Enviar vídeo".</p>
    <label class="inline"><input type="checkbox" id="a-at" ${a.ativo !== false ? "checked" : ""}> Ativo</label><div id="a-erro"></div>
    <div class="linha fim" style="margin-top:14px"><button onclick="fecharModal()">Cancelar</button><button class="principal" id="a-ok">Salvar</button></div>`);
  $("#a-ok").onclick = async () => {
    const pb = {}; if ($("input[name=modo]:checked").value === "bloco") $$("#a-blocos input").forEach(i => { if (+i.value > 0) pb[i.dataset.b] = +i.value; });
    const novo = { id: a.id, nome: $("#a-n").value, cliente: $("#a-c").value, inicio: $("#a-i").value, fim: $("#a-f").value,
      valor_insercao: $("#a-v").value, ativo: $("#a-at").checked, por_bloco: pb, por_dia: Object.keys(pb).length ? 0 : +$("#a-pd").value };
    try { await api("/api/anuncios", { anuncio: novo }); fecharModal(); toast("Anúncio salvo."); abrir(); }
    catch (e) { $("#a-erro").innerHTML = `<div class="erro">${esc(e.message)}</div>`; }
  };
}

async function relatorio(a) {
  modal(`<p class="apagado">Calculando a grade do período...</p>`);
  const r = await api("/api/anuncios/relatorio" + qs({ id: a.id }));
  modal(`<h3>Relatório: ${esc(r.nome)}</h3><p class="apagado">${esc(r.cliente)} · ${r.dias.length} dia(s)</p>
    <div class="grade2"><div class="cartao"><small>INSERÇÕES NA GRADE</small><div class="numero">${r.total}</div></div>
      ${r.preco ? `<div class="cartao"><small>VALOR (R$ ${r.preco.toFixed(2)} cada)</small><div class="numero">R$ ${r.valor.toFixed(2)}</div></div>` : ""}</div>
    ${r.aviso ? `<div class="alerta">${esc(r.aviso)}</div>` : ""}
    <table><tr><th>Dia</th><th>Pedidas</th><th>Na grade</th><th>Onde</th></tr>
    ${r.dias.map(d => `<tr><td>${dataBR(d.data)}</td><td>${d.pedidas}</td><td>${d.na_grade < d.pedidas ? `<b style="color:var(--vermelho)">${d.na_grade}</b>` : d.na_grade}</td>
      <td><small>${Object.entries(d.blocos).map(([b, n]) => esc(b) + ": " + n).join(", ")}</small></td></tr>`).join("")}</table>
    <p class="apagado">Calculado pela grade publicada mais as mudanças ainda não publicadas. Mudanças futuras na grade podem mudar os horários.</p>
    <div class="linha fim"><button onclick="window.print()">Imprimir</button></div>`);
}

// ---- Saúde ----
PAGINAS.saude = async main => {
  const r = await api("/api/saude");
  main.innerHTML = `<h1>Saúde do canal</h1><p class="sub">Os filmes vêm do Internet Archive; às vezes um link quebra. O canal no ar já pula sozinho os quebrados, mas aqui você troca a cópia de vez.</p>
    <div class="linha"><button class="principal" id="s-48">Testar os próximos 2 dias</button><button id="s-tudo">Testar o acervo inteiro (demora)</button>
      <span class="apagado">${r.ultima ? "Último teste: " + r.ultima : "Ainda não testado neste Mac."}</span></div>
    <div id="s-l" style="margin-top:14px"></div>`;
  const go = escopo => tenta(async () => seguir((await api("/api/saude/verificar", { escopo })).job, () => abrir()));
  $("#s-48").onclick = () => go("48h"); $("#s-tudo").onclick = () => go("tudo");
  const l = $("#s-l");
  if (!r.problemas.length) { l.innerHTML = `<div class="bom">Nenhum link quebrado encontrado${r.ultima ? "" : " (ainda não testado)"}.</div>`; return; }
  for (const p of r.problemas) {
    const d = document.createElement("div"); d.className = "cartao";
    d.innerHTML = `<div class="linha"><h3 style="flex:1">${esc(p.titulo)}</h3>${p.em_breve ? `<span class="pilula aviso">passa nos próximos 2 dias</span>` : ""}
      ${p.todas_ruins ? `<span class="pilula ruim">nenhuma cópia funciona</span>` : `<span class="pilula">${p.boas.length} cópia(s) boa(s)</span>`}${p.fora ? `<span class="pilula">fora do ar</span>` : ""}</div>
      ${p.ruins.map(s => `<div class="linha"><small style="flex:1;word-break:break-all">✕ ${esc(s.url)} <i>(${esc(s.porque)})</i></small>
        <button class="pequeno" data-u="${esc(s.url)}">Remover esta cópia</button></div>`).join("")}
      <div class="linha" style="margin-top:8px">${p.boas.length ? `<button class="principal pequeno" data-a="boa">Trocar: usar a cópia boa e remover as quebradas</button>` : ""}
        <button class="pequeno" data-a="proc">Procurar cópia nova</button>${p.fora ? "" : `<button class="pequeno perigo" data-a="tirar">Tirar do ar</button>`}</div>`;
    $$("button[data-u]", d).forEach(b => b.onclick = () => tenta(async () => { await api("/api/filmes/editar", { id: p.id, acao: "copia_remover", url: b.dataset.u }); toast("Removida."); abrir(); }));
    $$("button[data-a]", d).forEach(b => b.onclick = () => tenta(async () => {
      if (b.dataset.a === "boa") { await api("/api/filmes/editar", { id: p.id, acao: "copia_topo", url: p.boas[0] });
        for (const s of p.ruins) await api("/api/filmes/editar", { id: p.id, acao: "copia_remover", url: s.url }); toast("Trocado. Lembre de publicar."); abrir(); }
      if (b.dataset.a === "tirar") { await api("/api/filmes/editar", { id: p.id, acao: "tirar" }); toast("Tirado do ar."); abrir(); }
      if (b.dataset.a === "proc") { const j = await api("/api/filmes/procurar", { id: p.id }); seguir(j.job, job => mostrarCopias({ id: p.id, titulo: p.titulo }, job)); }
    }));
    l.appendChild(d);
  }
};

// ---- Publicar ----
PAGINAS.publicar = async main => {
  const r = await api("/api/publicar");
  const s = r.resumo, nada = !s.arquivos.length && !s.videos.length && !s.commits_de_fora.length;
  main.innerHTML = `<h1>Publicar</h1><p class="sub">Manda para o ar tudo o que você mudou aqui. O canal se atualiza sozinho em 1 a 3 minutos.</p>
    ${r.erros.map(e => `<div class="erro">${esc(e)}</div>`).join("")}${r.avisos.map(e => `<div class="alerta">${esc(e)}</div>`).join("")}
    <div class="cartao"><h3>O que vai</h3>${nada ? `<p class="apagado">Nada novo: o que está aqui já está no ar.</p>` : `<ul>
      ${s.arquivos.map(a => `<li>${esc(a.nome)}</li>`).join("")}
      ${s.videos.map(v => `<li>Vídeo: ${{ episodio: "episódio", anuncio: "anúncio", vinheta: "vinheta" }[v.tipo] || esc(v.tipo)} de "${esc(v.de)}" (${v.mb} MB)</li>`).join("")}
      ${s.commits_de_fora.length ? `<li>Mais ${s.commits_de_fora.length} mudança(s) feitas fora do Estúdio: <small>${s.commits_de_fora.map(esc).join(" · ")}</small></li>` : ""}</ul>`}
      <div class="linha" style="margin-top:12px"><button id="p-ensaio" ${nada ? "disabled" : ""}>Ensaio (confere sem enviar)</button>
        <button class="principal grande" id="p-ok" ${nada || r.erros.length ? "disabled" : ""}>Publicar agora</button>
        <span class="espaco"></span>${nada ? "" : `<button class="perigo pequeno" id="p-desc">Descartar as mudanças</button>`}</div></div>
    <div class="cartao"><h3>Conferir o canal no ar</h3><p class="apagado">Abre a grade publicada na internet e vê se seus programas e anúncios estão lá.</p>
      <button id="p-vivo">Conferir agora</button> <a class="botao" href="https://tv.kolja.com.br/" target="_blank">Abrir o site do canal</a><div id="p-vivo-r"></div></div>
    <div class="cartao"><h3>Configurar (só uma vez)</h3>
      <p>Chave do GitHub: ${r.chave === "chaveiro" ? `<span class="pilula ok">guardada no Chaveiro do Mac</span>` : r.chave === "gh" ? `<span class="pilula ok">usando o login do GitHub deste Mac</span>` : `<span class="pilula ruim">falta</span>`}
        <button class="pequeno" id="p-testar">Testar a chave</button></p>
      <details><summary>Colar uma chave nova do GitHub</summary><ol class="passos">
        <li>Abra <a href="https://github.com/settings/personal-access-tokens/new" target="_blank">github.com/settings/personal-access-tokens/new</a> (logado na sua conta).</li>
        <li>Nome: <b>Estúdio KÖLJA TV</b>. Validade: 1 ano. Resource owner: <b>koljatv</b>. Repository access: <b>Only select repositories</b> › koljatv.github.io.</li>
        <li>Permissions › Repository › <b>Contents: Read and write</b>. Clique em <b>Generate token</b> e copie.</li>
        <li>Cole aqui: <input id="p-tok" type="password" placeholder="github_pat_..." style="width:320px"> <button class="principal pequeno" id="p-salva">Guardar</button></li></ol></details>
      <label>Onde guardar os episódios dos programas</label>
      <label class="inline"><input type="radio" name="dest" value="github" ${r.conf.destino !== "ia" ? "checked" : ""}> GitHub (padrão, sem cadastro extra)</label>
      <label class="inline"><input type="radio" name="dest" value="ia" ${r.conf.destino === "ia" ? "checked" : ""}> Internet Archive (público e permanente)</label>
      <div id="p-ia" ${r.conf.destino === "ia" ? "" : "hidden"} style="margin-top:8px"><small>Chaves em <a href="https://archive.org/account/s3.php" target="_blank">archive.org/account/s3.php</a>. ${r.ia ? "<span class='pilula ok'>guardadas</span>" : ""}</small><br>
        <input id="p-iaa" placeholder="Access key" style="width:220px"> <input id="p-ias" type="password" placeholder="Secret key" style="width:220px"> <button class="pequeno" id="p-iasalva">Guardar</button></div>
      <p class="apagado">As chaves ficam no Chaveiro do Mac, nunca em arquivo nem no GitHub.</p></div>`;
  $("#p-ensaio").onclick = () => tenta(async () => seguir((await api("/api/publicar", { ensaio: true })).job));
  $("#p-ok").onclick = () => tenta(async () => { if (!confirm("Publicar agora? Em 1 a 3 minutos está no ar.")) return;
    seguir((await api("/api/publicar", {})).job, j => { if (j.estado === "pronto") toast("Publicado!"); abrir(); }); });
  if ($("#p-desc")) $("#p-desc").onclick = () => tenta(async () => { if (!confirm("Jogar fora TODAS as mudanças ainda não publicadas? (Os vídeos enviados continuam no Mac.)")) return;
    await api("/api/descartar", {}); toast("Descartado."); abrir(); });
  $("#p-vivo").onclick = () => tenta(async () => { $("#p-vivo-r").innerHTML = "<small>Abrindo...</small>"; const v = await api("/api/aovivo");
    $("#p-vivo-r").innerHTML = `<div class="${v.ok ? "bom" : "erro"}">${esc(v.msg)}${v.ok ? `<br>${v.programas.map(p => esc(p.nome) + (p.no_ar ? " ✓ no ar" : " ✕ ainda não")).join("<br>")}
      ${v.anuncios.map(p => "<br>Anúncio " + esc(p.nome) + (p.no_ar ? " ✓" : " ✕")).join("")}` : ""}</div>`; });
  $("#p-testar").onclick = () => tenta(async () => { const t = await api("/api/config/testar"); toast(t.msg, !t.ok); });
  $("#p-salva").onclick = () => tenta(async () => { await api("/api/config", { github: $("#p-tok").value }); const t = await api("/api/config/testar"); toast(t.msg, !t.ok); abrir(); });
  $$("input[name=dest]").forEach(i => i.onchange = () => tenta(async () => { await api("/api/config", { destino: i.value }); $("#p-ia").hidden = i.value !== "ia"; }));
  $("#p-iasalva").onclick = () => tenta(async () => { await api("/api/config", { ia_access: $("#p-iaa").value, ia_secret: $("#p-ias").value }); toast("Chaves do Internet Archive guardadas."); abrir(); });
};

// ---- Desfazer ----
PAGINAS.desfazer = async main => {
  const r = await api("/api/historico");
  main.innerHTML = `<h1>Desfazer</h1><p class="sub">Cada publicação fica guardada. Se algo saiu errado, volte a grade para uma publicação anterior: ela é publicada de novo, do jeito que era.</p>
    <div id="d-l"></div>`;
  const l = $("#d-l");
  if (!r.publicacoes.length) { l.innerHTML = `<div class="vazio">Ainda não há publicações feitas pelo Estúdio.</div>`; return; }
  r.publicacoes.forEach((p, i) => {
    const d = document.createElement("div"); d.className = "cartao linha";
    d.innerHTML = `<div style="flex:1"><b>${esc(p.quando)}</b> ${i === 0 ? `<span class="pilula ok">no ar agora</span>` : ""}<br><small>${esc(p.o_que)}</small></div>
      ${i ? `<button>Voltar para esta</button>` : ""}`;
    if (i) $("button", d).onclick = () => tenta(async () => {
      if (!confirm(`Voltar a grade para como estava em ${p.quando} e publicar?`)) return;
      seguir((await api("/api/desfazer", { tag: p.tag })).job, () => abrir()); });
    l.appendChild(d);
  });
};

// ---- Ajuda ----
PAGINAS.ajuda = async main => {
  main.innerHTML = `<h1>Ajuda</h1><p class="sub">Tudo aqui funciona sem internet, menos Publicar, Saúde e procurar cópias de filmes.</p>
    <div class="cartao"><h3>Manual da Emissora</h3><p>O passo a passo de cada tarefa, com figuras.</p><a class="botao principal" href="/web/manual.pdf" target="_blank">Abrir o Manual (PDF)</a></div>
    <div class="cartao"><h3>Começo rápido</h3><ol class="passos">
      <li><b>Programa novo:</b> Programas › + Novo programa › nome, dias e hora › Salvar. As vinhetas se fazem sozinhas.</li>
      <li><b>Episódio:</b> arraste o vídeo para o quadro do programa. Espere a barra chegar ao fim.</li>
      <li><b>Conferir:</b> Grade › escolha o dia › veja seu programa no horário. "Assistir neste horário" mostra o que passa.</li>
      <li><b>Publicar:</b> Publicar › Publicar agora. Em 1 a 3 minutos está no ar.</li>
      <li><b>Deu errado?</b> Desfazer › Voltar para esta (a publicação anterior).</li></ol></div>
    <div class="cartao"><h3>Se o Estúdio não abrir</h3><p>Dê dois cliques em <b>Estúdio KÖLJA TV</b> na Mesa (ou em <code>estudio/Estúdio KÖLJA TV.command</code> na pasta do canal). Ele abre aqui no navegador, no endereço <code>http://127.0.0.1:8799</code>.</p></div>`;
};

abrir();
