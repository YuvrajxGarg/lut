#!/bin/bash
# Builds "dist/Lut.app" (ffmpeg bundled). Run on a Mac.
#   ./build_mac.sh             build
#   ./build_mac.sh --install   build and copy to ~/Applications
#   ./build_mac.sh --release   build and make the update zip + .sha256 for a GitHub release
#
# Needs a Python with Tk 8.6+ / a modern WebKit host: we use uv's standalone Python
# if uv is installed, otherwise python.org / Homebrew Python.
set -e
cd "$(dirname "$0")"

PY=""
if command -v uv >/dev/null 2>&1; then
  uv python install 3.12 >/dev/null
  PY="$(uv python find 3.12)"
else
  for cand in /Library/Frameworks/Python.framework/Versions/3.*/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    if [ -x "$cand" ] && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
      PY="$cand"; break
    fi
  done
fi
if [ -z "$PY" ]; then
  echo "Need Python 3.9+. Install one of:"
  echo "  brew install uv            (then re-run this script)"
  echo "  https://www.python.org/downloads/macos/"
  exit 1
fi
echo "Building Lut $(cat VERSION) with $PY"

rm -rf .venv-build build dist
"$PY" -m venv .venv-build
source .venv-build/bin/activate
pip install --quiet --upgrade pip
pip install --quiet pyinstaller certifi -r requirements.txt
pyinstaller --noconfirm --log-level WARN Lut.spec
rm -rf "dist/Lut"   # the .app is the deliverable on macOS

if [ "$1" = "--release" ]; then
  (cd dist && ditto -c -k --keepParent Lut.app Lut-mac.zip \
    && shasum -a 256 Lut-mac.zip > Lut-mac.zip.sha256)
  echo "Release files: dist/Lut-mac.zip (+ .sha256)"
fi
if [ "$1" = "--install" ]; then
  mkdir -p ~/Applications
  rm -rf ~/Applications/Lut.app
  ditto dist/Lut.app ~/Applications/Lut.app
  echo "Installed to ~/Applications/Lut.app"
fi
echo
echo "Done: dist/Lut.app"
