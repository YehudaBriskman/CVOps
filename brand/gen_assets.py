import math, os, json
OUT="/sessions/amazing-upbeat-brown/mnt/outputs"
BLUE="#2563EB"; CYAN="#06B6D4"; CYAN_L="#22D3EE"; INK="#0B1F3A"; SLATE="#334155"
MIST="#94A3B8"; CLOUD="#E2E8F0"; PAPER="#F4F8FF"; WHITE="#FFFFFF"
SUCCESS="#16A34A"; WARN="#F59E0B"; ERR="#EF4444"; INFO="#0EA5E9"

def pt(cx,cy,r,deg):
    a=math.radians(deg); return (cx+r*math.cos(a), cy+r*math.sin(a))
def arc_path(cx,cy,r,s,e,sweep=1):
    x0,y0=pt(cx,cy,r,s); x1,y1=pt(cx,cy,r,e)
    d=(e-s)%360; large=1 if d>180 else 0
    return f"M {x0:.2f} {y0:.2f} A {r} {r} 0 {large} {sweep} {x1:.2f} {y1:.2f}"
def loop(cx,cy,r,color,sw):
    s,e=305,215; path=arc_path(cx,cy,r,s,e,1)
    ex,ey=pt(cx,cy,r,e); ta=math.radians(e)
    tx,ty=-math.sin(ta),math.cos(ta); nx,ny=math.cos(ta),math.sin(ta)
    L=sw*1.9; W=sw*1.25; bx,by=ex-tx*L,ey-ty*L
    p1=(bx+nx*W,by+ny*W); p2=(bx-nx*W,by-ny*W)
    head=f"M {ex:.2f} {ey:.2f} L {p1[0]:.2f} {p1[1]:.2f} L {p2[0]:.2f} {p2[1]:.2f} Z"
    return (f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round"/>'
            f'<path d="{head}" fill="{color}"/><circle cx="{cx}" cy="{cy}" r="{sw*1.1:.2f}" fill="{color}"/>')
GRAD=f'<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BLUE}"/><stop offset="1" stop-color="{CYAN}"/></linearGradient>'
FONT="Inter, 'DejaVu Sans', Arial, sans-serif"

# ---- icon tile (used for favicons) ----
def icon_tile(size=48,rx_ratio=0.25):
    rx=size*rx_ratio
    return (f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg"><defs>{GRAD}</defs>'
            f'<rect width="{size}" height="{size}" rx="{rx}" fill="url(#g)"/>'
            f'{loop(size/2,size/2,size*0.24,WHITE,size*0.071)}</svg>')
open(OUT+"/icon-master.svg","w").write(icon_tile(512,0.22))

# ---- SOCIAL BANNER (OG 1200x630) ----
def og_banner():
    W,H=1200,630
    s=[f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"><defs>{GRAD}'
       f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0B1F3A"/><stop offset="1" stop-color="#103A6B"/></linearGradient></defs>']
    s.append(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')
    # faint orbit motif right side
    cx,cy=980,315
    for r in (120,180,240):
        s.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{CYAN_L}" stroke-width="1.3" opacity="0.18"/>')
    for i in range(5):
        x,y=pt(cx,cy,180,-90+i*72)
        s.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="9" fill="{CYAN_L}" opacity="0.55"/>')
        s.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.0f}" y2="{y:.0f}" stroke="{CYAN_L}" stroke-width="1.2" stroke-dasharray="2 6" opacity="0.3"/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="52" fill="url(#g)"/>')
    s.append(loop(cx,cy,23,WHITE,5.5))
    # left content
    s.append(f'<g transform="translate(90,150)"><rect width="64" height="64" rx="16" fill="url(#g)"/></g>')
    s.append(loop(122,182,16,WHITE,4.6))
    s.append(f'<text x="170" y="198" font-family="{FONT}" font-size="40" font-weight="800" fill="{WHITE}" letter-spacing="-1">CV<tspan fill="{CYAN_L}">Ops</tspan></text>')
    s.append(f'<text x="92" y="320" font-family="{FONT}" font-size="62" font-weight="800" fill="{WHITE}" letter-spacing="-2">The ML lifecycle,</text>')
    s.append(f'<text x="92" y="388" font-family="{FONT}" font-size="62" font-weight="800" fill="{CYAN_L}" letter-spacing="-2">in one place.</text>')
    s.append(f'<text x="94" y="448" font-family="{FONT}" font-size="25" font-weight="500" fill="#CBD9EE">Datasets · models · workflows · audit — one platform</text>')
    s.append(f'<text x="94" y="500" font-family="{FONT}" font-size="20" font-weight="600" fill="{CYAN_L}">Replaces five fragmented tools.</text>')
    s.append('</svg>')
    return "\n".join(s)
open(OUT+"/social-banner-og.svg","w").write(og_banner())

# ---- WIDE BANNER (1500x500, X/LinkedIn header) ----
def wide_banner():
    W,H=1500,500
    s=[f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"><defs>{GRAD}'
       f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#2563EB"/><stop offset="1" stop-color="#06B6D4"/></linearGradient></defs>']
    s.append(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')
    # subtle dotted grid
    dots=[]
    for x in range(60,W,46):
        for y in range(40,H,46):
            dots.append(f'<circle cx="{x}" cy="{y}" r="1.6" fill="#FFFFFF" opacity="0.10"/>')
    s.append("".join(dots))
    s.append(f'<g transform="translate(110,205)"><rect width="90" height="90" rx="22" fill="#FFFFFF"/></g>')
    s.append(loop(155,250,21,BLUE,6))
    s.append(f'<text x="230" y="270" font-family="{FONT}" font-size="64" font-weight="800" fill="#FFFFFF" letter-spacing="-2">CVOps</text>')
    s.append(f'<text x="232" y="318" font-family="{FONT}" font-size="26" font-weight="500" fill="#EAF6FF">One platform for the whole ML lifecycle</text>')
    s.append('</svg>')
    return "\n".join(s)
open(OUT+"/social-banner-wide.svg","w").write(wide_banner())

# ---- PITCH TITLE SLIDE (1920x1080) ----
def title_slide():
    W,H=1920,1080
    s=[f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"><defs>{GRAD}'
       f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0B1F3A"/><stop offset="0.6" stop-color="#0E2C52"/><stop offset="1" stop-color="#06B6D4"/></linearGradient>'
       f'<filter id="gl" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="22"/></filter></defs>']
    s.append(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')
    # big faint orbit upper-right
    cx,cy=1500,360
    for r in (150,250,350,460):
        s.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{CYAN_L}" stroke-width="1.5" opacity="0.12"/>')
    for i in range(5):
        x,y=pt(cx,cy,250,-90+i*72)
        s.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.0f}" y2="{y:.0f}" stroke="{CYAN_L}" stroke-width="1.4" stroke-dasharray="3 9" opacity="0.25"/>')
        s.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="12" fill="{CYAN_L}" opacity="0.5"/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="70" fill="url(#g)" opacity="0.9"/>')
    s.append(loop(cx,cy,31,WHITE,7))
    # logo top-left
    s.append(f'<g transform="translate(140,120)"><rect width="86" height="86" rx="22" fill="url(#g)"/></g>')
    s.append(loop(183,163,21,WHITE,6))
    s.append(f'<text x="250" y="180" font-family="{FONT}" font-size="56" font-weight="800" fill="{WHITE}" letter-spacing="-1.5">CV<tspan fill="{CYAN_L}">Ops</tspan></text>')
    # headline
    s.append(f'<text x="140" y="560" font-family="{FONT}" font-size="118" font-weight="800" fill="{WHITE}" letter-spacing="-4">The ML lifecycle,</text>')
    s.append(f'<text x="140" y="690" font-family="{FONT}" font-size="118" font-weight="800" fill="{CYAN_L}" letter-spacing="-4">in one place.</text>')
    s.append(f'<rect x="146" y="760" width="90" height="7" rx="3" fill="url(#g)"/>')
    s.append(f'<text x="140" y="838" font-family="{FONT}" font-size="40" font-weight="500" fill="#C9D8EC">Track datasets · version models · orchestrate workflows · audit everything.</text>')
    s.append(f'<text x="140" y="900" font-family="{FONT}" font-size="34" font-weight="600" fill="{CYAN_L}">One dashboard that replaces five fragmented tools.</text>')
    s.append('</svg>')
    return "\n".join(s)
open(OUT+"/pitch-title-slide.svg","w").write(title_slide())

# ---- COLOR PALETTE: visual swatch sheet ----
PAL=[("Primary",[("Cobalt Blue",BLUE),("Aqua",CYAN),("Sky",CYAN_L)]),
     ("Neutral",[("Ink",INK),("Slate",SLATE),("Mist",MIST),("Cloud",CLOUD),("Paper",PAPER),("White",WHITE)]),
     ("Semantic",[("Success",SUCCESS),("Warning",WARN),("Error",ERR),("Info",INFO)])]
def palette_sheet():
    W=1100; pad=60; col_w=300; rowh=92; gap=18
    # compute height
    y=200
    blocks=[]
    for group,items in PAL:
        blocks.append(("H",group,y)); y+=54
        per=3
        rows=math.ceil(len(items)/per)
        for r in range(rows):
            for c in range(per):
                idx=r*per+c
                if idx<len(items):
                    blocks.append(("S",items[idx],(pad+c*col_w, y+r*(rowh+gap))))
        y+=rows*(rowh+gap)+30
    y+=120  # gradient block
    H=y
    s=[f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"><defs>{GRAD}</defs>']
    s.append(f'<rect width="{W}" height="{H}" fill="{WHITE}"/>')
    s.append(f'<rect width="{W}" height="10" fill="url(#g)"/>')
    s.append(f'<text x="{pad}" y="92" font-family="{FONT}" font-size="40" font-weight="800" fill="{INK}" letter-spacing="-1">CVOps Color Palette</text>')
    s.append(f'<text x="{pad}" y="128" font-family="{FONT}" font-size="18" fill="{MIST}">Modern &amp; approachable · blue → cyan core</text>')
    for b in blocks:
        if b[0]=="H":
            s.append(f'<text x="{pad}" y="{b[2]}" font-family="{FONT}" font-size="15" font-weight="700" letter-spacing="2" fill="{BLUE}">{b[1].upper()}</text>')
        else:
            (name,hexv),(x,yy)=b[1],b[2]
            stroke=f' stroke="{CLOUD}"' if hexv.upper() in (WHITE,PAPER) else ''
            s.append(f'<rect x="{x}" y="{yy}" width="{col_w-30}" height="{rowh}" rx="14" fill="{hexv}"{stroke}/>')
            tcol = INK if hexv.upper() in (WHITE,PAPER,CLOUD,CYAN_L,WARN) else WHITE
            s.append(f'<text x="{x+18}" y="{yy+40}" font-family="{FONT}" font-size="19" font-weight="700" fill="{tcol}">{name}</text>')
            s.append(f'<text x="{x+18}" y="{yy+68}" font-family="DejaVu Sans Mono, monospace" font-size="15" fill="{tcol}" opacity="0.92">{hexv}</text>')
    # gradient block
    gy=H-90
    s.append(f'<rect x="{pad}" y="{gy}" width="{W-2*pad}" height="56" rx="14" fill="url(#g)"/>')
    s.append(f'<text x="{pad+20}" y="{gy+34}" font-family="{FONT}" font-size="18" font-weight="700" fill="{WHITE}">Signature gradient</text>')
    s.append(f'<text x="{W-pad-20}" y="{gy+34}" text-anchor="end" font-family="DejaVu Sans Mono, monospace" font-size="15" fill="{WHITE}">135°  #2563EB → #06B6D4</text>')
    s.append('</svg>')
    return s, W, H
sheet,_,_=palette_sheet()
open(OUT+"/CVOps-color-palette.svg","w").write("\n".join(sheet))

# ---- TOKENS: CSS + JSON ----
tokens={
 "primary":{"cobalt-blue":BLUE,"aqua":CYAN,"sky":CYAN_L},
 "neutral":{"ink":INK,"slate":SLATE,"mist":MIST,"cloud":CLOUD,"paper":PAPER,"white":WHITE},
 "semantic":{"success":SUCCESS,"warning":WARN,"error":ERR,"info":INFO},
 "gradient":{"signature":"linear-gradient(135deg, #2563EB 0%, #06B6D4 100%)"}
}
open(OUT+"/cvops-colors.json","w").write(json.dumps(tokens,indent=2))
css=[":root {"]
flat={"cobalt-blue":BLUE,"aqua":CYAN,"sky":CYAN_L,"ink":INK,"slate":SLATE,"mist":MIST,
      "cloud":CLOUD,"paper":PAPER,"white":WHITE,"success":SUCCESS,"warning":WARN,"error":ERR,"info":INFO}
for k,v in flat.items(): css.append(f"  --cv-{k}: {v};")
css.append("  --cv-gradient: linear-gradient(135deg, #2563EB 0%, #06B6D4 100%);")
css.append("}")
open(OUT+"/cvops-colors.css","w").write("\n".join(css))
print("SVG/token files written")
