import math, os
OUT="/sessions/amazing-upbeat-brown/mnt/outputs"
BLUE="#2563EB"; CYAN="#06B6D4"; CYAN_L="#22D3EE"; INK="#0B1F3A"; SLATE="#334155"
BG="#F4F8FF"; WHITE="#FFFFFF"; MUTED="#94A3B8"

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

# ---------------- HERO: unified hub with 5 orbiting pillars ----------------
W,H=900,560; cx,cy=450,280
pillars=[("Datasets","M7 3h10l2 4v12H5V7z"),("Models",""),("Workflows",""),("Audit",""),("Versioning","")]
labels=["Datasets","Models","Workflows","Audit","Versioning"]
icons={  # simple rounded glyphs (white) drawn inside each node, 0..1 local space scaled
 "Datasets":'<rect x="-9" y="-7" width="18" height="14" rx="3" fill="none" stroke="#fff" stroke-width="2.2"/><line x1="-9" y1="-1" x2="9" y2="-1" stroke="#fff" stroke-width="2.2"/>',
 "Models":'<circle cx="0" cy="-5" r="2.6" fill="#fff"/><circle cx="-6" cy="5" r="2.6" fill="#fff"/><circle cx="6" cy="5" r="2.6" fill="#fff"/><path d="M0 -3 L-5 4 M0 -3 L5 4" stroke="#fff" stroke-width="2"/>',
 "Workflows":'<rect x="-9" y="-8" width="7" height="7" rx="2" fill="#fff"/><rect x="2" y="1" width="7" height="7" rx="2" fill="#fff"/><path d="M-5 -1 v4 h7" fill="none" stroke="#fff" stroke-width="2"/>',
 "Audit":'<path d="M-7 -8 h11 l3 3 v13 h-14 z" fill="none" stroke="#fff" stroke-width="2.2"/><path d="M-3 2 l2 2 4 -5" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
 "Versioning":'<circle cx="-5" cy="-5" r="2.4" fill="#fff"/><circle cx="-5" cy="6" r="2.4" fill="#fff"/><circle cx="6" cy="0" r="2.4" fill="#fff"/><path d="M-5 -3 v6 M-5 0 h8" fill="none" stroke="#fff" stroke-width="2"/>',
}
R=185
nodes=[]
for i,name in enumerate(labels):
    ang=-90+i*(360/len(labels))
    x,y=pt(cx,cy,R,ang)
    nodes.append((name,x,y))

svg=[f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">']
svg.append(f'''<defs>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BLUE}"/><stop offset="1" stop-color="{CYAN}"/></linearGradient>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#EAF2FF"/><stop offset="1" stop-color="#E6FBFF"/></linearGradient>
<filter id="sh" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="#2563EB" flood-opacity="0.18"/></filter>
</defs>''')
svg.append(f'<rect width="{W}" height="{H}" rx="28" fill="url(#bg)"/>')
# connecting lines hub->nodes
for name,x,y in nodes:
    svg.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{CYAN}" stroke-width="2" stroke-dasharray="2 6" stroke-linecap="round" opacity="0.5"/>')
# orbit ring
svg.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{BLUE}" stroke-width="1.5" stroke-dasharray="1 8" opacity="0.35"/>')
# pillar nodes
for name,x,y in nodes:
    svg.append(f'<g transform="translate({x:.1f},{y:.1f})">'
               f'<circle r="34" fill="{WHITE}" filter="url(#sh)"/>'
               f'<circle r="34" fill="none" stroke="{BLUE}" stroke-width="1.5" opacity="0.25"/>'
               f'<g transform="scale(1.15)">{icons[name]}</g>'.replace('#fff',BLUE)
               +f'<text y="54" text-anchor="middle" font-family="Inter,Arial,sans-serif" font-size="15" font-weight="600" fill="{SLATE}">{name}</text></g>')
# central hub
svg.append(f'<circle cx="{cx}" cy="{cy}" r="68" fill="url(#g)" filter="url(#sh)"/>')
svg.append(loop(cx,cy,30,WHITE,7))
svg.append(f'<text x="{cx}" y="{cy+92}" text-anchor="middle" font-family="Inter,Arial,sans-serif" font-size="18" font-weight="700" fill="{INK}">CVOps</text>')
svg.append(f'<text x="{cx}" y="{cy+112}" text-anchor="middle" font-family="Inter,Arial,sans-serif" font-size="13" font-weight="500" fill="{SLATE}">one platform, whole lifecycle</text>')
svg.append('</svg>')
open(os.path.join(OUT,"hero-orbit.svg"),"w").write("\n".join(svg))
print("wrote hero-orbit.svg")

# ---------------- PRODUCT GRAPHIC: clean dashboard mock ----------------
def bar(x,y,w,h,fill,rx=4): return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"/>'
d=[f'<svg viewBox="0 0 900 560" xmlns="http://www.w3.org/2000/svg">']
d.append(f'''<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BLUE}"/><stop offset="1" stop-color="{CYAN}"/></linearGradient>
<filter id="s" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="10" stdDeviation="18" flood-color="#1E293B" flood-opacity="0.12"/></filter></defs>''')
d.append(f'<rect width="900" height="560" rx="28" fill="{BG}"/>')
d.append(f'<g filter="url(#s)"><rect x="70" y="60" width="760" height="440" rx="18" fill="{WHITE}"/></g>')
# top bar
d.append(f'<rect x="70" y="60" width="760" height="56" rx="18" fill="{WHITE}"/>')
d.append(f'<rect x="70" y="98" width="760" height="18" fill="{WHITE}"/>')
d.append(f'<g transform="translate(94,72)"><rect width="32" height="32" rx="9" fill="url(#g)"/></g>')
d.append(loop(110,88,7.5,WHITE,2.2))
d.append(f'<text x="138" y="93" font-family="Inter,Arial,sans-serif" font-size="17" font-weight="700" fill="{INK}">CV<tspan fill="{BLUE}">Ops</tspan></text>')
for i,(lbl) in enumerate(["Overview","Datasets","Models","Runs"]):
    fill=BLUE if i==0 else MUTED
    d.append(f'<text x="{300+i*110}" y="93" font-family="Inter,Arial,sans-serif" font-size="13" font-weight="600" fill="{fill}">{lbl}</text>')
d.append(f'<circle cx="800" cy="88" r="13" fill="#EAF2FF"/>')
# sidebar
d.append(f'<rect x="70" y="116" width="170" height="384" fill="#F8FAFC"/>')
for i in range(5):
    on=i==0
    d.append(bar(94,150+i*46,18,18,BLUE if on else "#CBD5E1",5))
    d.append(bar(122,154+i*46,90 if on else 70,10,SLATE if on else "#CBD5E1",5))
# main: KPI cards
kpis=[("Datasets","128",BLUE),("Models","342",CYAN),("Active runs","17",CYAN_L)]
for i,(t,v,c) in enumerate(kpis):
    x=266+i*180
    d.append(f'<rect x="{x}" y="140" width="160" height="86" rx="14" fill="{WHITE}" stroke="#E2E8F0"/>')
    d.append(f'<rect x="{x+16}" y="158" width="10" height="10" rx="3" fill="{c}"/>')
    d.append(f'<text x="{x+34}" y="167" font-family="Inter,Arial,sans-serif" font-size="12" fill="{MUTED}">{t}</text>')
    d.append(f'<text x="{x+16}" y="208" font-family="Inter,Arial,sans-serif" font-size="30" font-weight="700" fill="{INK}">{v}</text>')
# chart card
d.append(f'<rect x="266" y="242" width="340" height="240" rx="14" fill="{WHITE}" stroke="#E2E8F0"/>')
d.append(f'<text x="284" y="272" font-family="Inter,Arial,sans-serif" font-size="13" font-weight="600" fill="{SLATE}">Model performance</text>')
# line chart
import random; random.seed(3)
pts=[]
for i in range(11):
    px=290+i*30; py=440-(20+ (math.sin(i/1.6)*0.5+0.5)*120 + random.random()*14)
    pts.append((px,py))
dpath="M "+" L ".join(f"{p[0]:.0f} {p[1]:.0f}" for p in pts)
area=dpath+f" L {pts[-1][0]:.0f} 450 L {pts[0][0]:.0f} 450 Z"
d.append(f'<path d="{area}" fill="url(#g)" opacity="0.10"/>')
d.append(f'<path d="{dpath}" fill="none" stroke="url(#g)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
for p in pts[::2]:
    d.append(f'<circle cx="{p[0]:.0f}" cy="{p[1]:.0f}" r="3.5" fill="{BLUE}"/>')
# right list card
d.append(f'<rect x="626" y="242" width="180" height="240" rx="14" fill="{WHITE}" stroke="#E2E8F0"/>')
d.append(f'<text x="644" y="272" font-family="Inter,Arial,sans-serif" font-size="13" font-weight="600" fill="{SLATE}">Recent runs</text>')
for i in range(5):
    y=292+i*36
    col=[BLUE,CYAN,"#16A34A",CYAN_L,"#16A34A"][i]
    d.append(f'<circle cx="652" cy="{y+6}" r="5" fill="{col}"/>')
    d.append(bar(668,y,80,9,"#475569",4))
    d.append(bar(668,y+14,50,7,"#CBD5E1",4))
d.append('</svg>')
open(os.path.join(OUT,"graphic-dashboard.svg"),"w").write("\n".join(d))
print("wrote graphic-dashboard.svg")
