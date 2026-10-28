/* ResilientSync dashboard client.
 *
 * The browser is a view + input device.  Two data sources feed the SAME renderers:
 *   LIVE    server state over WebSocket (fallback: polling /state)
 *   REPLAY  a saved, versioned recording (GET /recordings/{id}); nothing is re-simulated
 * Every control calls a server endpoint that validates the input; nothing here mutates robots.
 */
(() => {
  'use strict';
  const { $, esc, fmt, css, api, get, toast, colorOf, short, COLORS, SUP_NAMES, SUP_COLORS, bodyToWorld } = RS;

  const KEY_MAP = { w: 'W', a: 'A', s: 'S', d: 'D', arrowup: 'W', arrowdown: 'S', arrowleft: 'A',
                    arrowright: 'D', ' ': 'SPACE', r: 'R', x: 'X', f: 'F' };
  const ONE_SHOT = new Set(['SPACE', 'R', 'X', 'F']);
  const HIST_MAX = 1600;

  // ----------------------------------------------------------------- state
  let mode = 'live';                                   // 'live' | 'replay'
  let state = null, stateWall = 0, lastTime = -1;
  let ws = null, pollTimer = null, agentCount = 0, wsFails = 0;
  const held = new Set();
  const layers = { trails: true, links: true, slots: true, skeleton: true, target: false,
                   errvec: true, markers: true, sep: true, labels: true };
  let trailSec = 10;
  let winSec = 60;
  const live = { trails: {}, hist: [], markers: [], faultOn: false, tmax: 0 };
  const rp = { rec: null, id: null, i: 0, head: 0, playing: false, speed: 1, t: [], data: null, summary: null, wall: 0 };

  // ---------------------------------------------------------------- canvas
  const canvas = $('world'), ctx = canvas.getContext('2d');
  let view = { w: 0 };
  function relayout(world) { view = RS.viewport.layout(canvas, world); }

  // ------------------------------------------------------------ live scene
  function displayPose(a) {                            // cosmetic extrapolation between 10 Hz updates
    let dt = 0;
    if (state && !state.runner.paused && !state.halted) {
      dt = Math.min((performance.now() - stateWall) / 1000 * state.runner.speed, 0.2);
    }
    return { x: a.x + a.v * Math.cos(a.theta) * dt, y: a.y + a.v * Math.sin(a.theta) * dt, th: a.theta + a.omega * dt };
  }
  function liveScene() {
    const st = state, R = st.resilience || {}, C = st.connectivity || {};
    const fol = R.followers || {};
    const unreached = new Set(C.unreached_by_leader || []);
    const agents = st.agents.map((a) => {
      const p = displayPose(a);
      return { id: a.id, x: p.x, y: p.y, th: p.th, v: a.v, mode: a.mode, stopped: a.mode === 'STOPPED',
               sup: a.id > 0 && R.supervisor_active && fol[a.id] ? fol[a.id].state : null,
               age: a.id > 0 ? (a.communication_age ?? 0) : 0, up: a.id > 0 ? !unreached.has(a.id) : true,
               tx: a.slot ? a.slot[0] : null, ty: a.slot ? a.slot[1] : null, quality: a.communication_quality };
    });
    const f = R.faults || {};
    const trails = {};
    const t0 = st.time - trailSec;
    for (const id in live.trails) trails[id] = live.trails[id].filter((q) => q[0] >= t0).map((q) => [q[1], q[2]]);
    const ca = C.closest_approach;
    return { t: st.time, world: st.world, agents, offsets: st.formation.offsets, trails,
             isolated: C.isolated_from_leader || [], collisionDistance: st.collision_distance,
             faultActive: !!((f.active || []).length || f.blackout_active || f.forced_loss),
             markers: live.markers,
             closest: ca && ca.distance != null ? { ...ca, collision: ca.distance < st.collision_distance } : null };
  }

  // ---------------------------------------------------------- replay scene
  function idxAt(t) {                                  // nearest recorded frame
    const T = rp.t; let lo = 0, hi = T.length - 1;
    while (lo < hi) { const m = (lo + hi) >> 1; if (T[m] < t) lo = m + 1; else hi = m; }
    return (lo > 0 && t - T[lo - 1] < T[lo] - t) ? lo - 1 : lo;
  }
  function replayScene() {
    const rec = rp.rec, F = rec.frames, i = rp.i, n = rec.meta.n_agents;
    const t = F.t[i];
    const agents = [];
    for (let k = 0; k < n; k++) {
      const s = F.states[i][k];
      agents.push({ id: k, x: s[0], y: s[1], th: s[2], v: s[3], mode: k === 0 ? 'AUTO' : 'FOLLOW', stopped: false,
                    sup: k > 0 && rec.meta.supervisor_enabled && rec.meta.control_mode === 'adaptive_comm' ? SUP_NAMES[F.supervisor_state[i][k]] : null,
                    age: k > 0 ? F.age[i][k - 1] : 0, up: k > 0 ? F.downlink_up[i][k - 1] : true,
                    tx: k > 0 ? F.targets[i][k][0] : null, ty: k > 0 ? F.targets[i][k][1] : null,
                    quality: F.communication_quality[i][k] });
    }
    const trails = {}, t0 = t - trailSec;
    for (let k = 0; k < n; k++) {
      const pts = []; for (let j = i; j >= 0 && F.t[j] >= t0; j--) pts.push([F.states[j][k][0], F.states[j][k][1]]);
      trails[k] = pts.reverse();
    }
    const markers = [];
    for (const e of rec.events.fault_intervals || []) {
      const a = (tt) => { const j = idxAt(tt); return F.states[j][0]; };
      if (e.start <= rec.frames.t[F.t.length - 1]) markers.push({ kind: 'fault_start', x: a(e.start)[0], y: a(e.start)[1], label: `${e.kind} start ${e.start.toFixed(1)} s` });
      if (e.end != null && e.end <= F.t[F.t.length - 1]) markers.push({ kind: 'fault_end', x: a(e.end)[0], y: a(e.end)[1], label: `${e.kind} end ${e.end.toFixed(1)} s` });
    }
    const ca = rec.events.closest_approach;
    const faultNow = (rec.events.fault_intervals || []).some((e) => t >= e.start && (e.end == null || t < e.end));
    return { t, world: { ...rec.meta.world, margin: 0 }, agents, offsets: rec.meta.formation_offsets, trails,
             isolated: agents.filter((a) => a.id > 0 && !a.up).map((a) => a.id),
             collisionDistance: rec.meta.collision_distance, faultActive: faultNow, markers,
             closest: ca && ca.distance != null ? { ...ca, collision: ca.distance < rec.meta.collision_distance } : null };
  }

  // ------------------------------------------------------------- main draw
  function draw() {
    requestAnimationFrame(draw);
    if (mode === 'replay' && rp.rec && rp.playing) stepPlayback();
    const sc = mode === 'live' ? (state ? liveScene() : null) : (rp.rec ? replayScene() : null);
    if (!sc) return;
    const key = `${canvas.parentElement.clientWidth}|${sc.world.x_max}|${sc.world.y_max}|${window.devicePixelRatio}`;
    if (!view.w || view.key !== key) { relayout(sc.world); view.key = key; }
    RS.viewport.draw(ctx, view, sc, layers);
    paintOverlay(sc);
  }

  function paintOverlay(sc) {
    const el = $('status-overlay');
    const f = sc.agents.filter((a) => a.id > 0);
    const c = { ok: 0, stale: 0, lost: 0 };
    f.forEach((a) => { c[RS.linkClass(a.age, a.up)]++; });
    const comps = mode === 'live' ? (state.connectivity || {}).n_components : (rp.rec ? rp.rec.frames.n_components[rp.i] : null);
    const ctrl = mode === 'live' ? state.control_mode : rp.rec.meta.control_mode;
    const fl = [];
    if (sc.faultActive) fl.push('FAULT ACTIVE');
    el.innerHTML =
      `<div><b>${mode === 'live' ? 'LIVE' : 'REPLAY'}</b> t = ${sc.t.toFixed(2)} s &middot; ${esc(ctrl)}</div>` +
      `<div>links: <span class="c-ok">${c.ok} fresh</span> &middot; <span class="c-stale">${c.stale} stale</span> &middot; <span class="c-lost">${c.lost} lost</span></div>` +
      `<div>network components: ${comps ?? '–'}${sc.isolated.length ? ' &middot; isolated: ' + sc.isolated.map(short).join(', ') : ''}</div>` +
      (fl.length ? `<div class="c-lost"><b>${fl.join(' ')}</b></div>` : '');
  }

  function buildLegend() {
    const sw = (c, dash) => `<svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" stroke="${c}" stroke-width="2" ${dash ? `stroke-dasharray="${dash}"` : ''}/></svg>`;
    $('legend').innerHTML =
      `<div>${sw(COLORS.ok)} link fresh (age &le; ${RS.AGE_FRESH} s)</div>` +
      `<div>${sw(COLORS.stale, '6 3')} stale (&le; ${RS.AGE_LOST} s)</div>` +
      `<div>${sw(COLORS.lost, '2 3')} lost / isolated</div>` +
      `<div><svg width="26" height="10"><circle cx="13" cy="5" r="4" fill="none" stroke="#555" stroke-dasharray="3 2"/></svg> desired slot</div>` +
      `<div><svg width="26" height="10"><line x1="0" y1="5" x2="26" y2="5" stroke="${COLORS.stale}" stroke-width="2"/></svg> slot error</div>` +
      `<div><svg width="26" height="10"><circle cx="13" cy="5" r="4" fill="none" stroke="${SUP_COLORS.DEGRADED}" stroke-width="2"/></svg> supervisor ring</div>` +
      `<div><svg width="26" height="12"><path d="M13 1 L19 6 L13 11 L7 6 Z" fill="${COLORS.lost}"/></svg> fault start/end</div>`;
  }

  // ------------------------------------------------------------ live intake
  function onState(st) {
    if (st.time < lastTime - 1e-9) {                   // simulation was reset
      live.trails = {}; live.hist = []; live.markers = []; live.faultOn = false;
    }
    if (st.time !== lastTime) {
      for (const a of st.agents) (live.trails[a.id] || (live.trails[a.id] = [])).push([st.time, a.x, a.y]);
      for (const id in live.trails) { const tr = live.trails[id]; while (tr.length > HIST_MAX) tr.shift(); }
      pushHist(st);
    }
    const R = st.resilience || {}, f = R.faults || {};
    const fOn = !!((f.active || []).length || f.blackout_active || f.forced_loss);
    if (fOn !== live.faultOn && st.time !== lastTime) {
      const l = st.agents[0];
      live.markers.push({ kind: fOn ? 'fault_start' : 'fault_end', x: l.x, y: l.y, label: `fault ${fOn ? 'start' : 'end'} ${st.time.toFixed(1)} s` });
      if (live.markers.length > 8) live.markers.shift();
    }
    live.faultOn = fOn;
    lastTime = st.time; state = st; stateWall = performance.now();
    if (mode === 'live') updatePanels();
  }

  function pushHist(st) {
    const R = st.resilience || {}, C = st.connectivity || {}, fol = R.followers || {};
    const F = st.agents.filter((a) => a.id > 0);
    const q = F.map((a) => a.communication_quality ?? 1), ages = F.map((a) => a.communication_age ?? 0);
    live.hist.push({
      t: st.time, rms: st.formation_rms, sep: st.min_distance,
      qMin: Math.min(...q), qMean: q.reduce((x, y) => x + y, 0) / (q.length || 1), ageMax: Math.max(...ages),
      sup: F.map((a) => (R.supervisor_active && fol[a.id]) ? SUP_NAMES.indexOf(fol[a.id].state) : 0),
      nIso: (C.isolated_from_leader || []).length, lam2: C.algebraic_connectivity ?? 0,
      hRms: C.heading_rms ?? 0, sStd: C.speed_std ?? 0, faults: (R.faults || {}).events || [] });
    if (live.hist.length > HIST_MAX) live.hist.shift();
  }

  // ------------------------------------------------------------ plot data
  function liveData() {
    const H = live.hist; if (H.length < 2) return null;
    const nf = H[H.length - 1].sup.length;
    return { t: H.map((h) => h.t), rms: H.map((h) => h.rms), sep: H.map((h) => h.sep), qMin: H.map((h) => h.qMin),
             qMean: H.map((h) => h.qMean), ageMax: H.map((h) => h.ageMax), nIso: H.map((h) => h.nIso),
             lam2: H.map((h) => h.lam2), hRms: H.map((h) => h.hRms), sStd: H.map((h) => h.sStd),
             supRows: Array.from({ length: nf }, (_, k) => H.map((h) => h.sup[k])),
             supActive: !!(state && state.resilience && state.resilience.supervisor_active),
             faults: H[H.length - 1].faults, collisionDistance: state ? state.collision_distance : 0.38 };
  }
  function replayData(rec) {
    const F = rec.frames, n = rec.meta.n_agents;
    const col = (arr, k) => arr.map((r) => r[k]);
    const q = F.communication_quality.map((r) => r.slice(1));
    return { t: F.t, rms: F.formation_rms, sep: F.min_distance, qMin: q.map((r) => Math.min(...r)),
             qMean: q.map((r) => r.reduce((a, b) => a + b, 0) / r.length), ageMax: F.age.map((r) => Math.max(...r)),
             nIso: F.n_isolated, lam2: F.lambda2, hRms: F.heading_rms, sStd: F.speed_std,
             supRows: Array.from({ length: n - 1 }, (_, k) => col(F.supervisor_state, k + 1)),
             supActive: rec.meta.control_mode === 'adaptive_comm' && rec.meta.supervisor_enabled,
             faults: rec.events.fault_intervals || [], collisionDistance: rec.meta.collision_distance };
  }

  let lastPlot = 0;
  function renderPlots(force) {
    const now = performance.now();
    if (!force && now - lastPlot < 180) return;
    lastPlot = now;
    const D = mode === 'live' ? liveData() : rp.data;
    if (!D) return;
    let t0, t1, cursor = null;
    if (mode === 'live') { t1 = D.t[D.t.length - 1]; t0 = Math.max(0, t1 - winSec); t1 = Math.max(t1, t0 + 5); }
    else { t0 = D.t[0]; t1 = D.t[D.t.length - 1]; cursor = D.t[rp.i]; }
    const base = { t0, t1, faults: D.faults, cursor };
    const P = RS.plots;
    const imax = (a) => a.reduce((b, v, i) => (v > a[b] ? i : b), 0), imin = (a) => a.reduce((b, v, i) => (v < a[b] ? i : b), 0);
    const mk = [], mk2 = [];
    if (mode === 'replay') {
      const e = imax(D.rms), s = imin(D.sep);
      mk.push({ t: D.t[e], y: D.rms[e], label: `peak ${fmt(D.rms[e], 2)} m @ ${fmt(D.t[e], 1)} s` });
      mk2.push({ t: D.t[s], y: D.sep[s], label: `min ${fmt(D.sep[s], 2)} m @ ${fmt(D.t[s], 1)} s`, color: COLORS.info });
    }
    P.line($('pl-err'), { ...base, title: 'Formation RMS error', unit: 'm', markers: mk,
      series: [{ t: D.t, y: D.rms, color: '#2563eb', label: 'rms', dec: 2 }] });
    P.line($('pl-sep'), { ...base, title: 'Minimum separation', unit: 'm', yMin: 0, markers: mk2,
      hlines: [{ y: D.collisionDistance, label: `collision < ${D.collisionDistance} m`, color: COLORS.lost }],
      series: [{ t: D.t, y: D.sep, color: '#0f766e', label: 'min', dec: 2 }] });
    P.line($('pl-q'), { ...base, title: 'Communication quality (estimated)', unit: '0–1', yMax: 1,
      series: [{ t: D.t, y: D.qMean, color: '#475569', label: 'mean', dec: 2 }, { t: D.t, y: D.qMin, color: '#c98a00', label: 'worst follower', dec: 2 }] });
    P.line($('pl-age'), { ...base, title: 'Leader-message age (worst follower)', unit: 's',
      hlines: [{ y: RS.AGE_LOST, label: 'lost > 1 s', color: COLORS.lost }],
      series: [{ t: D.t, y: D.ageMax, color: '#7c3aed', label: 'max age', dec: 2 }] });
    P.strip($('pl-sup'), { ...base, title: D.supActive ? 'Supervisor state per follower' : 'Supervisor (not active for this controller)',
      rows: D.supRows.map((s, k) => ({ label: 'F' + (k + 1), t: D.t, s })) });
    P.line($('pl-net'), { ...base, title: 'Connectivity', unit: 'isolated', unitR: 'λ₂', rightAxis: true,
      yMax: Math.max(2, D.supRows.length), yMaxR: Math.max(1, ...D.lam2) * 1.1,
      series: [{ t: D.t, y: D.nIso, color: COLORS.lost, label: 'isolated followers', step: true, dec: 0 },
               { t: D.t, y: D.lam2, color: '#2c7fb8', label: 'λ₂', axis: 'r', step: true, dec: 2 }] });
    P.line($('pl-cons'), { ...base, title: 'Heading & speed disagreement (consensus)', unit: 'rad', unitR: 'm/s', rightAxis: true, last: true,
      hlines: [{ y: 0.25, label: 'consensus tol 0.25 rad', color: COLORS.ok }],
      series: [{ t: D.t, y: D.hRms, color: '#9d174d', label: 'heading rms', dec: 2 }, { t: D.t, y: D.sStd, color: '#b45309', label: 'speed std', axis: 'r', dec: 2 }] });
    plotMeta = { t0, t1 };
  }
  let plotMeta = { t0: 0, t1: 1 };

  // click / drag on any plot seeks the replay
  let dragging = false;
  function seekFromPlot(e, cv) {
    if (mode !== 'replay' || !rp.rec) return;
    const right = cv.id === 'pl-net' || cv.id === 'pl-cons';
    setReplayTime(RS.plots.xToT(cv, e.clientX, plotMeta.t0, plotMeta.t1, right));
  }
  document.querySelectorAll('canvas.plot').forEach((cv) => {
    cv.addEventListener('pointerdown', (e) => { dragging = true; cv.setPointerCapture(e.pointerId); seekFromPlot(e, cv); });
    cv.addEventListener('pointermove', (e) => { if (dragging) seekFromPlot(e, cv); });
    cv.addEventListener('pointerup', () => { dragging = false; });
  });

  // ----------------------------------------------------------- side panels
  function updatePanels() {
    const live_ = mode === 'live';
    const st = state;
    if (live_ && !st) return;
    // header chips
    const R = live_ ? (st.resilience || {}) : null;
    $('chip-view').textContent = live_ ? 'LIVE' : 'REPLAY';
    $('chip-view').dataset.view = mode;
    if (live_) {
      $('chip-time').textContent = `t = ${fmt(st.time, 1)} s`;
      $('chip-ctrl').textContent = st.control_mode;
      const w = R.supervisor_active ? R.worst_state : null;
      $('chip-sup').textContent = w ? `supervisor ${w}` : 'supervisor off';
      $('chip-sup').style.background = w ? SUP_COLORS[w] : ''; $('chip-sup').style.color = w ? '#fff' : '';
      const C = st.connectivity || {};
      $('chip-net').textContent = C.n_components != null ? (C.connected ? 'network connected' : `network split (${C.n_components} groups)`) : 'network -';
      $('chip-net').dataset.state = C.connected ? 'ok' : 'bad';
      $('btn-pause').textContent = st.runner.paused ? 'Resume' : 'Pause';
      syncSelect($('sel-simmode'), st.sim_mode); syncSelect($('sel-speed'), String(st.runner.speed));
      $('chk-loss').checked = !!st.network.forced_loss;
      const banner = $('halt-banner'); banner.hidden = !st.halted;
      if (st.halted) banner.textContent = 'SIMULATION HALTED: ' + (st.fault || '');
      if (st.agents.length !== agentCount) {
        agentCount = st.agents.length;
        const sel = $('sel-agent'), cur = sel.value;
        sel.innerHTML = '<option value="ALL">ALL</option><option value="LEADER">LEADER</option>' +
          st.agents.filter((a) => a.id > 0).map((a) => `<option value="${a.id}">Agent ${a.id}</option>`).join('');
        sel.value = [...sel.options].some((o) => o.value === cur) ? cur : 'ALL';
      }
    }
    if (!live_ && rp.rec) {                                   // chips describe the replayed frame
      const F = rp.rec.frames, i = rp.i, act = rp.rec.meta.control_mode === 'adaptive_comm' && rp.rec.meta.supervisor_enabled;
      const w = act ? F.supervisor_state[i].slice(1).map((c) => SUP_NAMES[c]).reduce((b, n) => (SUP_NAMES.indexOf(n) > SUP_NAMES.indexOf(b) ? n : b), 'NORMAL') : null;
      $('chip-sup').textContent = w ? `supervisor ${w}` : 'supervisor off';
      $('chip-sup').style.background = w ? SUP_COLORS[w] : ''; $('chip-sup').style.color = w ? '#fff' : '';
      const iso = F.downlink_up[i].filter((u) => !u).length;
      $('chip-net').textContent = iso ? `network split (${F.n_components[i]} groups)` : 'network connected';
      $('chip-net').dataset.state = iso ? 'bad' : 'ok';
    }
    renderInspector();
    renderNetwork();
    if (live_) renderOperator(st);
    renderPlots(false);
  }
  function syncSelect(sel, value) { if (document.activeElement !== sel && sel.value !== value) sel.value = value; }

  const trueSlotErr = (agents, offsets, a) => {
    const l = agents[0]; if (!offsets || a.id === 0) return null;
    const p = bodyToWorld(offsets[a.id], { x: l.x, y: l.y, th: l.th });
    return Math.hypot(p[0] - a.x, p[1] - a.y);
  };

  function renderInspector() {
    const live_ = mode === 'live';
    const sc = live_ ? (state ? liveScene() : null) : (rp.rec ? replayScene() : null);
    if (!sc) return;
    $('insp-time').textContent = `t = ${fmt(sc.t, 2)} s`;
    $('tbl-agents').querySelector('tbody').innerHTML = sc.agents.map((a) => {
      const e = trueSlotErr(sc.agents, sc.offsets, a);
      return `<tr><td><span class="swatch" style="background:${colorOf(a.id)}"></span>${short(a.id)}</td><td>${esc(a.mode)}</td>` +
        `<td>${fmt(a.x, 2)}</td><td>${fmt(a.y, 2)}</td><td>${fmt(a.th * 180 / Math.PI, 0)}</td><td>${fmt(a.v, 2)}</td>` +
        `<td class="link-${RS.linkClass(a.age, a.up)}">${a.id ? fmt(a.age, 2) : '–'}</td>` +
        `<td>${a.id && a.quality != null ? fmt(a.quality, 2) : '–'}</td><td>${e == null ? '–' : fmt(e, 2)}</td>` +
        `<td>${a.sup ? `<span class="state-pill sm st-${a.sup}">${a.sup.slice(0, 4)}</span>` : '–'}</td></tr>`;
    }).join('');

    // supervisor pane
    let active, worst, explain, stats = '', times = '', trans = [];
    if (live_) {
      const R = state.resilience || {};
      active = !!R.supervisor_active;
      if (active) {
        worst = R.worst_state;
        const sorted = Object.entries(R.followers).sort((a, b) => SUP_NAMES.indexOf(b[1].state) - SUP_NAMES.indexOf(a[1].state));
        explain = `F${sorted[0][0]}: ${sorted[0][1].reason}`;
        const q = Object.values(R.followers).map((v) => v.quality), ages = Object.values(R.followers).map((v) => v.age ?? Infinity);
        stats = `<div><b>quality min</b> ${fmt(Math.min(...q), 2)}</div><div><b>quality mean</b> ${fmt(q.reduce((a, b) => a + b, 0) / q.length, 2)}</div>` +
          `<div><b>max age</b> ${isFinite(Math.max(...ages)) ? fmt(Math.max(...ages), 2) + ' s' : '∞'}</div><div><b>blackout</b> ${(R.faults || {}).blackout_active ? 'ACTIVE' : 'no'}</div>` +
          Object.entries(R.followers).map(([id, v]) => `<div><b>F${id}</b> ${v.state} &middot; ff&times;${fmt(v.ff_scale, 2)}</div>`).join('');
        const n = Object.keys(R.followers).length, tot = R.durations_total, sum = Object.values(tot).reduce((a, b) => a + b, 0) || 1;
        times = Object.entries(tot).map(([k, v]) => `<div><b>${k}</b> ${fmt(v / n, 1)} s (${fmt(100 * v / sum, 0)}%)</div>`).join('');
        trans = (R.transitions || []).map((t) => ({ t: t.t, agent: t.agent, from: t.from, to: t.to, reason: t.reason }));
      }
      renderFault(R.faults || {});
    } else {
      const rec = rp.rec;
      active = rec.meta.control_mode === 'adaptive_comm' && rec.meta.supervisor_enabled;
      if (active) {
        const names = rec.frames.supervisor_state[rp.i].slice(1).map((c) => SUP_NAMES[c]);
        worst = names.reduce((b, n) => (SUP_NAMES.indexOf(n) > SUP_NAMES.indexOf(b) ? n : b), 'NORMAL');
        const T = rec.events.supervisor_transitions.filter((t) => t.t <= sc.t + 1e-9);
        const last = T.filter((t) => t.kind === 'transition').slice(-1)[0];
        explain = last ? `last transition (F${last.agent}, ${fmt(last.t, 2)} s): ${last.reason}` : 'no transition yet';
        stats = names.map((n, k) => `<div><b>F${k + 1}</b> ${n} &middot; q ${fmt(rec.frames.communication_quality[rp.i][k + 1], 2)} &middot; age ${fmt(rec.frames.age[rp.i][k], 2)} s</div>`).join('');
        const tot = {}; SUP_NAMES.forEach((n) => { tot[n] = 0; });
        for (let j = 0; j < rp.i; j++) for (let k = 1; k < rec.meta.n_agents; k++) tot[SUP_NAMES[rec.frames.supervisor_state[j][k]]] += (rec.frames.t[j + 1] - rec.frames.t[j]) / (rec.meta.n_agents - 1);
        times = Object.entries(tot).map(([k, v]) => `<div><b>${k}</b> ${fmt(v, 1)} s (to cursor)</div>`).join('');
        trans = rec.events.supervisor_transitions.filter((t) => t.kind === 'transition');
      }
      renderFault({ events: rec.events.fault_intervals, profile: rec.meta.fault_profile.name, active: [] });
    }
    $('res-off').hidden = active; $('res-body').hidden = !active;
    if (active) {
      const pill = $('res-state'); pill.textContent = worst; pill.className = 'state-pill st-' + worst;
      $('res-explain').textContent = explain; $('res-stats').innerHTML = stats; $('res-time').innerHTML = times;
      const cur = sc.t;
      $('res-trans').innerHTML = trans.length ? trans.slice(-40).reverse().map((t) =>
        `<div class="ev ${!live_ && t.t > cur ? 'future' : ''}" data-t="${t.t}"><span class="ev-t">${fmt(t.t, 2)} s</span> F${t.agent} ` +
        `<span class="state-pill sm st-${t.from}">${t.from.slice(0, 4)}</span>&rarr;<span class="state-pill sm st-${t.to}">${t.to.slice(0, 4)}</span><br>` +
        `<span class="muted">${esc(t.reason)}</span></div>`).join('') : '<span class="muted small">(no transitions yet)</span>';
    }
  }
  $('res-trans').addEventListener('click', (e) => {
    const el = e.target.closest('.ev'); if (el && mode === 'replay') setReplayTime(parseFloat(el.dataset.t));
  });

  function renderFault(f) {
    $('res-fault').textContent = (f.profile && f.profile !== 'none') || (f.events || []).length
      ? `profile: ${f.profile}` + (f.active && f.counts ? ` | fault-dropped ${f.counts.dropped_by_fault}, fault-delayed ${f.counts.delayed_by_fault}` : '') +
        (f.events || []).map((e) => `\n  ${e.kind}: ${fmt(e.start, 1)} s → ${e.end === null ? 'end of run' : fmt(e.end, 1) + ' s'}${e.active ? '  [ACTIVE]' : ''}`).join('')
      : 'no fault scheduled';
  }

  function renderNetwork() {
    const live_ = mode === 'live';
    let conn = '', iv = '', cons = '', stats = '';
    if (live_ && state) {
      const C = state.connectivity || {}, T = C.tracker || {}, n = state.network;
      conn = `<div><b>connected</b> ${C.connected ? 'yes' : 'NO'}</div><div><b>components</b> ${C.n_components ?? '–'}</div>` +
        `<div><b>λ₂ (algebraic conn.)</b> ${fmt(C.algebraic_connectivity, 3)}</div><div><b>isolated</b> ${(C.isolated_from_leader || []).map(short).join(', ') || 'none'}</div>` +
        `<div><b>unreached by leader</b> ${(C.unreached_by_leader || []).map(short).join(', ') || 'none'}</div><div><b>uplink down</b> ${(C.uplink_down || []).map(short).join(', ') || 'none'}</div>` +
        `<div><b>interruptions</b> ${T.n_interruptions ?? 0}</div><div><b>total interrupted</b> ${fmt(T.interruption_total_s, 2)} s</div>`;
      iv = (T.interruptions || []).map((x) => `${fmt(x.start, 2)} s → ${x.end == null ? 'ongoing' : fmt(x.end, 2) + ' s'}  (${fmt(x.duration, 2)} s)`).join('\n') || 'none';
      cons = `<div><b>heading rms</b> ${fmt(C.heading_rms, 3)} rad</div><div><b>heading max</b> ${fmt(C.heading_max, 3)} rad</div>` +
        `<div><b>speed std</b> ${fmt(C.speed_std, 3)} m/s</div><div><b>speed spread</b> ${fmt(C.speed_spread, 3)} m/s</div>` +
        `<div><b>edge heading</b> ${fmt(C.edge_heading, 3)} rad</div><div><b>edge speed</b> ${fmt(C.edge_speed, 3)} m/s</div>` +
        `<div><b>heading consensus</b> ${C.heading_consensus ? 'yes' : 'no'} (tol 0.25 rad)</div>`;
      stats = `<div><b>sent</b> ${n.sent}</div><div><b>received</b> ${n.received}</div><div><b>lost</b> ${n.lost}</div>` +
        `<div><b>loss rate</b> ${fmt(n.loss_rate)} %</div><div><b>latency avg</b> ${fmt(n.avg_latency * 1000, 0)} ms</div>` +
        `<div><b>latency max</b> ${fmt(n.max_latency * 1000, 0)} ms</div><div><b>awaiting ACK</b> ${state.pending_commands}</div>` +
        `<div><b>boundary clamps</b> ${state.boundary_clamps}</div><div><b>form. error</b> ${fmt(state.formation_rms, 2)} m</div>` +
        `<div><b>min separation</b> ${fmt(state.min_distance, 2)} m</div>`;
      commLog(state);
    } else if (rp.rec) {
      const F = rp.rec.frames, i = rp.i, ev = rp.rec.events;
      const iso = []; for (let k = 1; k < rp.rec.meta.n_agents; k++) if (!F.downlink_up[i][k - 1]) iso.push(k);
      conn = `<div><b>connected</b> ${iso.length ? 'NO' : 'yes'}</div><div><b>components</b> ${F.n_components[i]}</div>` +
        `<div><b>λ₂</b> ${fmt(F.lambda2[i], 3)}</div><div><b>isolated</b> ${iso.map(short).join(', ') || 'none'}</div>` +
        `<div><b>interruptions</b> ${(ev.connectivity_interruptions || []).length}</div>`;
      iv = (ev.connectivity_interruptions || []).map((x) => `${fmt(x.start, 2)} s → ${x.end == null ? 'end of run' : fmt(x.end, 2) + ' s'}  (${fmt(x.duration, 2)} s)`).join('\n') || 'none';
      cons = `<div><b>heading rms</b> ${fmt(F.heading_rms[i], 3)} rad</div><div><b>speed std</b> ${fmt(F.speed_std[i], 3)} m/s</div>` +
        `<div><b>heading consensus</b> ${F.heading_rms[i] <= 0.25 ? 'yes' : 'no'} (tol 0.25 rad)</div>`;
      stats = `<div><b>form. error</b> ${fmt(F.formation_rms[i], 2)} m</div><div><b>min separation</b> ${fmt(F.min_distance[i], 2)} m</div>` +
        `<div class="muted">packet-level statistics are live-only</div>`;
      $('comm-log').textContent = '(communication log is available in Live view only)';
    }
    $('net-conn').innerHTML = conn; $('net-iv').textContent = iv; $('net-cons').innerHTML = cons; $('net-stats').innerHTML = stats;
  }

  function commLog(st) {
    const ev = st.messages.filter((e) => e.type !== 'POSE_UPDATE').slice(-14);
    const pose = st.messages.filter((e) => e.type === 'POSE_UPDATE');
    const lines = ev.map((e) => {
      const tail = e.status === 'DELAYED' ? `DELAY=${fmt(e.latency, 2)}s` : e.status;
      const cls = e.status === 'LOST' ? 'lost' : e.status === 'DELAYED' ? 'delay' : '';
      return `<span class="${cls}">${fmt(e.t, 2).padStart(7)}  ${esc(e.from).padStart(2)}-&gt;${esc(e.to).padEnd(2)} ${esc(e.type).padEnd(11)} ${esc(tail)}</span>`;
    });
    if (pose.length) {
      const lost = pose.filter((e) => e.status === 'LOST').length;
      lines.push(`-- POSE_UPDATE stream (last ${pose.length}): ${pose.length - lost} ok / ${lost} lost`);
    }
    setLog($('comm-log'), lines.join('\n') || '(no events yet)');
  }

  function renderOperator(st) {
    $('task-list').innerHTML = st.tasks.length ? st.tasks.map((t) =>
      `<li class="st-${esc(t.status)}">Task ${esc(t.id)} (${fmt(t.x, 0)},${fmt(t.y, 0)}) p${t.priority} &rarr; ${t.agent === null ? 'unassigned' : 'Agent ' + t.agent} [${esc(t.status)}]</li>`).join('')
      : '<li class="muted">(no tasks)</li>';
    setLog($('cmd-history'), st.command_history.slice(0, 10).map((h) =>
      `<span class="${h.ok ? '' : 'err'}">[${esc(h.clock)}] ${h.ok ? 'ok ' : 'ERR'} ${esc(h.text)}  ${esc(h.message)}</span>`).join('\n') || '(no commands yet)', false);
    setLog($('status-log'), st.status_log.slice(-8).map((e) => `${fmt(e.t, 1).padStart(6)}  ${esc(e.text)}`).join('\n') || '(none)');
    document.querySelectorAll('#keys kbd[data-k]').forEach((k) => k.classList.toggle('down', st.keyboard[k.dataset.k] === 'PRESSED'));
    $('manual-cmd').textContent = `v_cmd ${fmt(st.manual_command.v, 2)}  w_cmd ${fmt(st.manual_command.omega, 2)}`;
  }
  function setLog(el, html, stick = true) {
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
    el.innerHTML = html; if (stick && atBottom) el.scrollTop = el.scrollHeight;
  }

  // ----------------------------------------------------------------- replay
  function setMode(m) {
    mode = m; rp.playing = false; $('rp-play').textContent = 'Play';
    $('tab-live').classList.toggle('active', m === 'live'); $('tab-replay').classList.toggle('active', m === 'replay');
    $('replay-bar').hidden = m !== 'replay';
    $('live-controls').classList.toggle('dim', m === 'replay');
    $('analysis-sub').textContent = m === 'live' ? 'live rolling window' : 'recorded run (click / drag to seek)';
    $('sel-window').disabled = m === 'replay';
    view.w = 0;
    if (m === 'replay' && !rp.rec) { activatePane('replay'); toast('Load a recording (Replay tab) or use Run & record.', true); }
    updatePanels(); renderPlots(true);
  }
  $('tab-live').addEventListener('click', () => setMode('live'));
  $('tab-replay').addEventListener('click', () => setMode('replay'));

  function setReplayTime(t) { if (!rp.rec) return; rp.i = idxAt(t); syncReplayUI(); }
  function syncReplayUI(keepHead) {
    const T = rp.t;
    if (!keepHead) rp.head = T[rp.i];                 // seeking resets the floating playhead
    $('rp-slider').value = rp.i;
    $('rp-time').textContent = `t = ${fmt(T[rp.i], 2)} / ${fmt(T[T.length - 1], 2)} s`;
    $('chip-time').textContent = `t = ${fmt(T[rp.i], 1)} s`;
    $('chip-ctrl').textContent = rp.rec.meta.control_mode + ' (recorded, seed ' + rp.rec.meta.seed + ')';
    updatePanels(); renderPlots(true);
  }
  function stepPlayback() {
    const now = performance.now(), dt = Math.min((now - rp.wall) / 1000, 0.25); rp.wall = now;
    const T = rp.t; rp.head += dt * rp.speed;         // sub-frame accumulation (frames are 50 ms apart)
    if (rp.head >= T[T.length - 1]) { rp.head = T[T.length - 1]; rp.i = T.length - 1; rp.playing = false; $('rp-play').textContent = 'Play'; }
    else rp.i = idxAt(rp.head);
    syncReplayUI(true);
  }
  $('rp-play').addEventListener('click', () => {
    if (!rp.rec) return toast('No recording loaded.', false);
    if (rp.i >= rp.t.length - 1) rp.i = 0;
    rp.playing = !rp.playing; rp.wall = performance.now(); $('rp-play').textContent = rp.playing ? 'Pause' : 'Play';
  });
  $('rp-back').addEventListener('click', () => { if (rp.rec) { rp.playing = false; rp.i = Math.max(0, rp.i - 1); syncReplayUI(); } });
  $('rp-fwd').addEventListener('click', () => { if (rp.rec) { rp.playing = false; rp.i = Math.min(rp.t.length - 1, rp.i + 1); syncReplayUI(); } });
  $('rp-slider').addEventListener('input', (e) => { if (rp.rec) { rp.playing = false; rp.i = parseInt(e.target.value, 10); syncReplayUI(); } });
  $('rp-speed').addEventListener('change', (e) => { rp.speed = parseFloat(e.target.value); });
  $('rp-maxerr').addEventListener('click', () => { if (rp.summary) setReplayTime(rp.summary.max_error.t); });
  $('rp-minsep').addEventListener('click', () => { if (rp.summary) setReplayTime(rp.summary.min_separation.t); });
  window.addEventListener('keydown', (e) => {                       // replay shortcuts
    if (mode !== 'replay' || !rp.rec || e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    if (e.key === 'ArrowRight') { rp.i = Math.min(rp.t.length - 1, rp.i + 1); syncReplayUI(); e.preventDefault(); }
    if (e.key === 'ArrowLeft') { rp.i = Math.max(0, rp.i - 1); syncReplayUI(); e.preventDefault(); }
    if (e.key === ' ') { $('rp-play').click(); e.preventDefault(); }
  }, true);

  async function refreshList(selectId) {
    const d = await get('/recordings'); const sel = $('rp-list');
    const rows = (d && d.recordings) || [];
    sel.innerHTML = rows.length ? rows.map((r) => `<option value="${esc(r.id)}">${esc(r.id)}</option>`).join('') : '<option value="">(no recordings yet)</option>';
    if (selectId) sel.value = selectId;
  }
  async function loadRecording(id) {
    if (!id) return toast('Choose a recording first.', false);
    const rec = await get('/recordings/' + encodeURIComponent(id));
    if (!rec || rec.format !== 'resilientsync-recording') return toast((rec && rec.message) || 'Could not load recording.', false);
    rp.rec = rec; rp.id = id; rp.t = rec.frames.t; rp.i = 0; rp.playing = false; rp.data = replayData(rec);
    $('rp-slider').max = rp.t.length - 1;
    const m = rec.meta;
    $('rp-meta').textContent = `${id}\ncontroller ${m.control_mode} | seed ${m.seed} | ${m.n_agents} agents | dt ${m.dt} s | stride ${m.stride}\n` +
      `fault ${m.fault_profile.name} | created ${m.created_utc}\nmetrics: RMSE ${fmt(m.metrics.RMSE, 3)} m, peak ${fmt(m.metrics.Peak, 2)} m, min separation ${fmt(m.metrics.MinSep, 2)} m`;
    $('rp-rerun-out').textContent = '';
    const s = await get(`/recordings/${encodeURIComponent(id)}/summary`);
    rp.summary = s && s.max_error ? s : null;
    renderSummary(rp.summary);
    setMode('replay'); setReplayTime(0);
    toast(`Loaded ${id}`, true);
  }
  function renderSummary(s) {
    if (!s) { $('rp-summary').textContent = 'Summary unavailable.'; return; }
    $('rp-summary').innerHTML = s.text.map((l) => `<p>${esc(l)}</p>`).join('') +
      `<p class="muted">time in state (mean over followers): ${Object.entries(s.time_in_state_s).map(([k, v]) => `${k} ${fmt(v, 1)} s`).join(' · ')}</p>`;
    const M = s.milestones || {};
    if (!M.window) { $('rp-milestones').textContent = M.note || 'no finite fault window'; return; }
    const row = (name, o, detail) => `<tr><td>${name}</td><td class="st-m-${esc(o.status)}">${esc(o.status.replace('_', ' '))}</td><td>${detail}</td></tr>`;
    const lag = (o) => o.t != null ? `t = ${fmt(o.t, 2)} s (${fmt(Math.max(0, o.lag_s), 2)} s after fault end)` : '';
    $('rp-milestones').innerHTML = `<div class="muted">fault window ${fmt(M.window[0], 1)} – ${fmt(M.window[1], 1)} s</div><table class="ms">` +
      row('communication restored', M.communication, `${lag(M.communication)} <span class="muted">every follower's message age ≤ 0.3 s</span>`) +
      row('connectivity restored', M.connectivity, lag(M.connectivity)) +
      row('heading consensus', M.consensus, `${M.consensus.t != null ? lag(M.consensus) : ''} <span class="muted">${esc(M.consensus.criterion)}</span>`) +
      row('formation recovered', M.formation, M.formation.recovery_time_s != null ? `recovery time ${fmt(M.formation.recovery_time_s, 2)} s` :
          `<span class="muted">threshold ${fmt(M.formation.threshold_m, 2)} m (baseline ${fmt(M.formation.baseline_m, 2)} m); final error ${fmt(M.formation.final_error_m, 2)} m</span>`) +
      '</table><p class="muted">Recovery time is reported only when the sustained criterion is met.</p>';
  }
  $('rp-load').addEventListener('click', () => loadRecording($('rp-list').value));
  $('rp-refresh').addEventListener('click', () => refreshList());
  $('rp-download').addEventListener('click', () => {
    if (!rp.rec) return toast('No recording loaded.', false);
    download(`${rp.id}.json`, JSON.stringify(rp.rec));
  });
  $('rp-upload').addEventListener('click', () => $('rp-file').click());
  $('rp-file').addEventListener('change', async (e) => {
    const f = e.target.files[0]; e.target.value = ''; if (!f) return;
    if (f.size > 40e6) return toast('File too large (limit 40 MB).', false);
    const r = await api('/recordings/upload', { text: await f.text(), name: f.name.replace(/\.json$/i, '') });
    if (r && r.ok) { await refreshList(r.id); loadRecording(r.id); }
  });
  $('rp-rerun').addEventListener('click', async () => {
    if (!rp.id) return toast('No recording loaded.', false);
    $('rp-rerun-out').textContent = 'rerunning…';
    const r = await api(`/recordings/${encodeURIComponent(rp.id)}/rerun`, {}, 'POST', true);
    $('rp-rerun-out').textContent = r && r.ok
      ? (r.identical ? 'Rerun from the saved seed + configuration reproduced the recording exactly.'
                     : `Rerun DIFFERS from the recording (max state deviation ${r.max_abs_state_deviation ?? 'n/a'} m). The replay shows the saved timeline.`)
      : ((r && r.message) || 'rerun failed');
  });
  function download(name, text) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type: 'application/json' })); a.download = name;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  // ------------------------------------------------------------- experiment
  const num = (id) => parseFloat($(id).value);
  function gatherSpec() {
    return { control_mode: $('x-ctrl').value, seed: parseInt($('x-seed').value, 10), duration: num('x-dur'),
      n_agents: parseInt($('x-n').value, 10), formation: $('x-form').value, loss_scale: num('x-loss'),
      supervisor_enabled: $('x-sup').value === 'true', fault_profile: $('x-prof').value, fault_start: num('x-fstart'),
      fault_duration: num('x-flen'), fault_probability: num('x-fprob'), extra_latency_s: num('x-flat'), jitter_s: num('x-fjit') };
  }
  function fillSpec(s) {
    const set = (id, v) => { if (v !== undefined && v !== null) $(id).value = String(v); };
    set('x-ctrl', s.control_mode); set('x-seed', s.seed); set('x-dur', s.duration); set('x-n', s.n_agents);
    set('x-form', s.formation); set('x-loss', s.loss_scale); set('x-sup', s.supervisor_enabled); set('x-prof', s.fault_profile);
    set('x-fstart', s.fault_start); set('x-flen', s.fault_duration); set('x-fprob', s.fault_probability);
    set('x-flat', s.extra_latency_s); set('x-fjit', s.jitter_s);
  }
  $('x-apply').addEventListener('click', async () => {
    const s = gatherSpec();
    const r = await api('/sim/reset', { seed: s.seed, supervisor_enabled: s.supervisor_enabled, fault_profile: s.fault_profile,
      fault_start: s.fault_start, fault_duration: s.fault_duration, fault_probability: s.fault_probability,
      extra_latency_s: s.extra_latency_s, jitter_s: s.jitter_s, loss_scale: s.loss_scale, control_mode: s.control_mode,
      sim_mode: $('sel-simmode').value, n_agents: s.n_agents, formation: s.formation });
    if (r && r.ok) setMode('live');
  });
  $('btn-reset').addEventListener('click', () => $('x-apply').click());
  let running = false;
  $('x-run').addEventListener('click', async () => {
    if (running) return;
    running = true; const b = $('x-run'); b.disabled = true; b.textContent = 'Running…';
    try {
      const r = await api('/experiments/run', gatherSpec());
      if (r && r.ok) { await refreshList(r.id); await loadRecording(r.id); }
    } finally { running = false; b.disabled = false; b.textContent = 'Run & record'; }
  });
  $('x-save').addEventListener('click', async () => {
    const r = await api('/experiments/config', gatherSpec());
    if (r && r.ok) download(`resilientsync-config-${r.spec.control_mode}-${r.spec.fault_profile}-s${r.spec.seed}.json`,
      JSON.stringify({ format: 'resilientsync-config', version: 1, spec: r.spec }, null, 2));
  });
  $('x-load').addEventListener('click', () => $('x-file').click());
  $('x-file').addEventListener('change', async (e) => {
    const f = e.target.files[0]; e.target.value = ''; if (!f) return;
    try {
      const j = JSON.parse(await f.text()); const spec = j.spec || j;
      fillSpec(spec);
      const r = await api('/experiments/config', gatherSpec());
      if (r && r.ok) toast('Configuration loaded and validated.', true);
    } catch (err) { toast('Not a valid configuration file: ' + err.message, false); }
  });
  $('form-fault').addEventListener('submit', async (e) => {
    e.preventDefault();
    await api('/faults', { profile: $('f-profile').value, start_in: num('f-start'), duration: num('f-dur'),
      probability: num('f-prob'), extra_latency_s: num('x-flat'), jitter_s: num('x-fjit') });
  });
  $('btn-fault-clear').addEventListener('click', () => api('/faults/clear', {}));

  // ---------------------------------------------------------------- benchmark
  async function loadBenchmark() {
    const el = $('bench-body');
    try {
      const d = await (await fetch('/benchmark')).json();
      if (!d.ok) { el.textContent = d.message || 'not available'; return; }
      $('bench-tag').textContent = `(${d.tag}, ${d.seeds.length} matched seeds)`;
      const scs = [...new Set(d.rows.map((r) => r.scenario))];
      const arms = ['pidr', 'advanced', 'adaptive_legacy', 'adaptive_supervisor'];
      let html = '<div>mean formation RMSE [m] / min separation [m]; lowest RMSE in <b>bold</b>. Recovered runs in brackets.</div><table class="bench"><thead><tr><th>scenario</th>' +
        arms.map((a) => `<th>${a}</th>`).join('') + '</tr></thead><tbody>';
      for (const sc of scs) {
        const row = arms.map((a) => d.rows.find((r) => r.scenario === sc && r.arm === a));
        const best = Math.min(...row.filter(Boolean).map((r) => r.RMSE_mean));
        html += `<tr><td>${esc(sc)}</td>` + row.map((r) => r ? `<td>${r.RMSE_mean === best ? '<b>' : ''}${fmt(r.RMSE_mean, 2)} / ${fmt(r.MinSep_mean, 2)}${r.RMSE_mean === best ? '</b>' : ''}` +
          `${r.recovery_applicable_runs ? ` <span class="muted">[${r.recovered_runs}/${r.recovery_applicable_runs}]</span>` : ''}</td>` : '<td>–</td>').join('') + '</tr>';
      }
      const nom = d.rows.find((r) => r.scenario === 'nominal' && r.arm === 'pidr');
      html += '</tbody></table>';
      if (nom && nom.sat_frac_mean != null) html += `<p class="muted">Nominal (no fault) pidr: follower commands sit at the speed limit in ${fmt(100 * nom.sat_frac_mean, 0)} % of ticks (partly noise chatter). Even without faults the default path is hard to track; the <code>*_gentle</code> scenarios are the feasible-tracking control.</p>`;
      el.innerHTML = html;
    } catch (e) { el.textContent = 'not available'; }
  }

  // ---------------------------------------------------------------- transport
  function connect() {
    ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);
    ws.onopen = () => { wsFails = 0; setConn(true); stopPolling(); };
    ws.onmessage = (m) => { try { onState(JSON.parse(m.data)); } catch (e) { console.error(e); } };
    ws.onclose = () => {
      setConn(false); startPolling();
      // without a WebSocket library on the server (uvicorn without `websockets`) polling still works
      if (++wsFails <= 3) setTimeout(connect, 1500 * wsFails);
      else { const c = $('chip-conn'); c.dataset.state = 'up'; c.textContent = 'server connected (polling)'; }
    };
    ws.onerror = () => { try { ws.close(); } catch (e) { /* ignore */ } };
  }
  function setConn(up) { const c = $('chip-conn'); c.dataset.state = up ? 'up' : 'down'; c.textContent = up ? 'server connected' : 'connecting...'; }
  function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(async () => { try { onState(await (await fetch('/state')).json()); } catch (e) { /* server down */ } }, 200);
  }
  function stopPolling() { clearInterval(pollTimer); pollTimer = null; }

  // -------------------------------------------------------------------- input
  const selAgent = () => $('sel-agent').value;
  document.querySelectorAll('button[data-cmd]').forEach((b) => b.addEventListener('click', () => {
    const c = b.dataset.cmd;
    if (c === 'stop' || c === 'resume') api('/' + c, { agent: selAgent() }); else api('/' + c, {});
  }));
  $('sel-simmode').addEventListener('change', (e) => api('/mode', { mode: e.target.value }));
  $('sel-formation').addEventListener('change', (e) => { if (e.target.value) api('/formation/' + e.target.value, {}); e.target.value = ''; });
  $('form-goto').addEventListener('submit', (e) => { e.preventDefault(); api('/goto', { x: parseFloat($('goto-x').value), y: parseFloat($('goto-y').value), agent: selAgent() }); });
  $('form-cmd').addEventListener('submit', (e) => { e.preventDefault(); const t = $('cmd-text').value.trim(); if (t) api('/command', { text: t }); $('cmd-text').value = ''; });
  $('form-task').addEventListener('submit', (e) => {
    e.preventDefault();
    api('/tasks', { id: $('task-id').value.trim(), x: parseFloat($('task-x').value), y: parseFloat($('task-y').value), priority: parseInt($('task-prio').value || '1', 10) });
  });
  $('btn-allocate').addEventListener('click', () => api('/tasks/allocate', {}));
  $('btn-cleartasks').addEventListener('click', () => api('/tasks/clear', {}));
  $('chk-loss').addEventListener('change', (e) => api('/network/loss', { forced: e.target.checked }));
  $('btn-pause').addEventListener('click', () => api('/sim/pause', { paused: !(state && state.runner.paused) }));
  $('sel-speed').addEventListener('change', (e) => api('/sim/speed', { speed: parseFloat(e.target.value) }));
  $('sel-window').addEventListener('change', (e) => { winSec = parseInt(e.target.value, 10); renderPlots(true); });
  $('sel-trail').addEventListener('change', (e) => { trailSec = parseFloat(e.target.value); });
  $('chk-legend').addEventListener('change', (e) => { $('legend').hidden = !e.target.checked; });
  if (window.innerWidth < 700) { $('chk-legend').checked = false; $('legend').hidden = true; }
  document.querySelectorAll('#layers input[data-layer]').forEach((c) => c.addEventListener('change', () => { layers[c.dataset.layer] = c.checked; }));

  canvas.addEventListener('pointerdown', (e) => {                      // click arena -> GOTO (live only)
    if (mode !== 'live' || !state || e.button !== 0 || !view.w) return;
    const r = canvas.getBoundingClientRect();
    const [x, y] = RS.viewport.toWorld(view, (e.clientX - r.left) * (canvas.width / r.width), (e.clientY - r.top) * (canvas.height / r.height));
    api('/goto', { x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100, agent: selAgent() });
  });

  const typing = (t) => t && (t.tagName === 'INPUT' || t.tagName === 'SELECT' || t.tagName === 'TEXTAREA');
  window.addEventListener('keydown', (e) => {
    if (mode !== 'live' || typing(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
    const k = KEY_MAP[e.key.toLowerCase()]; if (!k) return;
    e.preventDefault();
    if (e.repeat && ONE_SHOT.has(k)) return;
    if (!held.has(k) || ONE_SHOT.has(k)) api('/key', { key: k === 'SPACE' ? ' ' : k.toLowerCase(), down: true }, 'POST', true);
    held.add(k);
  });
  window.addEventListener('keyup', (e) => {
    if (typing(e.target)) return;
    const k = KEY_MAP[e.key.toLowerCase()]; if (!k || !held.has(k)) return;
    e.preventDefault(); held.delete(k); api('/key', { key: k === 'SPACE' ? ' ' : k.toLowerCase(), down: false }, 'POST', true);
  });
  window.addEventListener('blur', () => { for (const k of held) api('/key', { key: k === 'SPACE' ? ' ' : k.toLowerCase(), down: false }, 'POST', true); held.clear(); });
  window.addEventListener('resize', () => { view.w = 0; renderPlots(true); });

  // ------------------------------------------------------------------- tabs
  function activatePane(name) {
    document.querySelectorAll('#side-tabs button').forEach((b) => b.classList.toggle('active', b.dataset.pane === name));
    document.querySelectorAll('.pane').forEach((p) => { p.hidden = p.id !== 'pane-' + name; });
  }
  document.querySelectorAll('#side-tabs button').forEach((b) => b.addEventListener('click', () => activatePane(b.dataset.pane)));

  // ---------------------------------------------------------------------- go
  buildLegend(); refreshList(); loadBenchmark();
  setInterval(() => { if (mode === 'live') renderPlots(false); }, 250);
  startPolling(); connect(); requestAnimationFrame(draw);
})();
