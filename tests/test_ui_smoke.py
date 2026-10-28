"""Headless-browser smoke test of the dashboard (skipped when Playwright/Chromium is unavailable).

Setup on a developer machine:  pip install playwright && python -m playwright install chromium
"""
import os
import socket
import threading
import time

import pytest

pw = pytest.importorskip("playwright.sync_api")
uvicorn = pytest.importorskip("uvicorn")

from web.app import create_app


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    port = _free_port()
    app = create_app(recordings_dir=tmp_path_factory.mktemp("rec"))
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    th.join(timeout=5)


@pytest.fixture()
def page(server):
    with pw.sync_playwright() as p:
        exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
        try:
            b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        except Exception as exc:                                # browser not installed
            pytest.skip(f"Chromium unavailable: {exc}")
        pg = b.new_page(viewport={"width": 1400, "height": 900})
        pg.errors = []
        pg.on("pageerror", lambda e: pg.errors.append(str(e)))
        pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error"
              and "WebSocket" not in m.text else None)         # WS needs the optional `websockets` package
        pg.goto(server)
        yield pg
        b.close()


def test_live_view_draws_real_state(page):
    page.wait_for_function("document.getElementById('chip-time').textContent !== 't = 0.0 s'", timeout=10000)
    assert page.inner_text("#chip-view") == "LIVE"
    # the arena canvas is painted (non-blank)
    painted = page.evaluate("""() => { const c = document.getElementById('world');
        const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
        let n = 0; for (let i = 3; i < d.length; i += 4000) if (d[i] > 0) n++; return n; }""")
    assert painted > 50
    assert page.errors == []


def test_run_record_replay_playback_and_seek(page):
    page.fill("#x-dur", "10"); page.fill("#x-fstart", "3"); page.fill("#x-flen", "2")
    page.click("#x-run")
    page.wait_for_selector("#replay-bar:not([hidden])", timeout=30000)
    assert page.inner_text("#chip-view") == "REPLAY"
    page.click("#rp-play")
    page.wait_for_timeout(1500)
    t = float(page.inner_text("#rp-time").split("=")[1].split("/")[0])
    assert t > 0.8, "playback must advance in real time (regression: sub-frame steps were lost)"
    page.click("#rp-play")
    page.click("#rp-maxerr")
    assert "peak" in page.inner_text("#rp-summary").lower()
    page.click("[data-pane=replay]")
    assert "fault window 3.0" in page.inner_text("#rp-milestones")
    assert page.errors == []


def test_invalid_experiment_input_is_rejected_with_message(page):
    page.fill("#x-seed", "-5")
    page.click("#x-run")
    page.wait_for_function("document.getElementById('feedback').textContent.length > 0", timeout=10000)
    assert "err" in page.get_attribute("#feedback", "class")
    assert page.locator("#replay-bar").is_hidden()
