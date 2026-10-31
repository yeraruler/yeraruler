"""
Builds the white / minimal profile assets:
  assets/matrix-portrait.svg   code-glyph portrait (ink on white)
  assets/header.svg            name + role card
  assets/terminal.svg          "whoami" card

usage: python tools/build_assets.py PHOTO tools/fonts assets
FONT_DIR must contain the fontsource woff2 files:
  jetbrains-mono-latin-400-normal.woff2, jetbrains-mono-latin-700-normal.woff2,
  inter-latin-600-normal.woff2, inter-latin-700-normal.woff2
"""
import base64, os, random, sys
import cv2
import numpy as np
from PIL import Image, ImageFilter
from xml.sax.saxutils import escape

PHOTO, FONTS, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
random.seed(5)


def b64(name):
    with open(os.path.join(FONTS, name), "rb") as f:
        return base64.b64encode(f.read()).decode()


def font_css(jbm=(400,), inter=()):
    css = []
    for w in jbm:
        css.append("@font-face{font-family:'JBM';font-weight:%d;src:url(data:font/woff2;base64,%s) format('woff2');}"
                   % (w, b64(f"jetbrains-mono-latin-{w}-normal.woff2")))
    for w in inter:
        css.append("@font-face{font-family:'Inter';font-weight:%d;src:url(data:font/woff2;base64,%s) format('woff2');}"
                   % (w, b64(f"inter-latin-{w}-normal.woff2")))
    return "".join(css)


MONO = "'JBM','JetBrains Mono','SFMono-Regular',Consolas,monospace"
SANS = "'Inter','Segoe UI',Helvetica,Arial,sans-serif"

# =============================================================================
# 1. PORTRAIT  (ink on white, ASCII code glyphs only so the embedded font covers all of them)
# =============================================================================
raw = Image.open(PHOTO).convert("RGB").crop((110, 130, 1440, 2060))
rgb = np.array(raw)

hsv = np.array(raw.convert("HSV")).astype(float) / 255
wall = (hsv[..., 2] > 0.62) & (hsv[..., 1] < 0.16)
mask = Image.fromarray(((~wall) * 255).astype("uint8"))
mask = (mask.filter(ImageFilter.MedianFilter(15)).filter(ImageFilter.MaxFilter(9))
            .filter(ImageFilter.MinFilter(9)).filter(ImageFilter.GaussianBlur(2)))
mask = np.array(mask).astype(np.float32) / 255
_bin = (mask > 0.5).astype("uint8")
_n, _lab, _st, _ = cv2.connectedComponentsWithStats(_bin, connectivity=8)
_big = 1 + int(np.argmax(_st[1:, cv2.CC_STAT_AREA]))
_keep = cv2.morphologyEx((_lab == _big).astype("uint8"), cv2.MORPH_OPEN, np.ones((25, 25), np.uint8))
_keep = cv2.morphologyEx(_keep, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
mask = cv2.GaussianBlur(_keep.astype(np.float32), (0, 0), 2)

gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
gray = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(6, 6)).apply(gray).astype(np.float32)
sel = gray[mask > 0.5]
lo, hi = np.percentile(sel, 2), np.percentile(sel, 99.5)
t = np.clip((gray - lo) / (hi - lo), 0, 1)
t = np.clip(t, 0, 1) ** 1.55                      # darken mid-tones so skin keeps visible ink
t = cv2.GaussianBlur(t, (0, 0), 1.0)
t = np.clip(cv2.addWeighted(t, 2.3, cv2.GaussianBlur(t, (0, 0), 5), -1.3, 0.0), 0, 1)
ink = 1.0 - t                                            # dark = more ink

edge = cv2.GaussianBlur(cv2.Canny((mask * 255).astype("uint8"), 50, 150).astype(np.float32), (0, 0), 6)
edge = np.clip(edge / max(edge.max(), 1e-6) * 2.0, 0, 1)

COLS = 140
CW = 6.0
FS = CW / 0.6                    # JetBrains Mono advance = 0.6em  -> glyphs sit exactly on the grid
CH = 12.0
h, w = ink.shape
ROWS = int(COLS * h / w * (CW / CH))
rs = lambda a: cv2.resize(a, (COLS, ROWS), interpolation=cv2.INTER_AREA)
I, M, E = rs(ink), rs(mask), rs(edge)
W, H = int(COLS * CW), int(ROWS * CH)

RAMP = [".", ",", ":;", "il1", "+=", "/\\", "{}[]", "0O8", "#$", "&@%W"]
NL = len(RAMP)

rows = []
for y in range(ROWS):
    spans, run_cls, run = [], None, ""
    for x in range(COLS):
        if M[y, x] < 0.5:
            ch, cls = " ", None
        else:
            v = 0.30 + 0.70 * float(I[y, x]) ** 0.9
            v = min(1.0, v + 0.30 * float(E[y, x]))
            lvl = min(NL - 1, int(v * NL))
            ch, cls = escape(random.choice(RAMP[lvl])), f"k{lvl}"
        if cls == run_cls:
            run += ch
        else:
            if run:
                spans.append(f'<tspan class="{run_cls}">{run}</tspan>' if run_cls else run)
            run_cls, run = cls, ch
    if run:
        spans.append(f'<tspan class="{run_cls}">{run}</tspan>' if run_cls else run)
    rows.append(f'<text x="0" y="{(y+1)*CH - 2.2:.1f}" xml:space="preserve">{"".join(spans)}</text>')

greys = ["#c9c9c9", "#b4b4b4", "#9a9a9a", "#818181", "#686868", "#505050", "#3a3a3a", "#262626", "#161616", "#050505"]
cls_css = "".join(f".k{i}{{fill:{c}}}" for i, c in enumerate(greys))

portrait = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Portrait of Yerasyl Amirtay drawn with code characters">
<defs>
<linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".85"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
</defs>
<style>
{font_css((400,))}
text{{font-family:{MONO};font-size:{FS:.2f}px;font-weight:400;font-variant-ligatures:none;font-feature-settings:"liga" 0,"calt" 0;}}
{cls_css}
</style>
<rect width="{W}" height="{H}" fill="#ffffff"/>
<g>{"".join(rows)}</g>
</svg>'''
open(os.path.join(OUT, "matrix-portrait.svg"), "w", encoding="utf-8").write(portrait)
print("portrait", COLS, "x", ROWS, len(portrait) // 1024, "KB")

# =============================================================================
# 2. HEADER
# =============================================================================
header = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 210" width="1000" height="210" role="img" aria-label="Yerasyl Amirtay — Software Engineer, Backend, Cybersecurity">
<style>
{font_css((400,), (700,))}
.n{{font-family:{SANS};font-weight:700;font-size:72px;letter-spacing:-2px;fill:#0a0a0a}}
.r{{font-family:{MONO};font-weight:400;font-size:19px;fill:#6b6b6b;font-variant-ligatures:none}}
.c{{animation:b 1.1s steps(1,end) infinite}}
@keyframes b{{0%,49%{{opacity:1}}50%,100%{{opacity:0}}}}
.in{{animation:i .9s ease-out both}}
@keyframes i{{from{{opacity:0;transform:translateY(8px)}}}}
</style>
<rect x=".5" y=".5" width="999" height="209" rx="16" fill="#ffffff" stroke="#e6e6e6"/>
<text class="n in" x="500" y="108" text-anchor="middle">Yerasyl Amirtay</text>
<text class="r in" x="500" y="152" text-anchor="middle" style="animation-delay:.25s" xml:space="preserve">Software Engineer  /  Backend  /  Cybersecurity<tspan class="c" fill="#0a0a0a"> _</tspan></text>
<line x1="470" y1="176" x2="530" y2="176" stroke="#0a0a0a" stroke-width="2"/>
</svg>'''
open(os.path.join(OUT, "header.svg"), "w", encoding="utf-8").write(header)

# =============================================================================
# 3. TERMINAL CARD
# =============================================================================
lines = [
    ("whoami", "Yerasyl Amirtay"),
    ("location", "Aktobe, Kazakhstan"),
    ("education", "AQL IT School, 10th grade"),
    ("focus", "Websites / Apps / Backend / Cybersecurity"),
    ("goal", "Big Tech"),
    ("status", "building / breaking / learning"),
]
y0, step = 78, 62
body = []
for i, (cmd, out) in enumerate(lines):
    y = y0 + i * step
    body.append(
        f'<g class="l" style="animation-delay:{0.15 + i*0.35:.2f}s">'
        f'<text class="p" x="32" y="{y}">$</text><text class="m" x="56" y="{y}">{escape(cmd)}</text>'
        f'<text class="o" x="56" y="{y+26}">{escape(out)}</text></g>')
th = y0 + len(lines) * step + 6
terminal = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 {th}" width="560" height="{th}" role="img" aria-label="whoami: Yerasyl Amirtay, Aktobe Kazakhstan, AQL IT School 10th grade">
<style>
{font_css((400, 700))}
text{{font-family:{MONO};font-size:15px;font-variant-ligatures:none}}
.p{{fill:#9a9a9a}} .m{{fill:#0a0a0a;font-weight:700}} .o{{fill:#4a4a4a}}
.l{{animation:s .5s ease-out both}}
@keyframes s{{from{{opacity:0;transform:translateX(-6px)}}}}
.c{{animation:b 1.1s steps(1,end) infinite}}
@keyframes b{{0%,49%{{opacity:1}}50%,100%{{opacity:0}}}}
</style>
<rect x=".5" y=".5" width="559" height="{th-1}" rx="14" fill="#ffffff" stroke="#e6e6e6"/>
<circle cx="30" cy="28" r="4.5" fill="#d9d9d9"/><circle cx="48" cy="28" r="4.5" fill="#d9d9d9"/><circle cx="66" cy="28" r="4.5" fill="#d9d9d9"/>
{"".join(body)}
<rect class="c" x="32" y="{y0 + len(lines)*step - 14}" width="9" height="17" fill="#0a0a0a"/>
</svg>'''
open(os.path.join(OUT, "terminal.svg"), "w", encoding="utf-8").write(terminal)
print("ok")
