import math, os
OUT = "/sessions/amazing-upbeat-brown/mnt/outputs"

BLUE="#2563EB"; CYAN="#06B6D4"; CYAN_L="#22D3EE"; INK="#0B1F3A"; WHITE="#FFFFFF"

def pt(cx,cy,r,deg):
    a=math.radians(deg); return (cx+r*math.cos(a), cy+r*math.sin(a))
def arc_path(cx,cy,r,s,e,sweep=1):
    x0,y0=pt(cx,cy,r,s); x1,y1=pt(cx,cy,r,e)
    d=(e-s)%360; large=1 if d>180 else 0
    return f"M {x0:.2f} {y0:.2f} A {r} {r} 0 {large} {sweep} {x1:.2f} {y1:.2f}"
def glyph(cx,cy,r,color,sw):
    s,e=305,215
    path=arc_path(cx,cy,r,s,e,1)
    ex,ey=pt(cx,cy,r,e)
    ta=math.radians(e); tx,ty=-math.sin(ta),math.cos(ta); nx,ny=math.cos(ta),math.sin(ta)
    L=sw*1.9; W=sw*1.25; bx,by=ex-tx*L,ey-ty*L
    p1=(bx+nx*W,by+ny*W); p2=(bx-nx*W,by-ny*W)
    head=f"M {ex:.2f} {ey:.2f} L {p1[0]:.2f} {p1[1]:.2f} L {p2[0]:.2f} {p2[1]:.2f} Z"
    return (f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round"/>'
            f'<path d="{head}" fill="{color}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{sw*1.1:.2f}" fill="{color}"/>')

GRAD='<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient></defs>'%(BLUE,CYAN)

def mark_tile():
    return f'<svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">{GRAD}<rect width="48" height="48" rx="12" fill="url(#g)"/>{glyph(24,24,11.5,WHITE,3.4)}</svg>'
def mark_glyph():
    return f'<svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">{GRAD}{glyph(24,24,13,"url(#g)",4.2)}</svg>'
def primary(text_color):
    return (f'<svg viewBox="0 0 226 56" xmlns="http://www.w3.org/2000/svg">{GRAD}'
            f'<rect width="56" height="56" rx="14" fill="url(#g)"/>{glyph(28,28,13.5,WHITE,3.9)}'
            f'<text x="70" y="37" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="30" font-weight="700" fill="{text_color}" letter-spacing="-0.5">CV<tspan fill="url(#g)">Ops</tspan></text></svg>')

files={"logo-mark-tile.svg":mark_tile(),"logo-mark-glyph.svg":mark_glyph(),
       "logo-primary-light.svg":primary(INK),"logo-primary-dark.svg":primary(WHITE)}
for n,s in files.items():
    open(os.path.join(OUT,n),"w").write(s)
print("wrote",list(files))
