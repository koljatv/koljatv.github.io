// KÖLJA TV site: the pages around the player. Reads the same grade the player and Retrotv read (grade/now.json →
// grade/schedule2.json, legendas/index.json) and never writes anything. On pages with the player, tv.js loads the
// grade and hands it over through window.KTV; elsewhere this file loads it itself.
(() => {
  'use strict';
  const B = document.body.dataset.base || '';
  const PAGE = document.body.dataset.page || '';
  const TZ = 'America/Sao_Paulo', MIN = 60e3;
  const $ = (s, el = document) => el.querySelector(s);
  const esc = x => String(x == null ? '' : x).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const hm = ms => new Date(ms).toLocaleTimeString('pt-BR', { timeZone: TZ, hour: '2-digit', minute: '2-digit' });
  const dayKey = ms => new Date(ms).toLocaleDateString('en-CA', { timeZone: TZ });
  const mins = ms => { const [h, m] = hm(ms).split(':').map(Number); return h * 60 + m; };
  const cap = s => s ? s[0].toUpperCase() + s.slice(1).toLowerCase() : s;
  const SMALL = new Set(['de', 'da', 'do', 'das', 'dos', 'e']);
  const nice = s => String(s || '').toLowerCase().split(' ').map((w, i) => i && SMALL.has(w) ? w : w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  let regions = null;
  try { regions = new Intl.DisplayNames(['pt-BR'], { type: 'region' }); } catch (e) {}
  const country = c => { if (!c) return ''; try { return regions ? regions.of(c) : c; } catch (e) { return c; } };
  const KIND = { film: 'Filme', short: 'Curta', tv: 'Série', cartoon: 'Desenho' };
  const dur = s => { if (!s) return ''; const m = Math.round(s / 60); return m < 60 ? m + ' min' : Math.floor(m / 60) + 'h' + (m % 60 ? String(m % 60).padStart(2, '0') : ''); };
  const VIN = { toons: 'desenhos', terror: 'terror', muda: 'muda', ficcao: 'ficcao', noir: 'noir', cult: 'cult', comedia: 'comedia', series: 'series',
    classicos: 'classicos', aventura: 'aventura', faroeste: 'faroeste', seriados: 'seriados', docs: 'docs' };

  // ---------- menu ----------
  const menuBtn = $('.top .menu'), sheet = $('#sheet');
  if (menuBtn && sheet) menuBtn.addEventListener('click', () => {
    const open = !sheet.classList.contains('open');
    sheet.classList.toggle('open', open); menuBtn.setAttribute('aria-expanded', open);
    document.documentElement.style.overflow = open ? 'hidden' : '';
  });

  // ---------- data ----------
  let S = null, P = [], LG = null, ART = {}, clock = () => Date.now();
  const titleOf = id => S && S.titles[id];
  const blockName = b => (S && S.blocks[b] || {}).pt || '';
  const hasLeg = id => !!(LG && LG.titles && LG.titles[id]);
  const legBadge = id => hasLeg(id) ? '<span class="badge leg" title="Com legenda em português">LEG</span>' : '';
  function programmes() { // one entry per programme: a feature's parts are one, its breaks are inside it
    const out = []; let last = null;
    for (const r of S.items) {
      const t = S.titles[r[2]]; if (!t) continue;
      const x = r.length > 4 ? r[4] : null;
      if (x != null && x > 0 && last && last.id === r[2]) { last.e = r[1]; continue; }
      last = { s: r[0], e: r[1], id: r[2], block: r[3], t };
      out.push(last);
    }
    return out;
  }
  const getJSON = (u, nostore) => fetch(u, nostore ? { cache: 'no-store' } : {}).then(r => { if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); });
  async function loadOwn() {
    const n = await getJSON(B + 'grade/now.json?m=' + Math.floor(Date.now() / MIN), true);
    return getJSON(B + 'grade/' + (n.schedule2 || n.schedule) + '?r=' + (n.rev2 || n.rev), true);
  }
  const artP = getJSON(B + 'arte/index.json').then(j => { ART = j; }).catch(() => {});
  function art(id, block, cls = '', eager) {
    const t = titleOf(id) || {}, alt = '';
    const lazy = eager ? '' : ' loading="lazy"';
    if (ART[id]) return `<div class="art ${cls}"><img src="${B}arte/${encodeURIComponent(id)}.jpg" alt="${esc(alt)}"${lazy} decoding="async"></div>`;
    const v = VIN[block || t.block];
    if (v) return `<div class="art ${cls}"><img src="${B}img/vinheta-${v}.jpg" alt=""${lazy} decoding="async"></div>`;
    return `<div class="art fallback b-${esc(block || t.block)} ${cls}"><span>${esc(blockName(block || t.block))}</span></div>`;
  }
  const link = id => B + 'programa/?id=' + encodeURIComponent(id);
  function dayLabel(d, today) {
    const tm = dayKey(Date.parse(today + 'T12:00:00-03:00') + 864e5);
    if (d === today) return 'Hoje';
    if (d === tm) return 'Amanhã';
    const ms = Date.parse(d + 'T12:00:00-03:00');
    return cap(new Date(ms).toLocaleDateString('pt-BR', { timeZone: TZ, weekday: 'long' }).split('-')[0]);
  }
  const dayShort = d => new Date(Date.parse(d + 'T12:00:00-03:00')).toLocaleDateString('pt-BR', { timeZone: TZ, day: 'numeric', month: 'numeric' });
  // dayparts: [{at: minutes, pt: 'MANHÃ · DESENHOS'}], with the slot of a time
  const parts = () => (S.dayparts || []).map(x => ({ at: +x.at.slice(0, 2) * 60 + +x.at.slice(3), pt: x.pt, hhmm: x.at })).sort((a, b) => a.at - b.at);
  const partIndex = (ps, ms) => { const m = mins(ms); let k = 0; ps.forEach((p, i) => { if (m >= p.at) k = i; }); return k; };
  const partName = p => { const [a, b] = p.pt.split(' · '); return { name: cap(a), what: b ? b.toLowerCase().replace(/^./, c => c.toUpperCase()) : '' }; };

  async function ready() {
    if (document.getElementById('ktv')) { // tv.js is on this page
      await new Promise(res => {
        if (window.KTV && window.KTV.S) return res();
        window.addEventListener('ktv:grade', res, { once: true });
      });
      S = window.KTV.S; clock = window.KTV.now; LG = window.KTV.LG;
      window.addEventListener('ktv:subs', () => { LG = window.KTV.LG; draw(); });
      window.addEventListener('ktv:grade', () => { S = window.KTV.S; P = programmes(); draw(); });
    } else {
      S = await loadOwn();
      getJSON(B + 'legendas/index.json?m=' + Math.floor(Date.now() / (10 * MIN))).then(j => { LG = j; draw(); }).catch(() => {});
    }
    P = programmes();
    await artP;
    draw();
    setInterval(draw, 30e3);
  }

  // ---------- pieces ----------
  const cur = () => { const t = clock(); return P.find(p => p.s <= t && t < p.e); };
  const after = (t, n, pred = () => true) => P.filter(p => p.s >= t && pred(p)).slice(0, n);

  function ticker() {
    const el = $('#ticker'); if (!el) return;
    const c = cur(); if (!c) { el.hidden = true; return; }
    const nx = after(c.e, 1)[0];
    el.hidden = false;
    $('a', el).innerHTML = `<span class="lbl"><span class="dot"></span>No ar</span><span class="t">${hm(c.s)}</span>
      <span class="n"><b>${esc(c.t.title)}</b>${nx ? ' &nbsp;·&nbsp; a seguir ' + hm(nx.s) + ' ' + esc(nx.t.title) : ''}</span><span class="go">Assistir →</span>`;
  }

  function upnext() {
    const el = $('#upnext'); if (!el) return;
    const c = cur(), list = after(c ? c.e : clock(), 4);
    el.innerHTML = list.length ? '<h3>A seguir</h3>' + list.map(p => `<a href="${link(p.id)}"><time>${hm(p.s)}</time>
      <span><span class="tt">${esc(p.t.title)}</span> ${legBadge(p.id)}<span class="sub">${esc(blockName(p.block))}${p.t.year ? ' · ' + p.t.year : ''}</span></span></a>`).join('') : '';
  }

  function poster() { // the programme's still on the screen until the viewer presses play
    const g = $('.ktv-glass'); if (!g) return;
    const c = cur() || after(clock(), 1)[0];
    const url = c && ART[c.id] ? `${B}arte/${encodeURIComponent(c.id)}.jpg` : c && VIN[c.block] ? `${B}img/vinheta-${VIN[c.block]}.jpg` : '';
    if (url && g.dataset.poster !== url) { g.dataset.poster = url; g.style.backgroundImage = `url("${url}")`; }
  }

  function dayparts() {
    const el = $('#parts'); if (!el) return;
    const t = clock(), today = dayKey(t), ps = parts(); if (!ps.length) return;
    const nowK = partIndex(ps, t);
    el.innerHTML = ps.map((p, k) => {
      const list = P.filter(x => dayKey(x.s) === today && partIndex(ps, x.s) === k && !(k === 0 && mins(x.s) > 23 * 60));
      if (!list.length) return '';
      const end = ps[k + 1] ? ps[k + 1].hhmm : '24:00';
      const pick = list.filter(x => x.t.kind === 'film').sort((a, b) => (b.e - b.s) - (a.e - a.s))[0] || list.filter(x => ART[x.id])[0] || list[0];
      const blocks = [...new Set(list.map(x => blockName(x.block)).filter(Boolean))].map(nice).join(' · ');
      const img = ART[pick.id] && pick.t.kind !== 'cartoon' ? `${B}arte/${encodeURIComponent(pick.id)}.jpg` : `${B}img/vinheta-${VIN[pick.block] || 'classicos'}.jpg`;
      const { name } = partName(p);
      return `<a class="part${k === nowK ? ' now' : ''}" href="${B}programacao/?faixa=${k}">
        <img src="${img}" alt="" loading="lazy" decoding="async">${k === nowK ? '<span class="badge live nowtag">AGORA</span>' : ''}
        <div class="in"><div class="hrs">${p.hhmm} – ${end}</div><h3>${esc(name)}</h3><div class="what">${esc(blocks)}</div>
        <div class="pick">${pick.t.kind === 'cartoon' ? `${list.length} desenhos hoje` : `<b>${esc(pick.t.title)}</b> às ${hm(pick.s)}`}</div></div></a>`;
    }).join('');
  }

  function card(p, today, opts = {}) {
    const t = clock(), on = p.s <= t && t < p.e, d = dayKey(p.s);
    const when = on ? '<span class="badge live">AO VIVO</span>' : `${d !== today ? esc(dayLabel(d, today)) + ' · ' : ''}<time>${hm(p.s)}</time>`;
    return `<a class="card" href="${link(p.id)}">${art(p.id, p.block)}
      <div class="when">${when}<span>${esc(nice(blockName(p.block)))}</span>${legBadge(p.id)}</div>
      <h3>${esc(p.t.title)}${p.t.year ? ` <span style="color:var(--fg3);font-weight:400">${p.t.year}</span>` : ''}</h3>
      ${opts.syn !== false && p.t.synopsis ? `<p>${esc(p.t.synopsis)}</p>` : ''}</a>`;
  }

  function films() {
    const el = $('#films'); if (!el) return;
    const t = clock(), today = dayKey(t);
    let list = P.filter(p => p.e > t && p.t.kind === 'film' && dayKey(p.s) === today);
    if (list.length < 6) list = P.filter(p => p.e > t && p.t.kind === 'film').slice(0, 8);
    const seen = new Set(); list = list.filter(p => !seen.has(p.id) && seen.add(p.id)).slice(0, 10);
    el.innerHTML = list.map(p => card(p, today)).join('');
  }

  function legRail() {
    const el = $('#legrail'), box = $('#legbox'); if (!el) return;
    if (!LG) return;
    const t = clock(), today = dayKey(t), seen = new Set();
    const list = P.filter(p => p.e > t && hasLeg(p.id) && !seen.has(p.id) && seen.add(p.id)).slice(0, 8);
    if (box) box.hidden = !list.length;
    el.innerHTML = list.map(p => card(p, today, { syn: false })).join('');
  }

  function novela() {
    const el = $('#novela'); if (!el) return;
    const key = 'ad_novela-segredos-da-serra', until = el.dataset.until || '';
    const live = S.ours && S.ours[key] && dayKey(clock()) <= until;
    el.hidden = !live;
    if (!live || el.dataset.wired) return;
    el.dataset.wired = '1';
    const btn = $('button', el), media = $('.media', el);
    btn.addEventListener('click', () => {
      const v = document.createElement('video');
      v.controls = true; v.playsInline = true; v.setAttribute('playsinline', ''); v.preload = 'auto';
      v.src = B + 'tv/ours/' + key + '.mp4';
      v.onerror = () => { if (S.ours[key].url && v.src !== S.ours[key].url) { v.src = S.ours[key].url; v.play().catch(() => {}); } };
      media.textContent = ''; media.append(v); v.play().catch(() => {});
    });
  }

  // ---------- Programação ----------
  const st = { day: '', part: -1, leg: false };
  function guide() {
    const el = $('#grade'); if (!el) return;
    const t = clock(), today = dayKey(t), ps = parts();
    if (!st.init) {
      const q = new URLSearchParams(location.search);
      st.day = q.get('dia') || ''; st.part = q.has('faixa') ? +q.get('faixa') : -1; st.leg = q.get('leg') === '1'; st.init = true;
    }
    const days = [...new Set(P.map(p => dayKey(p.s)))].filter(d => d >= today);
    if (!days.includes(st.day)) st.day = days[0] || today;
    const dEl = $('#days'), fEl = $('#faixas');
    dEl.innerHTML = days.map(d => `<button class="chip" type="button" data-d="${d}" aria-pressed="${d === st.day}">${esc(dayLabel(d, today))}<small>${dayShort(d)}</small></button>`).join('');
    fEl.innerHTML = `<button class="chip" type="button" data-f="-1" aria-pressed="${st.part < 0}">Dia todo</button>` +
      ps.map((p, k) => `<button class="chip" type="button" data-f="${k}" aria-pressed="${st.part === k}">${esc(partName(p).name)}<small>${p.hhmm}</small></button>`).join('') +
      `<span class="sep"></span><button class="chip amber" type="button" data-leg aria-pressed="${st.leg}">LEG · com legenda</button>`;
    const list = P.filter(p => dayKey(p.s) === st.day && (st.part < 0 || partIndex(ps, p.s) === st.part) && (!st.leg || hasLeg(p.id)));
    let html = '', k = -1;
    for (let i = 0; i < list.length; i++) {
      const p = list[i], pk = ps.length ? partIndex(ps, p.s) : 0;
      if (pk !== k && ps.length) { k = pk; const n = partName(ps[k]); html += `<div class="dp"><h2>${esc(n.name)}</h2><span>${ps[k].hhmm}${n.what ? ' · ' + esc(n.what) : ''}</span></div>`; }
      if (p.t.kind === 'cartoon') { // a morning's cartoons: one row, opened on demand
        const run = [p]; while (list[i + 1] && list[i + 1].t.kind === 'cartoon' && partIndex(ps, list[i + 1].s) === k) run.push(list[++i]);
        if (run.length > 2) { html += toonRun(run, t); continue; }
        run.forEach(x => { html += row(x, t); }); continue;
      }
      html += row(p, t);
    }
    el.innerHTML = html || `<p class="empty">${st.leg ? 'Nenhum título com legenda nesta faixa. Tire o filtro LEG para ver a grade toda.' : 'Nada na grade para este horário.'}</p>`;
  }
  function row(p, t) {
    const on = p.s <= t && t < p.e, past = p.e <= t;
    const meta = [nice(blockName(p.block)), KIND[p.t.kind], p.t.kind !== 'cartoon' ? dur((p.e - p.s) / 1000) : ''].filter(Boolean).join(' · ');
    return `<a class="row${on ? ' on' : past ? ' past' : ''}${p.t.kind === 'film' ? ' feat' : ''}" href="${link(p.id)}"><time datetime="${new Date(p.s).toISOString()}">${hm(p.s)}</time>${art(p.id, p.block)}
      <div class="body"><div class="blk">${on ? '<span class="badge live">AO VIVO</span>' : ''}${esc(meta)} ${legBadge(p.id)}</div>
      <span class="tt">${esc(p.t.title)}${p.t.year ? `<span class="yr">${p.t.year}</span>` : ''}</span>${p.t.synopsis ? `<p class="syn">${esc(p.t.synopsis)}</p>` : ''}</div></a>`;
  }
  function toonRun(run, t) {
    const a = run[0], z = run[run.length - 1], on = a.s <= t && t < z.e, past = z.e <= t;
    const nowT = run.find(x => x.s <= t && t < x.e);
    return `<details class="toons"${st.openToons ? ' open' : ''}><summary class="row toonrun${on ? ' on' : past ? ' past' : ''}"><time>${hm(a.s)}</time>${art(a.id, 'toons')}
      <div class="body"><div class="blk">${on ? '<span class="badge live">AO VIVO</span>' : ''}${esc(nice(blockName(a.block)))} · ${hm(a.s)} – ${hm(z.e)}</div>
      <span class="tt">${run.length} desenhos clássicos</span>
      <p class="syn">${nowT ? 'Agora: ' + esc(nowT.t.title) + '. ' : ''}Os desenhos passam um atrás do outro, com intervalo a cada três.</p><span class="more">Ver os ${run.length} desenhos</span></div></summary>
      <ol>${run.map(x => `<li class="${x.s <= t && t < x.e ? 'on' : ''}"><time>${hm(x.s)}</time><a href="${link(x.id)}">${esc(x.t.title)}${x.t.year ? ` <span class="yr" style="color:var(--fg3)">${x.t.year}</span>` : ''}</a></li>`).join('')}</ol></details>`;
  }
  document.addEventListener('click', e => {
    const b = e.target.closest('#days .chip, #faixas .chip'); if (!b) return;
    if (b.dataset.d) st.day = b.dataset.d;
    if (b.dataset.f != null) st.part = +b.dataset.f;
    if (b.hasAttribute('data-leg')) st.leg = !st.leg;
    const q = new URLSearchParams(); if (st.day !== dayKey(clock())) q.set('dia', st.day); if (st.part >= 0) q.set('faixa', st.part); if (st.leg) q.set('leg', '1');
    history.replaceState(null, '', location.pathname + (q.toString() ? '?' + q : ''));
    guide();
  });
  document.addEventListener('toggle', e => { if (e.target.matches && e.target.matches('details.toons')) st.openToons = e.target.open; }, true);

  // today's rest, compact (Ao vivo page)
  function todayRest() {
    const el = $('#hoje'); if (!el) return;
    const t = clock(), today = dayKey(t), ps = parts();
    const list = P.filter(p => p.e > t && (dayKey(p.s) === today || p.s - t < 6 * 3600e3)).slice(0, 60);
    let html = '';
    for (let i = 0; i < list.length && i < 60; i++) {
      const p = list[i];
      if (p.t.kind === 'cartoon') { const run = [p]; while (list[i + 1] && list[i + 1].t.kind === 'cartoon') run.push(list[++i]); html += run.length > 2 ? toonRun(run, t) : run.map(x => row(x, t)).join(''); continue; }
      html += row(p, t);
    }
    el.innerHTML = html;
  }

  // ---------- title page ----------
  function titlePage() {
    const el = $('#titulo'); if (!el) return;
    const id = new URLSearchParams(location.search).get('id') || '', t = titleOf(id);
    if (!t) { el.innerHTML = `<div class="wrap page-head"><div class="kicker">Programa</div><h1>Não achamos este programa</h1><p>Ele pode ter saído da grade. Veja o que passa hoje na <a href="${B}programacao/">programação</a>.</p></div>`; return; }
    const now = clock(), today = dayKey(now), ups = P.filter(p => p.id === id && p.e > now), on = ups.find(p => p.s <= now);
    if (!el.dataset.id || el.dataset.id !== id || el.dataset.on !== String(!!on) || el.dataset.leg !== String(hasLeg(id))) {
      el.dataset.id = id; el.dataset.on = !!on; el.dataset.leg = hasLeg(id);
      document.title = `${t.title}${t.year ? ' (' + t.year + ')' : ''} · KÖLJA TV`;
      const md = document.querySelector('meta[name=description]'); if (md && t.synopsis) md.content = t.synopsis;
      const meta = [t.year, country(t.country), KIND[t.kind], dur(t.dur)].filter(Boolean).map(x => `<span>${esc(x)}</span>`).join('<span aria-hidden="true">·</span>');
      const sameBlock = []; const seen = new Set([id]);
      for (const p of P) if (p.e > now && p.block === t.block && p.t.kind !== 'cartoon' && !seen.has(p.id)) { seen.add(p.id); sameBlock.push(p); if (sameBlock.length >= 4) break; }
      el.innerHTML = `
      <section class="title-hero"><div class="bg">${art(id, t.block, '', true)}</div><div class="wrap">
        <div class="kicker">${on ? '<span class="dot"></span>No ar agora · ' : ''}${esc(blockName(t.block))}</div>
        <h1>${esc(t.title)}</h1>
        <div class="meta">${meta}${hasLeg(id) ? '<span class="badge leg">LEG</span>' : ''}</div>
        ${t.synopsis ? `<p class="syn">${esc(t.synopsis)}</p>` : ''}
        <div class="acts">${on ? `<a class="btn" href="${B}ao-vivo/"><svg viewBox="0 0 24 24"><path d="M7 4v16l13-8z"/></svg>Assistir ao vivo</a>` : ''}
          <a class="btn${on ? ' ghost' : ''}" href="${B}programacao/">Programação</a></div>
      </div></section>
      <section class="band"><div class="wrap two">
        <div><div class="h-sec"><h2>Quando passa</h2></div>${ups.length ? `<ul class="airings">${ups.slice(0, 8).map(p => `<li><div class="d">${esc(dayLabel(dayKey(p.s), today))}, ${hm(p.s)}<small>${dayShort(dayKey(p.s))} · ${esc(blockName(p.block))} · até ${hm(p.e)}</small></div>
          ${p === on ? '<a class="btn" href="' + B + 'ao-vivo/">Ao vivo</a>' : '<span class="lbl" style="color:var(--fg3)">' + esc(nice(blockName(p.block))) + '</span>'}</li>`).join('')}</ul>`
          : `<p style="color:var(--fg2);font-size:18px;max-width:46ch">Não está na grade dos próximos dias. A programação muda todo dia, então vale voltar aqui para conferir.</p>`}
        ${hasLeg(id) ? `<p style="color:var(--fg2);margin-top:22px;max-width:52ch"><span class="badge leg">LEG</span>&nbsp; Tem legenda em português e em inglês, feitas por nós. No player, o botão PT troca para EN ou desliga.</p>` : ''}</div>
        <div><div class="h-sec"><h2>Ficha</h2></div><dl class="facts">
          <div><dt>Título</dt><dd>${esc(t.title)}</dd></div>${t.year ? `<div><dt>Ano</dt><dd>${t.year}</dd></div>` : ''}
          ${t.country ? `<div><dt>País</dt><dd>${esc(country(t.country))}</dd></div>` : ''}<div><dt>Duração</dt><dd>${esc(dur(t.dur))}</dd></div>
          <div><dt>Faixa</dt><dd>${esc(nice(blockName(t.block)))}</dd></div><div><dt>Formato</dt><dd>${esc(KIND[t.kind] || '')}</dd></div></dl></div>
      </div></section>
      ${sameBlock.length ? `<section class="band"><div class="wrap"><div class="h-sec"><h2>Mais na ${esc(nice(blockName(t.block)))}</h2><a href="${B}programacao/">Programação</a></div>
        <div class="rail r4">${sameBlock.map(p => card(p, today)).join('')}</div></div></section>` : ''}`;
    }
  }

  // ---------- a day at KÖLJA TV (Sobre) ----------
  function dayMap() {
    const el = $('#daymap'); if (!el) return;
    const t = clock(), today = dayKey(t), runs = [];
    for (const p of P) if (dayKey(p.s) === today) { const l = runs[runs.length - 1]; if (!l || l.block !== p.block) runs.push({ block: p.block, s: p.s, n: 1, kinds: new Set([p.t.kind]) }); else { l.n++; l.kinds.add(p.t.kind); } }
    const merged = runs.filter(r => r.n > 1 || r.kinds.has('film'));
    const KW = { film: 'filmes', short: 'curtas', tv: 'episódios de séries' };
    const say = r => r.block === 'toons' ? 'Desenhos um atrás do outro, com intervalo a cada três' : cap(['film', 'tv', 'short'].filter(k => r.kinds.has(k)).map(k => KW[k]).join(' e ').replace(/ e (?=.* e )/, ', '));
    el.innerHTML = merged.map(r => `<li><time>${hm(r.s)}</time><div><b>${esc(nice(blockName(r.block)))}</b><span>${esc(say(r))}</span></div></li>`).join('');
  }

  function draw() {
    if (!S) return;
    try { ticker(); upnext(); poster(); dayparts(); films(); legRail(); novela(); guide(); todayRest(); titlePage(); dayMap(); }
    catch (e) { console.error(e); }
  }
  ready().catch(e => { console.error(e); const g = $('#grade') || $('#titulo'); if (g) g.innerHTML = '<p class="empty wrap">A programação não carregou agora. Tente de novo em instantes.</p>'; });
})();
