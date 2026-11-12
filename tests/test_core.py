import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lutmatch import cli, core  # noqa: E402


def scene(w=96, h=64, seed=0):
    """A colourful test picture: gradients plus random patches."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w]
    img = np.stack([x / (w - 1), y / (h - 1), 0.5 + 0.4 * np.sin(x / 7.0) * np.cos(y / 5.0)], -1)
    for _ in range(12):
        x0, y0 = rng.integers(0, w - 12), rng.integers(0, h - 12)
        img[y0:y0 + 12, x0:x0 + 12] = rng.random(3)
    return np.clip(img, 0, 1)


def look(rgb):
    """A known 'grade': warm, crushed, less saturated."""
    lab = core.rgb_to_oklab(rgb)
    lab[..., 0] = 0.08 + lab[..., 0] * 0.85
    lab[..., 1] = lab[..., 1] * 0.7 + 0.015
    lab[..., 2] = lab[..., 2] * 0.7 + 0.035
    return core.oklab_to_rgb(lab)


def save(path, rgb):
    from PIL import Image

    Image.fromarray(np.round(np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(path)


class ColourTests(unittest.TestCase):
    def test_oklab_round_trip(self):
        rgb = np.random.default_rng(1).random((500, 3))
        self.assertTrue(np.allclose(core.oklab_to_rgb(core.rgb_to_oklab(rgb)), rgb, atol=1e-6))

    def test_identity_when_source_is_reference(self):
        px = scene().reshape(-1, 3)
        cm = core.ColorMatch.fit(px, px)
        self.assertLess(np.abs(cm.apply_rgb(px) - px).max(), 0.02)

    def test_strength_zero_is_identity_lut(self):
        a, b = scene(seed=1).reshape(-1, 3), look(scene(seed=2)).reshape(-1, 3)
        table = core.ColorMatch.fit(a, b, strength=0).lut(9)
        axis = np.linspace(0, 1, 9)
        bb, gg, rr = np.meshgrid(axis, axis, axis, indexing="ij")
        self.assertTrue(np.allclose(table, np.stack([rr, gg, bb], -1), atol=1e-6))

    def test_match_moves_stats_to_reference(self):
        src = scene(seed=3).reshape(-1, 3)
        ref = look(scene(seed=4)).reshape(-1, 3)
        out = core.apply_lut(src, core.ColorMatch.fit(src, ref).lut())
        s, r, o = (core.rgb_to_oklab(v) for v in (src, ref, out))
        before = np.abs(s.mean(0) - r.mean(0)).sum() + np.abs(s.std(0) - r.std(0)).sum()
        after = np.abs(o.mean(0) - r.mean(0)).sum() + np.abs(o.std(0) - r.std(0)).sum()
        self.assertLess(after, before * 0.3)

    def test_keep_luma_keeps_lightness(self):
        src = scene(seed=5).reshape(-1, 3)
        ref = look(scene(seed=6)).reshape(-1, 3)
        out = core.ColorMatch.fit(src, ref, keep_luma=True).apply_rgb(src)
        dl = np.abs(core.rgb_to_oklab(out)[:, 0] - core.rgb_to_oklab(src)[:, 0])
        self.assertLess(np.median(dl), 0.01)

    def test_blank_frame_is_an_error(self):
        black = np.zeros((10, 3))
        with self.assertRaises(core.LutError):
            core.ColorMatch.fit(black, scene().reshape(-1, 3))

    def test_cube_round_trip_and_lookup(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        src, ref = scene(seed=7).reshape(-1, 3), look(scene(seed=8)).reshape(-1, 3)
        table = core.ColorMatch.fit(src, ref).lut()
        p = os.path.join(d, "x.cube")
        core.write_cube(p, table, 'a "quoted" title')
        with open(p) as f:
            text = f.read()
        self.assertIn("LUT_3D_SIZE 33", text)
        back = core.read_cube(p)
        self.assertTrue(np.allclose(back, table, atol=1e-5))
        # Grid points are exact; the first data row is black in, the second has red moved by one step.
        self.assertTrue(np.allclose(core.apply_lut(np.array([[0, 0, 0], [1, 1, 1]]), table), table[[0, -1], [0, -1], [0, -1]]))


class FileTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.src = os.path.join(self.d, "clip.png")
        self.ref = os.path.join(self.d, "ref.jpg")
        save(self.src, scene(seed=9))
        save(self.ref, look(scene(seed=10)))

    def test_match_image(self):
        r = core.match(self.src, self.ref, os.path.join(self.d, "graded"))
        self.assertTrue(os.path.isfile(r.cube))
        self.assertEqual(os.path.basename(r.graded), "clip_graded.png")
        from PIL import Image

        out = np.asarray(Image.open(r.graded).convert("RGB")) / 255.0
        ref = np.asarray(Image.open(self.ref).convert("RGB")) / 255.0
        self.assertLess(abs(core.rgb_to_oklab(out)[..., 2].mean() - core.rgb_to_oklab(ref)[..., 2].mean()), 0.01)

    def test_lut_only(self):
        r = core.match(self.src, self.ref, os.path.join(self.d, "g"), lut_only=True)
        self.assertIsNone(r.graded)
        self.assertEqual(os.listdir(os.path.join(self.d, "g")), ["clip.cube"])

    def test_same_file_refused(self):
        with self.assertRaises(core.LutError):
            core.match(self.src, self.src, self.d)

    def test_collect_skips_graded(self):
        core.match(self.src, self.ref, os.path.join(self.d, "graded"))
        found = sorted(os.path.basename(p) for p in core.collect_files([self.d]))
        self.assertEqual(found, ["clip.png", "ref.jpg"])

    def test_cli_match_and_apply(self):
        out = os.path.join(self.d, "out")
        self.assertEqual(cli.main(["match", self.ref, self.src, "-o", out, "-s", "0.8"]), 0)
        cube = os.path.join(out, "clip.cube")
        self.assertTrue(os.path.isfile(os.path.join(out, "clip_graded.png")))
        out2 = os.path.join(self.d, "out2")
        self.assertEqual(cli.main(["apply", cube, self.src, "-o", out2]), 0)
        from PIL import Image

        a = np.asarray(Image.open(os.path.join(out, "clip_graded.png")), dtype=int)
        b = np.asarray(Image.open(os.path.join(out2, "clip_graded.png")), dtype=int)
        self.assertLessEqual(np.abs(a - b).max(), 1)


@unittest.skipUnless(core.find_ffmpeg(), "needs ffmpeg")
class VideoTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        ff = core.find_ffmpeg()
        self.clip = os.path.join(self.d, "clip with spaces.mp4")
        subprocess.check_call([ff, "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=192x108:rate=12:duration=2",
                               "-f", "lavfi", "-i", "sine=frequency=330:duration=2", "-c:v", "mpeg4", "-q:v", "3",
                               "-c:a", "aac", "-shortest", self.clip])
        self.ref = os.path.join(self.d, "ref.png")
        save(self.ref, look(scene(192, 108, seed=11)))

    def test_probe(self):
        info = core.probe(self.clip)
        self.assertEqual((info.width, info.height), (192, 108))
        self.assertTrue(info.has_audio)
        self.assertAlmostEqual(info.duration, 2.0, delta=0.2)

    def test_sample_frames(self):
        frames = core.load_frames(self.clip, count=4, width=96)
        self.assertEqual(len(frames), 4)
        self.assertEqual(frames[0].shape[1], 96)

    def test_grade_video_keeps_audio(self):
        seen = []
        r = core.match(self.clip, self.ref, os.path.join(self.d, "graded"), progress=seen.append)
        self.assertTrue(r.graded.endswith("clip with spaces_graded.mp4"))
        info = core.probe(r.graded)
        self.assertEqual((info.width, info.height), (192, 108))
        self.assertTrue(info.has_audio)
        self.assertEqual(seen[-1], 1.0)
        # The graded video's colour agrees with grading a frame through the LUT directly.
        table = core.read_cube(r.cube)
        a = core.poster(core.load_frames(self.clip, count=1, width=192))
        b = core.poster(core.load_frames(r.graded, count=1, width=192))
        self.assertLess(np.abs(core.apply_lut(a, table).mean((0, 1)) - b.mean((0, 1))).max(), 0.03)

    def test_prores_goes_to_mov(self):
        r = core.match(self.clip, self.ref, os.path.join(self.d, "p"), codec="prores")
        self.assertTrue(r.graded.endswith(".mov"))
        self.assertTrue(os.path.getsize(r.graded) > 0)


if __name__ == "__main__":
    unittest.main()
