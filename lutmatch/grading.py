"""Small, bounded finishing adjustments applied after the match.

These are the only knobs the Claude refine step can turn, so whatever it asks
for stays a normal, smooth grade that bakes cleanly into the .cube.
All work happens in OKLab on Rec.709 code values.
"""

import numpy as np

# name: (low, high, neutral, what it does) -- the description is shown to Claude.
FIELDS = {
    "exposure": (-1.0, 1.0, 0.0, "overall brightness in stops"),
    "contrast": (-0.5, 0.5, 0.0, "contrast around mid grey; + is punchier"),
    "shadows": (-0.3, 0.3, 0.0, "lift (+) or crush (-) the shadows"),
    "highlights": (-0.3, 0.3, 0.0, "brighten (+) or pull down (-) the highlights"),
    "temperature": (-1.0, 1.0, 0.0, "white balance; + is warmer/orange, - cooler/blue"),
    "tint": (-1.0, 1.0, 0.0, "+ is more magenta, - more green"),
    "saturation": (0.5, 1.5, 1.0, "colour intensity multiplier"),
    "shadow_warmth": (-1.0, 1.0, 0.0, "split tone: + warms shadows, - pushes them teal"),
    "highlight_warmth": (-1.0, 1.0, 0.0, "split tone: + warms highlights, - cools them"),
    "skin_protect": (0.0, 1.0, 0.0, "how much to hold skin tones near their matched hue"),
}

_TEMP = 0.03      # OKLab b shift at temperature 1
_TINT = 0.03      # OKLab a shift at tint 1
_SPLIT = 0.025


def _srgb_to_lab(rgb):
    from .core import rgb_to_oklab
    return rgb_to_oklab(rgb)


def _lab_to_srgb(lab):
    from .core import oklab_to_rgb
    return oklab_to_rgb(lab)


class Adjust(object):
    def __init__(self, **kw):
        for k, (lo, hi, neutral, _) in FIELDS.items():
            v = kw.get(k, neutral)
            try:
                v = float(v)
            except (TypeError, ValueError):
                v = neutral
            if not np.isfinite(v):
                v = neutral
            setattr(self, k, float(min(hi, max(lo, v))))

    def to_dict(self):
        return {k: round(getattr(self, k), 3) for k in FIELDS}

    def is_neutral(self):
        return all(abs(getattr(self, k) - FIELDS[k][2]) < 1e-4 for k in FIELDS)

    def apply(self, rgb):
        """Rec.709 code values (..., 3) -> adjusted code values."""
        if self.is_neutral():
            return rgb
        shape = rgb.shape
        x = np.asarray(rgb, np.float64).reshape(-1, 3)
        lab = _srgb_to_lab(x)
        before = lab.copy()
        L, a, b = lab[:, 0], lab[:, 1], lab[:, 2]

        # Exposure: scale linear light, which in OKLab L is ~ a cube-root scale.
        L = L * (2.0 ** self.exposure) ** (1 / 3.0)
        # Contrast: S-shaped about mid grey (L ~ 0.6), soft at the ends.
        mid = 0.6
        L = mid + (L - mid) * (1 + self.contrast)
        # Shadows / highlights: weighted lifts that fade out across the range.
        ws = np.clip(1 - L / mid, 0, 1) ** 2
        wh = np.clip((L - mid) / (1 - mid), 0, 1) ** 2
        L = L + self.shadows * 0.25 * ws + self.highlights * 0.25 * wh

        # Colour balance and split toning.
        Lc = np.clip(L, 0, 1)
        b = b + self.temperature * _TEMP + self.shadow_warmth * _SPLIT * (1 - Lc) ** 2 \
            + self.highlight_warmth * _SPLIT * Lc ** 2
        a = a + self.tint * _TINT + 0.3 * (self.shadow_warmth * _SPLIT * (1 - Lc) ** 2
                                           + self.highlight_warmth * _SPLIT * Lc ** 2)
        a, b = a * self.saturation, b * self.saturation
        out = np.stack([L, a, b], axis=1)

        if self.skin_protect > 0:
            # Skin sits in a narrow hue band (~ 30-70 deg in OKLab). Pull those
            # pixels' hue back toward where the match put them.
            hue = np.degrees(np.arctan2(before[:, 2], before[:, 1]))
            chroma = np.hypot(before[:, 1], before[:, 2])
            w = np.clip(1 - np.abs(hue - 50) / 25, 0, 1) * np.clip(chroma / 0.04, 0, 1)
            w = w * self.skin_protect
            c_new = np.hypot(out[:, 1], out[:, 2])
            h_old = np.arctan2(before[:, 2], before[:, 1])
            h_new = np.arctan2(out[:, 2], out[:, 1])
            dh = np.angle(np.exp(1j * (h_old - h_new)))
            h = h_new + dh * w
            out[:, 1], out[:, 2] = c_new * np.cos(h), c_new * np.sin(h)

        return _lab_to_srgb(out).reshape(shape)
