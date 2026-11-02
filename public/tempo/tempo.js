// KÖLJA TV: the weather page. Reads tempo/previsao.json (the forecast the channel's PREVISÃO DO TEMPO is made from,
// refreshed every few hours) and draws the map and the capitals for the chosen day. An old forecast (over 12 h) is
// never shown.
(() => {
  'use strict';
  const B = document.body.dataset.base || '';
  const TZ = 'America/Sao_Paulo', MAX_AGE = 12 * 3600e3;
  const $ = (s, el = document) => el.querySelector(s);
  const esc = x => String(x == null ? '' : x).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const DOW = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];
  const dateOf = s => { const [y, m, d] = s.split('-').map(Number); return new Date(Date.UTC(y, m - 1, d, 12)); };
  const today = () => new Date().toLocaleDateString('en-CA', { timeZone: TZ });
  const short = s => { const d = dateOf(s); return d.getUTCDate() + '/' + String(d.getUTCMonth() + 1).padStart(2, '0'); };
  const label = s => { const t = today(), d = dateOf(s), diff = Math.round((d - dateOf(t)) / 864e5); return diff === 0 ? 'Hoje' : diff === 1 ? 'Amanhã' : DOW[d.getUTCDay()]; };
  const icon = (e, size) => `<img src="${B}tempo/icones/${esc(e.icone)}.png" alt="${esc(e.tempo)}" title="${esc(e.tempo)}" width="${size}" height="${size}">`;
  // where a pin's label sits: to the right, except where it would run into a neighbour
  const LEFT = new Set(['sao-paulo', 'curitiba', 'campo-grande', 'cuiaba', 'porto-velho', 'manaus', 'boa-vista', 'palmas']);
  const BELOW = new Set(['curitiba']); // under its pin, clear of São Paulo's
  let P = null, day = null, svgReady = null;

  function stamp() {
    const g = new Date(P.gerado);
    const hm = g.toLocaleTimeString('pt-BR', { timeZone: TZ, hour: '2-digit', minute: '2-digit' });
    const dm = g.toLocaleDateString('pt-BR', { timeZone: TZ, day: '2-digit', month: '2-digit' });
    $('#tp-stamp').innerHTML = `Atualizada às ${hm} de ${dm}, horário de Brasília`;
  }

  function days() {
    const all = new Set();
    for (const c of P.cidades) for (const e of c.dias) all.add(e.data);
    return [...all].sort().filter(d => d >= today()).slice(0, 4);
  }

  function tabs() {
    $('#tp-days').innerHTML = days().map(d => `<button class="chip" type="button" data-d="${d}" aria-pressed="${d === day}">${label(d)}<small>${short(d)}</small></button>`).join('');
  }

  function pins() {
    const svg = $('#tp-map svg');
    if (!svg) return;
    for (const g of svg.querySelectorAll('.pin')) {
      const c = P.cidades.find(x => x.id === g.dataset.id), e = c && c.dias.find(x => x.data === day);
      if (!e) { g.innerHTML = ''; continue; }
      const left = LEFT.has(c.id), x = left ? -14 : 14, a = left ? 'end' : 'start', y = BELOW.has(c.id) ? 30 : 0;
      g.innerHTML = `<circle r="7"/><text class="t" x="${x}" y="${y - 4}" text-anchor="${a}">${e.max}°<tspan class="m" dx="6">${e.min}°</tspan></text>` +
        `<text class="n" x="${x}" y="${y + 22}" text-anchor="${a}">${esc(c.nome)}</text>`;
    }
  }

  function regions() {
    $('#tp-regions').innerHTML = P.regioes.map(r => {
      const rows = P.cidades.filter(c => c.regiao === r.id).sort((a, b) => b.lat - a.lat || a.lon - b.lon).map(c => {
        const e = c.dias.find(x => x.data === day);
        if (!e) return '';
        const wet = e.chuva != null && e.chuva >= 30;
        return `<li><span class="c"><b>${esc(c.nome)}</b><small>${esc(c.uf)}</small></span>${icon(e, 40)}` +
          `<span class="mx">${e.max}°</span><span class="mn">${e.min}°</span>` +
          `<span class="ch${wet ? ' wet' : ''}" title="Chance de chuva">${e.chuva == null ? '' : e.chuva + '%'}</span></li>`;
      }).join('');
      return `<section class="tp-reg"><h2>${esc(r.nome)}</h2><ul>${rows}</ul></section>`;
    }).join('');
  }

  function draw() { tabs(); regions(); if (svgReady) svgReady.then(pins); }

  function none() {
    $('#tp-stamp').textContent = '';
    $('#tp-days').innerHTML = '';
    $('#tp-regions').innerHTML = '<p class="empty">A previsão está sendo atualizada. Volte daqui a pouco.</p>';
    $('#tp-map').hidden = true;
  }

  $('#tp-days').addEventListener('click', e => {
    const b = e.target.closest('[data-d]');
    if (!b) return;
    day = b.dataset.d; draw();
  });

  svgReady = fetch(B + 'tempo/mapa.svg').then(r => r.text()).then(t => { $('#tp-map').innerHTML = t; }).catch(() => {});

  function load() {
    fetch(B + 'tempo/previsao.json?t=' + Math.floor(Date.now() / 600e3), { cache: 'no-cache' }).then(r => r.ok ? r.json() : null).then(p => {
      if (!p || !p.cidades || Date.now() - p.gerado > MAX_AGE) { P = null; return none(); }
      P = p;
      $('#tp-map').hidden = false;
      const ds = days();
      if (!day || !ds.includes(day)) day = ds[0];
      stamp(); draw();
    }).catch(() => { if (!P) none(); });
  }
  load();
  setInterval(load, 15 * 60e3);
})();
