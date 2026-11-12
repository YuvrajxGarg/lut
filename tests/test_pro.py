import json
import os
import sys
import tempfile
import types
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lutmatch import core, grading, refine, transforms  # noqa: E402
from test_core import scene, look  # noqa: E402


def slog3_encode(lin):
    """Inverse of the S-Log3 curve, back to ffmpeg's expanded code values."""
    lin = np.asarray(lin, np.float64)
    cv = np.where(lin >= 0.01125000,
                  (420 + np.log10((lin + 0.01) / 0.19) * 261.5) / 1023,
                  (lin * (171.2102946929 - 95) / 0.01125 + 95) / 1023)
    return (cv * 1023 - 64) / 876


class TransformTests(unittest.TestCase):
    def test_mid_grey_lands_on_display_grey(self):
        for s in transforms.ORDER[1:]:
            xs = np.linspace(0, 1, 4001)
            disp = transforms.to_display(np.repeat(xs[:, None], 3, 1), s)[:, 0]
            self.assertTrue(np.all(np.diff(disp) >= -1e-6), s)          # monotonic
            self.assertLessEqual(disp.max(), 1.0)
            self.assertGreaterEqual(disp.min(), 0.0)

    def test_slog3_roundtrip(self):
        grey = slog3_encode(0.18)
        out = transforms.to_display(np.array([grey] * 3), "slog3")
        np.testing.assert_allclose(out, 0.461, atol=0.01)

    def test_gamut_matrix_keeps_white(self):
        for g in ("rec2020", "sgamut3cine", "vgamut", "awg3", "awg4", "cinema"):
            np.testing.assert_allclose(transforms.gamut_matrix(g) @ np.ones(3), np.ones(3), atol=1e-6)

    def test_rec709_is_identity(self):
        x = np.random.default_rng(0).random((10, 3))
        np.testing.assert_array_equal(transforms.to_display(x, "rec709"), x)

    def test_guess_from_tag(self):
        self.assertEqual(transforms.guess("tv, bt2020nc/bt2020/arib-std-b67"), "hlg")
        self.assertEqual(transforms.guess("tv, bt2020nc/bt2020/smpte2084"), "pq")
        self.assertEqual(transforms.guess("tv, bt709"), "rec709")


class LogMatchTests(unittest.TestCase):
    def test_log_clip_matches_through_lut(self):
        ref = look(scene(seed=1))
        # A "camera" shot of a scene, recorded in S-Log3.
        disp = scene(seed=2)
        lin = core.srgb_to_linear(disp)
        log = slog3_encode(lin)
        cm = core.ColorMatch.fit(log.reshape(-1, 3), ref.reshape(-1, 3), source="slog3")
        self.assertEqual(cm.source, "slog3")
        exact = cm.apply_rgb(log)
        via_lut = core.apply_lut(log, cm.lut())
        self.assertLess(np.abs(exact - via_lut).mean(), 0.01)
        # Matched output should sit close to the reference's overall look.
        a = core.rgb_to_oklab(exact.reshape(-1, 3)).mean(0)
        b = core.rgb_to_oklab(ref.reshape(-1, 3)).mean(0)
        self.assertLess(np.abs(a - b).max(), 0.03)

    def test_cube_header_names_source(self):
        cm = core.ColorMatch.fit(scene().reshape(-1, 3), look(scene(seed=3)).reshape(-1, 3), source="vlog")
        d = tempfile.mkdtemp()
        p = os.path.join(d, "x.cube")
        core.write_cube(p, cm.lut(9), "t", transforms.label(cm.source))
        with open(p) as f:
            self.assertIn("Panasonic V-Log", f.read())
        self.assertEqual(core.read_cube(p).shape, (9, 9, 9, 3))


class AdjustTests(unittest.TestCase):
    def test_clamps_and_neutral(self):
        a = grading.Adjust(exposure=9, saturation=-3, tint="x")
        self.assertEqual(a.exposure, 1.0)
        self.assertEqual(a.saturation, 0.5)
        self.assertEqual(a.tint, 0.0)
        x = scene()
        np.testing.assert_array_equal(grading.Adjust().apply(x), x)

    def test_directions(self):
        x = scene()
        lab = lambda r: core.rgb_to_oklab(r.reshape(-1, 3)).mean(0)
        self.assertGreater(lab(grading.Adjust(exposure=0.5).apply(x))[0], lab(x)[0])
        self.assertGreater(lab(grading.Adjust(temperature=0.5).apply(x))[2], lab(x)[2])
        self.assertLess(lab(grading.Adjust(tint=-0.5).apply(x))[1], lab(x)[1])


class FakeClient(object):
    """Stands in for anthropic.Anthropic: replies with scripted JSON."""

    def __init__(self, answers):
        self.answers, self.calls = list(answers), []
        self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.calls.append(kw)
        text = json.dumps(self.answers.pop(0))
        return types.SimpleNamespace(stop_reason="end_turn",
                                     content=[types.SimpleNamespace(type="text", text=text)])


class RefineTests(unittest.TestCase):
    def test_rounds_until_match(self):
        neutral = {k: v[2] for k, v in grading.FIELDS.items()}
        warm = dict(neutral, temperature=0.4, contrast=0.1)
        fake = FakeClient([
            {"verdict": "adjust", "notes": "A touch cool and flat.", "adjustments": warm},
            {"verdict": "matches", "notes": "Now it reads the same.", "adjustments": warm},
        ])
        src, ref = [scene(seed=4)], [look(scene(seed=5))]
        cm = core.fit(src, ref)
        r = refine.Refiner(client=fake)
        r(cm, src, ref)
        self.assertEqual(len(fake.calls), 2)
        self.assertAlmostEqual(cm.adjust.temperature, 0.4)
        self.assertEqual(cm.notes, ["A touch cool and flat.", "Now it reads the same."])
        call = fake.calls[0]
        self.assertEqual(call["model"], "claude-opus-5-5")
        self.assertEqual(call["output_config"]["format"]["type"], "json_schema")
        imgs = [c for c in call["messages"][0]["content"] if c["type"] == "image"]
        self.assertGreaterEqual(len(imgs), 3)
        # The adjustment is baked into the LUT.
        plain = core.fit(src, ref)
        self.assertGreater(np.abs(cm.lut(9) - plain.lut(9)).max(), 0.01)

    def test_no_key(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        r = refine.Refiner(api_key="")
        r._key = None
        saved, refine.get_key = refine.get_key, lambda: None
        try:
            with self.assertRaises(refine.RefineError):
                r.client()
        finally:
            refine.get_key = saved


if __name__ == "__main__":
    unittest.main()
