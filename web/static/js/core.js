/* ResilientSync front-end core: shared helpers, constants and API wrapper.
 * Everything displayed comes from the server (live state or a saved recording);
 * nothing in the browser simulates robots. */
window.RS = (() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = (v, d = 1) => (v === null || v === undefined || Number.isNaN(v) || !Number.isFinite(Number(v)))
    ? '–' : (Number(v) + 0).toFixed(d);
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  // Semantic palette (kept in sync with style.css tokens by name)
  const COLORS = {
    leader: '#c2410c',
    followers: ['#2563eb', '#0f766e', '#7c3aed', '#b45309', '#0891b2', '#9d174d', '#4d7c0f', '#475569'],
    ok: '#2e8b57', stale: '#c98a00', lost: '#c0392b', info: '#2c7fb8',
  };
  const SUP_NAMES = ['NORMAL', 'DEGRADED', 'HOLD', 'RECOVERING'];        // code -> name (supervisor.py)
  const SUP_COLORS = { NORMAL: '#2e8b57', DEGRADED: '#c98a00', HOLD: '#c0392b', RECOVERING: '#2c7fb8' };
  const AGE_FRESH = 0.30, AGE_LOST = 1.00;                              // link colouring thresholds [s]
  const colorOf = (id) => id === 0 ? COLORS.leader : COLORS.followers[(id - 1) % COLORS.followers.length];
  const short = (id) => id === 0 ? 'L' : 'F' + id;
  const linkClass = (age, up) => (up === false || age > AGE_LOST) ? 'lost' : (age > AGE_FRESH ? 'stale' : 'ok');

  let toastTimer = null;
  function toast(msg, ok = true) {
    const el = $('feedback');
    el.textContent = msg;
    el.className = 'feedback ' + (ok ? 'ok' : 'err');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.textContent = ''; }, 8000);
  }

  async function api(path, body, method = 'POST', quiet = false) {
    try {
      const res = await fetch(path, {
        method, headers: { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body) });
      const data = await res.json().catch(() => ({ ok: false, message: `HTTP ${res.status}` }));
      if (!quiet) {
        if (data && data.message !== undefined) toast(data.message, !!data.ok);
        else if (data && Array.isArray(data.detail) && data.detail.length) {
          const d = data.detail[0], field = (d.loc || []).slice(1).join('.');
          toast(`INVALID INPUT${field ? ' (' + field + ')' : ''}: ${d.msg}`, false);
        } else if (!res.ok) toast(`HTTP ${res.status}`, false);
      }
      if (!res.ok && data && data.ok === undefined) data.ok = false;
      return data;
    } catch (e) {
      toast('Server unreachable: ' + e.message, false);
      return { ok: false };
    }
  }
  const get = (path) => api(path, undefined, 'GET', true);

  // world -> body-frame offset -> world (same convention as simulation.kinematics.body_to_world)
  const bodyToWorld = (off, pose) => {
    const c = Math.cos(pose.th), s = Math.sin(pose.th);
    return [pose.x + off[0] * c - off[1] * s, pose.y + off[0] * s + off[1] * c];
  };
  return { $, esc, fmt, css, COLORS, SUP_NAMES, SUP_COLORS, AGE_FRESH, AGE_LOST, colorOf, short,
           linkClass, toast, api, get, bodyToWorld };
})();
