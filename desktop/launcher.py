"""
Açık Analiz — Masaüstü başlatıcı sarmalayıcısı (PyInstaller giriş noktası).

Tek dosya .app/.exe içine gömülür. Yaptığı:
  1. Python motorunu (server/engine.py) aynı süreçte çalıştırır.
  2. Arka planda sağlık kontrolü yapıp motor hazır olunca tarayıcıyı otomatik açar.

Varsayım: server/engine.py doğrudan çalıştırılabilen bir script'tir
(çalıştırıldığında uvicorn sunucusunu 127.0.0.1:8765 üzerinde başlatır) —
mevcut başlatıcıların `python server/engine.py` çağrısıyla aynı model.
Motor farklı bir portta/giriş noktasında ise PORT ve ENGINE'i buna göre düzenleyin.
"""
import os
import sys
import time
import threading
import webbrowser
import runpy
from urllib.request import urlopen

PORT = 8765
HEALTH_URL = f"http://127.0.0.1:{PORT}/api/health"
APP_URL = f"http://127.0.0.1:{PORT}"


def _base_dir():
    # PyInstaller onefile: gömülü veriler sys._MEIPASS altına açılır
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


ENGINE = os.path.join(_base_dir(), "server", "engine.py")


def _open_browser_when_ready():
    for _ in range(180):  # ilk açılışta indirme yok (her şey gömülü), yine de geniş süre
        try:
            urlopen(HEALTH_URL, timeout=2)
            webbrowser.open(APP_URL)
            return
        except Exception:
            time.sleep(1)


def main():
    if not os.path.exists(ENGINE):
        sys.stderr.write(
            "server/engine.py bulunamadı — derleme sırasında 'server' klasörü "
            "gömülmemiş olabilir.\n"
        )
        sys.exit(1)
    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    # engine.py'yi __main__ olarak çalıştır (sunucuyu kendi başlatır)
    sys.argv = [ENGINE]
    runpy.run_path(ENGINE, run_name="__main__")


if __name__ == "__main__":
    main()
