"""Замер: помогают ли параллельные запросы.

Если канал просто узкий — суммарная скорость не изменится.
Если теряются пакеты (один поток ждёт ретрансмита) — сумма вырастет.
"""

import http.client
import ssl
import sys
import threading
import time

sys.stdout.reconfigure(encoding="utf-8")

HOST = "46.flashscore.ninja"
HEADERS = {"x-fsign": "SW9D1eZo"}
# Разные матчи/дни — разные URL, чтобы не бить кэш
PATHS = [
    "/46/x/feed/f_1_2_-7_ru_1",
    "/46/x/feed/f_1_3_-7_ru_1",
    "/46/x/feed/f_1_4_-7_ru_1",
]

ctx = ssl.create_default_context()
results = []
lock = threading.Lock()


def fetch(path, idx):
    t0 = time.time()
    conn = http.client.HTTPSConnection(HOST, 443, timeout=40, context=ctx)
    try:
        conn.request("GET", path, headers=HEADERS)
        resp = conn.getresponse()
        size = 0
        while True:
            chunk = resp.read(32768)
            if not chunk:
                break
            size += len(chunk)
        el = time.time() - t0
        with lock:
            results.append((idx, size, el, "ok"))
    except Exception as exc:  # noqa: BLE001
        with lock:
            results.append((idx, 0, time.time() - t0, type(exc).__name__))
    finally:
        conn.close()


print("=== ПОСЛЕДОВАТЕЛЬНО ===")
t0 = time.time()
for i, p in enumerate(PATHS):
    fetch(p, i)
seq_total = time.time() - t0
seq_bytes = sum(r[1] for r in results)
for idx, size, el, st in sorted(results):
    print(f"  #{idx}: {size} байт за {el:.1f}s {st}")
print(f"  ИТОГО: {seq_bytes} байт за {seq_total:.1f}s = {seq_bytes/seq_total/1024:.0f} КБ/с")

results.clear()
print("\n=== ПАРАЛЛЕЛЬНО ===")
t0 = time.time()
threads = [threading.Thread(target=fetch, args=(p, i)) for i, p in enumerate(PATHS)]
for t in threads:
    t.start()
for t in threads:
    t.join()
par_total = time.time() - t0
par_bytes = sum(r[1] for r in results)
for idx, size, el, st in sorted(results):
    print(f"  #{idx}: {size} байт за {el:.1f}s {st}")
print(f"  ИТОГО: {par_bytes} байт за {par_total:.1f}s = {par_bytes/par_total/1024:.0f} КБ/с")

if seq_bytes and par_bytes:
    print(f"\nУскорение: {seq_total/par_total:.1f}x")
