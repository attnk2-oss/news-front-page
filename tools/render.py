#!/usr/bin/env python3
"""Render the one-day world news front page, 1024x1024, as a whole PNG.

This draws the image; it is not shipped to the sandbox. `main.py` in the repo
root copies the resulting entry.png, because the sandbox has no Pillow.

Two rules shape the drawing code:

  * Every illustration is painted on its own canvas and pasted, so a stroke can
    never spill into the text below it.
  * Each band is placed after the tallest content above it, so text is clipped
    by the layout author, not by the canvas edge.

The world map is drawn from coarse coastline rings in an equirectangular
projection. The nine numbered pins are the lead story plus the eight cards, in
reading order, so the map matches the page above it.

Usage:
    python3 tools/render.py [DATA_JSON] [OUT_PNG]

Both arguments are optional and default to data/2026-11-17.json and entry.png
at the repository root, so a bare `python3 tools/render.py` redraws the entry.
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

W = H = 1024
PAPER = (245, 242, 235)
INK = (24, 24, 26)
NAVY = (17, 35, 60)
GOLD = (196, 158, 72)
RED = (154, 52, 44)
MUTED = (104, 100, 92)
RULE = (204, 198, 186)
CARD = (237, 233, 223)
SEA = (218, 228, 234)
LAND = (228, 221, 206)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_DATA = os.path.join(ROOT, "data", "2026-11-17.json")
DEFAULT_OUT = os.path.join(ROOT, "entry.png")

# Liberation is what the layout was measured against; the other directories are
# only a fallback for machines that keep the same faces somewhere else.
FONT_DIRS = (
    "/usr/share/fonts/truetype/liberation",
    "/usr/share/fonts/liberation",
    "/usr/share/fonts/liberation-fonts",
)
FONT_FILES = {
    "serif-bold": "LiberationSerif-Bold.ttf",
    "serif": "LiberationSerif-Regular.ttf",
    "sans-bold": "LiberationSans-Bold.ttf",
    "sans": "LiberationSans-Regular.ttf",
    "sans-narrow": "LiberationSansNarrow-Regular.ttf",
}

# coarse coastlines: (lon, lat) rings, equirectangular
LAND_RINGS = [
    [(-168, 65), (-150, 70), (-128, 71), (-100, 72), (-80, 73), (-62, 60), (-55, 47),
     (-70, 42), (-76, 35), (-81, 25), (-97, 26), (-105, 20), (-115, 30), (-125, 40),
     (-130, 55), (-140, 60), (-168, 65)],
    [(-81, 12), (-70, 12), (-60, 10), (-50, 0), (-35, -5), (-38, -22), (-48, -25),
     (-58, -38), (-65, -45), (-72, -52), (-75, -45), (-72, -30), (-70, -18), (-78, -5),
     (-81, 2), (-81, 12)],
    [(-10, 36), (0, 44), (5, 52), (10, 58), (20, 70), (32, 70), (40, 66), (30, 55),
     (28, 45), (20, 40), (12, 38), (0, 37), (-10, 36)],
    [(-17, 15), (-10, 5), (5, 5), (10, 2), (12, -5), (14, -22), (20, -35), (28, -33),
     (35, -22), (40, -15), (43, 0), (50, 10), (43, 12), (35, 15), (32, 30), (20, 32),
     (10, 37), (-5, 36), (-17, 20), (-17, 15)],
    [(30, 70), (60, 75), (100, 78), (140, 74), (160, 70), (170, 64), (150, 58), (140, 50),
     (130, 40), (122, 30), (120, 22), (108, 10), (100, 5), (95, 15), (88, 22), (78, 8),
     (70, 20), (60, 25), (48, 30), (40, 38), (30, 45), (30, 70)],
    [(114, -22), (122, -18), (130, -12), (142, -11), (153, -26), (150, -38), (140, -38),
     (128, -32), (115, -34), (114, -22)],
    [(166, -35), (174, -37), (178, -40), (173, -46), (167, -45), (166, -35)],
]

# lead story first, then the eight cards, in reading order
PINS = [
    (56, 26, "1"), (36, 45, "2"), (-119, 33, "3"), (-104, 40, "4"),
    (-0.1, 51.5, "5"), (114, 22.5, "6"), (130, 34, "7"), (-77, 41, "8"), (22, -3, "9"),
]


class FontBook:
    """Resolve the five faces once, and fail loudly if one is missing."""

    def __init__(self):
        self.paths = {}
        for key, filename in FONT_FILES.items():
            for directory in FONT_DIRS:
                candidate = os.path.join(directory, filename)
                if os.path.isfile(candidate):
                    self.paths[key] = candidate
                    break
            else:
                raise SystemExit(
                    "missing font %s; install liberation fonts or add its "
                    "directory to FONT_DIRS" % filename
                )
        self._cache = {}

    def get(self, key, size):
        cached = self._cache.get((key, size))
        if cached is None:
            cached = ImageFont.truetype(self.paths[key], size)
            self._cache[(key, size)] = cached
        return cached


FONTS = FontBook()


def f(key, size):
    return FONTS.get(key, size)


def wrap(d, text, fnt, max_w):
    out, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if d.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                out.append(cur)
            cur = word
    if cur:
        out.append(cur)
    return out


def tracked(d, xy, text, fnt, fill, spacing):
    """Letter-spaced small caps, as a masthead kicker needs."""
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=fnt, fill=fill)
        x += d.textlength(ch, font=fnt) + spacing


def art_box(w, h, painter):
    """Paint one illustration on its own canvas, then hand it back to paste."""
    img = Image.new("RGB", (w, h), CARD)
    painter(ImageDraw.Draw(img), 0, 0, w, h)
    return img


def p_tanker(d, x, y, w, h):
    sea = int(h * 0.60)
    d.rectangle([x, y + sea, x + w, y + h], fill=(24, 54, 84))
    d.line([x, y + sea, x + w, y + sea], fill=(90, 128, 156), width=3)
    d.polygon([(x + w * .12, y + sea - 18), (x + w * .70, y + sea - 18),
               (x + w * .84, y + sea - 3), (x + w * .08, y + sea - 3)], fill=(212, 210, 204))
    d.rectangle([x + w * .28, y + sea - 35, x + w * .54, y + sea - 18], fill=(174, 176, 172))
    d.rectangle([x + w * .56, y + sea - 30, x + w * .63, y + sea - 18], fill=(174, 176, 172))
    d.rectangle([x + w * .585, y + sea - 53, x + w * .615, y + sea - 30], fill=(118, 120, 118))
    bx, by = x + w * .28, y + sea - 44
    for r, c in ((21, (222, 104, 38)), (14, (240, 166, 60)), (7, (252, 228, 152))):
        d.ellipse([bx - r, by - r, bx + r, by + r], fill=c)
    d.ellipse([x + w * .78, y + sea + 10, x + w * .90, y + sea + 20], outline=(228, 80, 60), width=3)


def p_bridge(d, x, y, w, h):
    deck = int(h * 0.40)
    d.rectangle([x, y + deck, x + w * .38, y + deck + 9], fill=(94, 94, 98))
    d.rectangle([x + w * .64, y + deck, x + w, y + deck + 9], fill=(94, 94, 98))
    for px in (x + w * .06, x + w * .24, x + w * .72, x + w * .90):
        d.rectangle([px, y + deck + 9, px + 5, y + h * .68], fill=(76, 76, 80))
    d.line([x + w * .38, y + deck + 3, x + w * .64, y + deck + 19], fill=(118, 118, 122), width=4)
    d.rectangle([x, y + h * .68, x + w, y + h], fill=(56, 94, 122))
    for i in range(2):
        yy = y + h * .68 + 7 + i * 8
        d.line([x + 8 + i * 9, yy, x + w - 12 - i * 6, yy], fill=(90, 130, 156), width=2)


def p_chips(d, x, y, w, h):
    s = int(min(w, h) * 0.60)
    cx, cy = x + w * .34, y + h * .50
    d.rectangle([cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2], fill=(28, 58, 42))
    d.rectangle([cx - s / 2 + 7, cy - s / 2 + 7, cx + s / 2 - 7, cy + s / 2 - 7], fill=(58, 120, 82))
    for i in range(4):
        off = -s / 2 + 11 + i * (s - 22) / 3
        d.rectangle([cx + off - 2, cy - s / 2 - 6, cx + off + 2, cy - s / 2], fill=(148, 154, 148))
        d.rectangle([cx + off - 2, cy + s / 2, cx + off + 2, cy + s / 2 + 6], fill=(148, 154, 148))
    for i, bar in enumerate((.30, .52, .74, .98)):
        bx = x + w * .64 + i * 13
        bh = h * .46 * bar
        d.rectangle([bx, y + h * .72 - bh, bx + 7, y + h * .72], fill=(70, 156, 108))


def p_ipo(d, x, y, w, h):
    cx, top = x + w * .38, y + h * .08
    d.pieslice([cx - 32, top, cx + 32, top + 64], 180, 360, fill=(204, 168, 84))
    d.rectangle([cx - 32, top + 32, cx + 32, top + 41], fill=(184, 148, 70))
    d.ellipse([cx - 6, top + 41, cx + 6, top + 52], fill=(146, 118, 56))
    d.polygon([(cx - 19, top + 75), (cx + 19, top + 75), (cx + 10, top + 91), (cx - 10, top + 91)],
              fill=(116, 94, 48))
    d.line([cx + 44, y + h * .70, cx + 96, y + h * .32], fill=(70, 156, 108), width=6)
    d.polygon([(cx + 100, y + h * .26), (cx + 82, y + h * .38), (cx + 104, y + h * .47)],
              fill=(70, 156, 108))


def p_gavel(d, x, y, w, h):
    d.rounded_rectangle([x + w * .12, y + h * .14, x + w * .54, y + h * .84],
                        radius=4, fill=(231, 227, 217), outline=(178, 172, 160), width=2)
    for i in range(5):
        yy = y + h * .26 + i * 11
        d.line([x + w * .18, yy, x + w * .48, yy], fill=(188, 184, 174), width=2)
    d.line([x + w * .17, y + h * .34, x + w * .33, y + h * .56], fill=(194, 72, 58), width=5)
    d.line([x + w * .33, y + h * .34, x + w * .17, y + h * .56], fill=(194, 72, 58), width=5)
    hx, hy = x + w * .70, y + h * .44
    d.rounded_rectangle([hx - 25, hy - 11, hx + 25, hy + 11], radius=4, fill=(124, 88, 56))
    d.line([hx + 21, hy + 8, hx + 44, hy + 33], fill=(124, 88, 56), width=8)


def p_handshake(d, x, y, w, h):
    d.rectangle([x + w * .10, y + h * .06, x + w * .36, y + h * .26], fill=(188, 58, 54))
    d.rectangle([x + w * .64, y + h * .06, x + w * .90, y + h * .26], fill=(210, 178, 78))
    cy = y + h * .56
    d.rounded_rectangle([x + w * .22, cy - 10, x + w * .48, cy + 10], radius=10, fill=(222, 184, 146))
    d.rounded_rectangle([x + w * .42, cy - 10, x + w * .68, cy + 10], radius=10, fill=(198, 160, 124))
    d.line([x + w * .18, y + h * .34, x + w * .82, y + h * .34], fill=(150, 168, 186), width=2)


def p_jet(d, x, y, w, h):
    cy0 = y + h * .44
    for r in (27, 18, 10):
        d.arc([x + w * .60 - r, cy0 - r, x + w * .60 + r, cy0 + r], 150, 330,
              fill=(146, 164, 182), width=2)
    cx, cy = x + w * .30, y + h * .46
    d.polygon([(cx + 46, cy), (cx - 6, cy - 6), (cx - 26, cy - 21), (cx - 16, cy - 3),
               (cx - 44, cy), (cx - 16, cy + 3), (cx - 26, cy + 21), (cx - 6, cy + 6)],
              fill=(54, 58, 66))
    d.line([x + w * .05, y + h * .74, x + w * .95, y + h * .74], fill=(186, 72, 60), width=3)


def p_virus(d, x, y, w, h):
    cx, cy = x + w * .32, y + h * .48
    r = min(w, h) * 0.18
    for i in range(12):
        a = i * math.pi / 6
        d.line([cx + r * .9 * math.cos(a), cy + r * .9 * math.sin(a),
                cx + r * 1.26 * math.cos(a), cy + r * 1.26 * math.sin(a)], fill=(148, 90, 60), width=3)
        d.ellipse([cx + r * 1.26 * math.cos(a) - 4, cy + r * 1.26 * math.sin(a) - 4,
                   cx + r * 1.26 * math.cos(a) + 4, cy + r * 1.26 * math.sin(a) + 4], fill=(148, 90, 60))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(196, 126, 94))
    d.ellipse([cx - r * .45, cy - r * .45, cx + r * .45, cy + r * .45], fill=(166, 98, 70))
    d.line([x + w * .60, y + h * .22, x + w * .84, y + h * .60], fill=(186, 72, 60), width=5)
    d.polygon([(x + w * .86, y + h * .66), (x + w * .73, y + h * .58), (x + w * .86, y + h * .50)],
              fill=(186, 72, 60))


def p_ebola(d, x, y, w, h):
    cx, cy = x + w * .34, y + h * .50
    r = min(w, h) * 0.10
    for i in range(10):
        a = i * math.pi / 5
        d.ellipse([cx + r * 2.4 * math.cos(a) - 4, cy + r * 2.4 * math.sin(a) - 4,
                   cx + r * 2.4 * math.cos(a) + 4, cy + r * 2.4 * math.sin(a) + 4],
                  outline=(198, 168, 120), width=2)
    d.ellipse([cx - r * 1.25, cy - r * 1.25, cx + r * 1.25, cy + r * 1.25], fill=(234, 230, 220))
    d.rectangle([cx - r * .36, cy - r, cx + r * .36, cy + r], fill=(190, 62, 52))
    d.rectangle([cx - r, cy - r * .36, cx + r, cy + r * .36], fill=(190, 62, 52))
    tx = x + w * .70
    d.polygon([(tx, y + h * .24), (tx + 24, y + h * .72), (tx - 24, y + h * .72)],
              outline=(190, 62, 52), width=3)
    d.line([tx, y + h * .36, tx, y + h * .54], fill=(190, 62, 52), width=4)
    d.ellipse([tx - 3, y + h * .58, tx + 3, y + h * .64], fill=(190, 62, 52))


ART = {
    "tanker_mine": p_tanker, "bridge_collapse": p_bridge, "chips_up": p_chips,
    "ipo_bell": p_ipo, "sanctions_gavel": p_gavel, "handshake_flags": p_handshake,
    "jet_intrusion": p_jet, "measles_virus": p_virus, "ebola_cross": p_ebola,
}


def draw_map(img, box, pins):
    x, y, w, h = box
    d = ImageDraw.Draw(img)
    d.rectangle([x, y, x + w, y + h], fill=SEA)
    for ring in LAND_RINGS:
        pts = [(x + (lon + 180) / 360 * w, y + (90 - lat) / 180 * h) for lon, lat in ring]
        d.polygon(pts, fill=LAND, outline=(196, 188, 172))
    d.rectangle([x, y, x + w, y + h], outline=(186, 196, 204))
    fpin = f("sans-bold", 9)
    for lon, lat, label in pins:
        px = x + (lon + 180) / 360 * w
        py = y + (90 - lat) / 180 * h
        d.ellipse([px - 7, py - 7, px + 7, py + 7], fill=RED)
        d.text((px - d.textlength(label, font=fpin) / 2, py - 5), label, font=fpin,
               fill=(255, 252, 246))


def render(data, out_path):
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    m = 42

    # masthead: kicker, edition line, the day, gold rule
    hh = 146
    d.rectangle([0, 0, W, hh], fill=NAVY)
    tracked(d, (m, 19), data["kicker"], f("sans-bold", 14), GOLD, 3.6)
    st = "%d STORIES \u00b7 %d CONTINENTS \u00b7 ONE DAY" % (
        data["stats"]["stories"], data["stats"]["continents"])
    f13 = f("sans-bold", 12)
    sw = sum(d.textlength(c, font=f13) + 2.0 for c in st)
    tracked(d, (W - m - sw, 21), st, f13, (146, 164, 188), 2.0)
    fdate = f("serif-bold", 52)
    dtl = data["date_label"]
    d.text(((W - d.textlength(dtl, font=fdate)) / 2, 50), dtl, font=fdate, fill=(252, 250, 245))
    d.rectangle([0, hh, W, hh + 4], fill=GOLD)

    # lead band: illustration left, then tag, two headline lines, one label
    y = hh + 4 + 12
    lh = 148
    d.rectangle([m, y, W - m, y + lh], fill=(233, 229, 219))
    aw, ah = 214, lh - 18
    img.paste(art_box(aw, ah, ART[data["lead"]["art"]]), (m + 9, y + 9))
    tx = m + 9 + aw + 16
    tracked(d, (tx, y + 12), data["lead"]["tag"], f("sans-bold", 11), RED, 1.6)
    fh = f("serif-bold", 29)
    hy = y + 30
    for line in wrap(d, data["lead"]["headline"], fh, W - m - tx - 10)[:2]:
        d.text((tx, hy), line, font=fh, fill=INK)
        hy += 32
    fl = f("serif", 15)
    for line in wrap(d, data["lead"]["label"], fl, W - m - tx - 10)[:2]:
        d.text((tx, hy + 3), line, font=fl, fill=MUTED)
        hy += 18

    # eight cards, four across and two down
    y += lh + 12
    gap, cw, ch = 11, (W - 2 * m - 11 * 3) // 4, 178
    art_h = 76
    ftag, fhead, flab = f("sans-bold", 8), f("serif-bold", 16), f("sans", 10)
    for i, c in enumerate(data["cards"][:8]):
        cx = m + (i % 4) * (cw + gap)
        cy = y + (i // 4) * (ch + gap)
        d.rectangle([cx, cy, cx + cw, cy + ch], fill=CARD)
        img.paste(art_box(cw, art_h, ART[c["art"]]), (cx, cy))
        d.rectangle([cx, cy + art_h, cx + cw, cy + art_h + 2], fill=NAVY)
        tracked(d, (cx + 7, cy + art_h + 6), c["tag"], ftag, RED, 1.0)
        yy = cy + art_h + 18
        for line in wrap(d, c["headline"], fhead, cw - 14)[:3]:
            d.text((cx + 7, yy), line, font=fhead, fill=INK)
            yy += 17
        for line in wrap(d, c["label"], flab, cw - 14)[:2]:
            d.text((cx + 7, yy), line, font=flab, fill=MUTED)
            yy += 11

    # bottom band: map on the left, twenty one-line stories on the right
    y += 2 * ch + gap + 12
    d.line([m, y, W - m, y], fill=RULE, width=2)
    my = y + 6
    map_w, map_h = 286, 132
    draw_map(img, (m, my + 16, map_w, map_h), PINS)
    tracked(d, (m, my), "WHERE IT HAPPENED", f("sans-bold", 10), NAVY, 1.8)
    d.text((m, my + 16 + map_h + 3), "Pins match the nine stories above.",
           font=f("sans", 8), fill=MUTED)

    dx = m + map_w + 18
    dw = W - m - dx
    tracked(d, (dx, my), "ALSO ON THE DAY", f("sans-bold", 10), NAVY, 1.8)
    fy = my + 16
    fw, ft2 = f("sans-bold", 9), f("sans", 9)
    items = data["also"][:20]
    colw = (dw - 16) // 2
    d.line([dx + colw + 8, fy, dx + colw + 8, fy + 9 * 14 + 8], fill=RULE, width=1)
    for col in range(2):
        col_items = items[col::2]
        lab_w = max((d.textlength(i["where"], font=fw) for i in col_items), default=0)
        for row, a in enumerate(col_items):
            cx = dx + col * (colw + 16)
            cy = fy + row * 14
            d.text((cx, cy), a["where"], font=fw, fill=RED)
            avail = colw - lab_w - 7
            text = a["text"]
            if d.textlength(text, font=ft2) > avail:
                while text and d.textlength(text + "\u2026", font=ft2) > avail:
                    text = text[:-1]
                text = text.rstrip() + "\u2026"
            d.text((cx + lab_w + 7, cy), text, font=ft2, fill=INK)

    # footer: repeat the day in words, then name the sources
    d.line([m, H - 42, W - m, H - 42], fill=RULE, width=2)
    fd = f("serif-bold", 12)
    line1 = "Every story was reported on %s." % data["date_label"].title()
    d.text((m, H - 36), line1, font=fd, fill=INK)
    fs = f("sans-narrow", 10)
    sy = H - 21
    for line in wrap(d, data["sources"], fs, W - 2 * m)[:1]:
        d.text((m, sy), line, font=fs, fill=(126, 120, 110))

    img.save(out_path, "PNG", optimize=True)
    return out_path


def main(argv):
    src = argv[1] if len(argv) > 1 else DEFAULT_DATA
    dst = argv[2] if len(argv) > 2 else DEFAULT_OUT
    with open(src, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    render(data, dst)
    print("wrote %s" % dst)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
