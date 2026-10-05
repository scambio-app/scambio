"""Generatore delle icone simboliche di Scambio (16x16, solo fill, evenodd).

Ogni icona è una lista di parti (d, kind): kind = fg | neg | dim.
- fg  : colore del testo (ColorScheme-Text / fill ricolorato da GTK)
- neg : colore d'errore (ColorScheme-NegativeText / classe .error)
- dim : colore del testo con opacità 0.4
"""
import json, math, sys

def f(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"

def rr(x, y, w, h, tl, tr=None, br=None, bl=None):
    tr = tl if tr is None else tr
    br = tl if br is None else br
    bl = tl if bl is None else bl
    p = [f"M{f(x+tl)} {f(y)}", f"H{f(x+w-tr)}"]
    if tr: p.append(f"A{f(tr)} {f(tr)} 0 0 1 {f(x+w)} {f(y+tr)}")
    p.append(f"V{f(y+h-br)}")
    if br: p.append(f"A{f(br)} {f(br)} 0 0 1 {f(x+w-br)} {f(y+h)}")
    p.append(f"H{f(x+bl)}")
    if bl: p.append(f"A{f(bl)} {f(bl)} 0 0 1 {f(x)} {f(y+h-bl)}")
    p.append(f"V{f(y+tl)}")
    if tl: p.append(f"A{f(tl)} {f(tl)} 0 0 1 {f(x+tl)} {f(y)}")
    p.append("Z")
    return "".join(p)

def circle(cx, cy, r):
    return (f"M{f(cx-r)} {f(cy)}A{f(r)} {f(r)} 0 1 0 {f(cx+r)} {f(cy)}"
            f"A{f(r)} {f(r)} 0 1 0 {f(cx-r)} {f(cy)}Z")

def seg(x1, y1, x2, y2, w):
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    nx, ny = -dy / L * w / 2, dx / L * w / 2
    pts = [(x1+nx, y1+ny), (x2+nx, y2+ny), (x2-nx, y2-ny), (x1-nx, y1-ny)]
    return "M" + "L".join(f"{f(a)} {f(b)}" for a, b in pts) + "Z"

# ---------- occhiali ----------
def lens(x, y, w, h, filled, t=1.25):
    outer = rr(x, y, w, h, 0.5, 0.5, 2.6, 2.6)
    if filled:
        return outer
    inner = rr(x+t, y+t*0.6, w-2*t, h-t*1.6, 0, 0, 1.5, 1.5)
    return outer + inner

def glasses(dy=0.0, filled=False, left_filled=None, right_filled=None):
    lf = filled if left_filled is None else left_filled
    rf = filled if right_filled is None else right_filled
    y = 2.5 + dy
    brow = rr(0.5, y, 15, 1.6, 0.8)
    return brow + lens(1.25, y+0.4, 5.75, 5.6, lf) + lens(9, y+0.4, 5.75, 5.6, rf)

# ---------- emblemi (quadrante in basso a destra) ----------
def monitor():
    return (rr(8.5, 9.75, 7, 4.5, 0.8) + rr(9.75, 11, 4.5, 2, 0.2)
            + rr(11.4, 14.1, 1.2, 1.2, 0) + rr(10.25, 15, 3.5, 1, 0.5))

def phone():
    return rr(11.25, 9, 4.25, 7, 1) + rr(12.4, 10.15, 1.95, 4.25, 0.2)

def lock(k='fg', x=0.0, y=0.0):
    return [(rr(10.25+x, 8.75+y, 4.5, 5, 2.25) + rr(11.5+x, 10+y, 2, 3.75, 1), k),
            (rr(9.5+x, 11.75+y, 6, 4.25, 1), k)]

def dots(y=13.0):
    return circle(10, y, 1) + circle(12.75, y, 1) + circle(15, y, 1) if False else \
        circle(9.75, y, 1.05) + circle(12.5, y, 1.05) + circle(15.0, y, 1.0)

def xmark(cx=12.5, cy=12.5, a=2.6, w=1.5):
    return seg(cx-a, cy-a, cx+a, cy+a, w) + seg(cx-a, cy+a, cx+a, cy-a, w)

def err_badge(cx=12.5, cy=12.5, r=3.5):
    return (circle(cx, cy, r) + rr(cx-0.625, cy-2.25, 1.25, 2.75, 0.6)
            + circle(cx, cy+1.65, 0.72))

# ---------- binari (variante C) ----------
def track(active):  # active: 'pc' | 'phone' | None
    parts = []
    stem = seg(8, 16, 8, 11, 2) + circle(8, 11, 1)
    L = seg(8, 11, 2.6, 3.4, 2 if active == 'pc' else 1)
    R = seg(8, 11, 13.4, 3.4, 2 if active == 'phone' else 1)
    parts.append(stem + (L if active == 'pc' else "") + (R if active == 'phone' else ""))
    thin = (L if active != 'pc' else "") + (R if active != 'phone' else "")
    return parts[0], thin

def variants():
    V = {}
    # A — Occhiali puri: pieni = sul PC
    gy = 2.5
    V['A'] = {
        'released':   [(glasses(gy), 'fg')],
        'connecting': [(glasses(gy, left_filled=True, right_filled=False), 'fg')],
        'on_pc':      [(glasses(gy, filled=True), 'fg')],
        'priority':   [(glasses(0), 'fg')] + lock(),
        'unavailable':[(glasses(gy), 'dim'), (seg(1.5, 14.5, 14.5, 1.5, 1.5), 'fg:nz')],
        'error':      [(glasses(0), 'fg'), (err_badge(), 'neg')],
    }
    # B — Occhiali + emblema del dispositivo che li ha
    V['B'] = {
        'released':   [(glasses(0), 'fg'), (phone(), 'fg')],
        'connecting': [(glasses(0, left_filled=True, right_filled=False), 'fg'), (dots(), 'fg')],
        'on_pc':      [(glasses(0, filled=True), 'fg'), (monitor(), 'fg')],
        'priority':   [(glasses(0), 'fg')] + lock(),
        'unavailable':[(glasses(0), 'dim'), (xmark(), 'fg:nz')],
        'error':      [(glasses(0), 'fg'), (err_badge(), 'neg')],
    }
    # C — Scambio ferroviario: ramo sinistro = PC, destro = iPhone
    def tr(active, extra=None, kind='fg'):
        solid, thin = track(active)
        out = [(solid, kind + ':nz'), (thin, ('dim' if kind == 'fg' else kind) + ':nz')]
        if extra: out += extra
        return out
    V['C'] = {
        'released':   tr('phone') + [(circle(13.4, 3.4, 2.2), 'fg')],
        'connecting': tr(None) + [(circle(5.3, 7.2, 1.3) , 'fg')],
        'on_pc':      tr('pc') + [(circle(2.6, 3.4, 2.2), 'fg')],
        'priority':   tr('phone') + lock(x=0.5, y=-8.75),
        'unavailable':[(track(None)[0] + track(None)[1], 'dim:nz'), (xmark(12.5, 12.5), 'fg:nz')],
        'error':      tr(None) + [(err_badge(), 'neg')],
    }
    return V

COLORS = {'light': {'fg': '#232629', 'neg': '#da4453'},
          'dark':  {'fg': '#fcfcfc', 'neg': '#da4453'}}

def split(k):
    return (k[:-3], 'nonzero') if k.endswith(':nz') else (k, 'evenodd')

def svg_preview(parts, fg='#232629', neg='#da4453', size=16):
    body = []
    for d, k in parts:
        k, rule = split(k)
        if not d: continue
        col = neg if k == 'neg' else fg
        op = ' opacity="0.4"' if k == 'dim' else ''
        body.append(f'<path d="{d}" fill="{col}" fill-rule="{rule}"{op}/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 16 16">{"".join(body)}</svg>')

def symbolic(parts):
    """File finale: Breeze (ColorScheme-*) + GTK (.error) insieme."""
    body = []
    for d, k in parts:
        k, rule = split(k)
        if not d: continue
        if k == 'neg':
            body.append(f'  <path class="ColorScheme-NegativeText error" d="{d}" '
                        f'fill="currentColor" fill-rule="{rule}"/>')
        else:
            op = ' opacity="0.4"' if k == 'dim' else ''
            body.append(f'  <path class="ColorScheme-Text" d="{d}" fill="currentColor" '
                        f'fill-rule="{rule}"{op}/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">\n'
            '  <style id="current-color-scheme" type="text/css">'
            '.ColorScheme-Text{color:#232629}.ColorScheme-NegativeText{color:#da4453}</style>\n'
            + "\n".join(body) + "\n</svg>\n")

if __name__ == "__main__":
    V = variants()
    if sys.argv[1:] == ["json"]:
        out = {}
        for v, states in V.items():
            out[v] = {}
            for s, parts in states.items():
                ps = []
                for d, k in parts:
                    if not d: continue
                    kk, rule = split(k)
                    ps.append({'d': d, 'k': kk, 'r': rule})
                assert len(ps) <= 4, (v, s, len(ps))
                while len(ps) < 4: ps.append({'d': '', 'k': 'fg', 'r': 'evenodd'})
                out[v][s] = ps
        print(json.dumps(out, separators=(',', ':')))
    elif sys.argv[1:2] == ["sheet"]:
        import cairosvg
        rows = []
        S = ['released', 'connecting', 'on_pc', 'priority', 'unavailable', 'error']
        x0 = 10
        cells = []
        for ti, theme in enumerate(['light', 'dark']):
            bg = '#eff0f1' if theme == 'light' else '#232629'
            for vi, v in enumerate('ABC'):
                for si, s in enumerate(S):
                    for zi, z in enumerate([16, 22, 48]):
                        X = 10 + si * 110 + [0, 22, 50][zi]
                        Y = 10 + (ti * 3 + vi) * 60
                        inner = svg_preview(V[v][s], COLORS[theme]['fg'], COLORS[theme]['neg'], z)
                        inner = inner.replace('<svg ', f'<svg x="{X}" y="{Y}" ', 1)
                        cells.append(inner)
                cells.insert(0, f'<rect x="0" y="{(ti*3+vi)*60}" width="680" height="60" fill="{bg}"/>')
        big = f'<svg xmlns="http://www.w3.org/2000/svg" width="680" height="360">{"".join(cells)}</svg>'
        cairosvg.svg2png(bytestring=big.encode(), write_to=sys.argv[2], output_width=1360)


def export():
    """Scrive le icone della variante B (approvata) in ../hicolor/."""
    import os
    from appicon import app_icon
    here = os.path.dirname(os.path.abspath(__file__))
    base = os.path.join(here, '..', 'hicolor')
    names = {'released': 'released', 'connecting': 'connecting', 'on_pc': 'on-pc',
             'priority': 'priority', 'unavailable': 'unavailable', 'error': 'error'}
    V = variants()
    for s, n in names.items():
        with open(f'{base}/scalable/status/app.scambio.Scambio-{n}-symbolic.svg', 'w') as fh:
            fh.write(symbolic(V['B'][s]))
    with open(f'{base}/symbolic/apps/app.scambio.Scambio-symbolic.svg', 'w') as fh:
        fh.write(symbolic(V['A']['released']))
    with open(f'{base}/scalable/apps/app.scambio.Scambio.svg', 'w') as fh:
        fh.write(app_icon())


if __name__ == "__main__" and sys.argv[1:] == ["export"]:
    export()
