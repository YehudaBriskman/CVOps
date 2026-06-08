import os
OUT="/sessions/amazing-upbeat-brown/mnt/outputs"
def rd(f): return open(os.path.join(OUT,f)).read()
mark=rd("logo-mark-tile.svg")
logo_light=rd("logo-primary-light.svg")
logo_dark=rd("logo-primary-dark.svg")
hero=rd("hero-orbit.svg")
dash=rd("graphic-dashboard.svg")

def swatch(name,hexv,use,dark=False):
    txt="#fff" if dark else "#0B1F3A"
    return f'''<div class="sw"><div class="chip" style="background:{hexv}"></div>
    <div class="meta"><strong>{name}</strong><span class="hex">{hexv}</span><span class="use">{use}</span></div></div>'''

primaries=[("Cobalt Blue","#2563EB","Primary. Buttons, links, key accents"),
           ("Aqua","#06B6D4","Secondary accent, gradients, highlights"),
           ("Sky","#22D3EE","Bright accent on dark surfaces")]
neutrals=[("Ink","#0B1F3A","Headlines, logo wordmark"),
          ("Slate","#334155","Body text"),
          ("Mist","#94A3B8","Muted/secondary text"),
          ("Cloud","#E2E8F0","Borders, dividers"),
          ("Paper","#F4F8FF","App / page background"),
          ("White","#FFFFFF","Cards, surfaces")]
semantic=[("Success","#16A34A","Passing runs, healthy"),
          ("Warning","#F59E0B","Drift, attention"),
          ("Error","#EF4444","Failed runs"),
          ("Info","#0EA5E9","Neutral status")]

html=f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CVOps — Brand Guide</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<style>
:root{{--blue:#2563EB;--cyan:#06B6D4;--ink:#0B1F3A;--slate:#334155;--mist:#94A3B8;--cloud:#E2E8F0;--paper:#F4F8FF;}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Inter,system-ui,Arial,sans-serif;color:var(--slate);background:var(--paper);line-height:1.55;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:980px;margin:0 auto;padding:0 28px 90px}}
.hero-band{{background:linear-gradient(135deg,#2563EB 0%,#06B6D4 100%);color:#fff;padding:64px 28px 72px;margin-bottom:56px}}
.hero-inner{{max-width:980px;margin:0 auto}}
.hero-band .logo svg{{height:52px;width:auto}}
.kicker{{text-transform:uppercase;letter-spacing:.18em;font-size:12px;font-weight:600;opacity:.85;margin:30px 0 10px}}
h1{{font-size:40px;font-weight:800;letter-spacing:-1px;line-height:1.1;margin-bottom:14px}}
.hero-band p{{font-size:18px;max-width:620px;opacity:.95}}
h2{{font-size:13px;text-transform:uppercase;letter-spacing:.16em;color:var(--blue);font-weight:700;margin:0 0 6px}}
.sec{{margin-top:56px}}
.sec-title{{font-size:26px;font-weight:800;color:var(--ink);letter-spacing:-.5px;margin-bottom:6px}}
.sec-sub{{color:var(--mist);margin-bottom:24px;font-size:15px}}
.card{{background:#fff;border:1px solid var(--cloud);border-radius:18px;padding:28px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.logobox{{display:flex;align-items:center;justify-content:center;border-radius:14px;padding:38px;min-height:130px}}
.logobox svg{{height:46px;width:auto}}
.bg-light{{background:#fff;border:1px solid var(--cloud)}}
.bg-dark{{background:var(--ink)}}
.bg-grad{{background:linear-gradient(135deg,#EAF2FF,#E6FBFF);border:1px solid var(--cloud)}}
.caption{{font-size:12.5px;color:var(--mist);margin-top:10px;text-align:center}}
.swgrid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}
.swgrid.n{{grid-template-columns:repeat(3,1fr)}}
.sw{{display:flex;gap:14px;align-items:center;background:#fff;border:1px solid var(--cloud);border-radius:14px;padding:14px}}
.chip{{width:52px;height:52px;border-radius:12px;flex:none;box-shadow:inset 0 0 0 1px rgba(0,0,0,.06)}}
.meta{{display:flex;flex-direction:column}}
.meta strong{{color:var(--ink);font-size:14px}}
.hex{{font-family:'JetBrains Mono',monospace;font-size:12.5px;color:var(--blue);margin:1px 0}}
.use{{font-size:12px;color:var(--mist)}}
.type-row{{display:flex;align-items:baseline;gap:18px;padding:16px 0;border-bottom:1px solid var(--cloud)}}
.type-row:last-child{{border:0}}
.type-row .lbl{{width:130px;flex:none;font-size:12.5px;color:var(--mist)}}
.do,.dont{{border-radius:14px;padding:18px 20px;font-size:14.5px}}
.do{{background:#ECFDF5;border:1px solid #A7F3D0}}
.dont{{background:#FEF2F2;border:1px solid #FECACA}}
.do b{{color:#047857}} .dont b{{color:#B91C1C}}
.do ul,.dont ul{{margin:8px 0 0 18px}} .do li,.dont li{{margin:4px 0}}
.imgcard svg{{width:100%;height:auto;display:block;border-radius:16px}}
.voice{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}}
.pill{{background:#fff;border:1px solid var(--cloud);border-radius:14px;padding:18px}}
.pill h4{{color:var(--ink);font-size:15px;margin-bottom:4px}}
.pill span{{font-size:13.5px}}
.ft{{margin-top:64px;color:var(--mist);font-size:13px;text-align:center}}
@media(max-width:720px){{.grid2,.swgrid,.voice{{grid-template-columns:1fr}}h1{{font-size:30px}}}}
</style></head>
<body>
<div class="hero-band"><div class="hero-inner">
  <div class="logo">{logo_dark}</div>
  <div class="kicker">Brand Guidelines · v1</div>
  <h1>The ML lifecycle, in one place.</h1>
  <p>CVOps replaces five fragmented tools — track datasets, version models, orchestrate workflows, and audit everything from a single platform.</p>
</div></div>

<div class="wrap">

  <div class="sec">
    <div class="sec-title">Brand essence</div>
    <div class="sec-sub">What CVOps stands for, in one breath.</div>
    <div class="card">
      <h2>Positioning</h2>
      <p style="font-size:18px;color:var(--ink);font-weight:600;max-width:760px">One calm, unified home for the entire machine-learning lifecycle — so teams stop stitching tools together and start shipping models with confidence.</p>
      <div class="voice" style="margin-top:22px">
        <div class="pill"><h4>Unified</h4><span>Five tools become one. Every stage connects.</span></div>
        <div class="pill"><h4>Trustworthy</h4><span>Versioned, auditable, reproducible by default.</span></div>
        <div class="pill"><h4>Approachable</h4><span>Powerful under the hood, friendly on the surface.</span></div>
        <div class="pill"><h4>Clear</h4><span>Signal over noise. The right view at the right time.</span></div>
      </div>
    </div>
  </div>

  <div class="sec">
    <div class="sec-title">Logo</div>
    <div class="sec-sub">The mark is a lifecycle loop circling a single hub node — iteration around one source of truth.</div>
    <div class="grid2">
      <div><div class="logobox bg-light">{logo_light}</div><div class="caption">Primary · light backgrounds</div></div>
      <div><div class="logobox bg-dark">{logo_dark}</div><div class="caption">Reversed · dark backgrounds</div></div>
    </div>
    <div class="grid2" style="margin-top:20px">
      <div><div class="logobox bg-grad">{mark}</div><div class="caption">App icon / standalone mark</div></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div class="do"><b>Do</b><ul><li>Keep clear space ≥ the mark's height</li><li>Use the gradient mark on white or navy</li><li>Scale proportionally</li></ul></div>
        <div class="dont"><b>Don't</b><ul><li>Recolor or stretch the logo</li><li>Add shadows or outlines</li><li>Place on busy/low-contrast images</li></ul></div>
      </div>
    </div>
  </div>

  <div class="sec">
    <div class="sec-title">Color</div>
    <div class="sec-sub">A confident blue→cyan core, grounded by deep navy and clean neutrals.</div>
    <h2 style="margin-bottom:12px">Primary &amp; accent</h2>
    <div class="swgrid">{''.join(swatch(*p) for p in primaries)}</div>
    <div class="card" style="margin-top:16px;background:linear-gradient(135deg,#2563EB,#06B6D4);border:0;color:#fff;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
      <strong style="font-size:16px">Signature gradient</strong>
      <span style="font-family:'JetBrains Mono',monospace;font-size:13px">linear-gradient(135°, #2563EB → #06B6D4)</span>
    </div>
    <h2 style="margin:28px 0 12px">Neutrals</h2>
    <div class="swgrid">{''.join(swatch(*p) for p in neutrals)}</div>
    <h2 style="margin:28px 0 12px">Semantic</h2>
    <div class="swgrid">{''.join(swatch(*p) for p in semantic)}</div>
  </div>

  <div class="sec">
    <div class="sec-title">Typography</div>
    <div class="sec-sub">Inter for everything — modern, highly legible, friendly. JetBrains Mono for IDs, hashes &amp; metrics.</div>
    <div class="card">
      <div class="type-row"><div class="lbl">Display · 800</div><div style="font-size:34px;font-weight:800;color:var(--ink);letter-spacing:-1px">Ship models with confidence</div></div>
      <div class="type-row"><div class="lbl">Heading · 700</div><div style="font-size:24px;font-weight:700;color:var(--ink)">Track every dataset version</div></div>
      <div class="type-row"><div class="lbl">Body · 400</div><div style="font-size:16px">Reproducible pipelines, audited end to end, with a single view across the lifecycle.</div></div>
      <div class="type-row"><div class="lbl">Mono · 500</div><div style="font-family:'JetBrains Mono',monospace;font-size:15px;color:var(--blue)">run_8f3a91 · acc 0.962 · v12</div></div>
    </div>
  </div>

  <div class="sec">
    <div class="sec-title">Imagery &amp; graphics</div>
    <div class="sec-sub">Soft gradients, rounded cards, generous whitespace, dotted connective lines. Light and airy — never heavy or dark.</div>
    <div class="card imgcard" style="padding:18px">{hero}</div>
    <div class="card imgcard" style="padding:18px;margin-top:20px">{dash}</div>
  </div>

  <div class="sec">
    <div class="sec-title">Voice &amp; tone</div>
    <div class="sec-sub">Like a sharp teammate: clear, calm, technically credible — never hypey.</div>
    <div class="voice">
      <div class="pill"><h4>Clear over clever</h4><span>Say the useful thing plainly. Short sentences win.</span></div>
      <div class="pill"><h4>Confident, not loud</h4><span>State capabilities directly; let proof do the bragging.</span></div>
      <div class="pill"><h4>Human &amp; specific</h4><span>Talk like an engineer who respects the reader's time.</span></div>
      <div class="pill"><h4>Calm under complexity</h4><span>Make a hard domain feel manageable and orderly.</span></div>
    </div>
    <div class="card" style="margin-top:18px">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">
        <div class="do"><b>On-brand</b><br><span>"Every model, versioned and traceable to the data that trained it."</span></div>
        <div class="dont"><b>Off-brand</b><br><span>"Revolutionary AI magic that 10x's your ML — guaranteed!"</span></div>
      </div>
    </div>
  </div>

  <div class="ft">CVOps Brand Guide · v1 · Cobalt #2563EB / Aqua #06B6D4 · Inter + JetBrains Mono</div>
</div>
</body></html>'''
open(os.path.join(OUT,"CVOps-Brand-Guide.html"),"w").write(html)
print("wrote CVOps-Brand-Guide.html", len(html),"bytes")
