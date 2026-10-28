"""Regression tests for the Analysis / live rolling-window panel (web/static/js/plots.js).

Defect: prep() re-read the canvas `height` attribute (which it had just overwritten with height*devicePixelRatio),
so for any devicePixelRatio != 1 the panel grew geometrically and then went blank.  These tests load the REAL static
assets in Chromium (no backend needed) at several device pixel ratios and assert the panel height stays bounded and
constant under repeated redraws, window changes, malformed data, hide/show, remount and viewport resizing.

Skipped when Playwright/Chromium is unavailable.  Setup: pip install playwright && python -m playwright install chromium
"""
import pathlib

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

STATIC = pathlib.Path(__file__).resolve().parents[1] / "web" / "static"
IDS = ["pl-err", "pl-sep", "pl-q", "pl-age", "pl-sup", "pl-net", "pl-cons"]
HEIGHTS = [120, 100, 100, 100, 86, 100, 100]
PAGE = ("<!doctype html><html><head><meta charset=utf-8><link rel=stylesheet href='style.css'></head><body>"
        "<main style='max-width:900px'><section class='analysis' id='analysis'>"
        + "".join(f"<canvas class='plot' id='{i}' height='{h}' data-h='{h}'></canvas>" for i, h in zip(IDS, HEIGHTS))
        + "</section></main><script src='js/core.js'></script><script src='js/plots.js'></script></body></html>")

FRESH = PAGE[PAGE.index("<section"):PAGE.index("</section>") + len("</section>")]

DRAW = """([k, t0, t1, mode]) => {
  const ids = %s; let t = [...Array(300).keys()].map(i => i * 0.2), y = t.map((_, i) => 0.1 + 0.01 * ((i + k) %% 7));
  if (mode === 'bad') { y = y.map((v, i) => i %% 9 === 0 ? NaN : i %% 11 === 0 ? Infinity : i %% 13 === 0 ? null : v); t = t.slice().reverse(); }
  if (mode === 'empty') { t = []; y = []; }
  for (const id of ids) RS.plots.line(document.getElementById(id), {title: id, unit: 'm', t0, t1, last: id === 'pl-cons',
        series: [{label: 's', color: '#2563eb', t, y}]});
}""" % IDS

MEASURE = """() => ({panel: Math.round(document.getElementById('analysis').getBoundingClientRect().height),
  buf: Math.max(...%s.map(i => Math.max(document.getElementById(i).width, document.getElementById(i).height))),
  css: %s.map(i => document.getElementById(i).clientHeight)})""" % (IDS, IDS)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # Chromium not installed
            pytest.skip(f"Chromium unavailable: {e}")
        yield b
        b.close()


@pytest.fixture()
def make_page(browser, tmp_path):
    (tmp_path / "index.html").write_text(PAGE)
    for n in ("style.css",):
        (tmp_path / n).write_text((STATIC / n).read_text())
    (tmp_path / "js").mkdir()
    for n in ("core.js", "plots.js"):
        (tmp_path / "js" / n).write_text((STATIC / "js" / n).read_text())
    pages = []

    def _make(dpr):
        pg = browser.new_page(viewport={"width": 1200, "height": 900}, device_scale_factor=dpr)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto((tmp_path / "index.html").as_uri())
        pages.append(pg)
        return pg, errors
    yield _make
    for pg in pages:
        pg.close()


DPRS = [1, 1.25, 1.5, 2, 3]


@pytest.mark.parametrize("dpr", DPRS)
def test_repeated_live_updates_keep_panel_height_constant(make_page, dpr):
    pg, errors = make_page(dpr)
    pg.evaluate(DRAW, [0, 0, 60, "ok"])
    base = pg.evaluate(MEASURE)
    for k in range(1, 400):  # ~100 s of live redraws at 250 ms
        pg.evaluate(DRAW, [k, k * 0.2, k * 0.2 + 60, "ok"])
    now = pg.evaluate(MEASURE)
    assert now["panel"] == base["panel"] <= 800, (dpr, base, now)
    assert now["css"] == [h for h in HEIGHTS] or all(abs(a - b) <= 1 for a, b in zip(now["css"], HEIGHTS))
    assert now["buf"] <= 8192
    assert not errors, errors


@pytest.mark.parametrize("dpr", [1, 1.5, 2])
def test_empty_malformed_and_window_changes_stay_bounded(make_page, dpr):
    pg, errors = make_page(dpr)
    pg.evaluate(DRAW, [0, 0, 60, "ok"])
    base = pg.evaluate(MEASURE)["panel"]
    for mode in ("empty", "bad", "ok", "bad", "empty"):
        for (a, b) in ((0, 30), (0, 60), (0, 120), (50, 55)):
            pg.evaluate(DRAW, [3, a, b, mode])
            assert pg.evaluate(MEASURE)["panel"] == base
    assert not errors, errors


@pytest.mark.parametrize("dpr", [1, 1.5])
def test_hide_show_remount_and_resize(make_page, dpr):
    pg, errors = make_page(dpr)
    pg.evaluate(DRAW, [0, 0, 60, "ok"])
    base = pg.evaluate(MEASURE)["panel"]
    for _ in range(5):  # tab switch: section hidden (clientWidth == 0) then shown
        pg.evaluate("document.getElementById('analysis').style.display='none'")
        pg.evaluate(DRAW, [1, 0, 60, "ok"])
        pg.evaluate("document.getElementById('analysis').style.display=''")
        pg.evaluate(DRAW, [2, 0, 60, "ok"])
    assert pg.evaluate(MEASURE)["panel"] == base
    for _ in range(5):  # unmount / remount: a framework re-renders the ORIGINAL markup
        pg.evaluate("""(html) => { document.getElementById('analysis').outerHTML = html; }""", FRESH)
        pg.evaluate(DRAW, [4, 0, 60, "ok"])
        assert pg.evaluate(MEASURE)["panel"] == base
    # cloning an already-drawn panel must also be safe because data-h (not the height attribute) is authoritative
    pg.evaluate("""() => { const s = document.getElementById('analysis'); s.replaceWith(s.cloneNode(true)); }""")
    pg.evaluate(DRAW, [4, 0, 60, "ok"])
    assert pg.evaluate(MEASURE)["panel"] == base
    for w in (600, 900, 1400, 700):  # viewport changes: height must not depend on width
        pg.set_viewport_size({"width": w, "height": 900})
        pg.evaluate(DRAW, [5, 0, 60, "ok"])
        assert abs(pg.evaluate(MEASURE)["panel"] - base) <= 1
    assert not errors, errors
