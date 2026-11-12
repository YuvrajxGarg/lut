"""Smoke-test a built app: run its CLI on a photo and a video, check the LUT and graded copies.
    python tests/smoke_app.py <path to Lut executable>
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_core as t  # noqa: E402
from lutmatch import core  # noqa: E402

exe = sys.argv[1]
d = tempfile.mkdtemp()
src = os.path.join(d, "clip.png")
ref = os.path.join(d, "ref.jpg")
t.save(src, t.scene(seed=1))
t.save(ref, t.look(t.scene(seed=2)))
out = os.path.join(d, "out")
r = subprocess.run([exe, "match", ref, src, "-o", out], timeout=300)
assert os.path.isfile(os.path.join(out, "clip.cube")), "app produced no LUT (exit %s)" % r.returncode
assert os.path.isfile(os.path.join(out, "clip_graded.png")), "app produced no graded photo (exit %s)" % r.returncode
core.read_cube(os.path.join(out, "clip.cube"))

# A camera log profile goes through the frozen app too (transforms module bundled).
r = subprocess.run([exe, "match", ref, src, "-o", os.path.join(d, "slog"), "--source", "slog3", "--lut-only"], timeout=300)
with open(os.path.join(d, "slog", "clip.cube")) as f:
    assert "S-Log3" in f.read(), "S-Log3 LUT header missing (exit %s)" % r.returncode

# Video: proves the built app finds its bundled ffmpeg and can encode H.264.
ff = core.find_ffmpeg()
if ff:
    vid = os.path.join(d, "clip.mp4")
    subprocess.check_call([ff, "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=24:duration=1",
                           "-c:v", "mpeg4", vid])
    env = dict(os.environ)
    env.pop("LUT_FFMPEG", None)
    env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep) if "ffmpeg" not in p.lower())
    r = subprocess.run([exe, "match", ref, vid, "-o", out], timeout=300, env=env)
    vdst = os.path.join(out, "clip_graded.mp4")
    assert os.path.isfile(vdst) and os.path.getsize(vdst) > 0, "app produced no graded video (exit %s)" % r.returncode
    print("video graded too")

print("smoke test passed: %s (exit %s)" % (exe, r.returncode))
