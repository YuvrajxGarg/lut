"""Optional "Refine with Claude" step.

After the statistical match, Claude looks at small previews of the reference
and of the current result, and answers with bounded finishing adjustments
(grading.Adjust). Lut applies them itself, renders again and asks Claude to
check, for a few rounds. Only downscaled JPEG previews leave the computer; the
clips themselves never do.

The API key is the user's own, kept in the OS keychain (macOS Keychain,
Windows Credential Manager) or read from ANTHROPIC_API_KEY.
"""

import base64
import io
import json
import os

import numpy as np

from . import grading, transforms

MODEL = "claude-opus-5-5"
KEYRING_SERVICE = "Lut"
KEYRING_USER = "anthropic-api-key"
PREVIEW_WIDTH = 512
MAX_ROUNDS = 3


class RefineError(Exception):
    pass


# --------------------------------------------------------------------------
# API key storage
# --------------------------------------------------------------------------

def get_key():
    env = os.environ.get("ANTHROPIC_API_KEY")
    if env:
        return env.strip()
    try:
        import keyring

        return keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        return None


def set_key(key):
    import keyring

    key = (key or "").strip()
    if key:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, key)
    else:
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
        except Exception:
            pass


def has_key():
    return bool(get_key())


def key_hint():
    k = get_key()
    return ("…" + k[-4:]) if k and len(k) > 8 else ""


# --------------------------------------------------------------------------
# Previews
# --------------------------------------------------------------------------

def _pick(frames, n):
    if len(frames) <= n:
        return list(frames)
    idx = np.linspace(0, len(frames) - 1, n + 2)[1:-1].round().astype(int)
    return [frames[i] for i in idx]


def _jpeg(rgb, width=PREVIEW_WIDTH):
    from PIL import Image

    im = Image.fromarray(np.clip(np.round(rgb * 255), 0, 255).astype(np.uint8), "RGB")
    if im.width > width:
        im = im.resize((width, max(1, round(im.height * width / im.width))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def _image(data):
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


def _stats(rgb):
    """A few numbers so Claude isn't judging from compressed pixels alone."""
    from .core import rgb_to_oklab

    lab = rgb_to_oklab(rgb.reshape(-1, 3)[::7])
    L = lab[:, 0]
    return {"L_p5": round(float(np.percentile(L, 5)), 3), "L_median": round(float(np.median(L)), 3),
            "L_p95": round(float(np.percentile(L, 95)), 3), "a_mean": round(float(lab[:, 1].mean()), 4),
            "b_mean": round(float(lab[:, 2].mean()), 4),
            "chroma_mean": round(float(np.hypot(lab[:, 1], lab[:, 2]).mean()), 4)}


# --------------------------------------------------------------------------
# The prompt
# --------------------------------------------------------------------------

SYSTEM = """You are the finishing colourist inside Lut, a desktop app that matches the colour of a clip to a reference.

Lut has already done a statistical match (OKLab mean/covariance transfer plus a lightness tone curve). Your job is to look at the reference and at the current result and decide whether a small set of bounded adjustments would make the result read as the same look as the reference: same white balance, contrast, black level, highlight roll-off, saturation and split-toning, with natural skin.

Judge the overall look, not the content. The clip and the reference usually show different scenes, so do not try to make objects the same colour. A blue sky in the reference does not mean the clip should turn blue. Keep skin believable. Prefer small moves; the match is usually close already. If the result already matches well, say so and return the current values unchanged.

The adjustments are absolute values for the whole finishing pass, not deltas: return the complete set you want applied on top of the match. Ranges and neutral values:
{fields}

Each image's OKLab statistics are given (L is lightness 0..1, a is green(-)/magenta(+), b is blue(-)/yellow(+)). Use them to check what you see."""


SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["matches", "adjust"]},
        "notes": {"type": "string"},
        "adjustments": {
            "type": "object",
            "properties": {k: {"type": "number"} for k in grading.FIELDS},
            "required": list(grading.FIELDS),
            "additionalProperties": False,
        },
    },
    "required": ["verdict", "notes", "adjustments"],
    "additionalProperties": False,
}


def _fields_text():
    return "\n".join("- %s: %g to %g (neutral %g), %s" % (k, lo, hi, n, d)
                     for k, (lo, hi, n, d) in grading.FIELDS.items())


class Refiner(object):
    """Callable passed to core.match(refine=...)."""

    def __init__(self, api_key=None, model=MODEL, rounds=MAX_ROUNDS, status=None, client=None, soft=False):
        self.soft = soft     # on an API problem keep the plain match instead of failing the clip
        self.model = model
        self.rounds = max(1, min(int(rounds), 5))
        self.status = status or (lambda msg: None)
        self._client = client
        self._key = api_key

    def client(self):
        if self._client is None:
            key = self._key or get_key()
            if not key:
                raise RefineError("Add your Claude API key in Settings to use Refine with Claude.")
            try:
                import anthropic
            except ImportError:
                raise RefineError("This build of Lut doesn't include the Claude SDK.")

            self._client = anthropic.Anthropic(api_key=key, timeout=120.0, max_retries=2)
        return self._client

    def ask(self, ref_imgs, ref_stats, src_imgs, res_imgs, res_stats, current, history):
        content = [{"type": "text", "text": "REFERENCE (the look we want), stats %s:" % json.dumps(ref_stats)}]
        content += [_image(d) for d in ref_imgs]
        content.append({"type": "text", "text": "CLIP BEFORE MATCHING (for context):"})
        content += [_image(d) for d in src_imgs]
        content.append({"type": "text", "text": "CURRENT RESULT with adjustments %s, stats %s:" % (
            json.dumps(current), json.dumps(res_stats))})
        content += [_image(d) for d in res_imgs]
        if history:
            content.append({"type": "text", "text": "Earlier rounds:\n" + "\n".join(history)})
        content.append({"type": "text", "text": "Does the current result carry the reference's look? "
                        "Return your verdict, a one-sentence note a filmmaker would understand, "
                        "and the full set of adjustments."})
        import anthropic

        try:
            resp = self.client().beta.messages.create(
                model=self.model,
                max_tokens=8000,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                system=SYSTEM.format(fields=_fields_text()),
                output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
                messages=[{"role": "user", "content": content}],
            )
        except anthropic.AuthenticationError:
            raise RefineError("Claude didn't accept the API key. Check it in Settings.")
        except anthropic.PermissionDeniedError:
            raise RefineError("This API key can't use %s." % self.model)
        except anthropic.RateLimitError:
            raise RefineError("Claude is rate-limiting this key. Try again in a minute.")
        except anthropic.APIConnectionError:
            raise RefineError("Couldn't reach Claude. Check the internet connection.")
        except anthropic.APIStatusError as e:
            raise RefineError("Claude API error %s: %s" % (e.status_code, getattr(e, "message", e)))
        if resp.stop_reason == "refusal":
            raise RefineError("Claude declined to review these frames.")
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except ValueError:
            raise RefineError("Claude's answer wasn't readable; kept the plain match.")

    def __call__(self, cm, src_frames, ref_frames):
        cm.refine_error = None
        try:
            return self._run(cm, src_frames, ref_frames)
        except RefineError as e:
            if not self.soft:
                raise
            cm.adjust = None
            cm.refine_error = str(e)
            return cm

    def _run(self, cm, src_frames, ref_frames):
        ref = [transforms.to_display(f, cm.ref_source) for f in _pick(ref_frames, 2)]
        src = _pick(src_frames, 3)
        src_disp = [transforms.to_display(f, cm.source) for f in src]
        ref_imgs = [_jpeg(f) for f in ref]
        ref_stats = _stats(np.concatenate([f.reshape(-1, 3) for f in ref]))
        src_imgs = [_jpeg(f) for f in src_disp[:1]]
        # Work at preview size so each round is quick.
        small = [_downscale(f) for f in src]
        adjust = grading.Adjust()
        history = []
        for rnd in range(1, self.rounds + 1):
            self.status("Claude is checking the match (round %d of %d)…" % (rnd, self.rounds))
            cm.adjust = adjust
            res = [np.clip(cm.apply_rgb(f), 0, 1) for f in small]
            res_stats = _stats(np.concatenate([f.reshape(-1, 3) for f in res]))
            ans = self.ask(ref_imgs, ref_stats, src_imgs, [_jpeg(f) for f in res], res_stats,
                           adjust.to_dict(), history)
            note = (ans.get("notes") or "").strip()
            if note:
                cm.notes.append(note)
            history.append("Round %d: %s -> %s (%s)" % (rnd, json.dumps(adjust.to_dict()), ans.get("verdict"), note))
            if ans.get("verdict") == "matches":
                break
            new = grading.Adjust(**(ans.get("adjustments") or {}))
            if new.to_dict() == adjust.to_dict():
                break
            adjust = new
        cm.adjust = None if adjust.is_neutral() else adjust
        return cm


def _downscale(frame, width=PREVIEW_WIDTH):
    h, w = frame.shape[:2]
    if w <= width:
        return frame
    step = int(np.ceil(w / float(width)))
    return frame[::step, ::step]
