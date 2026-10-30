"""Проверка: режут именно Flashscore или «интернет» в целом.

Качаем одинаковый объём с разных хостов и сравниваем скорость.
Если другие быстрые — дело в конкретном сервере (throttling/маршрут).
"""

import ssl
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

TESTS = [
    ("Flashscore .ninja", "https://46.flashscore.ninja/46/x/feed/f_1_2_-7_ru_1",
     {"x-fsign": "SW9D1eZo"}),
    ("Google (204)", "https://www.google.com/generate_204", {}),
    ("Cloudflare", "https://cloudflare.com/cdn-cgi/trace", {}),
    ("GitHub API", "https://api.github.com/zen", {}),
]

for label, url, extra in TESTS:
    headers = {"User-Agent": "Mozilla/5.0", **extra}
    times = []
    for attempt in range(2):
        t0 = time.time()
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
            times.append((time.time() - t0, len(data), "ok"))
        except Exception as exc:  # noqa: BLE001
            times.append((time.time() - t0, 0, type(exc).__name__))
    for el, size, st in times:
        rate = size / el / 1024 if el else 0
        print(f"{label:20}: {size:7} байт {el:6.2f}s {st:12} {rate:6.0f} КБ/с", flush=True)
