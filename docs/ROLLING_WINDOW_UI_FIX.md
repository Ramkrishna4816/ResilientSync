# Rolling-window (Analysis) panel: expansion and blanking defect

Status: **root cause confirmed and fixed at the component level; full-dashboard verification against the real FastAPI backend is NOT done** (see "Verification limits").

## Symptom
The "Analysis / live rolling window" panel appears correctly, then grows without bound, then renders blank white, and may repeat.

## Root cause (confirmed)
`web/static/js/plots.js::prep()` took the logical canvas height from `canvas.getAttribute('height')`, then wrote
`canvas.height = round(H * devicePixelRatio)`. Assigning `canvas.height` **rewrites the `height` content attribute**, so on the next redraw
the function read its own device-pixel output as the logical height and multiplied it by `devicePixelRatio` again.
The stylesheet gives plot canvases `width:100%` and no CSS height, so the displayed height follows the canvas's intrinsic aspect ratio, and the page layout grew with it.

* `devicePixelRatio == 1`: factor 1, no growth. This is why it did not appear in the author's headless Chromium on Linux (DPR 1).
* `devicePixelRatio != 1` (Windows display scaling of 125/150/200 %, HiDPI, browser zoom): geometric growth by that factor per redraw.
  `renderPlots` runs every 250 ms in live mode (`setInterval`, app.js) and on every state update, so growth is visible within seconds.
  When the backing store exceeds the browser's maximum canvas size the canvas stops rendering, which gives the blank white area.

The feedback loop is between the canvas's own attribute and its own sizing code; it is independent of the backend, the data volume and the window setting.

### Evidence (`docs/evidence/repro_dpr_growth.py`, real `style.css`/`core.js`/`plots.js`, Chromium via Playwright, 14 redraws)
| DPR | `pl-err` height attr, frame 0 -> 13 | whole panel height, frame 0 -> 13 |
|---|---|---|
| 1 | 120 -> 120 | 729 -> 729 px |
| 1.25 | 150 -> 2,744 | 729 -> 12,880 px |
| 1.5 | 180 -> 35,064 | 729 -> 137,814 px |
| 2 | 240 -> 1,966,080 | 729 -> 5,783,575 px |

Raw numbers: `docs/evidence/repro_dpr_growth.json`. After the fix: 722/729 px (see below) constant at DPR 1, 1.25, 1.5, 2, 3.
Original code in the regression harness at DPR 1.25: 729 px -> 149,695 px after 24 redraws.

### Hypotheses checked
* Unbounded data history (6): ruled out by code reading; `live.hist` is capped by `HIST_MAX` (app.js:174). Not observed at runtime.
* Repeated chart init / duplicate timers (3, 5, 11): only code reading; `renderPlots` is a plain redraw on persistent canvases, one `setInterval`, one `resize` listener. No leak found in code. Not observed at runtime.
* Resize-observer loop (1): no ResizeObserver in the code; the `resize` handler only redraws.
* Non-finite values (8): `plots.js` already skips non-finite points; covered by tests below.
* `viewport.js` (arena canvas): sets an explicit CSS height; not affected.

## Files changed
* `web/static/js/plots.js`: `prep()` stores the logical height once in `data-h`, sets `style.height` explicitly, clamps the backing store to 8192 px per side and DPR to 4.
* `web/templates/index.html`: `data-h` added to the 7 plot canvases (logical height is in the markup, never read back from the canvas).
* `web/static/style.css`: `canvas.plot` gets `max-width:100%; box-sizing:content-box` (keeps the original visual height).
* `tests/test_plot_canvas_stability.py` (new), `docs/evidence/repro_dpr_growth.{py,json}` (new).

## Regression tests and actual outcomes
10 parametrised cases (live updates x DPR {1,1.25,1.5,2,3}; empty/NaN/Infinity/null/out-of-order data and 30/60/120 s window changes x DPR {1,1.5,2}; hide/show, remount, clone and viewport resize x DPR {1,1.5}).
**Result in this environment: 10 passed, 0 failed.** They were executed with a minimal local stand-in for pytest (pytest could not be installed offline), not with real pytest.
The tests were shown to detect the defect: against the original `plots.js` the panel went from 729 px to 149,695 px.
The tests use the real static assets with synthetic data; they do not start the backend.

## Verification limits (not done)
* The real dashboard was **not** started or browsed: `fastapi`, `uvicorn`, `httpx` and `pytest` are not installed and there is no network in this environment. The live-WebSocket/polling path, pause/resume, reset, replay and tab-switch behaviour of `app.js` were therefore not exercised end to end.
* No loading / empty-data / error overlay was added; the plots already draw their frame when there is no data. That requirement is still open.
* Not run on Windows or at the reporter's actual scaling. The fix removes the DPR dependence by construction, but this must be confirmed in the real dashboard.

## How to verify on your machine
`python -m web.app`, open http://127.0.0.1:8000, set browser zoom to 125 %/150 % (or use Windows scaling != 100 %), press Run, watch the Analysis panel for several minutes; its height should stay ~729 px.
Automated: `python -m pip install playwright && python -m playwright install chromium && python -m pytest -q tests/test_plot_canvas_stability.py`.

---
# Stage 1 addendum (second session): end-to-end verification status

**Component-level evidence above is unchanged. End-to-end verification is STILL NOT DONE: the sandbox again had no network and no `fastapi`, `uvicorn`, `httpx`, `pytest`, and no Windows.**

Done in this session (static): the seven plot canvases in `web/templates/index.html` all carry `data-h` (7/7 by regex count); both `RS.plots.line` and `RS.plots.strip` size through `prep()`; `viewport.js` (arena) sizes independently with an explicit CSS height. Not done: items 3-10 of the Stage 1 list (clean venv, real pytest, real FastAPI dashboard, zoom 100/125/150/200 %, multi-minute run, pause/reset/replay/tab checks, console/network inspection). No loading/error overlay was added because I could not observe the empty-data behaviour in the real app.

Run on your Windows machine (PowerShell, project root):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1            # if blocked: Set-ExecutionPolicy -Scope Process Bypass  (this session only)  or use Git Bash: source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt playwright
python -m playwright install chromium
python -m pytest -q                      # record passed/failed/skipped
python -m web.app                        # then open http://127.0.0.1:8000
```
Manual check: press Run, set browser zoom 125 / 150 / 200 % (Ctrl +), and also try Windows display scaling != 100 %. With DevTools open run
`setInterval(()=>console.log(document.getElementById('analysis').getBoundingClientRect().height), 30000)`; the value must stay constant over time (it was 729 px at every viewport width in the component harness, since canvas heights are fixed in CSS pixels). Exercise window 30/60/120, pause/resume, reset, replay, tab switching, window resizing; keep the Console and Network tabs open and report any error.
Fastest automated confirmation of the fix with real pytest: `python -m pytest -q tests/test_plot_canvas_stability.py` (10 cases, expects 10 passed with Playwright+Chromium installed).
