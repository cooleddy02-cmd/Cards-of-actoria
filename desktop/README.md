# Cards of Factoria — Desktop (.exe)

A thin native window wrapper around the deployed web app. Looks and feels like
a real desktop app while still using the live multiplayer server.

## What's in this folder

- `main.py` — pywebview wrapper (~30 lines) that opens the app URL in a native window
- `icon.ico` — Windows multi-resolution app icon (fanned cards / FACTORIA banner)
- `config.json` — change the URL here without rebuilding (sits next to the exe)
- `requirements.txt` — pywebview + pyinstaller
- `build.bat` — one-click local build script for Windows
- `../.github/workflows/build-exe.yml` — auto-build on every push (GitHub Actions, Windows runner)

## Option A — Automatic build (recommended)

1. Push this project to a GitHub repo
2. Every push to `main` triggers `.github/workflows/build-exe.yml`
3. Go to your repo → **Actions** tab → click the latest "Build Windows EXE" run
4. Scroll to the bottom → download the **CardsOfFactoria-Windows** artifact (zip)
5. Unzip → double-click `CardsOfFactoria.exe`

For a tagged release (creates a downloadable Release page):
```bash
git tag v1.0.0 && git push --tags
```

## Option B — Build locally on a Windows PC

Requirements: Python 3.11+ installed and on PATH.

1. Copy this `desktop/` folder to your Windows machine
2. Open a Command Prompt in that folder
3. Run `build.bat`
4. The exe lands in `dist\CardsOfFactoria.exe`

## Changing the server URL

Edit `config.json` next to the exe — no rebuild needed:
```json
{ "url": "https://your-deployed-url.replit.app" }
```

## Notes

- The exe is ~15-25 MB (pywebview uses the OS's built-in WebView2 / Edge runtime on Windows 10+)
- WebView2 is installed by default on Windows 11 and most updated Windows 10 machines
- Multiplayer, marketplace, and gem gifting all work because the exe just renders the live deployed app
- Replace the deployed URL with `http://localhost:5000` to point at a local dev server
