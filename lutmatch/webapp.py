"""Lut's desktop UI: an HTML/CSS interface (lutmatch/ui) in a native window via pywebview.

Uses WebKit on macOS and Edge WebView2 on Windows, so both platforms get the same UI.
"""

import base64
import io
import json
import os
import subprocess
import sys
import threading

import numpy as np
import webview
from webview.dom import DOMEventHandler

from . import __version__, core, refine, transforms
from .settings import Settings
from .updater import Updater

UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    UI_DIR = os.path.join(sys._MEIPASS, "lutmatch", "ui")

BG = "#0b0b0c"
PREVIEW_WIDTH = 640


def _human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0


def _jpeg(rgb, quality=86):
    from PIL import Image

    arr = np.clip(np.round(np.asarray(rgb) * 255), 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr, "RGB").save(buf, "JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _first(res):
    if not res:
        return None
    return res[0] if isinstance(res, (list, tuple)) else res


class Api(object):
    def __init__(self):
        self.window = None
        self.ref = None          # {"path", "name", "frames", "thumb", "kind"}
        self.items = {}          # id -> clip dict
        self.next_id = 1
        self.lock = threading.Lock()
        self.preview_gen = 0
        self.busy = False
        self.settings = Settings()
        self.updater = Updater(self.settings, lambda st: self._emit("update", st))

    # ---- helpers ---------------------------------------------------------
    def _emit(self, event, payload):
        if self.window:
            try:
                self.window.evaluate_js("window.App && App.on(%s, %s)" % (json.dumps(event), json.dumps(payload)))
            except Exception:
                pass

    def _public(self, it):
        return {
            "id": it["id"], "name": os.path.basename(it["path"]), "path": it["path"],
            "folder": os.path.dirname(it["path"]), "size": it["size"], "kind": it["kind"],
            "ext": os.path.splitext(it["path"])[1][1:].upper(), "status": it["status"],
            "error": it.get("error"), "before": it.get("before"), "after": it.get("after"),
            "cube": it.get("cube"), "graded": it.get("graded"), "progress": it.get("progress", 0),
            "source": self._src_for(it), "note": it.get("note"), "warn": it.get("warn"),
        }

    def _ref_public(self):
        r = self.ref
        if not r:
            return None
        return {"name": os.path.basename(r["path"]), "path": r["path"], "kind": r["kind"],
                "thumb": r.get("thumb"), "status": r["status"], "error": r.get("error"),
                "source": self._ref_source()}

    def _src_for(self, it):
        s = self.settings.get("source")
        return s if s in transforms.SOURCES else it.get("auto_source", "rec709")

    def _ref_source(self):
        s = self.settings.get("ref_source")
        if s in transforms.SOURCES:
            return s
        return (self.ref or {}).get("auto_source", "rec709")

    def _opts(self):
        s = self.settings
        return {"strength": max(0, min(100, int(s.get("strength") or 0))) / 100.0,
                "keep_luma": bool(s.get("keep_luma")), "lut_only": bool(s.get("lut_only")),
                "codec": s.get("codec") if s.get("codec") in core.CODECS else "h264"}

    # ---- called from JS --------------------------------------------------
    def info(self):
        return {"version": __version__, "ffmpeg": bool(core.find_ffmpeg()), "platform": sys.platform,
                "settings": self.settings.public(), "update": self.updater.state(),
                "home": os.path.expanduser("~"), "ref": self._ref_public(), "claude": self.claude_state(),
                "sources": [[k, transforms.label(k)] for k in transforms.ORDER]}

    # Claude API key (kept in the OS keychain, never in settings.json)
    def claude_state(self):
        return {"has_key": refine.has_key(), "hint": refine.key_hint(),
                "env": bool(os.environ.get("ANTHROPIC_API_KEY"))}

    def set_claude_key(self, key):
        try:
            refine.set_key(key)
        except Exception as e:
            return dict(self.claude_state(), error="Couldn't save the key: %s" % e)
        if not (key or "").strip() and self.settings.get("refine"):
            self.settings.set("refine", False)
        return self.claude_state()

    def set_setting(self, key, value):
        if key in ("out_mode", "custom_dir", "open_after", "auto_check", "auto_install", "welcomed",
                   "strength", "keep_luma", "lut_only", "codec", "source", "ref_source", "refine"):
            self.settings.set(key, value)
            if key == "auto_install" and value and self.updater.phase == "available":
                threading.Thread(target=self.updater.stage_newest, daemon=True).start()
            if key in ("strength", "keep_luma", "source", "ref_source"):
                self._refresh_previews()
            if key == "ref_source":
                self._emit("ref", self._ref_public())
        return self.settings.public()

    # updates
    def check_updates(self):
        return self.updater.check(manual=True)

    def download_update(self):
        threading.Thread(target=self.updater.stage_newest, daemon=True).start()

    def install_update(self):
        def go():
            if self.updater.install() == "open_page":
                self.open_url(self.updater.state()["page"])
        threading.Thread(target=go, daemon=True).start()

    def open_url(self, url):
        if not url.startswith(("https://github.com/", "https://console.anthropic.com/")):
            return
        import webbrowser
        webbrowser.open(url)

    # pickers
    def _file_types(self):
        exts = ";".join("*" + e for e in sorted(core.SUPPORTED_EXTS))
        return ("Photos and videos (%s)" % exts, "All files (*.*)")

    def pick_reference(self):
        res = self.window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False, file_types=self._file_types())
        if _first(res):
            self.set_reference(_first(res))

    def pick_clips(self):
        res = self.window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True, file_types=self._file_types())
        if res:
            self.add_clips(list(res))

    def pick_folder(self):
        res = _first(self.window.create_file_dialog(webview.FileDialog.FOLDER))
        if res:
            self.add_clips([res])

    def choose_output(self):
        return _first(self.window.create_file_dialog(webview.FileDialog.FOLDER))

    def dropped(self, paths, zone):
        """Files dropped on the window. The reference slot takes the first file; the rest are clips."""
        files = core.collect_files(paths)
        if not files:
            self._emit("toast", {"text": "No supported photos or videos there", "err": True})
            return
        if zone == "ref" or self.ref is None:
            self.set_reference(files[0])
            files = files[1:]
        if files:
            self.add_clips(files)

    # reference
    def set_reference(self, path):
        if not core.kind_of(path):
            self._emit("toast", {"text": "The reference needs to be a photo or video", "err": True})
            return
        # A clip promoted to reference leaves the clip list.
        for k, it in list(self.items.items()):
            if os.path.abspath(it["path"]) == os.path.abspath(path):
                self.items.pop(k)
                self._emit("removed", {"id": k})
        self.ref = {"path": path, "kind": core.kind_of(path), "status": "loading"}
        self._emit("ref", self._ref_public())
        threading.Thread(target=self._load_ref, args=(self.ref,), daemon=True).start()

    def _load_ref(self, ref):
        try:
            ref["auto_source"] = core.resolve_source(ref["path"], "auto")
            ref["frames"] = core.load_frames(ref["path"], width=PREVIEW_WIDTH // 2)
            ref["thumb"] = _jpeg(core.poster(core.load_frames(ref["path"], count=1, width=PREVIEW_WIDTH))
                                 if ref["kind"] == "video" else core._load_image(ref["path"], PREVIEW_WIDTH))
            ref["status"] = "ready"
        except Exception as e:
            ref["status"] = "failed"
            ref["error"] = str(e)
        if ref is self.ref:
            self._emit("ref", self._ref_public())
            self._refresh_previews()

    def clear_reference(self):
        if not self.busy:
            self.ref = None
            self._emit("ref", None)
            for it in self.items.values():
                it["after"] = None
                self._emit("upsert", self._public(it))

    # clips
    def add_clips(self, paths):
        files = core.collect_files(paths)
        ref_path = os.path.abspath(self.ref["path"]) if self.ref else None
        known = {os.path.abspath(it["path"]) for it in self.items.values()}
        new = []
        with self.lock:
            for p in files:
                ap = os.path.abspath(p)
                if ap in known or ap == ref_path:
                    continue
                known.add(ap)
                it = {"id": self.next_id, "path": p, "size": _human(os.path.getsize(p)), "kind": core.kind_of(p),
                      "status": "loading"}
                self.items[self.next_id] = it
                self.next_id += 1
                new.append(it)
        if not files:
            self._emit("toast", {"text": "No supported photos or videos there", "err": True})
        for it in new:
            self._emit("upsert", self._public(it))
        if new:
            threading.Thread(target=self._load_clips, args=(new,), daemon=True).start()

    def _load_clips(self, items):
        for it in items:
            try:
                it["auto_source"] = core.resolve_source(it["path"], "auto")
                it["frames"] = core.load_frames(it["path"], width=PREVIEW_WIDTH // 2)
                if it["kind"] == "video":
                    it["poster"] = core.poster(core.load_frames(it["path"], count=1, width=PREVIEW_WIDTH))
                else:
                    it["poster"] = core._load_image(it["path"], PREVIEW_WIDTH)
                it["before"] = _jpeg(it["poster"])
                it["status"] = "ready"
            except Exception as e:
                it["status"] = "unsupported"
                it["error"] = str(e)
            self._preview(it)
            self._emit("upsert", self._public(it))

    def _preview(self, it, gen=None):
        ref = self.ref
        if not ref or ref.get("status") != "ready" or "poster" not in it:
            it["after"] = None
            return
        o = self._opts()
        try:
            cm = core.fit(it["frames"], ref["frames"], o["strength"], o["keep_luma"],
                          self._src_for(it), self._ref_source())
            table = cm.lut(core.LUT_SIZE)
            if gen is not None and gen != self.preview_gen:
                return
            it["after"] = _jpeg(core.apply_lut(it["poster"], table))
        except Exception as e:
            it["after"] = None
            it["error"] = str(e)

    def _refresh_previews(self):
        self.preview_gen += 1
        gen = self.preview_gen

        def run():
            for it in list(self.items.values()):
                if gen != self.preview_gen:
                    return
                if it["status"] in ("loading", "unsupported"):
                    continue
                self._preview(it, gen)
                if gen == self.preview_gen:
                    self._emit("upsert", self._public(it))
        threading.Thread(target=run, daemon=True).start()

    def remove(self, item_id):
        with self.lock:
            self.items.pop(int(item_id), None)

    def clear(self):
        if not self.busy:
            with self.lock:
                self.items.clear()

    def make_reference(self, item_id):
        it = self.items.get(int(item_id))
        if it and not self.busy:
            old = self.ref["path"] if self.ref else None
            self.set_reference(it["path"])
            if old:
                self.add_clips([old])

    # the batch
    def match(self, mode, custom_dir):
        if self.busy or not self.ref or self.ref.get("status") != "ready":
            return
        todo = [it for it in self.items.values() if it["status"] in ("ready", "failed", "done")]
        if not todo:
            return
        self.busy = True
        o = self._opts()
        o["refine"] = bool(self.settings.get("refine")) and refine.has_key()
        threading.Thread(target=self._match, args=(todo, mode, custom_dir, o), daemon=True).start()

    def _match(self, todo, mode, custom_dir, o):
        ok = 0
        last_dir = None
        self._emit("busy", {"busy": True, "total": len(todo)})
        ref = self.ref
        for i, it in enumerate(todo):
            src = it["path"]
            out_dir = custom_dir if (mode == "custom" and custom_dir) else os.path.join(os.path.dirname(src), "graded")
            it["status"] = "matching"
            it["progress"] = 0
            it["error"] = it["note"] = it["warn"] = None
            self._emit("upsert", self._public(it))

            refiner = None
            if o.get("refine"):
                def status(msg, it=it):
                    it["status"] = "refining"
                    it["note"] = msg
                    self._emit("upsert", self._public(it))
                refiner = refine.Refiner(status=status, soft=True)

            def prog(p, it=it, i=i):
                it["progress"] = p
                self._emit("progress", {"id": it["id"], "p": p, "done": i + p, "total": len(todo)})

            try:
                def prog_and_status(p, prog=prog, it=it):
                    if it["status"] != "matching":
                        it["status"] = "matching"
                        it["note"] = None
                        self._emit("upsert", self._public(it))
                    prog(p)

                r = core.match(src, ref["path"], out_dir, o["strength"], o["keep_luma"], o["codec"], o["lut_only"],
                               ref_frames=ref["frames"], progress=prog_and_status,
                               source=self._src_for(it), ref_source=self._ref_source(), refine=refiner)
                it["cube"], it["graded"] = r.cube, r.graded
                it["note"] = r.match.notes[-1] if r.match.notes else None
                it["warn"] = getattr(r.match, "refine_error", None)
                if r.match.adjust is not None and "poster" in it:
                    it["after"] = _jpeg(core.apply_lut(it["poster"], r.match.lut()))
                it["status"] = "done"
                ok += 1
                last_dir = out_dir
            except Exception as e:
                it["status"] = "failed"
                it["error"] = str(e)
            self._emit("upsert", self._public(it))
            self._emit("progress", {"done": i + 1, "total": len(todo)})
        self.busy = False
        self._emit("busy", {"busy": False})
        self._emit("finished", {"ok": ok, "total": len(todo), "dir": last_dir})
        if ok and last_dir and self.settings.get("open_after"):
            self.reveal(last_dir)

    def reveal(self, path):
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path] if os.path.isfile(path) else ["open", path])
            elif os.name == "nt":
                if os.path.isfile(path):
                    subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
                else:
                    os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(path) if os.path.isfile(path) else path])
        except Exception:
            pass


# ---- native window chrome -------------------------------------------------

def _style_mac(window):
    """Dark, transparent title bar with content running underneath (like Dwn)."""
    try:
        import AppKit
        from PyObjCTools import AppHelper

        def apply():
            w = window.native
            w.setStyleMask_(w.styleMask() | AppKit.NSWindowStyleMaskFullSizeContentView)
            w.setTitlebarAppearsTransparent_(True)
            w.setTitleVisibility_(AppKit.NSWindowTitleHidden)
            w.setAppearance_(AppKit.NSAppearance.appearanceNamed_(AppKit.NSAppearanceNameDarkAqua))
            w.setBackgroundColor_(AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(0.043, 0.043, 0.047, 1.0))
            w.setMovableByWindowBackground_(False)
            try:
                w.contentView().superview().subviews().lastObject().setBackgroundColor_(AppKit.NSColor.clearColor())
            except Exception:
                pass
            if hasattr(w, "setToolbarStyle_"):
                w.setToolbarStyle_(AppKit.NSWindowToolbarStyleUnifiedCompact)

        AppHelper.callAfter(apply)
    except Exception:
        pass


def _style_windows(window):
    """Dark title bar on Windows 10/11; caption colour matches the app on Windows 11."""
    try:
        import ctypes

        hwnd = window.native.Handle.ToInt32()
        dwm = ctypes.windll.dwmapi
        on = ctypes.c_int(1)
        for attr in (20, 19):
            if dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(on), 4) == 0:
                break
        caption = ctypes.c_int(0x000C0B0B)
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), 4)
    except Exception:
        pass


def main():
    api = Api()
    webview.settings["DRAG_REGION_DIRECT_TARGET_ONLY"] = True
    window = webview.create_window(
        "Lut", url=os.path.join(UI_DIR, "index.html"), js_api=api,
        width=1180, height=760, min_size=(920, 600), background_color=BG, easy_drag=False,
    )
    api.window = window

    def on_drop(e):
        files = (e.get("dataTransfer") or {}).get("files") or []
        paths = [f.get("pywebviewFullPath") for f in files if f.get("pywebviewFullPath")]
        if not paths:
            return
        # app.js records which half of the window the files were dropped on.
        try:
            zone = window.evaluate_js("window.__lutZone || ''")
        except Exception:
            zone = ""
        api.dropped(paths, zone)

    def on_loaded():
        try:
            window.dom.document.events.drop += DOMEventHandler(on_drop, True, True)
        except Exception:
            pass

    def quit_for_install():
        try:
            window.destroy()
        finally:
            threading.Timer(3.0, lambda: os._exit(0)).start()

    api.updater.on_quit_for_install = quit_for_install
    window.events.closing += lambda: api.updater.install_on_quit()
    window.events.loaded += lambda: api.updater.start()

    if sys.platform == "darwin":
        window.events.before_show += lambda: _style_mac(window)
    elif os.name == "nt":
        window.events.shown += lambda: _style_windows(window)
    window.events.loaded += on_loaded
    webview.start(debug=bool(os.environ.get("LUT_DEBUG")))


if __name__ == "__main__":
    main()
