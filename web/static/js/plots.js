/* Synchronised analysis plots (plain canvas).  All panels share the same time axis and left
 * padding, so a vertical cursor lines up across them.  Fault intervals are shaded on every panel. */
RS.plots = (() => {
  'use strict';
  const { css, fmt, COLORS, SUP_COLORS, SUP_NAMES } = RS;
  const PADL = 52, PADR = 46, PADT = 18, PADB = 6;
  const MONO = 'ui-monospace, Menlo, Consolas, monospace';

  // Backing-store limit: browsers silently blank (or refuse to create) canvases beyond ~16k px / ~268 Mpx.
  const MAX_SIDE = 8192;

  /* Size a plot canvas.  The *logical* (CSS) height is read ONCE from the markup's height attribute and
   * stored in data-h; it is never re-derived from canvas.height.  (Setting canvas.height rewrites the
   * `height` attribute, so the previous implementation re-read its own device-pixel output as the next
   * logical height and multiplied it by devicePixelRatio on every redraw whenever dpr != 1: the panel grew
   * geometrically, then the oversized canvas went blank.  See docs/ROLLING_WINDOW_UI_FIX.md.)
   * The CSS height is also set explicitly so layout never depends on the canvas's intrinsic aspect ratio. */
  function prep(canvas) {
    if (!canvas.dataset.h) {
      const h0 = parseInt(canvas.getAttribute('height'), 10);
      canvas.dataset.h = String(Number.isFinite(h0) && h0 > 0 ? h0 : 100);
    }
    const H = parseInt(canvas.dataset.h, 10);
    canvas.style.height = H + 'px';
    const W = canvas.clientWidth;
    const dpr = Math.min(window.devicePixelRatio || 1, 4);
    const bw = Math.min(MAX_SIDE, Math.max(1, Math.round(W * dpr))), bh = Math.min(MAX_SIDE, Math.round(H * dpr));
    if (canvas.width !== bw || canvas.height !== bh) { canvas.width = bw; canvas.height = bh; }
    const g = canvas.getContext('2d');
    g.setTransform(bw / Math.max(W, 1), 0, 0, bh / H, 0, 0); g.clearRect(0, 0, W, H);
    return { g, W, H };
  }
  const niceMax = (v) => {
    if (!(v > 0)) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v))), f = v / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  };
  const niceStep = (span) => { const raw = span / 6, p = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p; };
  const bandColor = (k) => k === 'blackout' ? 'rgba(192,57,43,.16)' : 'rgba(201,138,0,.16)';

  function frame(g, W, H, spec, last) {
    const x0 = PADL, x1 = W - (spec.rightAxis ? PADR : 10), y0 = PADT, y1 = H - PADB - (last ? 14 : 0);
    const X = (t) => x0 + (t - spec.t0) / Math.max(spec.t1 - spec.t0, 1e-9) * (x1 - x0);
    for (const e of spec.faults || []) {                       // fault bands
      const a = Math.max(e.start, spec.t0), b = Math.min(e.end == null ? spec.t1 : e.end, spec.t1);
      if (b > a) { g.fillStyle = bandColor(e.kind); g.fillRect(X(a), y0, X(b) - X(a), y1 - y0); }
    }
    g.strokeStyle = css('--panel-border'); g.lineWidth = 1; g.fillStyle = css('--muted'); g.font = `10px ${MONO}`;
    const st = niceStep(spec.t1 - spec.t0);                    // vertical time grid
    for (let t = Math.ceil(spec.t0 / st) * st; t <= spec.t1 + 1e-9; t += st) {
      g.globalAlpha = .6; g.beginPath(); g.moveTo(X(t), y0); g.lineTo(X(t), y1); g.stroke(); g.globalAlpha = 1;
      if (last) g.fillText(fmt(t, st < 1 ? 1 : 0), X(t) - 8, H - 2);
    }
    if (last) g.fillText('time [s]', x1 - 44, H - 2);
    g.strokeStyle = css('--muted'); g.beginPath(); g.moveTo(x0, y0); g.lineTo(x0, y1); g.lineTo(x1, y1); g.stroke();
    return { x0, x1, y0, y1, X };
  }

  function title(g, spec, W) {
    g.fillStyle = css('--text'); g.font = `600 11px system-ui, sans-serif`; g.textAlign = 'left';
    const head = spec.title + (spec.unit ? ` [${spec.unit}]` : '') + (spec.unitR ? `  (right axis: ${spec.unitR})` : '');
    g.fillText(head, PADL, 12);
    let x = PADL + g.measureText(head).width + 12;
    g.font = `10.5px ${MONO}`;
    for (const s of spec.series || []) {
      g.fillStyle = s.color; g.fillRect(x, 5, 9, 3); x += 12;
      let lab = s.label;
      if (spec.cursor != null && s.t) {
        const v = valueAt(s, spec.cursor); if (v != null) lab += ' ' + fmt(v, s.dec ?? 2);
      }
      g.fillStyle = css('--text'); g.fillText(lab, x, 12); x += g.measureText(lab).width + 12;
    }
  }
  function valueAt(s, t) {
    const ts = s.t; if (!ts || !ts.length || t < ts[0] - 1e-9 || t > ts[ts.length - 1] + 1e-9) return null;
    let lo = 0, hi = ts.length - 1;
    while (lo < hi) { const m = (lo + hi) >> 1; if (ts[m] < t) lo = m + 1; else hi = m; }
    if (lo > 0 && t - ts[lo - 1] < ts[lo] - t) lo--;
    return s.y[lo];
  }

  function line(canvas, spec) {
    const { g, W, H } = prep(canvas);
    const f = frame(g, W, H, spec, spec.last);
    const sides = { l: [], r: [] };
    for (const s of spec.series) (s.axis === 'r' ? sides.r : sides.l).push(s);
    const rng = (arr, fixedMax, fixedMin) => {
      let mx = fixedMax ?? 0;
      if (fixedMax == null) for (const s of arr) for (let i = 0; i < s.t.length; i++) {
        if (s.t[i] >= spec.t0 && s.t[i] <= spec.t1 && Number.isFinite(s.y[i])) mx = Math.max(mx, s.y[i]);
      }
      for (const h of spec.hlines || []) if (arr === sides.l && fixedMax == null) mx = Math.max(mx, h.y * 1.05);
      return [fixedMin ?? 0, fixedMax ?? niceMax(mx * 1.08)];
    };
    const [lmin, lmax] = rng(sides.l, spec.yMax, spec.yMin);
    const [rmin, rmax] = rng(sides.r, spec.yMaxR, 0);
    const Y = (v, r) => { const [a, b] = r ? [rmin, rmax] : [lmin, lmax]; return f.y1 - (v - a) / (b - a || 1) * (f.y1 - f.y0); };
    g.fillStyle = css('--muted'); g.font = `10px ${MONO}`; g.textAlign = 'right';
    for (const fr of [0, .5, 1]) {
      g.fillText(fmt(lmin + (lmax - lmin) * fr, lmax < 5 ? 2 : 0), f.x0 - 4, Y(lmin + (lmax - lmin) * fr) + 3);
      if (sides.r.length) { g.textAlign = 'left'; g.fillText(fmt(rmin + (rmax - rmin) * fr, rmax < 5 ? 2 : 0), f.x1 + 4, Y(rmin + (rmax - rmin) * fr, true) + 3); g.textAlign = 'right'; }
    }
    for (const h of spec.hlines || []) {
      g.strokeStyle = h.color || css('--muted'); g.setLineDash([4, 3]); g.lineWidth = 1;
      g.beginPath(); g.moveTo(f.x0, Y(h.y)); g.lineTo(f.x1, Y(h.y)); g.stroke(); g.setLineDash([]);
      g.fillStyle = h.color || css('--muted'); g.fillText(h.label, f.x1 - g.measureText(h.label).width - 4, Y(h.y) - 3);
    }
    g.save(); g.beginPath(); g.rect(f.x0, f.y0 - 2, f.x1 - f.x0, f.y1 - f.y0 + 4); g.clip();
    for (const s of spec.series) {
      g.strokeStyle = s.color; g.lineWidth = s.w || 1.5; g.beginPath(); let started = false, prevY = 0;
      for (let i = 0; i < s.t.length; i++) {
        if (s.t[i] < spec.t0 - 1 || s.t[i] > spec.t1 + 1 || !Number.isFinite(s.y[i])) continue;
        const x = f.X(s.t[i]), y = Y(s.y[i], s.axis === 'r');
        if (!started) { g.moveTo(x, y); started = true; } else if (s.step) { g.lineTo(x, prevY); g.lineTo(x, y); } else g.lineTo(x, y);
        prevY = y;
      }
      g.stroke();
    }
    g.restore();
    for (const m of spec.markers || []) {                       // e.g. peak error / minimum separation
      if (m.t < spec.t0 || m.t > spec.t1) continue;
      g.fillStyle = m.color || COLORS.lost; g.beginPath(); g.arc(f.X(m.t), Y(m.y), 3.5, 0, 7); g.fill();
      g.fillStyle = css('--text'); g.textAlign = m.t > (spec.t0 + spec.t1) / 2 ? 'right' : 'left';
      g.fillText(m.label, f.X(m.t) + (g.textAlign === 'right' ? -6 : 6), Math.max(f.y0 + 10, Y(m.y) - 5)); g.textAlign = 'left';
    }
    cursor(g, f, spec);
    title(g, spec, W);
    return f;
  }

  function strip(canvas, spec) {
    const { g, W, H } = prep(canvas);
    const f = frame(g, W, H, spec, false);
    const rows = spec.rows, rh = (f.y1 - f.y0) / Math.max(rows.length, 1);
    g.font = `10px ${MONO}`; g.textAlign = 'right';
    rows.forEach((r, k) => {
      const yy = f.y0 + k * rh;
      g.fillStyle = css('--muted'); g.fillText(r.label, f.x0 - 4, yy + rh / 2 + 3);
      for (let i = 0; i < r.t.length - 1; i++) {
        if (r.t[i + 1] < spec.t0 || r.t[i] > spec.t1) continue;
        g.fillStyle = SUP_COLORS[SUP_NAMES[r.s[i]]] || '#999';
        const a = Math.max(f.X(r.t[i]), f.x0), b = Math.min(f.X(r.t[i + 1]), f.x1);
        g.fillRect(a, yy + 1, Math.max(1, b - a + 0.6), rh - 2);
      }
    });
    g.textAlign = 'left'; g.fillStyle = css('--text'); g.font = '600 11px system-ui, sans-serif';
    g.fillText(spec.title, PADL, 12);
    let x = PADL + g.measureText(spec.title).width + 12; g.font = `10.5px ${MONO}`;
    for (const n of SUP_NAMES) { g.fillStyle = SUP_COLORS[n]; g.fillRect(x, 5, 9, 6); x += 12; g.fillStyle = css('--text'); g.fillText(n, x, 12); x += g.measureText(n).width + 10; }
    cursor(g, f, spec);
    return f;
  }

  function cursor(g, f, spec) {
    if (spec.cursor == null || spec.cursor < spec.t0 || spec.cursor > spec.t1) return;
    g.strokeStyle = css('--text'); g.lineWidth = 1; g.setLineDash([]);
    g.beginPath(); g.moveTo(f.X(spec.cursor), f.y0); g.lineTo(f.X(spec.cursor), f.y1); g.stroke();
  }

  const xToT = (canvas, clientX, t0, t1, rightAxis) => {
    const r = canvas.getBoundingClientRect(), x0 = PADL, x1 = r.width - (rightAxis ? PADR : 10);
    return Math.min(t1, Math.max(t0, t0 + (clientX - r.left - x0) / (x1 - x0) * (t1 - t0)));
  };
  return { line, strip, xToT };
})();
