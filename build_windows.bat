@echo off
REM Builds dist\Lut\Lut.exe (ffmpeg bundled). Run on Windows with Python 3.9+ installed.
cd /d "%~dp0"
py -3 -m venv .venv-build || python -m venv .venv-build
call .venv-build\Scripts\activate.bat
python -m pip install --upgrade pip
pip install pyinstaller certifi -r requirements.txt
pyinstaller --noconfirm --log-level WARN Lut.spec
echo.
echo Done: dist\Lut\Lut.exe
pause
