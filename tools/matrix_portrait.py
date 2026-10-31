import random, sys
import numpy as np
import cv2
from PIL import Image, ImageFilter
from xml.sax.saxutils import escape

SRC, OUT = sys.argv[1], sys.argv[2]
random.seed(11)

# ---- crop: head + shoulders -------------------------------------------------
raw = Image.open(SRC).convert("RGB").crop((110, 130, 1440, 2060))
rgb = np.array(raw)

# ---- subject mask (wall is bright + unsaturated) ----------------------------
hsv = np.array(raw.convert("HSV")).astype(float) / 255
wall = (hsv[..., 2] > 0.62) & (hsv[..., 1] < 0.16)
mask = Image.fromarray(((~wall) * 255).astype("uint8"))
mask = (mask.filter(ImageFilter.MedianFilter(15)).filter(ImageFilter.MaxFilter(9))
            .filter(ImageFilter.MinFilter(9)).filter(ImageFilter.GaussianBlur(2)))
mask = np.array(mask).astype(np.float32) / 255

# ---- tone: stretch contrast over the subject only, S-curve for depth --------
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
gray = cv2.createCLAHE(clipLimit=1.4, tileGridSize=(6, 6)).apply(gray.astype("uint8")).astype(np.float32)
sel = gray[mask > 0.5]
lo, hi = np.percentile(sel, 3), np.percentile(sel, 99)
t = np.clip((gray - lo) / (hi - lo), 0, 1)
t = t * t * (3 - 2 * t)                      # smoothstep S-curve
t = cv2.GaussianBlur(t, (0, 0), 1.0)
tone = np.clip(cv2.addWeighted(t, 2.3, cv2.GaussianBlur(t, (0, 0), 5), -1.3, 0.05), 0, 1)

# rim light on the silhouette
edge = cv2.GaussianBlur(cv2.Canny((mask * 255).astype("uint8"), 50, 150).astype(np.float32), (0, 0), 7)
edge = np.clip(edge / edge.max() * 2.2, 0, 1)

# ---- grid -------------------------------------------------------------------
COLS = 150
CW, CH = 6.0, 9.0
h, w = tone.shape
ROWS = int(COLS * h / w * (CW / CH))
def rs(a): return cv2.resize(a, (COLS, ROWS), interpolation=cv2.INTER_AREA)
T, M, E = rs(tone), rs(mask), rs(edge)
W, H = int(COLS * CW), int(ROWS * CH)

# glyph ramps: dark -> bright. Shape density carries the brightness, colour reinforces it.
RAMPS = [
    list(".'`,:"),
    list(";:ｰ-+ﾆ"),
    list("ｱｲｳｵ1ｸ7ﾄ=*"),
    list("ｻｼｽ0ﾊﾋ2ﾀ3ﾁ%"),
    list("01#$&8ﾎﾓ@W"),
]
def pick(level):
    return escape(random.choice(RAMPS[level]))

rows_svg = []
for y in range(ROWS):
    spans = []
    for x in range(COLS):
        m = M[y, x]
        if m < 0.5:
            spans.append(" "); continue
        v = 0.14 + 0.86 * float(T[y, x]) ** 0.85
        v = min(1.0, v + 0.30 * float(E[y, x]))
        lvl = min(4, int(v * 5))
        spans.append(f'<tspan class="c{lvl+1}">{pick(lvl)}</tspan>')
    rows_svg.append(f'<text x="0" y="{(y+1)*CH:.1f}" class="r r{y%6}" xml:space="preserve">{"".join(spans)}</text>')

# ---- background code rain ---------------------------------------------------
RAIN = list("01ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄ{}[]<>/=+*#")
rain = []
for i in range(70):
    x = random.randint(0, COLS - 1) * CW
    n = random.randint(12, 30)
    dur = random.uniform(5, 12)
    delay = -random.uniform(0, dur)
    chars = "".join(f'<tspan x="{x:.0f}" dy="{CH:.0f}">{escape(random.choice(RAIN))}</tspan>' for _ in range(n))
    head = f'<tspan x="{x:.0f}" dy="{CH:.0f}" class="hd">{escape(random.choice(RAIN))}</tspan>'
    rain.append(f'<g class="rain" style="animation-duration:{dur:.1f}s;animation-delay:{delay:.1f}s">'
                f'<text x="{x:.0f}" y="-{n*CH:.0f}">{chars}{head}</text></g>')

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Matrix-style portrait of Yerasyl Amirtay">
<defs>
  <linearGradient id="scan" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#b6ffcf" stop-opacity="0"/>
    <stop offset="0.5" stop-color="#b6ffcf" stop-opacity="0.20"/>
    <stop offset="1" stop-color="#b6ffcf" stop-opacity="0"/>
  </linearGradient>
  <radialGradient id="vig" cx="50%" cy="44%" r="72%">
    <stop offset="0.6" stop-color="#000" stop-opacity="0"/>
    <stop offset="1" stop-color="#000" stop-opacity="0.92"/>
  </radialGradient>
  <clipPath id="clip"><rect width="{W}" height="{H}"/></clipPath>
</defs>
<style>
  text {{ font-family: "Courier New","DejaVu Sans Mono",monospace; font-size: {CH-1.2:.1f}px; }}
  .bg {{ fill: #010603; }}
  .c1 {{ fill: #0e7a26; }}
  .c2 {{ fill: #18a63c; }}
  .c3 {{ fill: #2be05a; }}
  .c4 {{ fill: #7dffa0; }}
  .c5 {{ fill: #eafff0; }}
  .rain text {{ fill: #0c7a24; opacity: .5; }}
  .rain .hd {{ fill: #9dffb8; }}
  .rain {{ animation: fall linear infinite; }}
  @keyframes fall {{ from {{ transform: translateY(0); }} to {{ transform: translateY({H + 400}px); }} }}
  .r {{ animation: flick 4s steps(2,end) infinite; }}
  .r1 {{ animation-delay:-.7s; }} .r2 {{ animation-delay:-1.4s; }} .r3 {{ animation-delay:-2.1s; }}
  .r4 {{ animation-delay:-2.8s; }} .r5 {{ animation-delay:-3.4s; }}
  @keyframes flick {{ 0%,92%,100% {{ opacity:1; }} 94% {{ opacity:.7; }} 97% {{ opacity:.88; }} }}
  .sweep {{ animation: sweep 5.5s ease-in-out infinite; }}
  @keyframes sweep {{ from {{ transform: translateY(-120px); }} to {{ transform: translateY({H}px); }} }}
</style>
<rect class="bg" width="{W}" height="{H}"/>
<g clip-path="url(#clip)">
  <g>{"".join(rain)}</g>
  <g>{"".join(rows_svg)}</g>
  <rect class="sweep" width="{W}" height="120" fill="url(#scan)"/>
  <rect width="{W}" height="{H}" fill="url(#vig)"/>
</g>
</svg>'''
open(OUT, "w", encoding="utf-8").write(svg)
print("rows", ROWS, "size", W, H, "bytes", len(svg))
