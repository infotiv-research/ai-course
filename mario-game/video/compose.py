# Compose 1280x720 video frames: feature list on the left, the game (3x, pixel-sharp) on the right.
# usage: python3 compose.py rawframesdir composeddir   (build.sh runs this)
import sys, glob, os, shutil
from PIL import Image, ImageDraw, ImageFont

src, dst = sys.argv[1], sys.argv[2]
shutil.rmtree(dst, ignore_errors=True); os.makedirs(dst)

SCENES = [
    ("banana",   "Banana boomerang", "X", "Flies out, swings back and passes\nthrough every enemy on the way."),
    ("dynamite", "Dynamite",         "C", "Lobbed in an arc, then the blast\nclears everything around it."),
    ("wings",    "Wings",            "F", "Hold to fly, let go to glide."),
    ("umbrella", "Bombers & umbrella", "U", "Swat a falling bomb back\nat the enemies."),
    ("laser",    "Laser",            "L", "One beam clears the whole line.\nCosts the full KI meter."),
]
D = "/usr/share/fonts/truetype/dejavu/"
f_brand = ImageFont.truetype(D + "DejaVuSansMono-Bold.ttf", 22)
f_item  = ImageFont.truetype(D + "DejaVuSans-Bold.ttf", 30)
f_key   = ImageFont.truetype(D + "DejaVuSansMono-Bold.ttf", 26)
f_desc  = ImageFont.truetype(D + "DejaVuSans.ttf", 22)

BG, PANEL_W = (11, 11, 16), 512
GOLD, WHITE, DIM, MUTED = (252, 216, 0), (240, 240, 245), (90, 90, 108), (150, 150, 172)
KEY_BG, KEY_LINE = (24, 24, 34), (60, 60, 80)
HOLD_END = 18          # extra frames held on the last image of each scene

def panel(active):
    im = Image.new("RGB", (1280, 720), BG)
    d = ImageDraw.Draw(im)
    d.text((56, 56), "SUPER MARIO++  ·  NEW FEATURES", font=f_brand, fill=GOLD)
    y = 120
    for i, (_, title, key, desc) in enumerate(SCENES):
        on = i == active
        # keycap
        d.rounded_rectangle((56, y, 56 + 44, y + 44), radius=7, fill=KEY_BG,
                            outline=GOLD if on else KEY_LINE, width=2)
        kw = d.textlength(key, font=f_key)
        d.text((56 + 22 - kw / 2, y + 7), key, font=f_key, fill=GOLD if on else DIM)
        d.text((120, y + 5), title, font=f_item, fill=WHITE if on else DIM)
        y += 64
        if on:
            d.multiline_text((120, y - 8), desc, font=f_desc, fill=MUTED, spacing=8)
            y += 70
    return im

n = 0
for i, (name, *_ ) in enumerate(SCENES):
    base = panel(i)
    frames = sorted(glob.glob(f"{src}/{name}/*.png"))
    for j, f in enumerate(frames):
        im = base.copy()
        im.paste(Image.open(f).convert("RGB").resize((768, 720), Image.NEAREST), (PANEL_W, 0))
        for _ in range(1 + (HOLD_END if j == len(frames) - 1 else 0)):
            im.save(f"{dst}/{n:05d}.png"); n += 1
print(n, "frames")
