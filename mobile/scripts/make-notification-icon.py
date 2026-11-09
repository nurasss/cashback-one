#!/usr/bin/env python3
"""Builds the Android small notification icon (white shape on a transparent background) for a client.

Android uses only the alpha channel of a notification small icon, so the result is a pure-white silhouette with no opaque
square/round backing. For Keremet the silhouette is the white "k" taken from the existing round badge
(clients/keremet/header_badge.png); no new emblem is drawn. Cashback One keeps its existing ONE-coin silhouette, which is
copied (not regenerated) into clients/cashbackone/android/res.

Usage: python3 mobile/scripts/make-notification-icon.py keremet     (needs Pillow and NumPy; does not touch the Android build)
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SIZES = {'mdpi': 24, 'hdpi': 36, 'xhdpi': 48, 'xxhdpi': 72, 'xxxhdpi': 96}
FILL = 20 / 24  # the glyph's height as a share of the canvas (Android keeps small icons inside a 20dp area of 24dp)
SUPER = 16


def keremet_mask() -> Image.Image:
    badge = np.array(Image.open(ROOT / 'clients/keremet/header_badge.png').convert('RGBA')).astype(float)
    mn, mx, alpha = badge[..., :3].min(axis=2), badge[..., :3].max(axis=2), badge[..., 3]
    # The letter is the near-white, low-saturation part of the badge; the ornament and rim are saturated red/pink.
    soft = np.clip((mn - 120) / 60, 0, 1) * np.clip((90 - (mx - mn)) / 40, 0, 1) * (alpha > 200)
    mask = Image.fromarray((soft * 255).astype('uint8'), 'L')
    big = mask.resize((mask.width * SUPER, mask.height * SUPER), Image.BICUBIC).filter(ImageFilter.GaussianBlur(SUPER * 0.7))
    return big.point(lambda v: 255 if v >= 128 else 0)  # smooth vector-like contour at high resolution


def render(mask: Image.Image, size: int) -> Image.Image:
    box = mask.getbbox()
    assert box, 'empty mask'
    glyph = mask.crop(box)
    scale = size * SUPER * FILL / glyph.height
    glyph = glyph.resize((max(1, round(glyph.width * scale)), max(1, round(glyph.height * scale))), Image.LANCZOS)
    canvas = Image.new('L', (size * SUPER, size * SUPER), 0)
    canvas.paste(glyph, ((canvas.width - glyph.width) // 2, (canvas.height - glyph.height) // 2))
    alpha = canvas.resize((size, size), Image.LANCZOS)
    out = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    out.putalpha(alpha)
    return out


def main() -> None:
    if sys.argv[1:] != ['keremet']:
        sys.exit('usage: make-notification-icon.py keremet')
    mask = keremet_mask()
    for density, size in SIZES.items():
        target = ROOT / f'clients/keremet/android/res/drawable-{density}/notification_icon.png'
        target.parent.mkdir(parents=True, exist_ok=True)
        render(mask, size).save(target, optimize=True)
        print(target.relative_to(ROOT), size)


if __name__ == '__main__':
    main()
