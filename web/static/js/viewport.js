/* Simulation arena renderer.
 *
 * draw(ctx, view, scene, layers) paints ONE scene.  A scene is built either from the live
 * server state or from a recorded frame, so both go through the same code:
 *
 * scene = { t, world:{x_min,x_max,y_min,y_max,margin}, agents:[{id,x,y,th,mode,stopped,sup,age,up,tx,ty}],
 *           offsets:[[dx,dy]...] (body frame), trails:{id:[[x,y]...]}, isolated:[ids],
 *           faultActive:bool, markers:[{kind,x,y,label}], closest:{pair,distance,midpoint,t,collision},
 *           collisionDistance }
 * Everything is in metres; +x right, +y up.
 */
RS.viewport = (() => {
  'use strict';
  const { css, COLORS, SUP_COLORS, SUP_NAMES, colorOf, short, linkClass, bodyToWorld } = RS;
  const PAD = 1.0;                                          // metres around the world rectangle
  const LINK = { ok: COLORS.ok, stale: COLORS.stale, lost: COLORS.lost };

  function layout(canvas, world) {
    const wm = world.x_max - world.x_min + 2 * PAD, hm = world.y_max - world.y_min + 2 * PAD;
    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.parentElement.clientWidth;
    const cssH = cssW * hm / wm;
    canvas.style.height = cssH + 'px';
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    return { s: canvas.width / wm, ox: world.x_min - PAD, oy: world.y_max + PAD,
             w: canvas.width, h: canvas.height, dpr, key: `${cssW}|${world.x_max}|${world.y_max}` };
  }

  function draw(ctx, v, sc, L) {
    const W = sc.world, s = v.s, d = v.dpr;
    const px = (x, y) => [(x - v.ox) * s, (v.oy - y) * s];
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, v.w, v.h);
    ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
    const text = css('--text'), muted = css('--muted'), border = css('--panel-border');

    // ---- grid (1 m minor, 5 m major) + axes with units --------------------
    ctx.lineWidth = d;
    for (let x = Math.ceil(W.x_min - PAD); x <= W.x_max + PAD; x++) {
      const [X] = px(x, 0); ctx.strokeStyle = border; ctx.globalAlpha = x % 5 === 0 ? 0.9 : 0.35;
      ctx.beginPath(); ctx.moveTo(X, 0); ctx.lineTo(X, v.h); ctx.stroke();
    }
    for (let y = Math.ceil(W.y_min - PAD); y <= W.y_max + PAD; y++) {
      const [, Y] = px(0, y); ctx.strokeStyle = border; ctx.globalAlpha = y % 5 === 0 ? 0.9 : 0.35;
      ctx.beginPath(); ctx.moveTo(0, Y); ctx.lineTo(v.w, Y); ctx.stroke();
    }
    ctx.globalAlpha = 1; ctx.fillStyle = muted; ctx.font = `${10.5 * d}px ui-monospace, Menlo, Consolas, monospace`;
    for (let x = Math.ceil((W.x_min - PAD) / 5) * 5; x <= W.x_max + PAD; x += 5) {
      const [X] = px(x, 0); ctx.fillText(String(x), X + 3 * d, v.h - 4 * d);
    }
    for (let y = Math.ceil((W.y_min - PAD) / 5) * 5; y <= W.y_max + PAD; y += 5) {
      const [, Y] = px(0, y); ctx.fillText(String(y), 3 * d, Y - 3 * d);
    }
    ctx.fillText('x [m]', v.w - 40 * d, v.h - 16 * d); ctx.fillText('y [m]', 20 * d, 12 * d);

    // ---- world boundary + soft-guard zone -----------------------------------
    const [bx0, by0] = px(W.x_min, W.y_max), [bx1, by1] = px(W.x_max, W.y_min);
    ctx.strokeStyle = text; ctx.lineWidth = 1.6 * d; ctx.strokeRect(bx0, by0, bx1 - bx0, by1 - by0);
    if (W.margin) {
      const m = W.margin * s; ctx.setLineDash([6 * d, 5 * d]); ctx.lineWidth = d; ctx.strokeStyle = muted;
      ctx.strokeRect(bx0 + m, by0 + m, bx1 - bx0 - 2 * m, by1 - by0 - 2 * m); ctx.setLineDash([]);
    }
    if (sc.faultActive) {                                   // red frame while a fault is injected
      ctx.strokeStyle = COLORS.lost; ctx.lineWidth = 4 * d; ctx.strokeRect(2 * d, 2 * d, v.w - 4 * d, v.h - 4 * d);
    }

    const A = sc.agents, lead = A[0];
    const trueSlot = (a) => sc.offsets && sc.offsets[a.id] ? bodyToWorld(sc.offsets[a.id], { x: lead.x, y: lead.y, th: lead.th }) : null;

    // ---- trails ------------------------------------------------------------------
    if (L.trails) {
      ctx.lineWidth = 1.4 * d; ctx.globalAlpha = 0.5;
      for (const a of A) {
        const tr = sc.trails[a.id]; if (!tr || tr.length < 2) continue;
        ctx.strokeStyle = colorOf(a.id); ctx.beginPath();
        tr.forEach(([x, y], i) => { const [X, Y] = px(x, y); i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); });
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    // ---- desired formation geometry (true slots from the actual leader pose) ---
    if (L.skeleton && sc.offsets) {
      const slots = A.map((a) => a.id === 0 ? [lead.x, lead.y] : trueSlot(a));
      ctx.strokeStyle = muted; ctx.lineWidth = d; ctx.setLineDash([3 * d, 4 * d]); ctx.globalAlpha = 0.8;
      for (const a of A) {
        if (a.id === 0 || !slots[a.id]) continue;
        // parent = nearest slot (to the leader) that is closer to the leader than this one
        const dl = (p) => Math.hypot(p[0] - lead.x, p[1] - lead.y);
        let best = 0, bd = Infinity;
        for (const b of A) {
          if (b.id === a.id || !slots[b.id] || dl(slots[b.id]) >= dl(slots[a.id]) - 1e-6) continue;
          const dd = Math.hypot(slots[b.id][0] - slots[a.id][0], slots[b.id][1] - slots[a.id][1]);
          if (dd < bd) { bd = dd; best = b.id; }
        }
        const [x0, y0] = px(...slots[best]), [x1, y1] = px(...slots[a.id]);
        ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
      }
      ctx.setLineDash([]); ctx.globalAlpha = 1;
    }
    if (L.slots && sc.offsets) {
      ctx.lineWidth = 1.4 * d;
      for (const a of A) {
        if (a.id === 0) continue; const p = trueSlot(a); if (!p) continue;
        const [X, Y] = px(...p); ctx.strokeStyle = colorOf(a.id); ctx.setLineDash([4 * d, 3 * d]);
        ctx.beginPath(); ctx.arc(X, Y, 0.3 * s, 0, 7); ctx.stroke(); ctx.setLineDash([]);
      }
    }
    // tracking error vector: robot -> its desired slot (colour by magnitude)
    if (L.errvec && sc.offsets) {
      ctx.lineWidth = 1.3 * d;
      for (const a of A) {
        if (a.id === 0) continue; const p = trueSlot(a); if (!p) continue;
        const e = Math.hypot(p[0] - a.x, p[1] - a.y);
        ctx.strokeStyle = e > 1.5 ? COLORS.lost : e > 0.5 ? COLORS.stale : COLORS.ok; ctx.globalAlpha = 0.85;
        const [x0, y0] = px(a.x, a.y), [x1, y1] = px(...p);
        ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }
    // what each follower's controller is actually chasing (dead-reckoned estimate)
    if (L.target) {
      for (const a of A) {
        if (a.id === 0 || a.tx == null) continue;
        const [X, Y] = px(a.tx, a.ty), r = 0.14 * s;
        ctx.fillStyle = colorOf(a.id); ctx.beginPath();
        ctx.moveTo(X, Y - r); ctx.lineTo(X + r, Y); ctx.lineTo(X, Y + r); ctx.lineTo(X - r, Y); ctx.closePath(); ctx.fill();
      }
    }

    // ---- communication links (leader -> follower), real state ----------------------
    if (L.links) {
      for (const a of A) {
        if (a.id === 0) continue;
        const k = linkClass(a.age, a.up);
        const [x0, y0] = px(lead.x, lead.y), [x1, y1] = px(a.x, a.y);
        ctx.strokeStyle = LINK[k]; ctx.lineWidth = (k === 'ok' ? 1.8 : 1.6) * d;
        ctx.setLineDash(k === 'ok' ? [] : k === 'stale' ? [8 * d, 5 * d] : [2 * d, 5 * d]);
        ctx.globalAlpha = k === 'ok' ? 0.5 : 0.9;
        ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
        if (k === 'lost') {                                   // break mark at the midpoint
          const mx = (x0 + x1) / 2, my = (y0 + y1) / 2, r = 5 * d;
          ctx.setLineDash([]); ctx.lineWidth = 2 * d; ctx.beginPath();
          ctx.moveTo(mx - r, my - r); ctx.lineTo(mx + r, my + r); ctx.moveTo(mx - r, my + r); ctx.lineTo(mx + r, my - r); ctx.stroke();
        }
      }
      ctx.setLineDash([]); ctx.globalAlpha = 1;
    }

    // ---- current closest pair ---------------------------------------------------------
    if (L.sep && A.length > 2) {
      let bi = -1, bj = -1, bd = Infinity;
      for (let i = 0; i < A.length; i++) for (let j = i + 1; j < A.length; j++) {
        const dd = Math.hypot(A[i].x - A[j].x, A[i].y - A[j].y); if (dd < bd) { bd = dd; bi = i; bj = j; }
      }
      if (bi >= 0) {
        const [x0, y0] = px(A[bi].x, A[bi].y), [x1, y1] = px(A[bj].x, A[bj].y);
        const hot = bd < (sc.collisionDistance || 0.38);
        ctx.strokeStyle = hot ? COLORS.lost : muted; ctx.lineWidth = d; ctx.setLineDash([2 * d, 3 * d]);
        ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillStyle = hot ? COLORS.lost : muted; ctx.font = `${10 * d}px ui-monospace, Menlo, Consolas, monospace`;
        ctx.fillText(`${bd.toFixed(2)} m`, (x0 + x1) / 2 + 4 * d, (y0 + y1) / 2 - 3 * d);
      }
    }

    // ---- event markers: fault start/end, closest approach ----------------------------------
    if (L.markers) {
      ctx.font = `${10 * d}px ui-monospace, Menlo, Consolas, monospace`;
      for (const m of sc.markers || []) {
        const [X, Y] = px(m.x, m.y), r = 6 * d;
        ctx.fillStyle = m.kind === 'fault_end' ? COLORS.ok : COLORS.lost; ctx.strokeStyle = '#fff'; ctx.lineWidth = d;
        ctx.beginPath(); ctx.moveTo(X, Y - r); ctx.lineTo(X + r, Y); ctx.lineTo(X, Y + r); ctx.lineTo(X - r, Y); ctx.closePath();
        ctx.fill(); ctx.stroke(); ctx.fillStyle = text; ctx.fillText(m.label, X + 8 * d, Y - 6 * d);
      }
      const c = sc.closest;
      if (c && c.midpoint && c.distance != null) {
        const [X, Y] = px(c.midpoint[0], c.midpoint[1]), r = 7 * d, hot = !!c.collision;
        ctx.strokeStyle = hot ? COLORS.lost : COLORS.info; ctx.lineWidth = 2 * d;
        ctx.beginPath(); ctx.arc(X, Y, r, 0, 7); ctx.moveTo(X - r, Y); ctx.lineTo(X + r, Y); ctx.moveTo(X, Y - r); ctx.lineTo(X, Y + r); ctx.stroke();
        ctx.fillStyle = text;
        ctx.fillText(`${hot ? 'COLLISION' : 'closest approach'} ${c.distance.toFixed(2)} m @ ${c.t.toFixed(1)} s`, X + 10 * d, Y + 14 * d);
      }
    }

    // ---- partitions: isolated agents ---------------------------------------------------------
    for (const id of sc.isolated || []) {
      const a = A[id]; if (!a) continue; const [X, Y] = px(a.x, a.y);
      ctx.strokeStyle = COLORS.lost; ctx.lineWidth = 1.6 * d; ctx.setLineDash([5 * d, 4 * d]);
      ctx.beginPath(); ctx.arc(X, Y, 0.62 * s, 0, 7); ctx.stroke(); ctx.setLineDash([]);
    }

    // ---- robots (true pose and heading) -------------------------------------------------------
    ctx.font = `600 ${11 * d}px system-ui, sans-serif`; ctx.textAlign = 'center';
    for (const a of A) {
      const [X, Y] = px(a.x, a.y), c = Math.cos(a.th), sn = Math.sin(a.th);
      if (a.sup && a.sup !== 'NORMAL') {                       // supervisor state ring
        ctx.strokeStyle = SUP_COLORS[a.sup]; ctx.lineWidth = 2.4 * d;
        ctx.beginPath(); ctx.arc(X, Y, 0.5 * s, 0, 7); ctx.stroke();
      }
      ctx.beginPath();
      [[0.50, 0], [-0.34, 0.30], [-0.20, 0], [-0.34, -0.30]].forEach(([u, w], i) => {
        const wx = u * c - w * sn, wy = u * sn + w * c;
        i ? ctx.lineTo(X + wx * s, Y - wy * s) : ctx.moveTo(X + wx * s, Y - wy * s);
      });
      ctx.closePath(); ctx.fillStyle = colorOf(a.id); ctx.fill();
      ctx.strokeStyle = a.stopped ? COLORS.lost : '#111'; ctx.lineWidth = (a.stopped ? 2.4 : 1) * d; ctx.stroke();
      if (L.labels) { ctx.fillStyle = text; ctx.fillText(short(a.id), X, Y - 0.62 * s); }
    }
    ctx.textAlign = 'start';

    // ---- scale bar -----------------------------------------------------------------------------
    const bx = v.w - 14 * d - 2 * s, by = v.h - 26 * d;
    ctx.strokeStyle = text; ctx.lineWidth = 2 * d; ctx.beginPath();
    ctx.moveTo(bx, by); ctx.lineTo(bx + 2 * s, by); ctx.moveTo(bx, by - 3 * d); ctx.lineTo(bx, by + 3 * d);
    ctx.moveTo(bx + 2 * s, by - 3 * d); ctx.lineTo(bx + 2 * s, by + 3 * d); ctx.stroke();
    ctx.fillStyle = text; ctx.font = `${10 * d}px ui-monospace, Menlo, Consolas, monospace`; ctx.fillText('2 m', bx + s - 8 * d, by - 6 * d);
  }

  const toWorld = (v, X, Y) => [X / v.s + v.ox, v.oy - Y / v.s];
  return { layout, draw, toWorld };
})();
