# PyInstaller build recipe for macOS (.app) and Windows (folder with .exe).
#   pyinstaller --noconfirm Lut.spec
import os
import sys

from PyInstaller.utils.hooks import collect_all

root = SPECPATH
version = open(os.path.join(root, "VERSION")).read().strip()

datas, binaries, hiddenimports = collect_all("imageio_ffmpeg")
datas += [
    (os.path.join(root, "lutmatch", "ui"), os.path.join("lutmatch", "ui")),
    (os.path.join(root, "VERSION"), "."),
]
hiddenimports += ["certifi"]
excludes = ["tkinter", "_tkinter", "matplotlib", "scipy"] if sys.platform == "darwin" else ["matplotlib", "scipy"]

a = Analysis(
    [os.path.join(root, "Lut.py")],
    pathex=[root],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=excludes,
)
pyz = PYZ(a.pure)
icon = os.path.join(root, "assets", "AppIcon.icns" if sys.platform == "darwin" else "icon.ico")

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Lut",
    console=False,
    icon=icon,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Lut")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Lut.app",
        icon=icon,
        bundle_identifier="com.yuvrajgarg.lut",
        version=version,
        info_plist={
            "CFBundleShortVersionString": version,
            "CFBundleVersion": version,
            "CFBundleDisplayName": "Lut",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSRequiresAquaSystemAppearance": False,
        },
    )
