"""Camera log and HDR input transforms.

Each source turns the code values ffmpeg hands us (0..1 RGB, video range already
expanded) into Rec.709 / sRGB display code values, so log footage is matched as a
normal picture instead of a flat grey one. Curves and gamuts come from the camera
makers' published white papers; nothing here is copied from a vendor LUT.

The path is: code values -> scene-linear (curve) -> Rec.709 linear (gamut
matrix, all D65) -> gentle highlight roll-off -> sRGB code values.
"""

import numpy as np

# name: (label, curve, gamut, input range)
# "legal" means the published curve is written against the stored 10-bit code
# value (64 = black), so we undo ffmpeg's video-range expansion first.
SOURCES = {
    "rec709": ("Rec.709 / normal", None, None, None),
    "slog3": ("Sony S-Log3 (S-Gamut3.Cine)", "slog3", "sgamut3cine", "legal"),
    "vlog": ("Panasonic V-Log", "vlog", "vgamut", "legal"),
    "logc3": ("ARRI LogC3", "logc3", "awg3", "legal"),
    "logc4": ("ARRI LogC4", "logc4", "awg4", "legal"),
    "clog3": ("Canon Log 3", "clog3", "cinema", "full"),
    "nlog": ("Nikon N-Log", "nlog", "rec2020", "legal"),
    "flog": ("Fujifilm F-Log", "flog", "rec2020", "legal"),
    "flog2": ("Fujifilm F-Log2", "flog2", "rec2020", "legal"),
    "applelog": ("Apple Log (iPhone)", "applelog", "rec2020", "legal"),
    "hlg": ("HLG (HDR)", "hlg", "rec2020", "full"),
    "pq": ("PQ / HDR10", "pq", "rec2020", "full"),
}
ORDER = ["rec709", "slog3", "vlog", "logc3", "logc4", "clog3", "nlog", "flog", "flog2", "applelog", "hlg", "pq"]

_PRIMARIES = {
    "rec709": ((0.640, 0.330), (0.300, 0.600), (0.150, 0.060)),
    "rec2020": ((0.708, 0.292), (0.170, 0.797), (0.131, 0.046)),
    "sgamut3cine": ((0.766, 0.275), (0.225, 0.800), (0.089, -0.087)),
    "vgamut": ((0.730, 0.280), (0.165, 0.840), (0.100, -0.030)),
    "awg3": ((0.6840, 0.3130), (0.2210, 0.8480), (0.0861, -0.1020)),
    "awg4": ((0.7347, 0.2653), (0.1424, 0.8576), (0.0991, -0.0308)),
    "cinema": ((0.740, 0.270), (0.170, 1.140), (0.080, -0.100)),
}
_D65 = (0.3127, 0.3290)


def _xyz(xy):
    x, y = xy
    return np.array([x / y, 1.0, (1 - x - y) / y])


def _rgb_to_xyz(name):
    p = np.stack([_xyz(c) for c in _PRIMARIES[name]], axis=1)
    s = np.linalg.solve(p, _xyz(_D65))
    return p * s


def gamut_matrix(name):
    """3x3 matrix taking linear RGB in gamut `name` to linear Rec.709."""
    return np.linalg.inv(_rgb_to_xyz("rec709")) @ _rgb_to_xyz(name)


# --------------------------------------------------------------------------
# Log curves: code value -> scene-linear (0.18 = mid grey)
# --------------------------------------------------------------------------

def _slog3(x):
    return np.where(x >= 171.2102946929 / 1023,
                    10 ** ((x * 1023 - 420) / 261.5) * 0.19 - 0.01,
                    (x * 1023 - 95) * 0.01125 / (171.2102946929 - 95))


def _vlog(x):
    return np.where(x < 0.181, (x - 0.125) / 5.6, 10 ** ((x - 0.598206) / 0.241514) - 0.00873)


def _logc3(x):
    cut, a, b, c, d, e, f = 0.010591, 5.555556, 0.052272, 0.247190, 0.385537, 5.367655, 0.092809
    return np.where(x > e * cut + f, (10 ** ((x - d) / c) - b) / a, (x - f) / e)


def _logc4(x):
    a = (2 ** 18 - 16) / 117.45
    b = (1023 - 95) / 1023
    c = 95 / 1023
    s = (7 * np.log(2) * 2 ** (7 - 14 * c / b)) / (a * b)
    t = (2 ** (14 * (-c / b) + 6) - 64) / a
    return np.where(x >= 0, (2 ** (14 * (x - c) / b + 6) - 64) / a, x * s + t)


def _clog3(x):
    y = np.select([x < 0.04076162, x <= 0.105357102],
                  [-(10 ** ((0.07623209 - x) / 0.42889912) - 1) / 14.98325,
                   (x - 0.073059361) / 2.3069815],
                  (10 ** ((x - 0.069886632) / 0.42889912) - 1) / 14.98325)
    return y * 0.9


def _nlog(x):
    return np.where(x < 452 / 1023, (np.maximum(x, 0) / (650 / 1023)) ** 3 - 0.0075,
                    np.exp((x - 619 / 1023) / (150 / 1023)))


def _flog(x):
    a, b, c, d, e, f = 0.555556, 0.009468, 0.344676, 0.790453, 8.735631, 0.092864
    return np.where(x < 0.100537775223865, (x - f) / e, 10 ** ((x - d) / c) / a - b / a)


def _flog2(x):
    a, b, c, d, e, f = 5.555556, 0.064829, 0.245281, 0.384316, 8.799461, 0.092864
    return np.where(x < 0.100686685370811, (x - f) / e, 10 ** ((x - d) / c) / a - b / a)


def _applelog(x):
    r0, rt, c, b, g, beta = -0.05641088, 0.01, 47.28711236, 0.00964052, 0.08550479, 0.69336945
    pt = c * (rt - r0) ** 2
    return np.where(x >= pt, 2 ** ((x - beta) / g) - b,
                    np.where(x >= 0, np.sqrt(np.maximum(x, 0) / c) + r0, r0))


def _hlg(x):
    a, b, c = 0.17883277, 0.28466892, 0.55991073
    e = np.where(x <= 0.5, x * x / 3, (np.exp((x - c) / a) + b) / 12)
    # HLG reference white (75% signal) lands on scene-linear 0.265; put it at 1.0
    # and mid grey near 0.18 like the log curves.
    return e / 0.265 * 0.9


def _pq(x):
    m1, m2, c1, c2, c3 = 0.1593017578125, 78.84375, 0.8359375, 18.8515625, 18.6875
    p = np.power(np.clip(x, 0, 1), 1 / m2)
    nits = 10000 * np.power(np.maximum(p - c1, 0) / (c2 - c3 * p), 1 / m1)
    return nits / 203.0 * 0.9   # 203 nits = HDR reference white


_CURVES = {"slog3": _slog3, "vlog": _vlog, "logc3": _logc3, "logc4": _logc4, "clog3": _clog3,
           "nlog": _nlog, "flog": _flog, "flog2": _flog2, "applelog": _applelog, "hlg": _hlg, "pq": _pq}


def _rolloff(x, knee=0.62):
    """Identity up to the knee, then a smooth shoulder towards 1 (no hard clip)."""
    over = np.maximum(x - knee, 0)
    return np.where(x <= knee, x, knee + (1 - knee) * (1 - np.exp(-over / (1 - knee))))


def _encode_srgb(lin):
    c = np.clip(lin, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def to_display(rgb, source):
    """Code values (..., 3) in `source` -> Rec.709 / sRGB code values in 0..1."""
    rgb = np.asarray(rgb, dtype=np.float64)
    if not source or source == "rec709":
        return rgb
    if source not in SOURCES:
        raise ValueError("Unknown source: %s" % source)
    _, curve, gamut, rng = SOURCES[source]
    x = rgb
    if rng == "legal":
        x = (64 + x * 876) / 1023.0
    lin = _CURVES[curve](x) @ gamut_matrix(gamut).T
    lin = np.maximum(lin, 0.0)
    # Bring hot channels down together so saturated highlights keep their hue.
    peak = lin.max(axis=-1, keepdims=True)
    scale = np.where(peak > 1e-6, _rolloff(peak) / np.maximum(peak, 1e-6), 1.0)
    return _encode_srgb(lin * scale)


def label(source):
    return SOURCES.get(source or "rec709", SOURCES["rec709"])[0]


def guess(transfer):
    """Pick a source from an ffmpeg colour-transfer tag, if it says HDR."""
    t = (transfer or "").lower()
    if "arib-std-b67" in t:
        return "hlg"
    if "smpte2084" in t:
        return "pq"
    return "rec709"
