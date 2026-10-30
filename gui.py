"""
POLIZ Kalkulyatori — oyna.

Interfeys ui/ papkasida (HTML/CSS/JS, Liquid Glass uslubi). Python kiçik lokal
server oçadi va hisoblaşni poliz.py orqali bajaradi:

  GET  /...          ui/ fayllari
  POST /api/<nom>    Api metodlari, argumentlar — JSON röyxat

pywebview örnatilgan bölsa — native oyna (macOSda haqiqiy vibrancy bilan),
aks holda — standart brauzerda oçiladi.

  python poliz_kalkulyator.py             # oyna
  python poliz_kalkulyator.py --browser   # majburan brauzerda
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from poliz import PolizError, calculate

APP_TITLE = "POLIZ Kalkulyatori"
UI_DIR = Path(__file__).resolve().with_name("ui")
HISTORY_FILE = Path.home() / ".poliz_tarix.json"
HISTORY_LIMIT = 100


class Api:
    """Interfeys çaqiradigan metodlar. Har biri JSON ga aylantiriladigan qiymat qaytaradi."""

    def __init__(self, history_file: Path = HISTORY_FILE):
        self.history_file = history_file
        self.lock = threading.Lock()

    def calculate(self, expr: str, values: dict | None = None) -> dict:
        try:
            return {"ok": True, "result": calculate(expr, values).to_dict()}
        except PolizError as err:
            return {"ok": False,
                    "error": {"message": err.message, "pos": err.pos, "length": err.length}}

    def history(self) -> list[dict]:
        try:
            data = json.loads(self.history_file.read_text(encoding="utf-8"))
            return [h for h in data if isinstance(h, dict) and "expr" in h][:HISTORY_LIMIT]
        except (OSError, ValueError):
            return []

    def add_history(self, item: dict) -> list[dict]:
        with self.lock:
            items = [h for h in self.history() if h["expr"] != item.get("expr")]
            items.insert(0, item)
            self._save(items[:HISTORY_LIMIT])
            return items[:HISTORY_LIMIT]

    def clear_history(self) -> list[dict]:
        with self.lock:
            self._save([])
        return []

    def copy(self, text: str) -> bool:
        """Brauzer clipboard API sini bermasa — tizim buferiga yozamiz."""
        commands = {
            "darwin": [["pbcopy"]],
            "win32": [["clip"]],
        }.get(sys.platform, [["wl-copy"], ["xclip", "-selection", "clipboard"]])
        for cmd in commands:
            if shutil.which(cmd[0]):
                data = text.encode("utf-16le" if cmd[0] == "clip" else "utf-8")
                return subprocess.run(cmd, input=data, check=False).returncode == 0
        return False

    def _save(self, items: list[dict]) -> None:
        try:
            self.history_file.write_text(json.dumps(items, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
        except OSError:
            pass  # tarixni saqlab bölmasa ham dastur işlayveradi


API_METHODS = {"calculate", "history", "add_history", "clear_history", "copy"}


class Handler(SimpleHTTPRequestHandler):
    api: Api

    def do_POST(self):
        name = self.path.removeprefix("/api/")
        if name not in API_METHODS:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            args = json.loads(self.rfile.read(length) or b"[]")
            body = json.dumps(getattr(self.api, name)(*args), ensure_ascii=False).encode()
        except (ValueError, TypeError) as err:
            self.send_error(400, str(err))
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass  # konsolni sörovlar bilan töldirmaymiz


def start_server(api: Api | None = None, port: int = 0) -> ThreadingHTTPServer:
    handler = partial(type("BoundHandler", (Handler,), {"api": api or Api()}),
                      directory=str(UI_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _open_native(url: str) -> bool:
    try:
        import webview  # pywebview
    except ImportError:
        return False
    mac = sys.platform == "darwin"
    options = dict(width=1220, height=800, min_size=(940, 660), text_select=True)
    if mac:
        # Liquid Glass: oyna orqasidagi iş stoli xiralaşib körinadi (NSVisualEffectView)
        url += "?glass=native"
        options.update(transparent=True, vibrancy=True)
    try:
        window = webview.create_window(APP_TITLE, url, **options)
    except TypeError:  # pywebviewning eski versiyasi
        for key in ("vibrancy", "transparent", "text_select"):
            options.pop(key, None)
        window = webview.create_window(APP_TITLE, url.replace("?glass=native", ""), **options)
    if mac and options.get("transparent"):
        window.events.shown += lambda: _restore_mac_shadow(window)
    webview.start()
    return True


def _restore_mac_shadow(window) -> None:
    """pywebview şaffof oynaning soyasini öçiradi — macOSdagidek qaytaramiz."""
    try:
        from PyObjCTools import AppHelper

        def apply():
            if window.native is not None:
                window.native.setHasShadow_(True)
                window.native.invalidateShadow()

        AppHelper.callAfter(apply)  # AppKit faqat asosiy oqimda
    except Exception:  # bezak xolos — oyna soyasiz ham işlayveradi
        pass


def main():
    server = start_server()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    try:
        if "--browser" in sys.argv or not _open_native(url):
            print(f"{APP_TITLE}: {url}")
            print("pywebview topilmadi — brauzerda oçildi. Native oyna uçun: pip install pywebview")
            print("Töxtatiş: Ctrl+C")
            webbrowser.open(url)
            threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
