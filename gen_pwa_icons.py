"""One-off generator for PWA icons — pixel-heart logo on dark brand background.
Run: .venv/bin/python gen_pwa_icons.py  (safe to delete afterwards)
"""
from PIL import Image, ImageDraw

# Pixel-heart pattern (5x5 grid) mirrored from gamebeat-favicon.svg
PATTERN = {0: [1, 3], 1: [0, 1, 2, 3, 4], 2: [0, 1, 2, 3, 4], 3: [1, 2, 3], 4: [2]}
HIGHLIGHT = {1: [1, 3]}

PURPLE = (139, 92, 246)        # #8b5cf6  brand
PURPLE_LIGHT = (192, 132, 252) # #c084fc
PURPLE_DARK = (91, 33, 182)    # #5b21b6
BG = (22, 22, 30)              # #16161e  --bg-void


def make_icon(size, maskable=False):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if maskable:
        d.rectangle([0, 0, size, size], fill=BG)   # full bleed; OS applies mask
        scale = 0.52
    else:
        r = int(size * 0.18)
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=BG)
        scale = 0.64

    grid = 5
    heart_px = size * scale
    cell = heart_px / (grid + (grid - 1) * 0.25)
    gap = cell * 0.25
    stride = cell + gap
    total = grid * cell + (grid - 1) * gap
    ox = oy = (size - total) / 2
    rad = max(2, int(cell * 0.18))

    for row, cols in PATTERN.items():
        for c in cols:
            color = PURPLE
            if row in HIGHLIGHT and c in HIGHLIGHT[row]:
                color = PURPLE_LIGHT
            if row == 4:
                color = PURPLE_DARK
            x0 = ox + c * stride
            y0 = oy + row * stride
            d.rounded_rectangle([x0, y0, x0 + cell, y0 + cell], radius=rad, fill=color)
    return img


targets = [
    ("static/images/icon-192.png", 192, False),
    ("static/images/icon-512.png", 512, False),
    ("static/images/icon-512-maskable.png", 512, True),
    ("static/images/apple-touch-icon.png", 180, False),
]
for path, size, maskable in targets:
    make_icon(size, maskable).save(path)
    print("wrote", path)
