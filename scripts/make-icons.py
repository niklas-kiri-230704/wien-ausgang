#!/usr/bin/env python3
"""Render the app icons (red square, white "U") into icons/. Needs Pillow."""
from PIL import Image, ImageDraw

RED, WHITE = (227, 0, 15), (255, 255, 255)


def icon(size, out):
    s = 4 * size  # supersample, then downscale for smooth edges
    im = Image.new("RGB", (s, s), RED)
    d = ImageDraw.Draw(im)
    # "U" in the middle ~60% so it survives maskable/rounded cropping
    u = s * 0.6 / 16          # 16 design units wide stroke box
    x0, y0 = s / 2 - 8 * u, s / 2 - 9 * u
    w = 3.6 * u               # stroke width
    r = 7 * u                 # bend radius (stroke centre)
    cx, cy = s / 2, y0 + 10 * u
    left, right = cx - r, cx + r
    d.rectangle([left - w / 2, y0, left + w / 2, cy], fill=WHITE)
    d.rectangle([right - w / 2, y0, right + w / 2, cy], fill=WHITE)
    d.arc([cx - r - w / 2, cy - r - w / 2, cx + r + w / 2, cy + r + w / 2], 0, 180, fill=WHITE, width=round(w))
    for x in (left, right):  # round stroke caps on top
        d.ellipse([x - w / 2, y0 - w / 2, x + w / 2, y0 + w / 2], fill=WHITE)
    im.resize((size, size), Image.LANCZOS).save(out)


for size, name in [(180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")]:
    icon(size, f"icons/{name}")
print("icons written")
