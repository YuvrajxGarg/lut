"""Colour matching engine.

Give it a reference (a still or a clip whose look you want) and a source clip.
It samples both, works out a colour transform in OKLab, and bakes it into a
33x33x33 .cube LUT that also loads in Resolve, Premiere, Final Cut and OBS.
The graded copy is that same LUT applied with ffmpeg's lut3d filter (videos) or
with trilinear interpolation here (photos), so the file and the LUT always agree.

The transform has two parts, both fitted in OKLab:
  1. A Monge-Kantorovich linear map (MKL) that matches the mean and covariance
     of the colours: white balance, tint, saturation and how hue and lightness
     move together. It is the smallest 3x3 change that does this, so it doesn't
     rotate skin tones off somewhere odd.
  2. A smooth tone curve on lightness (L) from matching the L histograms, which
     brings over the contrast, black level and highlight roll-off.
Strength blends between the original and the full match.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np

from . import transforms

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
SUPPORTED_EXTS = IMAGE_EXTS | VIDEO_EXTS

LUT_SIZE = 33
SAMPLE_FRAMES = 12      # frames sampled across a video for its colour statistics
SAMPLE_WIDTH = 320      # frames are analysed at this width
MAX_PIXELS = 250000     # cap on pixels used per side when fitting

CODECS = ("h264", "hevc", "prores")

_NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}


class LutError(Exception):
    pass


def kind_of(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return None


# --------------------------------------------------------------------------
# Colour spaces (sRGB / Rec.709 code values <-> OKLab)
# --------------------------------------------------------------------------

def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(np.asarray(c, dtype=np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]])
_M1_INV = np.linalg.inv(_M1)
_M2_INV = np.linalg.inv(_M2)


def rgb_to_oklab(rgb):
    """sRGB code values in 0..1 (..., 3) -> OKLab (..., 3)."""
    lms = srgb_to_linear(rgb) @ _M1.T
    return np.cbrt(lms) @ _M2.T


def oklab_to_rgb(lab):
    """OKLab (..., 3) -> sRGB code values in 0..1, clipped to the gamut."""
    lms = (np.asarray(lab, dtype=np.float64) @ _M2_INV.T) ** 3
    return linear_to_srgb(lms @ _M1_INV.T)


# --------------------------------------------------------------------------
# The transform
# --------------------------------------------------------------------------

def _sqrtm(m):
    w, v = np.linalg.eigh((m + m.T) / 2)
    return (v * np.sqrt(np.clip(w, 1e-12, None))) @ v.T


def _mkl(cs, cr):
    """Monge-Kantorovich linear map taking covariance cs to cr."""
    cs_h = _sqrtm(cs)
    cs_hi = np.linalg.inv(cs_h)
    t = cs_hi @ _sqrtm(cs_h @ cr @ cs_h) @ cs_hi
    # Keep it sane on flat or tiny samples: limit how hard any axis is stretched.
    w, v = np.linalg.eigh((t + t.T) / 2)
    return (v * np.clip(w, 1 / 3.0, 3.0)) @ v.T


def _quantiles(x, n):
    return np.quantile(x, np.linspace(0.005, 0.995, n))


def _usable(rgb):
    """Drop letterbox / pure-black pixels so bars don't skew the match."""
    keep = rgb.max(axis=1) > 0.015
    return rgb[keep] if keep.mean() > 0.3 else rgb


def _subsample(x, n, seed=0):
    if len(x) <= n:
        return x
    idx = np.random.default_rng(seed).choice(len(x), n, replace=False)
    return x[idx]


class ColorMatch(object):
    """A fitted source -> reference colour transform."""

    def __init__(self, mu_s, mu_r, t, curve_x, curve_y, strength=1.0, keep_luma=False, source="rec709"):
        self.mu_s, self.mu_r, self.t = mu_s, mu_r, t
        self.curve_x, self.curve_y = curve_x, curve_y
        self.strength = float(strength)
        self.keep_luma = bool(keep_luma)
        self.source = source or "rec709"
        self.adjust = None   # optional grading.Adjust applied after the match
        self.ref_source = "rec709"
        self.notes = []      # what the refine step said, round by round

    @classmethod
    def fit(cls, src_rgb, ref_rgb, strength=1.0, keep_luma=False, source="rec709", ref_source="rec709"):
        """src_rgb, ref_rgb: (N, 3) arrays of code values in 0..1, in their sources."""
        src_rgb = transforms.to_display(_subsample(np.asarray(src_rgb, np.float64), MAX_PIXELS * 2, 3), source)
        ref_rgb = transforms.to_display(_subsample(np.asarray(ref_rgb, np.float64), MAX_PIXELS * 2, 4), ref_source)
        src = rgb_to_oklab(_subsample(_usable(src_rgb), MAX_PIXELS, 1))
        ref = rgb_to_oklab(_subsample(_usable(ref_rgb), MAX_PIXELS, 2))
        if len(src) < 16 or len(ref) < 16:
            raise LutError("Not enough picture to measure. Is the frame blank?")
        mu_s, mu_r = src.mean(0), ref.mean(0)
        eps = np.diag([1e-5, 1e-6, 1e-6])
        t = _mkl(np.cov(src.T) + eps, np.cov(ref.T) + eps)
        # Tone curve on L, fitted on top of the linear map.
        mapped_l = (src - mu_s) @ t.T[:, 0] + mu_r[0]
        n = 64
        xs = _quantiles(mapped_l, n)
        ys = _quantiles(ref[:, 0], n)
        xs = np.maximum.accumulate(xs + np.arange(n) * 1e-6)
        # Smooth the correction so the curve has no kinks (no banding in gradients).
        d = ys - xs
        k = np.ones(7) / 7.0
        d = np.convolve(np.pad(d, 3, mode="edge"), k, mode="valid")
        ys = xs + d
        ys = np.maximum.accumulate(ys)
        cm = cls(mu_s, mu_r, t, xs, ys, strength, keep_luma, source)
        cm.ref_source = ref_source or "rec709"
        return cm

    def _curve(self, l):
        xs, ys = self.curve_x, self.curve_y
        out = np.interp(l, xs, ys)
        # Outside the measured range keep slope 1 instead of flattening (no clipping).
        out = np.where(l < xs[0], ys[0] + (l - xs[0]), out)
        return np.where(l > xs[-1], ys[-1] + (l - xs[-1]), out)

    def apply_lab(self, lab):
        shape = lab.shape
        x = lab.reshape(-1, 3)
        y = (x - self.mu_s) @ self.t.T + self.mu_r
        y[:, 0] = self._curve(y[:, 0])
        if self.keep_luma:
            y[:, 0] = x[:, 0]
        y = x + (y - x) * self.strength
        return y.reshape(shape)

    def apply_display(self, rgb):
        """Rec.709 code values (already out of log) -> graded code values."""
        out = oklab_to_rgb(self.apply_lab(rgb_to_oklab(rgb)))
        if self.adjust is not None:
            out = self.adjust.apply(out)
        return out

    def apply_rgb(self, rgb):
        """Exact (non-LUT) transform of source code values."""
        return self.apply_display(transforms.to_display(rgb, self.source))

    def lut(self, size=LUT_SIZE):
        """(size, size, size, 3) table indexed [b, g, r] (the .cube order)."""
        axis = np.linspace(0.0, 1.0, size)
        b, g, r = np.meshgrid(axis, axis, axis, indexing="ij")
        grid = np.stack([r, g, b], axis=-1)
        return self.apply_rgb(grid)


def write_cube(path, table, title="Lut", source_label="Rec.709 / sRGB"):
    size = table.shape[0]
    rows = table.reshape(-1, 3)
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write('TITLE "%s"\n' % title.replace('"', "'"))
        f.write("# Made with Lut (PXLVZN). Input: %s. Output: Rec.709 / sRGB.\n" % source_label)
        f.write("LUT_3D_SIZE %d\n" % size)
        f.write("DOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n")
        for r, g, b in rows:
            f.write("%.6f %.6f %.6f\n" % (r, g, b))


def read_cube(path):
    size, rows = None, []
    with open(path, encoding="ascii", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("LUT_3D_SIZE"):
                size = int(line.split()[1])
            elif line[0] in "-.0123456789":
                rows.append([float(v) for v in line.split()[:3]])
    if not size or len(rows) != size ** 3:
        raise LutError("Not a 3D .cube LUT")
    return np.array(rows).reshape(size, size, size, 3)


def apply_lut(rgb, table):
    """Trilinear lookup. rgb: (..., 3) in 0..1. table: [b, g, r, 3]."""
    n = table.shape[0]
    p = np.clip(np.asarray(rgb, np.float64), 0, 1) * (n - 1)
    i0 = np.minimum(p.astype(np.int64), n - 2)
    f = p - i0
    r0, g0, b0 = i0[..., 0], i0[..., 1], i0[..., 2]
    fr, fg, fb = f[..., 0:1], f[..., 1:2], f[..., 2:3]
    out = 0
    for db, wb in ((0, 1 - fb), (1, fb)):
        for dg, wg in ((0, 1 - fg), (1, fg)):
            for dr, wr in ((0, 1 - fr), (1, fr)):
                out = out + table[b0 + db, g0 + dg, r0 + dr] * (wr * wg * wb)
    return out


# --------------------------------------------------------------------------
# Reading pictures (Pillow for stills, ffmpeg for video)
# --------------------------------------------------------------------------

def find_ffmpeg():
    """Locate an ffmpeg binary: env var, bundled copy, PATH, then imageio-ffmpeg."""
    env = os.environ.get("LUT_FFMPEG")
    if env and os.path.isfile(env):
        return env
    exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    bases = []
    if getattr(sys, "frozen", False):
        bases.append(getattr(sys, "_MEIPASS", ""))
        bases.append(os.path.dirname(sys.executable))
    bases.append(os.path.dirname(os.path.abspath(__file__)))
    for base in bases:
        cand = os.path.join(base, exe)
        if base and os.path.isfile(cand):
            return cand
    found = shutil.which("ffmpeg")
    if found:
        return found
    for extra in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if os.path.isfile(extra):
            return extra
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _need_ffmpeg():
    ff = find_ffmpeg()
    if not ff:
        raise LutError("ffmpeg not found. Install it (macOS: 'brew install ffmpeg', "
                       "Windows: 'winget install ffmpeg') or 'pip install imageio-ffmpeg'.")
    return ff


class VideoInfo(object):
    def __init__(self, duration=None, width=None, height=None, has_audio=False, fps=None, transfer=None):
        self.duration, self.width, self.height = duration, width, height
        self.has_audio, self.fps, self.transfer = has_audio, fps, transfer


def probe(path):
    """Duration, size and audio presence, read from ffmpeg's banner (no ffprobe needed)."""
    ff = _need_ffmpeg()
    p = subprocess.run([ff, "-hide_banner", "-nostdin", "-i", path], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=60, **_NO_WINDOW)
    txt = p.stderr.decode("utf-8", "replace")
    info = VideoInfo()
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", txt)
    if m:
        info.duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    for line in txt.splitlines():
        if "Video:" in line and info.width is None:
            m = re.search(r"[ ,](\d{2,5})x(\d{2,5})[ ,\[]", line + " ")
            if m:
                info.width, info.height = int(m.group(1)), int(m.group(2))
            m = re.search(r"([\d.]+) fps", line)
            if m:
                info.fps = float(m.group(1))
            # e.g. "yuv420p10le(tv, bt2020nc/bt2020/arib-std-b67)": keep the colour tags.
            tags = [g for g in re.findall(r"\(([^()]*)\)", line) if "/" in g and "0x" not in g]
            info.transfer = tags[0] if tags else None
        if "Audio:" in line:
            info.has_audio = True
    if info.width is None:
        raise LutError("No video stream found")
    return info


def _frames_from_video(path, count, width):
    ff = _need_ffmpeg()
    info = probe(path)
    work = tempfile.mkdtemp(prefix="lut-")
    try:
        dur = info.duration or 0
        if dur > 0.5 and count > 1:
            vf = "fps=%f,scale=%d:-2" % (count / dur, width)
            args = ["-vf", vf, "-frames:v", str(count)]
        else:
            args = ["-vf", "scale=%d:-2" % width, "-frames:v", "1"]
        cmd = [ff, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", path, "-an"] + args + [
            os.path.join(work, "f%03d.png")]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600, **_NO_WINDOW)
        names = sorted(n for n in os.listdir(work) if n.endswith(".png"))
        if not names:
            raise LutError("Couldn't read frames: " + p.stderr.decode("utf-8", "replace").strip()[-300:])
        from PIL import Image

        frames = []
        for n in names:
            with Image.open(os.path.join(work, n)) as im:
                frames.append(np.asarray(im.convert("RGB"), dtype=np.float64) / 255.0)
        return frames
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _load_image(path, width=None):
    from PIL import Image, ImageOps

    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        if width and im.width > width:
            im = im.resize((width, max(1, round(im.height * width / im.width))), Image.LANCZOS)
        return np.asarray(im.convert("RGB"), dtype=np.float64) / 255.0


def load_frames(path, count=SAMPLE_FRAMES, width=SAMPLE_WIDTH):
    """A list of (H, W, 3) float frames representative of the file."""
    k = kind_of(path)
    if k == "image":
        return [_load_image(path, width * 2)]
    if k == "video":
        return _frames_from_video(path, count, width)
    raise LutError("Not a supported photo or video")


def pixels(frames):
    return np.concatenate([f.reshape(-1, 3) for f in frames], axis=0)


def poster(frames):
    """The frame used for previews: the middle sample."""
    return frames[len(frames) // 2]


# --------------------------------------------------------------------------
# Writing the graded copy
# --------------------------------------------------------------------------

def output_paths(src, out_dir, codec="h264"):
    """(.cube path, graded copy path) for a source file."""
    stem, ext = os.path.splitext(os.path.basename(src))
    if kind_of(src) == "video":
        if codec == "prores":
            ext = ".mov"
        elif codec == "hevc" and ext.lower() in (".webm", ".avi"):
            ext = ".mp4"
        elif ext.lower() == ".avi":
            ext = ".mp4"
    return (os.path.join(out_dir, stem + ".cube"), os.path.join(out_dir, stem + "_graded" + ext))


def grade_image(src, dst, table):
    from PIL import Image, ImageOps

    with Image.open(src) as im:
        icc = im.info.get("icc_profile")
        im = ImageOps.exif_transpose(im)
        alpha = im.getchannel("A") if im.mode in ("RGBA", "LA") else None
        rgb = np.asarray(im.convert("RGB"), dtype=np.float64) / 255.0
    out = np.clip(np.round(apply_lut(rgb, table) * 255), 0, 255).astype(np.uint8)
    res = Image.fromarray(out, "RGB")
    if alpha is not None:
        res.putalpha(alpha)
    ext = os.path.splitext(dst)[1].lower()
    kw = {"icc_profile": icc} if icc else {}
    if ext in (".jpg", ".jpeg"):
        res = res.convert("RGB")
        kw.update(quality=95, subsampling=0)
    elif ext == ".webp":
        kw.update(quality=95)
    res.save(dst, **kw)


def _video_codec_args(codec, ext):
    if codec == "prores":
        return ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le", "-vendor", "apl0"]
    if ext == ".webm":
        return ["-c:v", "libvpx-vp9", "-crf", "20", "-b:v", "0", "-row-mt", "1", "-pix_fmt", "yuv420p"]
    if codec == "hevc":
        args = ["-c:v", "libx265", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p"]
        if ext in (".mp4", ".mov", ".m4v"):
            args += ["-tag:v", "hvc1"]
        return args
    return ["-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p"]


def grade_video(src, dst, cube_path, codec="h264", progress=None, tag709=False):
    """Apply a .cube with ffmpeg's lut3d. Audio is copied untouched when the container allows."""
    ff = _need_ffmpeg()
    info = probe(src)
    ext = os.path.splitext(dst)[1].lower()
    work = tempfile.mkdtemp(prefix="lut-")
    try:
        # lut3d's file= option needs escaping for drive letters and colons; a plain
        # relative name in a scratch working directory sidesteps that on every OS.
        shutil.copyfile(cube_path, os.path.join(work, "match.cube"))
        vf = "lut3d=file=match.cube:interp=tetrahedral"

        def run(audio):
            cmd = [ff, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", os.path.abspath(src),
                   "-map", "0:V:0", "-map", "0:a?", "-vf", vf] + _video_codec_args(codec, ext) + audio + [
                   "-map_metadata", "0", "-progress", "pipe:1", "-nostats"]
            if tag709:
                # The LUT turned log/HDR into Rec.709: say so, or players will treat it as HDR.
                cmd += ["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709"]
            if ext in (".mp4", ".mov", ".m4v"):
                cmd += ["-movflags", "+faststart"]
            cmd.append(os.path.abspath(dst))
            # stderr goes to a file so a chatty ffmpeg can never block on a full pipe.
            with open(os.path.join(work, "err.txt"), "w+b") as errf:
                with subprocess.Popen(cmd, cwd=work, stdout=subprocess.PIPE, stderr=errf, **_NO_WINDOW) as proc:
                    for raw in proc.stdout:
                        line = raw.decode("ascii", "replace").strip()
                        if progress and info.duration and line.startswith("out_time_us="):
                            try:
                                progress(min(0.999, max(0.0, int(line.split("=", 1)[1]) / 1e6 / info.duration)))
                            except ValueError:
                                pass
                    code = proc.wait()
                errf.seek(0)
                return code, errf.read().decode("utf-8", "replace")

        if ext == ".webm":
            audio = ["-c:a", "libopus", "-b:a", "160k"]
        else:
            audio = ["-c:a", "copy"]
        code, err = run(audio)
        if code != 0 and info.has_audio and audio[1] == "copy":
            # The audio codec doesn't fit the container: re-encode just the audio.
            code, err = run(["-c:a", "aac", "-b:a", "256k"] if ext != ".webm" else ["-c:a", "libopus"])
        if code != 0:
            if os.path.exists(dst):
                os.remove(dst)
            raise LutError("ffmpeg failed: " + err.strip()[-600:])
        if progress:
            progress(1.0)
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --------------------------------------------------------------------------
# One call that does the whole job
# --------------------------------------------------------------------------

class Result(object):
    def __init__(self, cube=None, graded=None, match=None):
        self.cube, self.graded, self.match = cube, graded, match


def resolve_source(path, source):
    """'auto' -> HLG/PQ when the file is tagged that way, else Rec.709."""
    if source and source != "auto":
        if source not in transforms.SOURCES:
            raise LutError("Unknown source: %s" % source)
        return source
    if kind_of(path) != "video":
        return "rec709"
    try:
        return transforms.guess(probe(path).transfer)
    except LutError:
        return "rec709"


def fit(src_frames, ref_frames, strength=1.0, keep_luma=False, source="rec709", ref_source="rec709"):
    return ColorMatch.fit(pixels(src_frames), pixels(ref_frames), strength, keep_luma, source, ref_source)


def write_outputs(cm, src, ref, out_dir, codec="h264", lut_only=False, progress=None):
    """Bake a fitted match into the .cube and (unless lut_only) the graded copy."""
    if codec not in CODECS:
        raise LutError("codec must be one of " + ", ".join(CODECS))
    os.makedirs(out_dir, exist_ok=True)
    cube, graded = output_paths(src, out_dir, codec)
    if os.path.abspath(graded) == os.path.abspath(src):
        raise LutError("Output would overwrite the original")
    table = cm.lut()
    write_cube(cube, table, "%s to %s" % (os.path.basename(src), os.path.basename(ref)),
               transforms.label(cm.source))
    if progress:
        progress(0.02)
    if not lut_only:
        if kind_of(src) == "image":
            grade_image(src, graded, table)
        else:
            grade_video(src, graded, cube, codec, progress, tag709=cm.source != "rec709")
    return Result(cube, None if lut_only else graded, cm)


def match(src, ref, out_dir, strength=1.0, keep_luma=False, codec="h264", lut_only=False,
          ref_frames=None, progress=None, source="auto", ref_source="auto", refine=None):
    """Fit src -> ref, write the .cube and (unless lut_only) the graded copy.

    refine, if given, is called as refine(cm, src_frames, ref_frames) before the
    outputs are written and may set cm.adjust (see refine.py)."""
    if codec not in CODECS:
        raise LutError("codec must be one of " + ", ".join(CODECS))
    if os.path.abspath(src) == os.path.abspath(ref):
        raise LutError("The clip and the reference are the same file")
    ref_frames = ref_frames if ref_frames is not None else load_frames(ref)
    src_frames = load_frames(src)
    cm = fit(src_frames, ref_frames, strength, keep_luma,
             resolve_source(src, source), resolve_source(ref, ref_source))
    if refine:
        refine(cm, src_frames, ref_frames)
    return write_outputs(cm, src, ref, out_dir, codec, lut_only, progress)


def collect_files(paths, recursive=True):
    """Expand files/folders into a list of supported media files."""
    result = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d != "graded" and not d.startswith(".")]
                for fn in sorted(files):
                    if os.path.splitext(fn)[1].lower() in SUPPORTED_EXTS and "_graded." not in fn:
                        result.append(os.path.join(root, fn))
                if not recursive:
                    break
        elif os.path.isfile(p) and kind_of(p):
            result.append(p)
    return result
