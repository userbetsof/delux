"""Гипотеза: сервер режет скорость по объёму за период (rate limit).

Качаем один и тот же файл подряд. Если первый раз быстро, а дальше
всё медленнее — это лимит. Если скорость случайна — потери пакетов.
"""

import ssl
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

PATH = "https://46.flashscore.ninja/46/x/feed/f_1_2_-7_ru_1"
HEADERS = {"x-fsign": "SW9D1eZo", "User-Agent": "Mozilla/5.0"}

print("качаем один файл 8 раз подряд:")
for i in range(8):
    t0 = time.time()
    try:
        req = urllib.request.Request(PATH, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = resp.read()
        el = time.time() - t0
        rate = len(data) / el / 1024
        print(f"  #{i+1}: {el:6.1f}s  {rate:6.0f} КБ/с", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"  #{i+1}: {time.time()-t0:6.1f}s  ERR {type(exc).__name__}", flush=True)
    time.sleep(1)
