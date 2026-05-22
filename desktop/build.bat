@echo off
REM Local Windows build script — run this on a Windows PC with Python 3.11+ installed.
REM Produces dist\CardsOfFactoria.exe

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

pyinstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --name "CardsOfFactoria" ^
  --icon "icon.ico" ^
  main.py

echo.
echo ======================================================
echo  Build complete: dist\CardsOfFactoria.exe
echo  (config.json next to the exe lets you change the URL)
echo ======================================================
pause
