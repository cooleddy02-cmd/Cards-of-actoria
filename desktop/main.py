"""
Cards of Factoria — desktop wrapper.
Opens the deployed web app in a native window using pywebview.
URL can be overridden by editing config.json next to the exe.
"""
import ctypes
import json
import os
import sys
import tempfile
import webview

DEFAULT_URL = "https://cards-of-factoria.replit.app"
WEBVIEW2_DOWNLOAD = "https://developer.microsoft.com/microsoft-edge/webview2/"

def _exe_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _load_url():
    cfg_path = os.path.join(_exe_dir(), "config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            url = data.get("url", "").strip()
            if url:
                return url
        except Exception:
            pass
    return DEFAULT_URL

def _webview2_installed():
    """Best-effort check for the WebView2 runtime on Windows."""
    if not sys.platform.startswith("win"):
        return True
    try:
        import winreg
        for hive, path in [
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
            (winreg.HKEY_CURRENT_USER,
             r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
        ]:
            try:
                with winreg.OpenKey(hive, path) as k:
                    version, _ = winreg.QueryValueEx(k, "pv")
                    if version and version != "0.0.0.0":
                        return True
            except OSError:
                continue
    except Exception:
        pass
    return False

def _show_missing_webview2():
    if sys.platform.startswith("win"):
        msg = (
            "Cards of Factoria needs the Microsoft Edge WebView2 Runtime.\n\n"
            "Click OK to open the download page in your browser.\n"
            "After installing it (~30 seconds), launch Cards of Factoria again."
        )
        ctypes.windll.user32.MessageBoxW(0, msg, "WebView2 Runtime Required", 0x40)
        try:
            os.startfile(WEBVIEW2_DOWNLOAD)
        except Exception:
            pass

def main():
    if not _webview2_installed():
        _show_missing_webview2()
        return
    url = _load_url()

    # Give WebView2 a guaranteed-writable data folder (otherwise it can
    # init then silently fail to navigate when running from restricted dirs).
    user_data = os.path.join(tempfile.gettempdir(), "CardsOfFactoria-WebView2")
    os.makedirs(user_data, exist_ok=True)
    os.environ["WEBVIEW2_USER_DATA_FOLDER"] = user_data

    window = webview.create_window(
        title="Cards of Factoria",
        url=url,
        width=1280,
        height=820,
        min_size=(900, 600),
        background_color="#0d0d0d",
        text_select=False,
    )

    def _on_loaded():
        # If page loads, this fires. Good signal it's working.
        pass

    def _on_started():
        # Force-reload after a short delay in case initial nav was dropped.
        try:
            window.load_url(url)
        except Exception:
            pass

    window.events.loaded += _on_loaded

    try:
        # debug=True enables right-click → Inspect for diagnostics.
        # Let pywebview auto-detect the GUI backend (WebView2 on Win11).
        webview.start(debug=True, func=_on_started)
    except Exception as e:
        if sys.platform.startswith("win"):
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Failed to start the embedded browser engine.\n\n{e}\n\n"
                "Try installing/repairing Microsoft Edge WebView2 Runtime.",
                "Cards of Factoria — Error", 0x10)

if __name__ == "__main__":
    main()
