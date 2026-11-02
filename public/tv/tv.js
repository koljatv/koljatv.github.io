// KÖLJA TV ao vivo: the channel in the browser, played the way Retrotv plays it. Everyone sees the same thing at
// the same time: the page reads the grade (grade/now.json names the current build of grade/schedule2.json) and
// puts on whatever the clock says, at the right point. A feature's commercial break is our INTERVALO and VOLTAMOS;
// our idents run between programmes. The next item is loaded ahead in a hidden player so the cut is clean.
// The copies of a film race (archive.org servers vary from fast to a crawl): the first to play goes on the air,
// over the programme's still and a "Carregando…" mark. If every copy fails, the round starts again, never a dead
// end. And the screen never waits on a programme that won't come: after a few seconds without its picture,
// PROGRAMAÇÃO ALTERNATIVA puts on a short from the same part of the day (tv/reserva.json: copies that start fast;
// our own pieces as the last resort) while the copies keep trying behind it; once one plays, the channel goes back
// to the clock at the next natural point. Our "PROBLEMAS TÉCNICOS" card only when nothing at all will play.
(() => {
  'use strict';
  const host = document.getElementById('ktv');
  if (!host) return;
  const BASE = host.dataset.base || '';
  const TZ = 'America/Sao_Paulo', MIN = 60e3;
  const CUE_PROG = 45e3, CUE_RETURN = 75e3, CUE_BREAK = 3 * MIN, CUE_OURS = 15e3, // how far ahead each kind is loaded
        OURS_START_MS = 8000, DEAD_MS = 10 * MIN,
        // archive.org: a copy's index (1-4 MB, read before the first picture) comes over a connection that may be fast
        // or crawl at 15 KB/s, a lottery per connection. So copies race: another starts every RACE_MS while none plays
        // (RACES at most), and a copy that hasn't moved on for a while reconnects (RESTART_MS, more patient each time).
        // A copy is given up on an error or after GIVEUP_MS; when every copy failed, the round starts again after a
        // pause (BACKOFF). Our card shows only after a real failure and CARD_AFTER.
        RACE_MS = 6000, RACES = 3, RESTART_MS = 15000, GIVEUP_MS = 150e3, STALL_RACE_MS = 8000, STALL_FAIL_MS = 45e3, CARD_AFTER = 30e3,
        BACKOFF = [2000, 6000, 15000, 30000, 60000];
  const TROUBLE = { trouble: true, dur: 12000, url: BASE + 'tv/tecnicos.mp4' };

  // ---------- the set ----------
  host.classList.add('ktv-set');
  host.innerHTML = `
    <div class="ktv-cab"><div class="ktv-bezel"><div class="ktv-glass">
      <div class="ktv-screen"><img class="ktv-still on" alt="" decoding="async"></div>
      <div class="ktv-o ktv-card hide"></div>
      <div class="ktv-o ktv-live hide"><i></i>AO VIVO</div>
      <div class="ktv-o ktv-bug hide">KÖLJA<b>TV</b></div>
      <div class="ktv-o ktv-next hide"><b>A SEGUIR</b><span></span></div>
      <div class="ktv-o ktv-msg hide"></div>
      <div class="ktv-o ktv-load hide" role="status" aria-live="polite"><span class="ring"><i></i></span><span class="mk">KÖLJA<b>TV</b></span><span class="tx">Carregando…</span></div>
      <button class="ktv-o ktv-tap hide" type="button">TOQUE PARA ATIVAR O SOM</button>
      <div class="ktv-sub hide" aria-live="off"></div>
      <div class="ktv-crt"></div><div class="ktv-shine"></div>
      <div class="ktv-power" role="button" tabindex="0" aria-label="Assistir à KÖLJA TV ao vivo">
        <div class="knob"></div><strong>ASSISTIR <b>AO VIVO</b></strong><span>toque para ligar · com som</span>
      </div>
    </div></div>
    <div class="ktv-brand">KÖLJA</div><div class="ktv-model"><span class="ktv-lamp"></span>TV-14 · CANAL 1</div></div>
    <div class="ktv-ctl">
      <button type="button" data-k="power" aria-label="Ligar ou desligar"><svg viewBox="0 0 24 24"><path d="M11 2h2v10h-2zM6.3 5.3l1.4 1.4A7 7 0 1 0 16.3 6.7l1.4-1.4A9 9 0 1 1 6.3 5.3z"/></svg><span class="lbl">LIGAR</span></button>
      <button type="button" data-k="mute" aria-label="Som"><svg viewBox="0 0 24 24"><path d="M3 9h4l5-4v14l-5-4H3z"/><path class="w" d="M15.5 8.5a5 5 0 0 1 0 7l1.4 1.4a7 7 0 0 0 0-9.8zM18.4 5.6a9 9 0 0 1 0 12.8l1.4 1.4a11 11 0 0 0 0-15.6z"/><path class="x" d="M15 9.4 16.4 8l2.1 2.1L20.6 8 22 9.4l-2.1 2.1 2.1 2.1-1.4 1.4-2.1-2.1-2.1 2.1-1.4-1.4 2.1-2.1z" style="display:none"/></svg></button>
      <input type="range" min="0" max="1" step="0.05" aria-label="Volume">
      <button type="button" data-k="cc" aria-label="Legendas"><svg viewBox="0 0 24 24"><path d="M3 5h18v14H3zm2 2v10h14V7zm2 3h4v1.5H8.5v1H11V14H7zm6 0h4v1.5h-2.5v1H17V14h-4z"/></svg><span class="cc">PT</span></button>
      <span class="sp"></span>
      <span class="clock"></span>
      <button type="button" data-k="full" aria-label="Tela cheia"><svg viewBox="0 0 24 24"><path d="M3 3h7v2H5v5H3zm11 0h7v7h-2V5h-5zM3 14h2v5h5v2H3zm16 0h2v7h-7v-2h5z"/></svg><span class="lbl">TELA CHEIA</span></button>
    </div>`;
  const q = s => host.querySelector(s);
  const screen = q('.ktv-screen'), stillEl = q('.ktv-still'), glass = q('.ktv-glass'), powerEl = q('.ktv-power');
  const loadEl = q('.ktv-load'), loadTx = q('.ktv-load .tx');
  const cardEl = q('.ktv-card'), liveEl = q('.ktv-live'), bugEl = q('.ktv-bug'), nextEl = q('.ktv-next'), msgEl = q('.ktv-msg'), tapEl = q('.ktv-tap');
  const volEl = q('input[type=range]'), clockEl = q('.clock'), subEl = q('.ktv-sub'), ccEl = q('[data-k=cc]');
  const info = document.getElementById('ktv-info'), guideEl = document.getElementById('ktv-guide'), daysEl = document.getElementById('ktv-days');
  const show = (el, on) => el.classList.toggle('hide', !on);

  // ---------- the clock: the server's, not this computer's ----------
  let skew = 0, gen = 0;
  const offs = [];
  const now = () => Date.now() + skew;
  async function getJSON(url) {
    const t0 = Date.now(), r = await fetch(url, { cache: 'no-store' }), t1 = Date.now();
    if (!r.ok) throw new Error(url + ' ' + r.status);
    const d = Date.parse(r.headers.get('date') || '');
    if (d) { offs.push(d + 500 - (t0 + t1) / 2); if (offs.length > 7) offs.shift(); } // the CDN stamps Date when it answers
    return r.json();
  }
  function setClock() {
    const o = offs.slice().sort((a, b) => a - b)[offs.length >> 1] || 0;
    skew = Math.abs(o) > 2500 ? o : 0;                                   // the header's rounding is noise, a wrong clock isn't
    if (gen && Date.now() + skew < gen) skew = gen - Date.now() + 1000;  // it can't be earlier than when now.json was written
  }

  // ---------- the grade ----------
  let S = null, rev = '', items = [], progs = [];
  async function load() {
    const n = await getJSON(BASE + 'grade/now.json?m=' + Math.floor(Date.now() / MIN));
    gen = n.generated || 0;
    const r = n.rev2 || n.rev, file = n.schedule2 || n.schedule; // schedule2: with the commercial breaks
    let fresh = false;
    if (!S || r !== rev) { S = await getJSON(BASE + 'grade/' + file + '?r=' + r); rev = r; parse(); drawGuide(); fresh = true; }
    setClock();
    if (fresh) window.dispatchEvent(new CustomEvent('ktv:grade')); // the site's own pages (now/next, highlights) read it from window.KTV
  }

  // items: [start, end, id, block(, part)]. part 0, 1... is a feature's part; -1 is a piece of its break.
  function parse() {
    items = []; progs = [];
    let open = null;
    for (const r of S.items) {
      const p = S.titles[r[2]] || null, o = p ? null : S.ours[r[2]] || null, x = r.length > 4 ? r[4] : null;
      const it = { s: r[0], e: r[1], id: r[2], block: r[3], p, o, part: p && x != null && x >= 0 ? x : -1, brk: x != null && x < 0 };
      if (it.brk) it.first = open;
      else if (p && it.part === 0) { open = it; it.whole = it.e; }
      else if (p && it.part > 0 && open && open.id === it.id) { it.first = open; open.whole = it.e; }
      else if (p) open = null;
      if (p && it.part <= 0) progs.push(it);
      items.push(it);
    }
  }
  const showEnd = it => it.first ? it.first.whole : it.whole || it.e;
  const toBreak = it => !!it.p && it.part >= 0 && it.e < showEnd(it);
  const keyOf = it => it.s + '|' + it.id;
  const isTempo = it => !!(it && it.o && it.o.kind === 'tempo'); // PREVISÃO DO TEMPO: our segment, on the clock like a programme
  function find(t) {
    let lo = 0, hi = items.length - 1;
    while (lo <= hi) { const m = (lo + hi) >> 1; if (items[m].e <= t) lo = m + 1; else if (items[m].s > t) hi = m - 1; else return m; }
    return -1;
  }
  const progAt = t => progs.find(p => p.s <= t && t < showEnd(p));
  window.KTV = { get S() { return S; }, get progs() { return progs; }, get LG() { return LG; }, get power() { return power; }, now: () => now(), showEnd };
  const progAfter = t => progs.find(p => p.s >= t);

  // ---------- what can play an item ----------
  const dead = new Map(); // copies that failed lately: tried last
  const isDead = u => Date.now() - (dead.get(u) || -1e12) < DEAD_MS;
  function copies(it) {
    if (it.p) return (it.p.sources || []).map(c => ({ url: c.url, cuts: c.cuts || [] }));
    if (it.o) return [{ url: BASE + 'tv/ours/' + it.id + '.mp4', cuts: [] }, { url: it.o.url, cuts: [] }];
    return [];
  }
  // A play: one copy of one item, and where in its file the clock is.
  function plan(it, c) {
    const cut0 = it.part > 0 ? c.cuts[it.part - 1] || 0 : 0;
    const stop = it.part >= 0 && it.part < c.cuts.length ? c.cuts[it.part] : -1;
    const loop = !!(it.o && it.o.loop), dur = it.o ? it.o.dur * 1000 : 0;
    return { url: c.url, it, key: c.url + '@' + keyOf(it), stop, loop, ours: !it.p,
             at: t => { const o = Math.max(0, t - it.s); return (loop && dur ? o % dur : o) + cut0; } };
  }
  function firstCopy(it, tried) {
    const cs = copies(it);
    let k = cs.findIndex((c, i) => !tried.has(i) && !isDead(c.url));
    if (k < 0) k = cs.findIndex((c, i) => !tried.has(i)); // everything failed lately: try again anyway, once
    return k < 0 ? null : { k, pl: plan(it, cs[k]) };
  }
  // A stand-in for what is left of a slot: the same block's longest that fits (more than half of it), else any
  // shorter one, this block's first.
  function standIn(block, room, skip) {
    let best = null, short = null;
    for (const [id, p] of Object.entries(S.titles)) {
      const d = (p.dur || 0) * 1000;
      if (!d || d > room || skip.has(id) || !(p.sources || []).some(c => !isDead(c.url))) continue;
      if (p.block === block && (!best || d > best.d)) best = { id, p, d };
      const r = (p.block === block ? 1e12 : 0) + d;
      if (!short || r > short.r) short = { id, p, d, r };
    }
    const pick = best && best.d > room / 2 ? best : short;
    return pick ? { s: now(), e: now() + pick.d, id: pick.id, block, p: pick.p, o: null, part: -1, alt: true } : null;
  }

  // ---------- players: one on the air, copies racing to take over, the rest loading what comes next ----------
  const slots = [0, 1, 2, 3, 4].map(() => {
    const v = document.createElement('video');
    v.setAttribute('playsinline', ''); v.playsInline = true; v.preload = 'auto'; v.muted = true;
    screen.insertBefore(v, stillEl);
    return { v, pl: null, role: '', ready: false, timer: 0, stall: 0, pre: false, t0: 0, rs: 0, rsAt: 0, wait: 0, patience: RESTART_MS, waiting: false };
  });
  // Programação alternativa: two more players above the still, for the shorts that cover a programme that won't start.
  // FILL_PREP without its picture and a short gets ready on its first frame (another joins after FILL_TRY, then our
  // own pieces); it goes on at FILL_AFTER. Back to the clock at once if the short has only just begun or has long to
  // go, else at its end.
  const FILL_PREP = 5000, FILL_AFTER = 12000, FILL_STALL = 8000, FILL_TRY = 6000, FILL_CUT = 20e3, FILL_HOLD = 4 * MIN, FILL_REST = 30e3, FILL_LABEL = 10e3;
  const F = { on: null, list: null, used: new Set(), tries: 0, gaveUp: 0, oi: 0, back: false,
    v: [0, 1].map(() => {
      const v = document.createElement('video');
      v.setAttribute('playsinline', ''); v.playsInline = true; v.preload = 'auto'; v.muted = true;
      screen.append(v); // over the still and the schedule's players
      return v;
    }) };
  const air = () => slots.find(s => s.role === 'air');
  const same = (s, it) => !!(s.pl && it && !s.pl.trouble && keyOf(s.pl.it) === keyOf(it)); // a copy of this item (not our card)
  const racing = it => slots.filter(s => s.role === 'next' && same(s, it));
  let sound = false, muted = localStorage.getItem('ktv.mute') === '1', vol = +(localStorage.getItem('ktv.vol') || 0.8);

  function release(sl) {
    clearTimeout(sl.timer); clearTimeout(sl.stall);
    const v = sl.v;
    v.onloadedmetadata = v.oncanplay = v.onplaying = v.onwaiting = v.onerror = v.onended = null;
    v.pause(); v.classList.remove('air'); v.muted = true; v.playbackRate = 1;
    if (v.getAttribute('src')) { v.removeAttribute('src'); try { v.load(); } catch (e) {} }
    sl.pl = null; sl.role = ''; sl.ready = false; sl.pre = false; sl.waiting = false;
  }
  function want(sl) { // seconds into the file: where the clock is (on the air) or where the item starts (loading ahead)
    const pl = sl.pl; let w = (sl.role === 'cue' && !sl.pre ? pl.at(pl.it.s) : pl.at(now())) / 1000;
    if (pl.loop && sl.v.duration) w %= sl.v.duration;
    return w;
  }
  function prepare(sl, pl, role) {
    const v = sl.v;
    sl.pl = pl; sl.role = role; sl.ready = false; sl.t0 = sl.rsAt = Date.now(); sl.rs = 0; sl.patience = RESTART_MS;
    v.onloadedmetadata = () => {
      const w = want(sl);
      if (sl.role === 'next' && !pl.loop && !pl.ours && v.duration && w >= v.duration - 1) { // this print ends before the slot
        release(sl);
        if (cur && cur.target && keyOf(pl.it) === keyOf(cur.target) && !more() && !racing(pl.it).length) fill();
        return;
      }
      try { v.currentTime = w; } catch (e) {}
    };
    v.oncanplay = () => { sl.ready = true; };
    v.onerror = () => { if (sl.role === 'cue') { dead.set(pl.url, Date.now()); release(sl); } else fail(sl, true); };
    v.loop = pl.loop; v.muted = true;
    v.src = pl.url;
    try { v.load(); } catch (e) {}
  }
  function levels() {
    for (const f of F.v) { f.volume = vol; f.muted = f !== F.on || !sound || muted || tapNeeded; }
    for (const s of slots) {
      const on = s.role === 'air' || s.role === 'next';
      s.v.volume = vol;
      if (!on || !sound || muted || F.on) s.v.muted = true;
      else if (s.v.muted && !tapNeeded) s.v.muted = false;
    }
  }
  let tapNeeded = false;
  function start(sl) {
    const v = sl.v;
    v.volume = vol; v.muted = !sound || muted || tapNeeded;
    const p = v.play();
    if (p) p.catch(e => {
      if (sl.v !== v || !sl.pl) return;
      if (e && e.name === 'NotAllowedError' && !v.muted) { tapNeeded = true; show(tapEl, true); v.muted = true; v.play().catch(() => {}); }
    });
  }

  // Put a play on the air: the copy loaded ahead if it's ready, else load it now (the old picture holds meanwhile).
  // Other copies of the same item may be loading alongside: the first to play goes on the air.
  function onAir(pl) {
    const a = air();
    if (a && a.pl && a.pl.key === pl.key) { a.pl = pl; return; } // already there (our card while trying the next copy)
    if (slots.some(s => s.role === 'next' && s.pl.key === pl.key)) return; // already on its way
    let sl = slots.find(s => s.role === 'cue' && s.pl.key === pl.key);
    for (const s of slots) if (s.role === 'next' && !s.pl.trouble && !same(s, pl.it)) release(s); // our card and this item's other copies stay
    let rolling = false;
    if (sl) {
      const pre = sl.pre; sl.pl = pl; sl.role = 'next'; sl.pre = false;
      if (sl.v.readyState >= 1 && Math.abs(sl.v.currentTime - want(sl)) > (pre ? 4 : 0.35)) try { sl.v.currentTime = want(sl); } catch (e) {}
      else rolling = pre && !sl.v.paused && sl.v.readyState >= 3; // rolled ahead in the dark: on the air right away
    } else {
      sl = slots.find(s => !s.role) || slots.find(s => s.role === 'cue');
      if (!sl) return;
      release(sl); prepare(sl, pl, 'next');
    }
    if (a && !a.pl.loop && !same(a, pl.it)) a.v.pause(); // a stalled copy of the same film keeps trying
    const v = sl.v;
    if (pl.ours) sl.timer = setTimeout(() => fail(sl), OURS_START_MS);
    else sl.timer = setTimeout(() => { if (sl.role === 'next') more(); }, RACE_MS); // no picture yet: another copy joins in
    v.onplaying = () => { clearTimeout(sl.stall); sl.waiting = false; if (sl.role === 'next') live(sl); else if (sl.role === 'air') back(sl); };
    v.onwaiting = () => {
      if (sl.role !== 'air' || sl.pl.loop) return;
      sl.waiting = true; sl.wait = Date.now(); if (cur && !cur.lost) cur.lost = Date.now();
      clearTimeout(sl.stall);
      if (!sl.pl.ours) sl.stall = setTimeout(() => { if (sl.role === 'air' && sl.waiting) more(true); }, STALL_RACE_MS); // still stuck: another copy at the clock's point
      loading();
    };
    v.onended = () => { if (sl.role === 'air') ended(sl); };
    clearTimeout(stillTimer);
    if (!(a && (a.pl.loop || same(a, pl.it)))) stillTimer = setTimeout(() => { if (sl.role === 'next') setStill(true); }, a ? 900 : 0); // our looping card holds
    start(sl);
    if (rolling) live(sl);
    loading();
  }
  let stillTimer = 0;
  function live(sl) {
    clearTimeout(sl.timer); clearTimeout(stillTimer);
    for (const s of slots) if (s !== sl && (s.role === 'air' || (s.role === 'next' && !sl.pl.trouble && (s.pl.trouble || same(s, sl.pl.it))))) release(s); // our card going up leaves the copies racing
    sl.role = 'air'; sl.v.classList.add('air'); sl.waiting = false;
    if (cur && !sl.pl.trouble) { cur.lost = 0; cur.bad = 0; cur.cycle = 0; cur.again = 0; }
    setStill(false); show(cardEl, false); show(msgEl, false);
    if (Math.abs(sl.v.currentTime - want(sl)) > 1.5 && (!sl.pl.ours || isTempo(sl.pl.it))) try { sl.v.currentTime = want(sl); } catch (e) {}
    levels(); ui(); loading();
  }
  function back(sl) { // a copy that stopped to load plays again: the ones racing to replace it stop
    if (sl.pl.trouble || sl.pl.ours) return;
    if (cur) cur.lost = 0;
    for (const s of slots) if (s.role === 'next' && same(s, sl.pl.it)) release(s);
    loading();
  }
  // Another copy of what should be on the air starts loading alongside. again: any copy not loading right now
  // (a picture that stalled), else one not tried this round. False: nothing left to try.
  function more(again) {
    if (!cur || !cur.target || cur.mode !== 'play') return false;
    const tg = cur.target;
    if (racing(tg).length >= RACES) return true;
    const skip = again ? new Set(slots.filter(s => same(s, tg)).map(s => s.pl.k)) : cur.tried;
    const c = firstCopy(tg, skip);
    if (!c) return false;
    launch(c);
    return true;
  }
  function launch(c) { cur.tried.add(c.k); c.pl.k = c.k; cur.mode = 'play'; onAir(c.pl); }
  function fail(sl, error) {
    if (!sl.pl || (sl.role !== 'next' && sl.role !== 'air')) return;
    const pl = sl.pl;
    if (error && sl.role === 'next' && !pl.retried && !pl.trouble) { // hosts sometimes refuse one request: once more, a second later
      pl.retried = true; release(sl);
      setTimeout(() => {
        if (!cur || !cur.target || keyOf(pl.it) !== keyOf(cur.target) || cur.mode !== 'play' || slots.some(s => s.pl && s.pl.key === pl.key)) return;
        const a = air();
        if (a && same(a, pl.it) && !a.waiting) return;
        onAir(pl);
      }, 1000);
      return;
    }
    if (!pl.trouble) dead.set(pl.url, Date.now());
    const wasAir = sl.role === 'air';
    release(sl);
    if (wasAir || !air()) setStill(true);
    if (!cur || !cur.target) return;
    if (pl.trouble) { if (!air()) { cardEl.textContent = 'PROBLEMAS TÉCNICOS · JÁ VOLTAMOS'; show(cardEl, true); setStill(false); } loading(); return; } // even our card won't load: the page's own (the copies keep trying)
    if (pl.fill) { if (pl.next) onAir(pl.next); else htmlCard('A PROGRAMAÇÃO CONTINUA JÁ'); return; }
    if (keyOf(pl.it) !== keyOf(cur.target)) return; // an old attempt
    if (pl.ours) { advance(); return; }  // our piece: its other copy, else our bug over the still till the next item
    cur.bad = (cur.bad || 0) + 1; if (!cur.lost) cur.lost = Date.now();
    const a = air();
    if (more() || racing(cur.target).length || (a && same(a, cur.target))) { trouble(); loading(); return; } // other copies are on their way
    exhausted();
  }
  function ended(sl) { // the file ran out before the slot did: the next stand-in, or our station card till the next item
    if (!cur || sl.pl.loop || sl.pl.stop >= 0 || sl.pl.ours || now() >= cur.it.e - 2000) return;
    if (cur.target.alt) { cur.target = null; advance(); } else fill();
  }

  // ---------- following the grade ----------
  let cur = null, power = false;
  function tune(it) {
    cur = { key: keyOf(it), it, target: it, tried: new Set(), used: new Set([it.id]), mode: 'play', lost: Date.now(), bad: 0, cycle: 0, again: 0 };
    show(cardEl, false);
    advance();
  }
  function advance() {
    const t = now();
    if (cur.target) {
      const c = firstCopy(cur.target, cur.tried);
      if (c) { launch(c); return; }
      if (cur.target.o) { quiet(); return; }
      exhausted(); return;
    }
    if (cur.it.e - t > 60e3) { // a stand-in ran out: the next one for what is left of the slot, the longest that fits first
      const alt = standIn(cur.it.block, cur.it.e - t, cur.used);
      if (alt) { cur.used.add(alt.id); cur.target = alt; cur.tried = new Set(); advance(); return; }
    }
    fill();
  }
  // Every copy failed this round: a short pause (longer each round) and the round starts again, every other one with
  // a stand-in from the same block if one fits. Never a dead end: the moment a copy plays, it is on the air.
  function exhausted() {
    const c0 = cur, k = c0.cycle = (c0.cycle || 0) + 1;
    c0.mode = 'retry';
    trouble(); loading();
    clearTimeout(c0.rt);
    c0.rt = setTimeout(() => {
      if (cur !== c0 || c0.mode !== 'retry') return;
      const t = now(), it = c0.it;
      if (c0.target && c0.target.alt) c0.target = it; // the programme itself again (the alternative covers the wait)
      c0.tried = new Set(); c0.mode = 'play';
      advance();
    }, BACKOFF[Math.min(k - 1, BACKOFF.length - 1)]);
  }
  window.addEventListener('online', () => { // back on the internet: the next round now
    F.gaveUp = 0; F.tries = 0;
    if (power && cur && cur.mode === 'retry') { clearTimeout(cur.rt); cur.tried = new Set(); cur.mode = 'play'; advance(); }
  });
  // Our card: only once a copy really failed and the picture has been gone for half a minute; till then the
  // programme's still with "Reconectando…". The copies keep trying behind it.
  function trouble() {
    if (!power || !cur || !cur.target || !cur.bad || !cur.lost || Date.now() - cur.lost < CARD_AFTER) return;
    if (cur.mode !== 'play' && cur.mode !== 'retry') return;
    if (F.on || F.v.some(f => f.pk) || (cur.target.p && !F.gaveUp)) return; // the alternative plays, is on its way or hasn't had its go
    const a = air();
    if (a && (a.pl.trouble || (same(a, cur.target) && !a.waiting))) return;
    if (slots.some(s => s.pl && s.pl.trouble) || !cardEl.classList.contains('hide')) return;
    onAir({ url: TROUBLE.url, it: cur.target, key: 'trouble', stop: -1, loop: true, ours: true, trouble: true, at: () => 0 });
  }
  // The loading mark over the still (or over a picture that stopped to load): "Carregando…", or "Reconectando…"
  // once a copy failed or the picture has been stuck a while.
  function loading() {
    let on = false, re = false;
    if (power && S && cur && cur.target && (cur.mode === 'play' || cur.mode === 'retry')) {
      const a = air(), playing = a && !a.waiting && !a.pl.trouble && keyOf(a.pl.it) === keyOf(cur.target);
      on = !playing;
      re = cur.mode === 'retry' || cur.bad > 0 || cur.again > 0 || (!!a && a.waiting && !!cur.lost && Date.now() - cur.lost > STALL_RACE_MS);
    }
    const tx = re ? 'Reconectando…' : 'Carregando…';
    if (loadTx.textContent !== tx) loadTx.textContent = tx;
    loadEl.classList.toggle('re', re);
    show(loadEl, on);
  }
  // A copy that hasn't moved on (its readyState) for a while reconnects: a new connection, maybe a fast one.
  function reconnect(s) {
    const v = s.v, u = s.pl.url;
    s.rs = 0; s.rsAt = Date.now(); s.patience = Math.min(60e3, s.patience * 2);
    if (cur) cur.again = (cur.again || 0) + 1;
    v.removeAttribute('src'); try { v.load(); } catch (e) {}
    v.src = u; try { v.load(); } catch (e) {}
    start(s);
  }
  setInterval(() => { // stuck copies reconnect, hopeless ones are given up; the card when it's due; the loading mark
    if (!power || !cur) return;
    const t = Date.now();
    for (const s of slots) {
      if (!s.pl || s.pl.ours || (s.role !== 'next' && s.role !== 'air')) continue;
      const rs = s.v.readyState;
      if (rs > s.rs) { s.rs = rs; s.rsAt = t; }
      if (s.role === 'next') { if (t - s.t0 > GIVEUP_MS) fail(s); else if (t - s.rsAt > s.patience) reconnect(s); }
      else if (s.waiting && t - s.wait > STALL_FAIL_MS) fail(s); // stuck on the air: the copies racing take over, or our card
    }
    fillTick(); trouble(); loading();
  }, 1000);
  function fill() {
    cur.mode = 'fill';
    const o = S.ours.cartao;
    if (!o) { htmlCard('A PROGRAMAÇÃO CONTINUA JÁ'); return; }
    const it = { s: now(), e: cur.it.e, id: 'cartao', block: cur.it.block, p: null, o, part: -1 };
    const [here, there] = copies(it).map(c => Object.assign(plan(it, c), { fill: true }));
    here.key = 'fill'; there.key = 'fill2'; here.next = there; // ours on this site, else the release copy
    onAir(here);
    loading();
  }
  function quiet() { // one of our short pieces can't be fetched: our bug over the still till the next item
    cur.mode = 'quiet';
    for (const s of slots) if (s.role === 'air' || s.role === 'next') release(s);
    setStill(true); loading();
  }
  function htmlCard(text) {
    if (cur) { cur.mode = 'card'; cur.retry = now() + 30e3; }
    for (const s of slots) if (s.role === 'air' || s.role === 'next') release(s);
    cardEl.textContent = text; show(cardEl, true); setStill(false); loading();
  }

  // ---------- programação alternativa ----------
  fetch(BASE + 'tv/reserva.json').then(r => r.ok ? r.json() : null).then(j => { if (j && j.items && j.items.length) F.list = j.items; }).catch(() => {});
  const onTarget = () => { const a = air(); return !!a && !a.waiting && !a.pl.trouble && same(a, cur.target); };
  function fillWanted(after = FILL_AFTER) { // a programme is due and its picture has been missing for a while
    if (!power || !S || !cur || !cur.target || !cur.target.p || (cur.mode !== 'play' && cur.mode !== 'retry')) return false;
    return !onTarget() && !!cur.lost && Date.now() - cur.lost >= after;
  }
  const PREFER = { madrugada: ['toons'], manha: ['toons'], tarde: ['seriados', 'comedia', 'muda', 'toons'], noite: ['toons'] };
  function partOfDay() {
    const [h, m] = hm(now()).split(':').map(Number), x = h * 60 + m;
    return x < 360 ? 'madrugada' : x < 810 ? 'manha' : x < 1140 ? 'tarde' : 'noite';
  }
  function fillPick() { // a short from this block, else this part of the day's, one we haven't shown lately
    const pool = F.list || Object.entries(S.titles).filter(([, p]) => p.dur >= 60 && p.dur <= 900)
      .map(([id, p]) => ({ id, title: p.title, block: p.block, dur: p.dur, copies: (p.sources || []).map(c => c.url) }));
    const pref = [cur.it.block, ...PREFER[partOfDay()]], busy = new Set(F.v.map(f => f.pk && f.pk.id));
    let best = [], score = 1e9;
    for (const e of pool) {
      if (F.used.has(e.id) || busy.has(e.id) || e.id === cur.target.id) continue;
      const u = e.copies.find(c => !isDead(c));
      if (!u) continue;
      const k = pref.indexOf(e.block), sc = k < 0 ? 99 : k;
      if (sc < score) { score = sc; best = []; }
      if (sc === score) best.push({ id: e.id, title: e.title, dur: e.dur, url: u });
    }
    if (!best.length) { if (F.used.size) { F.used.clear(); return fillPick(); } return null; }
    return best[Math.floor(Math.random() * best.length)];
  }
  function oursPick() { // the last resort: our own pieces, from this site first
    const o = S.ours, ids = Object.keys(o).filter(k => o[k].kind === 'ad')
      .concat(Object.keys(o).filter(k => o[k].kind === 'vignette' && o[k].block === cur.it.block), ['ident_tubo', 'ident_barras'])
      .filter(k => o[k]);
    if (!ids.length) return null;
    const id = ids[F.oi++ % ids.length];
    return { id, title: o[id].title, dur: o[id].dur, url: BASE + 'tv/ours/' + id + '.mp4', alt: o[id].url, ours: true };
  }
  function dropF(f) {
    f.onplaying = f.onended = f.onerror = f.onwaiting = f.ontimeupdate = null; f.waitAt = 0;
    f.pause(); f.classList.remove('air'); f.muted = true;
    if (f.getAttribute('src')) { f.removeAttribute('src'); try { f.load(); } catch (e) {} }
    f.pk = null; f.live = false; f.ready = false; f.chk = null; f.crawl = false;
    if (F.on === f) { F.on = null; F.back = false; host.classList.remove('ktv-alt', 'ktv-altw'); }
  }
  function tryF(f, pk) {
    dropF(f);
    f.pk = pk; f.t0 = Date.now(); F.tries++;
    f.onplaying = () => { // on the glass if it's time, else it waits on its first frame
      if (f.pk !== pk || f.live) return;
      if (fillWanted()) fillLive(f); else { f.ready = true; f.pause(); }
    };
    f.onerror = () => {
      if (f.pk !== pk) return;
      if (!pk.ours) dead.set(pk.url, Date.now());
      const was = f.live; dropF(f);
      if (!was && pk.alt) tryF(f, Object.assign({}, pk, { url: pk.alt, alt: null })); // our piece from its release copy
      else if (was) fillGone(); else fillTick();
    };
    f.onended = () => { if (f.pk === pk) { dropF(f); fillGone(); } };
    f.onwaiting = () => { if (f.pk === pk && f.live && !f.waitAt) f.waitAt = Date.now(); };
    f.ontimeupdate = () => { if (f.waitAt && !f.paused && f.readyState >= 3) { f.waitAt = 0; host.classList.remove('ktv-altw'); } };
    f.src = pk.url; try { f.load(); } catch (e) {}
    f.volume = vol; f.muted = true; // silent till it's on the glass (levels)
    const p = f.play(); if (p) p.catch(() => {});
  }
  function fillLive(f) {
    for (const g of F.v) if (g !== f) dropF(g);
    for (const s of slots) if (s.pl && s.pl.trouble) release(s); // our card isn't needed
    show(cardEl, false);
    f.live = true; f.liveAt = Date.now(); f.classList.add('air'); F.on = f; F.back = false;
    F.used.add(f.pk.id); F.tries = 0; F.gaveUp = 0;
    host.classList.add('ktv-alt');
    levels(); ui();
  }
  function fillGone() { // the short ended (or broke): back to the clock, or the next one with our loading mark between
    F.back = false; host.classList.remove('ktv-alt'); levels(); loading();
    if (fillWanted()) fillTick(); else ui();
  }
  function fillTick() {
    const t = Date.now(), f = F.on;
    if (f) {
      if (f.waitAt && t - f.waitAt > 2000) host.classList.add('ktv-altw'); // the short stopped to load: our mark over it
      if (document.hidden) f.chk = null; // a phone may hold a video in a tab out of sight: no verdict then
      else if (!f.chk || t - f.chk[0] >= 15e3) { f.crawl = !!f.chk && f.currentTime - f.chk[1] < 6; f.chk = [t, f.currentTime]; } // a short that crawls on
      if ((f.waitAt && t - f.waitAt > FILL_STALL) || f.crawl) { // and doesn't come back: another (ours, if a short already stalled)
        if (!f.pk.ours) dead.set(f.pk.url, Date.now());
        dropF(f); F.tries = 2; fillGone(); return;
      }
      if (fillWanted()) { F.back = false; return; }
      const left = (f.duration || f.pk.dur) - f.currentTime, ready = !cur || !cur.target || !cur.target.p || onTarget();
      if (ready && (t - f.liveAt < FILL_CUT || left > FILL_HOLD / 1000)) { dropF(f); fillGone(); } // straight back
      else F.back = ready; // the programme is ready: back at the short's end (one still loading gets its few seconds)
      return;
    }
    const trying = F.v.filter(g => g.pk);
    if (!fillWanted(FILL_PREP)) { for (const g of trying) dropF(g); F.tries = 0; F.gaveUp = 0; return; }
    const ready = trying.find(g => g.ready);
    if (ready) { if (fillWanted()) { const p = ready.play(); if (p) p.catch(() => {}); } return; }
    for (const g of trying) if (t - g.t0 > FILL_TRY * 3) dropF(g); // never played
    if (F.gaveUp) { if (t - F.gaveUp < FILL_REST) return; F.gaveUp = 0; F.tries = 0; }
    const now2 = F.v.filter(g => g.pk), last = now2.reduce((m, g) => Math.max(m, g.t0), 0);
    if (now2.length && t - last < FILL_TRY) return;
    if (F.tries >= 6) { if (!now2.length) { F.gaveUp = t; trouble(); } return; } // nothing will play: our card, and again in a while
    const pk = (F.tries < 2 && fillPick()) || oursPick();
    if (!pk) { if (!now2.length) { F.gaveUp = t; trouble(); } return; }
    const g = F.v.find(x => !x.pk) || now2.sort((a, b) => a.t0 - b.t0)[0]; // two at a time: the oldest try makes room
    tryF(g, pk);
  }

  function tick() {
    if (!power || !S) return;
    const t = now(), i = find(t);
    if (i < 0) { if (!cur || cur.key !== 'standby') { cur = { key: 'standby', it: null }; htmlCard('JÁ VOLTAMOS'); } ui(); return; }
    const it = items[i], a = air();
    if (a && a.pl.stop >= 0 && !a.v.paused && a.v.currentTime * 1000 >= a.pl.stop - 20) a.v.pause(); // also with the tab in the background
    if (!cur || cur.key !== keyOf(it)) tune(it);
    else if (cur.mode === 'card' && t >= cur.retry && t < it.e - 60e3) { cur.target = it; cur.tried = new Set(); cur.used = new Set([it.id]); dead.clear(); advance(); } // try again now and then
    cue(t, i);
    ui();
  }

  // Load what comes next in the spare players: a feature's return from its break well ahead (a film takes a while to
  // answer), a programme's start and our short pieces a little ahead.
  function cue(t, i) {
    const wanted = [];
    if (cur.mode === 'play' || cur.mode === 'retry') {
      for (let j = i + 1; j < items.length && wanted.length < 3; j++) {
        const n = items[j], ahead = n.s - t;
        if (ahead > CUE_BREAK) break;
        const win = n.o ? CUE_OURS : n.part > 0 ? (items[i].brk ? CUE_BREAK : CUE_RETURN) : CUE_PROG;
        if (ahead > win) continue;
        const c = firstCopy(n, new Set());
        if (c) { c.pl.k = c.k; wanted.push(c.pl); }
      }
      wanted.sort((x, y) => x.ours - y.ours); // a film takes longest to answer: it gets a player first
    }
    for (const s of slots) if (s.role === 'cue' && !wanted.some(w => w.key === s.pl.key)) release(s);
    if (cur.target && slots.some(s => s.role === 'next' && same(s, cur.target))) return; // the line goes to the copies racing for the air
    for (const w of wanted) {
      if (slots.some(s => s.pl && s.pl.key === w.key)) continue;
      const sl = slots.find(s => !s.role);
      if (sl) prepare(sl, w, 'cue');
    }
  }

  // Before the first click: what is on the air now loads (and rolls, muted and unseen, for a while) in a spare
  // player, so the picture is there the moment the set is switched on. Never with data saver on.
  const PRE_ROLL_MS = 90e3, t0 = Date.now(), preconnected = new Set();
  let everOn = false;
  const saveData = !!(navigator.connection && navigator.connection.saveData);
  function preconnect(url) {
    try {
      const o = new URL(url, location.href).origin;
      if (o === location.origin || preconnected.has(o)) return;
      preconnected.add(o);
      for (const rel of ['preconnect', 'dns-prefetch']) { const l = document.createElement('link'); l.rel = rel; l.href = o; document.head.append(l); }
    } catch (e) {}
  }
  function preroll() {
    if (power || everOn || !S || saveData) return;
    const old = slots.find(s => s.pre), rollOk = Date.now() - t0 < PRE_ROLL_MS && !document.hidden;
    const i = find(now()), c = i >= 0 ? firstCopy(items[i], new Set()) : null;
    if (c) preconnect(c.pl.url);
    if (old && c && old.pl.key === c.pl.key) { if (!rollOk && !old.v.paused) old.v.pause(); return; }
    if (old) release(old);
    if (!c || !rollOk) return;
    const sl = slots.find(s => !s.role); if (!sl) return;
    c.pl.k = c.k; sl.pre = true;
    prepare(sl, c.pl, 'cue');
    sl.v.oncanplay = () => {
      sl.ready = true;
      if (!sl.pre || power || !sl.v.paused) return;
      if (Math.abs(sl.v.currentTime - want(sl)) > 4) { try { sl.v.currentTime = want(sl); } catch (e) {} return; } // it took a while: catch up first
      sl.v.play().catch(() => {});
    };
  }
  document.addEventListener('visibilitychange', () => { const o = slots.find(s => s.pre); if (o && document.hidden) o.v.pause(); });

  // By the clock: a film that started late plays a touch faster till it has caught up; far behind, it jumps.
  setInterval(() => {
    const a = power ? air() : slots.find(s => s.pre && !s.v.paused); // the pre-rolled one keeps time too
    if (!a || a.pl.loop || a.pl.ours) return;
    const v = a.v;
    if (v.paused || v.readyState < 3) return;
    const lag = want(a) - v.currentTime;
    if (a.pl.stop >= 0 && v.currentTime * 1000 >= a.pl.stop - 50) return;
    const b = v.buffered, ahead = b.length ? b.end(b.length - 1) - v.currentTime : 0;
    if (lag > 30 || lag < -3 || (lag > 2 && ahead > lag + 1)) { v.currentTime += lag; return; }
    const r = lag > 0.6 ? 1.08 : lag > 0.15 ? 1.04 : 1;
    if (v.playbackRate !== r) v.playbackRate = r;
  }, 1000);
  // A feature's part stops on its last picture before the break; the clock does the rest.
  // ---------- legendas: our own subtitles, per title and language ----------
  // legendas/index.json lists the subtitled titles and, for each copy (by a hash of its address), how its clock lines up
  // with the copy we subtitled: ref = (t - offset) / s, the offset stepping at the copy times listed. A copy that isn't
  // listed plays without subtitles rather than out of sync.
  const SUBS = ['pt-BR', 'en', ''], SUB_NAME = { 'pt-BR': 'PT', en: 'EN', '': 'OFF' };
  let subLang = localStorage.getItem('ktv.sub'); if (subLang === null || !SUBS.includes(subLang)) subLang = 'pt-BR';
  let LG = null, subShown = null;
  const vtts = new Map();
  const fnv = s => { let h = 0x811c9dc5; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; } return ('0000000' + h.toString(16)).slice(-8); };
  async function loadSubs() {
    const r = await fetch(BASE + 'legendas/index.json?m=' + Math.floor(Date.now() / MIN), { cache: 'no-store' });
    if (r.ok) { LG = await r.json(); window.dispatchEvent(new CustomEvent('ktv:subs')); }
  }
  const vttTime = x => { const p = x.trim().split(':').map(Number); return p.length === 3 ? p[0] * 3600 + p[1] * 60 + p[2] : p[0] * 60 + p[1]; };
  function parseVTT(t) {
    const out = [];
    for (const b of t.replace(/\r/g, '').split(/\n\n+/)) {
      const ls = b.split('\n'), k = ls.findIndex(l => l.includes('-->'));
      if (k < 0) continue;
      const [a, z] = ls[k].split('-->');
      out.push([vttTime(a), vttTime(z.trim().split(' ')[0]), ls.slice(k + 1).map(esc).join('<br>')]);
    }
    return out;
  }
  function cueAt(cs, t) {
    let lo = 0, hi = cs.length - 1, k = -1;
    while (lo <= hi) { const m = (lo + hi) >> 1; if (cs[m][0] <= t) { k = m; lo = m + 1; } else hi = m - 1; }
    return k >= 0 && t < cs[k][1] ? cs[k][2] : '';
  }
  function subs(a) {
    let html = '';
    const it = a && a.pl && !a.pl.ours && a.pl.it, e = power && subLang && LG && it && it.p && LG.titles[it.id];
    const c = e && e.langs.includes(subLang) && e.copies[fnv(a.pl.url)];
    if (c) {
      const key = it.id + '.' + subLang, cs = vtts.get(key);
      if (cs === undefined || (cs.failed && Date.now() - cs.failed > 60e3)) {
        vtts.set(key, { loading: 1 });
        fetch(BASE + 'legendas/' + key + '.vtt?r=' + (e.r || '')).then(r => { if (!r.ok) throw r.status; return r.text(); })
          .then(t => vtts.set(key, parseVTT(t))).catch(() => vtts.set(key, { failed: Date.now() }));
      } else if (Array.isArray(cs)) {
        const t = a.v.currentTime;
        let off = c.map[0][1];
        for (const [tc, o] of c.map) { if (t >= tc) off = o; else break; }
        html = cueAt(cs, (t - off) / (c.s || 1));
      }
    }
    if (html !== subShown) { subShown = html; subEl.innerHTML = html; show(subEl, !!html); }
  }
  function setSub(l) {
    subLang = l; localStorage.setItem('ktv.sub', l);
    ccEl.querySelector('.cc').textContent = SUB_NAME[l];
    ccEl.classList.toggle('off', !l);
    ccEl.setAttribute('aria-label', 'Legendas: ' + (l ? SUB_NAME[l] : 'desligadas'));
    subShown = null;
  }

  (function watch() {
    const a = air();
    if (a && a.pl.stop >= 0 && !a.v.paused && a.v.currentTime * 1000 >= a.pl.stop - 20) a.v.pause();
    subs(F.on ? null : a);
    requestAnimationFrame(watch);
  })();

  // ---------- the still: the programme's own picture while its copy loads, never noise ----------
  let ART = {};
  fetch(BASE + 'arte/index.json').then(r => r.ok ? r.json() : {}).then(j => { ART = j || {}; setStill(stillEl.classList.contains('on')); }).catch(() => {});
  function stillUrl() {
    if (!S) return '';
    const t = now(), p = progAt(t) || progAfter(t);
    return p && ART[p.id] ? BASE + 'arte/' + encodeURIComponent(p.id) + '.jpg' : '';
  }
  function setStill(on) {
    const u = on ? stillUrl() : '';
    if (u && stillEl.getAttribute('src') !== u) stillEl.src = u;
    stillEl.classList.toggle('on', on);
    stillEl.classList.toggle('none', on && !u); // no picture for this one: black
  }


  // ---------- what's on ----------
  const hm = ms => new Date(ms).toLocaleTimeString('pt-BR', { timeZone: TZ, hour: '2-digit', minute: '2-digit' });
  const esc = x => String(x).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const blockName = b => (S && S.blocks[b] || {}).pt || '';
  let infoHtml = '', regions = null;
  try { regions = new Intl.DisplayNames(['pt-BR'], { type: 'region' }); } catch (e) {}
  const region = c => { try { return c && regions ? regions.of(c) : c; } catch (e) { return c; } };
  function ui() {
    const t = now();
    clockEl.textContent = new Date(t).toLocaleTimeString('pt-BR', { timeZone: TZ }) + ' · BRASÍLIA';
    if (!S) return;
    const i = find(t), it = i >= 0 ? items[i] : null, a = air();
    show(liveEl, power);
    show(bugEl, power && cur && (!!F.on || cur.mode === 'quiet' || (!!a && !a.pl.ours && cur.mode !== 'card')));
    // "A SEGUIR" on the glass: during our pieces and a programme's last minute; "VOLTAMOS COM" in a break
    let head = '', line = '';
    if (power && F.on) { // the alternative: its name at first, the programme when it's next
      const pr = progAt(t) || progAfter(t);
      if (F.back && pr) { head = 'A SEGUIR'; line = pr.p.title; }
      else if (Date.now() - F.on.liveAt < FILL_LABEL) { head = 'PROGRAMAÇÃO ALTERNATIVA'; line = F.on.pk.title; }
    } else if (power && it && cur && cur.mode !== 'card') {
      const pr = progAt(t), nx = progAfter(pr ? showEnd(pr) : t);
      if (it.brk && it.first) { if (!(it.o && it.o.kind === 'ad')) { head = 'VOLTAMOS COM'; line = it.first.p.title; } } // a spot keeps its own picture clear
      else if (nx && ((it.o && !isTempo(it)) || (!toBreak(it) && pr && showEnd(pr) - t < 60e3))) { head = 'A SEGUIR'; line = hm(nx.s) + ' · ' + nx.p.title; } // not over the weather forecast: it has its own picture
    }
    nextEl.querySelector('b').textContent = head; nextEl.querySelector('span').textContent = line;
    show(nextEl, !!head); host.classList.toggle('ktv-nx', !!head);
    if (info) {
      let html;
      const pr = progAt(t), nx = progAfter(pr ? showEnd(pr) : t), p = pr || nx;
      if (!p) html = '<div class="ttl">Já voltamos</div>'; else {
      const end = showEnd(p), brk = it && it.brk && pr;
      const meta = [p.p.year, region(p.p.country), hm(p.s) + ' – ' + hm(end), brk ? 'INTERVALO' : pr ? '' : 'COMEÇA ÀS ' + hm(p.s)].filter(Boolean).join(' · ');
      const nn = pr ? nx : progAfter(end);
      const leg = LG && LG.titles[p.id] ? ' <span class="badge leg" title="Com legenda em português">LEG</span>' : '';
      html = `<div class="blk${pr ? '' : ' soon'}">${esc(pr ? 'NO AR' : 'A SEGUIR')} · ${esc(blockName(p.p.block || p.block))}</div><h1 class="ttl"><a href="${BASE}programa/?id=${encodeURIComponent(p.id)}">${esc(p.p.title)}</a></h1>
        <div class="meta">${esc(meta)}${leg}</div>${p.p.synopsis ? `<p class="syn">${esc(p.p.synopsis)}</p>` : ''}
        <div class="bar"><i style="width:${pr ? Math.min(100, (t - p.s) / (end - p.s) * 100) : 0}%"></i></div>
        ${F.on ? `<div class="nx alt"><b>PROGRAMAÇÃO ALTERNATIVA</b>${esc(F.on.pk.title)} · em seguida, de volta à grade</div>` : ''}
        ${nn ? `<div class="nx"><b>A SEGUIR</b>${hm(nn.s)} · ${esc(nn.p.title)}</div>` : ''}`; }
      if (html !== infoHtml) info.innerHTML = infoHtml = html;
    }
  }

  // ---------- the week's guide ----------
  const dayKey = ms => new Date(ms).toLocaleDateString('en-CA', { timeZone: TZ });
  let day = '';
  function drawGuide() {
    if (!guideEl || !S) return;
    const t = now(), today = dayKey(t), list = progs.filter(p => (dayKey(p.s) >= today && showEnd(p) > t - 3600e3) || showEnd(p) > t); // today from an hour ago
    const days = [...new Set(list.map(p => dayKey(p.s)))].filter(d => d >= today);
    if (!days.includes(day)) day = days[0] || today;
    if (daysEl) {
      daysEl.textContent = '';
      days.forEach((d, n) => {
        const b = document.createElement('button'); b.type = 'button';
        const at = list.find(p => dayKey(p.s) === d).s;
        b.textContent = n === 0 && d === today ? 'Hoje' : n === 1 && days[0] === today ? 'Amanhã'
          : new Date(at).toLocaleDateString('pt-BR', { timeZone: TZ, weekday: 'short', day: 'numeric' }).replace('.', '');
        b.className = d === day ? 'sel' : '';
        b.onclick = () => { day = d; drawGuide(); };
        daysEl.append(b);
      });
    }
    guideEl.textContent = '';
    let block = null, part = null;
    const parts = (S.dayparts || []).map(x => [+x.at.slice(0, 2) * 60 + +x.at.slice(3), x.pt]).sort((x, y) => x[0] - y[0]);
    const partOf = ms => { const [h, m] = hm(ms).split(':').map(Number); let n = null; for (const x of parts) if (h * 60 + m >= x[0]) n = x[1]; return n; };
    for (const p of list) {
      if (dayKey(p.s) !== day) continue;
      const pt = parts.length ? partOf(p.s) : null;
      if (pt && pt !== part) { part = pt; block = null; const li = document.createElement('li'); li.className = 'part'; li.textContent = pt; guideEl.append(li); }
      if (p.block !== block) { block = p.block; const li = document.createElement('li'); li.className = 'sec'; li.textContent = '— ' + (blockName(block) || block); guideEl.append(li); }
      const li = document.createElement('li'), e = showEnd(p);
      li.className = p.s <= t && t < e ? 'on' : e <= t ? 'past' : '';
      li.innerHTML = '<time>' + hm(p.s) + '</time><span>' + esc(p.p.title) + (p.p.year ? '<small>' + p.p.year + '</small>' : '') + '</span>';
      guideEl.append(li);
    }
  }

  // ---------- the knobs ----------
  function powerOn() {
    if (power) return;
    power = true; sound = true; everOn = true;
    host.classList.add('on'); powerEl.style.display = 'none';
    q('[data-k=power] .lbl').textContent = 'DESLIGAR';
    // Browsers let a page play sound only from a click: start every player here so each may play later on its own.
    for (const v of slots.filter(s => !s.role).map(s => s.v).concat(F.v.filter(f => !f.pk))) {
      v.muted = false; v.src = TROUBLE.url;
      const p = v.play(); if (p) p.catch(() => {});
      v.pause(); v.muted = true; v.removeAttribute('src'); try { v.load(); } catch (e) {}
    }
    screen.classList.remove('off');
    setStill(true);
    if (!S) { msgEl.textContent = 'SINTONIZANDO…'; show(msgEl, true); load().then(tick).catch(() => htmlCard('JÁ VOLTAMOS')); }
    else tick();
  }
  function powerOff() {
    power = false; cur = null;
    for (const s of slots) release(s);
    for (const f of F.v) dropF(f);
    F.tries = 0; F.gaveUp = 0;
    host.classList.remove('on'); powerEl.style.display = '';
    q('[data-k=power] .lbl').textContent = 'LIGAR';
    void screen.offsetWidth; screen.classList.add('off');
    show(cardEl, false); show(msgEl, false); show(tapEl, false); setStill(true); loading(); ui();
  }
  function setMute(m) {
    muted = m; localStorage.setItem('ktv.mute', m ? '1' : '0');
    q('[data-k=mute] .w').style.display = m ? 'none' : ''; q('[data-k=mute] .x').style.display = m ? '' : 'none';
    levels();
  }
  function unmuteTap() { tapNeeded = false; show(tapEl, false); const a = air(); if (a) { a.v.muted = muted; a.v.play().catch(() => {}); } levels(); }
  function full() {
    const fs = document.fullscreenElement || document.webkitFullscreenElement;
    if (fs) { (document.exitFullscreen || document.webkitExitFullscreen).call(document); return; }
    if (host.classList.contains('full')) { host.classList.remove('full'); return; }
    const req = host.requestFullscreen || host.webkitRequestFullscreen;
    if (req) { const p = req.call(host); if (p && p.catch) p.catch(() => host.classList.add('full')); }
    else host.classList.add('full'); // iPhone: the page's own full window
  }
  const fsChange = () => host.classList.toggle('full', !!(document.fullscreenElement || document.webkitFullscreenElement));
  document.addEventListener('fullscreenchange', fsChange); document.addEventListener('webkitfullscreenchange', fsChange);
  let idle = 0;
  const wake = () => { host.classList.remove('idle'); clearTimeout(idle); idle = setTimeout(() => host.classList.add('idle'), 2500); };
  host.addEventListener('mousemove', wake); host.addEventListener('touchstart', wake, { passive: true });

  powerEl.addEventListener('click', e => { e.stopPropagation(); powerOn(); });
  powerEl.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); powerOn(); } });
  tapEl.addEventListener('click', e => { e.stopPropagation(); unmuteTap(); });
  glass.addEventListener('click', () => { if (!power) powerOn(); else if (tapNeeded) unmuteTap(); });
  glass.addEventListener('dblclick', () => { if (power) full(); });
  q('[data-k=power]').onclick = () => power ? powerOff() : powerOn();
  q('[data-k=mute]').onclick = () => { if (tapNeeded) unmuteTap(); else setMute(!muted); };
  q('[data-k=full]').onclick = full;
  ccEl.onclick = () => setSub(SUBS[(SUBS.indexOf(subLang) + 1) % SUBS.length]);
  volEl.value = vol;
  volEl.oninput = () => { vol = +volEl.value; localStorage.setItem('ktv.vol', vol); if (muted && vol > 0) setMute(false); else levels(); };
  document.addEventListener('keydown', e => {
    if (e.target.closest && e.target.closest('input,textarea')) return;
    const k = e.key.toLowerCase();
    if (k === 'f' && power) full();
    else if (k === 'm') setMute(!muted);
    else if (k === 'c' || k === 'l') ccEl.click();
    else if (k === 'escape' && host.classList.contains('full')) host.classList.remove('full');
  });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) tick(); });
  setMute(muted); setSub(subLang);

  loadSubs().catch(() => {});
  setInterval(() => loadSubs().catch(() => {}), 10 * MIN);
  load().then(() => { ui(); drawGuide(); setStill(true); preroll(); }).catch(() => { if (info) info.innerHTML = '<div class="ttl">Já voltamos</div>'; });
  setInterval(tick, 500);
  setInterval(() => { if (!power) { ui(); preroll(); if (!everOn) setStill(true); } }, 1000);
  setInterval(drawGuide, 60e3);
  setInterval(() => load().then(() => power && tick()).catch(() => {}), 5 * MIN);
  setInterval(() => { if (power && cur && cur.key === 'standby') load().then(tick).catch(() => {}); }, 30e3);
})();
