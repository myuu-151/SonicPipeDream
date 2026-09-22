# Cuts imaged.png (the flat menu mockup) into separate RGBA parts in parts/,
# writes parts/layout.json (positions in mockup pixels) and a recomposite check.
import json, os
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'parts')
os.makedirs(OUT, exist_ok=True)
src = np.array(Image.open(os.path.join(HERE, 'imaged.png')).convert('RGB')).astype(float)
H, W, _ = src.shape

YELLOW = np.array([246, 211, 43.])
BLUE = np.array([3, 38, 174.])
PANEL_TOP = 47          # rows above this are fake transparency baked into the mockup

# ---- background: horizontal scanlines, so one colour per row -------------
bgrow = np.zeros((H, 3))
for y in range(H):
    m = np.linalg.norm(src[y] - YELLOW, axis=1) < 30
    bgrow[y] = np.median(src[y][m], axis=0) if m.sum() > 40 else np.nan
ok = ~np.isnan(bgrow[:, 0])
# scanline period, to continue the pattern into rows that have no clean pixels
rows = np.where(ok)[0]
lum = bgrow[ok].sum(1) - bgrow[ok].sum(1).mean()
full = np.zeros(H); full[rows] = lum
score = {p: np.sum(full[:-p] * full[p:]) for p in range(2, 9)}
PERIOD = max(score, key=score.get)
for y in np.where(~ok)[0]:
    cands = [r for r in rows if (r - y) % PERIOD == 0]
    bgrow[y] = bgrow[min(cands, key=lambda r: abs(r - y))]

layout = []

def shift_stack(m):
    p = np.pad(m, 1, mode='edge')
    return [p[1 + dy:p.shape[0] - 1 + dy, 1 + dx:p.shape[1] - 1 + dx]
            for dy in (-1, 0, 1) for dx in (-1, 0, 1)]

def dilate(m): return np.any(shift_stack(m), axis=0)
def erode(m): return np.all(shift_stack(m), axis=0)

def fill_holes(m):
    out = np.zeros_like(m); out[0, :] = out[-1, :] = out[:, 0] = out[:, -1] = True
    out &= ~m
    while True:
        n = (dilate(out) & ~m) | out
        if (n == out).all(): break
        out = n
    return ~out

def propagate(col, known, iters=4):
    col = col.copy(); known = known.copy()
    for _ in range(iters):
        ks = np.array(shift_stack(known)).astype(float)
        cs = np.array([np.stack(shift_stack(col[..., c])) for c in range(3)])  # 3,9,h,w
        cnt = ks.sum(0)
        avg = (cs * ks[None]).sum(1) / np.maximum(cnt, 1)
        new = ~known & (cnt > 0)
        col[new] = np.moveaxis(avg, 0, -1)[new]
        known |= new
    return col, known

def project(p, bg, fg):
    v = fg - bg
    return np.clip(((p - bg) * v).sum(-1) / np.maximum((v * v).sum(-1), 1), 0, 1)

def save(name, rgb, alpha, x, y, note=''):
    rgba = np.dstack([np.clip(rgb, 0, 255), np.clip(alpha, 0, 1) * 255]).round().astype(np.uint8)
    ys, xs = np.where(rgba[..., 3] > 0)                      # trim
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgba = rgba[y0:y1, x0:x1]
    Image.fromarray(rgba).save(os.path.join(OUT, name + '.png'))
    layout.append(dict(name=name, x=int(x + x0), y=int(y + y0), w=int(x1 - x0), h=int(y1 - y0), note=note))
    return rgba

def cut(name, box, bg=None, T=28, fill=False, edge_fg=None, flat_fg=None, note=''):
    x0, y0, x1, y1 = box
    p = src[y0:y1, x0:x1]
    b = np.broadcast_to(bgrow[y0:y1, None, :], p.shape) if bg is None else bg
    if flat_fg is not None:                                  # single-colour art
        a = project(p, b, flat_fg); a[a < 0.1] = 0
        return save(name, np.broadcast_to(flat_fg, p.shape), a, x0, y0, note)
    nb = np.linalg.norm(p - b, axis=2) > T
    if fill: nb = fill_holes(nb)
    core = erode(nb)
    if edge_fg is None:
        fg, known = propagate(np.where(core[..., None], p, 0), core)
    else:
        fg, known = np.broadcast_to(edge_fg, p.shape).copy(), np.ones_like(nb)
    zone = dilate(nb) & ~core
    a = core.astype(float)
    rgb = p.copy()
    za = project(p, b, fg)
    za[~known] = nb[~known]
    a[zone] = za[zone]
    soft = zone & known & (a < 0.97)
    rgb[soft] = fg[soft]
    a[a < 0.1] = 0
    return save(name, rgb, a, x0, y0, note)

def poly_cov(poly, box, ss=8):
    x0, y0, x1, y1 = box
    im = Image.new('L', ((x1 - x0) * ss, (y1 - y0) * ss), 0)
    ImageDraw.Draw(im).polygon([((x - x0) * ss, (y - y0) * ss) for x, y in poly], fill=255)
    return np.array(im.resize((x1 - x0, y1 - y0), Image.BOX)).astype(float) / 255

def plate(name, text_name, poly, box, text_box, ref_cols, flat_from, note=''):
    """A flat polygon plate with outlined text on it: saves both, separated."""
    x0, y0, x1, y1 = box
    cov = poly_cov(poly, box)
    p = src[y0:y1, x0:x1].copy()
    # plate colour per row, sampled where there is no text
    rowcol = np.median(src[y0:y1, ref_cols[0]:ref_cols[1]], axis=1)
    tx0, ty0, tx1, ty1 = text_box
    tb = np.broadcast_to(rowcol[ty0 - y0:ty1 - y0, None, :], (ty1 - ty0, tx1 - tx0, 3))
    # paint the text out of the plate
    tm = np.linalg.norm(src[ty0:ty1, tx0:tx1] - tb, axis=2) > 12
    tm = dilate(dilate(tm))
    sub = p[ty0 - y0:ty1 - y0, tx0 - x0:tx1 - x0]
    sub[tm] = tb[tm]
    # the plate only varies by row, so right of flat_from use the row colour outright (no text ghost)
    p[:, flat_from - x0:] = rowcol[:, None, :]
    inner = erode(cov >= 0.999)
    rgb, _ = propagate(np.where(inner[..., None], p, 0), inner, iters=3)
    save(name, rgb, cov, x0, y0, note)
    cut(text_name, text_box, bg=tb, T=30, edge_fg=BLUE)

# ---- parts ---------------------------------------------------------------
plate('title_banner', 'title_text', [(0, 12.6), (297.3, 12.6), (322.6, 47), (0, 47)], (0, 12, 324, 47),
      (28, 16, 278, 43), (279, 292), 27)
# selection bar = orange plate + blue underline
plate('select_bar', 'item_main_game', [(28.3, 98.6), (315.2, 98.6), (297.8, 142.4), (28.3, 142.4)],
      (28, 98, 317, 143), (36, 101, 246, 138), (250, 290), 28)

cut('cursor_arrow', (9, 107, 27, 134), fill=True)
cut('item_time_attack', (34, 157, 250, 194), edge_fg=BLUE)
cut('item_records', (34, 209, 182, 246), edge_fg=BLUE)
cut('item_options', (34, 262, 178, 304), edge_fg=BLUE)
cut('label_special_stage', (358, 269, 474, 287), flat_fg=BLUE)
cut('button_a', (367, 310, 398, 343), T=60, fill=True)
cut('button_b', (449, 310, 480, 343), T=60, fill=True)
cut('label_select', (397, 316, 441, 337), flat_fg=BLUE)
cut('label_back', (478, 316, 514, 337), flat_fg=BLUE)
# watermark: the mockup cuts the word off on three sides, so the letters are redrawn whole from
# their measured geometry (47 px tall, 13.5 px stems) instead of being cut out of the image
WM_COL = np.array([251, 240, 87.])
WM_H, ST = 47.0, 13.5

def glyph(ch, ss):
    w = dict(S=35, O=37, N=38, I=13.5, C=33, P=37, E=33, D=38, R=38, A=40.5, M=45.5)[ch]
    im = Image.new('L', (int(np.ceil(w * ss)), int(WM_H * ss)), 0)
    d = ImageDraw.Draw(im)
    k = lambda *v: [c * ss for c in v]
    def rr(x0, y0, x1, y1, r=0, corners=(1, 1, 1, 1), fill=255):
        d.rounded_rectangle(k(x0, y0, x1, y1), radius=r * ss, fill=fill, corners=tuple(bool(c) for c in corners))
    def poly(pts, fill=255): d.polygon([tuple(k(*p)) for p in pts], fill=fill)
    if ch == 'O':
        rr(0, 0, w, 47, 7); rr(13.7, 13.3, 23.5, 33.7, 1.5, fill=0)
    elif ch == 'C':
        rr(0, 0, w, 47, 7, (1, 0, 0, 1)); rr(13.7, 13.3, w + 2, 33.7, 1.5, (1, 0, 0, 1), fill=0)
    elif ch == 'S':
        rr(0, 0, w, 47, 7, (1, 0, 1, 0))
        rr(ST, 13.3, w + 9, 17, 0, fill=0); rr(-9, 30, w - ST, 33.7, 0, fill=0)
        # the rounded shoulders where each slot opens
        rr(w - 6, 13.3, w + 1, 23, 0, fill=0); rr(ST, 17, w, 30, 5, (0, 1, 0, 0))
        rr(-1, 24, 6, 33.7, 0, fill=0); rr(0, 17, w - ST, 30, 5, (0, 0, 0, 1))
        rr(ST - 1, 17, w - ST + 1, 30)
    elif ch == 'N':
        rr(0, 0, ST, 47); rr(w - ST + 0.2, 0, w, 47); poly([(2, 0), (17, 0), (37, 47), (22, 47)])
    elif ch == 'I':
        rr(0, 0, w, 47)
    elif ch == 'P':
        rr(0, 0, ST, 47); rr(0, 0, w, 33.6, 7, (0, 1, 1, 0)); rr(14, 13.3, 24, 21, 1, fill=0)
    elif ch == 'E':
        rr(0, 0, w, 47); rr(14.5, 13.3, w + 1, 17.5, fill=0); rr(14.5, 29.5, w + 1, 35.3, fill=0)
        rr(w - 1, 17.5, w + 1, 29.5, fill=0)
    elif ch == 'D':
        rr(0, 0, w, 47, 7, (0, 1, 1, 0)); rr(14, 13.5, 24.5, 33.5, 1.5, fill=0)
    elif ch == 'R':
        rr(0, 0, ST, 47); rr(0, 0, w, 27.8, 7, (0, 1, 0, 0)); rr(0, 10, w, 27.8, 5, (0, 0, 1, 0))
        rr(0, 20, 34.3, 34); rr(24.3, 27.8, w, 47, 5, (0, 1, 0, 0))
        rr(14.5, 13.3, 24, 20.3, 1, fill=0); rr(14.5, 32.4, 23.6, 48, 1, (1, 1, 0, 0), fill=0)
    elif ch == 'A':
        c = w / 2
        poly([(c - 9.3, 0), (c + 9.3, 0), (c + 20.25, 47), (c - 20.25, 47)])
        poly([(c, 15.3), (c + 1.9, 26.8), (c - 1.9, 26.8)], fill=0)
        poly([(c - 4.7, 38.7), (c + 4.7, 38.7), (c + 6.9, 47), (c - 6.9, 47)], fill=0)
    elif ch == 'M':
        c = w / 2
        poly([(0, 0), (18, 0), (c, 22.5), (w - 18, 0), (w, 0), (w, 47), (w - 12.5, 47), (w - 12.5, 27),
              (w - 16.8, 47), (16.8, 47), (12.5, 27), (12.5, 47), (0, 47)])
    return im

# left edge of each letter in mockup pixels (S and the end of M are past the mockup's edges)
WM_X = [('S', -16.5), ('O', 23), ('N', 63.7), ('I', 106.8), ('C', 124.8), ('P', 175.8), ('I', 216.5), ('P', 233.8),
        ('E', 274.8), ('D', 323.8), ('R', 365.8), ('E', 407.8), ('A', 442.4), ('M', 486)]
WM_X0, WM_Y0 = -17, 344
for scale, nm in ((1, 'watermark_text'), (2, 'watermark_text_2x')):
    ss = 8
    big = Image.new('L', (int(552 * ss), int(WM_H * ss)), 0)
    for ch, x in WM_X:
        g = glyph(ch, ss)
        big.paste(255, (int(round((x - WM_X0) * ss)), 0), g)
    al = np.array(big.resize((552 * scale, int(WM_H) * scale), Image.BOX)).astype(float) / 255
    if scale == 1:
        save(nm, np.broadcast_to(WM_COL, al.shape + (3,)), al, WM_X0, WM_Y0,
             note='redrawn whole; runs past the mockup edges (x < 0, bottom below 386)')
        seen = project(src[WM_Y0:H], bgrow[WM_Y0:H, None, :], WM_COL)
        mine = al[:H - WM_Y0, -WM_X0:-WM_X0 + W]
        print('watermark redraw vs mockup, mean alpha error: %.3f' % np.abs(seen - mine)[:, 6:].mean())
        Image.fromarray(np.dstack([seen, (seen + mine) / 2, mine]).__mul__(255).astype(np.uint8)).resize(
            (W * 3, (H - WM_Y0) * 3), Image.NEAREST).save(os.path.join(OUT, '_watermark_check.png'))
    else:
        Image.fromarray(np.dstack([np.broadcast_to(WM_COL, al.shape + (3,)), al * 255]).round().astype(np.uint8)).save(
            os.path.join(OUT, nm + '.png'))

# preview: locate the blue frame, split border and picture
reg = src[90:275, 325:510]
isblue = np.linalg.norm(reg - np.array([10, 40, 190.]), axis=2) < 70
cols = np.where(isblue.sum(0) > 100)[0] + 325
rws = np.where(isblue.sum(1) > 100)[0] + 90
fx0, fx1, fy0, fy1 = cols.min(), cols.max() + 1, rws.min(), rws.max() + 1
print('preview frame', fx0, fy0, fx1, fy1, 'border cols', cols, 'rows', rws)
BW = 3
fcol = np.median(src[fy0:fy1, fx0 + 1], axis=0)
ob = (fx0 - 1, fy0 - 1, fx1 + 1, fy1 + 1)                  # one soft pixel outside the border
fr = src[ob[1]:ob[3], ob[0]:ob[2]]
a = project(fr, bgrow[ob[1]:ob[3], None, :], fcol)         # only the outer ring keeps this
a[1:-1, 1:-1] = 1; a[1 + BW:-1 - BW, 1 + BW:-1 - BW] = 0
a[a < 0.1] = 0
save('preview_frame', np.broadcast_to(fcol, fr.shape), a, ob[0], ob[1])
pic = src[fy0 + BW:fy1 - BW, fx0 + BW:fx1 - BW]
save('preview_picture', pic, np.ones(pic.shape[:2]), fx0 + BW, fy0 + BW)
cut('emerald', (395, 88, 440, fy0 - 2), T=75, fill=True)   # high T: skip its drop shadow

# concentric circles: fitted centre/radii, redrawn whole (the mockup hides most of them)
CX, CY, RAD = 17.5, -30.5, (85.0, 107.0, 121.0, 146.0)
LIGHT, OLIVE = np.array([166, 238, 83.]), np.array([132, 163, 34.])
R = int(RAD[-1]) + 2; ss = 4
yy, xx = (np.mgrid[0:2 * R * ss, 0:2 * R * ss] + 0.5) / ss - R
band = np.searchsorted(RAD, np.hypot(xx, yy))
colr = np.where((band % 2 == 0)[..., None], LIGHT, OLIVE) * (band < 4)[..., None]
ds = lambda m: m.reshape(2 * R, ss, 2 * R, ss, -1).mean((1, 3))
al = ds((band < 4).astype(float))[..., 0]
save('bg_circles', ds(colr) / np.maximum(al, 1e-6)[..., None], al, round(CX) - R, round(CY) - R,
     note='full disc; centre at (%.1f, %.1f) in the mockup' % (CX, CY))

# background scanlines: a one-period tile, plus the full-height strip
Image.fromarray(np.repeat(bgrow[:, None, :], 8, axis=1).round().astype(np.uint8)).save(
    os.path.join(OUT, 'bg_scanlines_full.png'))
t0 = 200 - 200 % PERIOD
Image.fromarray(np.repeat(bgrow[t0:t0 + PERIOD, None, :], 8, axis=1).round().astype(np.uint8)).save(
    os.path.join(OUT, 'bg_scanlines_tile.png'))
print('scanline period', PERIOD)

json.dump(dict(reference_size=[W, H], panel_top=PANEL_TOP, parts=layout),
          open(os.path.join(OUT, 'layout.json'), 'w'), indent=1)

# ---- check: rebuild the mockup from the parts ----------------------------
order = ['bg_circles', 'watermark_text', 'title_banner', 'title_text', 'select_bar', 'item_main_game',
         'cursor_arrow', 'item_time_attack', 'item_records', 'item_options', 'preview_picture', 'preview_frame',
         'emerald', 'label_special_stage', 'button_a', 'label_select', 'button_b', 'label_back']
assert sorted(order) == sorted(l['name'] for l in layout), set(order) ^ set(l['name'] for l in layout)
canvas = Image.fromarray(np.repeat(bgrow[:, None, :], W, axis=1).round().astype(np.uint8)).convert('RGBA')
pos = {l['name']: l for l in layout}
for n in order:
    im = Image.open(os.path.join(OUT, n + '.png'))
    sx, sy = max(-pos[n]['x'], 0), max(-pos[n]['y'], 0)
    dx, dy = max(pos[n]['x'], 0), max(pos[n]['y'], 0)
    canvas.alpha_composite(im.crop((sx, sy, min(im.width, sx + W - dx), min(im.height, sy + H - dy))), (dx, dy))
canvas.convert('RGB').save(os.path.join(OUT, '_recomposed.png'))
diff = np.abs(np.array(canvas.convert('RGB')).astype(float) - src)[PANEL_TOP:].mean()
print('mean abs difference below the fake-transparency rows: %.2f / 255' % diff)

# contact sheet on a dark checker so the alpha edges can be inspected
ims = [Image.open(os.path.join(OUT, l['name'] + '.png')) for l in layout]
SC = 3; pad = 10; sw = 1000; x = y = pad; rh = 0; places = []
for im in ims:
    w, h = im.width * SC, im.height * SC
    if w > sw - 2 * pad: w, h = im.width, im.height
    if x + w > sw - pad: x = pad; y += rh + pad; rh = 0
    places.append((x, y, w, h)); x += w + pad; rh = max(rh, h)
sheet = Image.new('RGBA', (sw, y + rh + pad))
d = ImageDraw.Draw(sheet)
for cy in range(0, sheet.height, 16):
    for cx in range(0, sw, 16):
        d.rectangle([cx, cy, cx + 15, cy + 15], fill=(40, 40, 60, 255) if (cx + cy) // 16 % 2 else (70, 70, 95, 255))
for im, (x, y, w, h) in zip(ims, places):
    sheet.alpha_composite(im.resize((w, h), Image.NEAREST), (x, y))
sheet.save(os.path.join(OUT, '_contact_sheet.png'))
