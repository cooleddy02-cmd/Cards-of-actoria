"""
Cards of Factoria — desktop wrapper.
Opens the deployed web app in a native window using pywebview.
URL can be overridden by editing config.json next to the exe.
"""
import json
import os
import sys
import webview

DEFAULT_URL = "https://cards-of-factoria.replit.app"

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

def main():
    url = _load_url()
    webview.create_window(
        title="Cards of Factoria",
        url=url,
        width=1280,
        height=820,
        min_size=(900, 600),
        background_color="#0d0d0d",
        text_select=False,
    )
    webview.start()

if __name__ == "__main__":
    main()
