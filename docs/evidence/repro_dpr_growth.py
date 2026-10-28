"""Reproduce the Analysis-panel growth using the REAL static assets (style.css, core.js, plots.js).
Backend is not involved: the defect is in canvas sizing in plots.js::prep()."""
import json, sys, pathlib
from playwright.sync_api import sync_playwright
STATIC = pathlib.Path(__file__).resolve().parents[2] / "web" / "static"
HTML = f"""<!doctype html><html><head><meta charset=utf-8><link rel=stylesheet href="file://{STATIC}/style.css"></head>
<body><main style="max-width:900px"><section class="analysis" id="analysis">
<canvas class="plot" id="pl-err" height="120"></canvas><canvas class="plot" id="pl-sep" height="100"></canvas>
<canvas class="plot" id="pl-q" height="100"></canvas><canvas class="plot" id="pl-age" height="100"></canvas>
<canvas class="plot" id="pl-sup" height="86"></canvas><canvas class="plot" id="pl-net" height="100"></canvas>
<canvas class="plot" id="pl-cons" height="100" ></canvas></section></main>
<script src="file://{STATIC}/js/core.js"></script><script src="file://{STATIC}/js/plots.js"></script></body></html>"""
def spec(k):
    t = [i*0.2 for i in range(300)]
    return dict(title="Formation error", unit="m", t0=0, t1=60, last=True,
                series=[dict(label="rmse", color="#2563eb", t=t, y=[0.1+0.01*((i+k)%7) for i in range(300)])])
def run(dsf, frames=14):
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width":1200,"height":900}, device_scale_factor=dsf)
        f=pathlib.Path("/tmp/repro_page.html"); f.write_text(HTML); pg.goto("file:///tmp/repro_page.html"); pg.wait_for_timeout(200)
        for k in range(frames):
            r = pg.evaluate("""(k)=>{ const ids=['pl-err','pl-sep','pl-q','pl-age','pl-sup','pl-net','pl-cons'];
              const t=[...Array(300).keys()].map(i=>i*0.2), y=t.map((_,i)=>0.1+0.01*((i+k)%7));
              for (const id of ids) RS.plots.line(document.getElementById(id), {title:id,unit:'m',t0:0,t1:60,last:id==='pl-cons',series:[{label:'s',color:'#2563eb',t,y}]});
              const c=document.getElementById('pl-err'); const a=document.getElementById('analysis').getBoundingClientRect();
              return {attrH:c.getAttribute('height'), bufW:c.width, bufH:c.height, cssH:c.clientHeight, panelH:Math.round(a.height)}; }""", k)
            out.append(r)
        b.close()
    return out
if __name__ == "__main__":
    res = {str(d): run(d) for d in (1, 1.25, 1.5, 2, 3)}
    for d, rows in res.items():
        print(f"\nDPR {d}: frame -> pl-err height attr | CSS height px | whole panel px")
        for i, r in enumerate(rows): print(f"  {i:2d}  attr={r['attrH']:>9}  css={r['cssH']:>8}  panel={r['panelH']:>9}")
    pathlib.Path(__file__).with_name("repro_dpr_growth.json").write_text(json.dumps(res, indent=1))
