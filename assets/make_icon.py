"""Renders the Lut icon: "lut" in a heavy grotesk with a before/after wipe, on the same tile as Dwn and Tag.
Left of the lime handle the letters are white (the original); right of it they're lime (graded).
    python assets/make_icon.py        (writes icon.png, icon.ico, AppIcon.icns and docs/icon-256.png)
Needs Pillow and the Inter Display Black font (https://rsms.me/inter/); pass a font path to override.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = sys.argv[1] if len(sys.argv) > 1 else "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
LIME = (204, 255, 77, 255)
S = 1024
X0, Y0, X1, Y1 = 70, 67, 954, 951   # tile bounds, same as the Tag icon
R = 200


def tile():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((X0, Y0, X1, Y1), R, fill=255)
    grad = Image.new("RGBA", (S, S))
    d = ImageDraw.Draw(grad)
    for y in range(S):
        t = min(1, max(0, (y - Y0) / (Y1 - Y0)))
        c = round(43 + (18 - 43) * t)
        d.line([(0, y), (S, y)], fill=(c, c, c + 2, 255))
    img.paste(grad, (0, 0), mask)
    ImageDraw.Draw(img).rounded_rectangle((X0, Y0, X1, Y1), R, outline=(255, 255, 255, 36), width=4)
    # soft drop shadow underneath
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((X0, Y0 + 14, X1, Y1 + 14), R, fill=(0, 0, 0, 90))
    from PIL import ImageFilter

    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    return Image.alpha_composite(shadow, img)


def mark(img):
    size = 420
    font = ImageFont.truetype(FONT, size)
    kern = -0.055 * size
    widths = [font.getlength(ch) for ch in "lut"]
    total = sum(widths) + kern * 2
    x0 = (S - total) / 2
    asc, _ = font.getmetrics()
    baseline = (Y0 + Y1) / 2 + size * 0.36

    def letters(color):
        layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        x = x0
        for ch, w in zip("lut", widths):
            d.text((x, baseline - asc), ch, font=font, fill=color)
            x += w + kern
        return layer

    wx = x0 + total * 0.57                # the wipe handle, same place as in the app's mark
    line_w, gap = 0.075 * size, 0.045 * size
    top, bottom = baseline - size * 0.77, baseline + size * 0.17
    white, lime = letters((255, 255, 255, 242)), letters(LIME)
    cut = Image.new("L", (S, S), 0)
    ImageDraw.Draw(cut).rectangle((wx, 0, S, S), fill=255)
    graded = Image.composite(lime, white, cut)
    # knock a gap around the handle so it reads as slicing through the letters
    knock = Image.new("L", (S, S), 255)
    ImageDraw.Draw(knock).rounded_rectangle((wx - line_w / 2 - gap, top - gap, wx + line_w / 2 + gap, bottom + gap), line_w, fill=0)
    graded.putalpha(Image.composite(graded.getchannel("A"), Image.new("L", (S, S), 0), knock))
    img = Image.alpha_composite(img, graded)
    ImageDraw.Draw(img).rounded_rectangle((wx - line_w / 2, top, wx + line_w / 2, bottom), line_w / 2, fill=LIME)
    return img


img = mark(tile())
img.save(os.path.join(HERE, "icon.png"))
img.resize((256, 256), Image.LANCZOS).save(os.path.join(HERE, "..", "docs", "icon-256.png"))
img.save(os.path.join(HERE, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.save(os.path.join(HERE, "AppIcon.icns"))
print("icons written")
