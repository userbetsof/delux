"""Сравнение: новый коннект на каждый запрос vs переиспользование.

При потерях пакетов рукопожатие и медленный старт TCP повторяются каждый
раз. Если держать соединение открытым — эти издержки платятся один раз.
"""

import http.client
import ssl
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

HOST = "46.flashscore.ninja"
HEADERS = {"x-fsign": "SW9D1eZo", "Connection": "keep-alive"}
PATHS = [f"/46/x/feed/f_1_{d}_-7_ru_1" for d in (0, 1, 2, 3)]

ctx = ssl.create_default_context()


def fresh_conns():
    total = 0
    times = []
    for p in PATHS:
        t0 = time.time()
        c = http.client.HTTPSConnection(HOST, 443, timeout=40, context=ctx)
        try:
            c.request("GET", p, headers=HEADERS)
            r = c.getresponse()
            size = len(r.read())
            total += size
            times.append((size, time.time() - t0, "ok"))
        except Exception as exc:  # noqa: BLE001
            times.append((0, time.time() - t0, type(exc).__name__))
        finally:
            c.close()
    return total, times, sum(t[1] for t in times)


def kept_conn():
    total = 0
    times = []
    c = http.client.HTTPSConnection(HOST, 443, timeout=40, context=ctx)
    try:
        for p in PATHS:
            t0 = time.time()
            try:
                c.request("GET", p, headers=HEADERS)
                r = c.getresponse()
                size = len(r.read())
                total += size
                times.append((size, time.time() - t0, "ok"))
            except Exception as exc:  # noqa: BLE001
                times.append((0, time.time() - t0, type(exc).__name__))
                break
    finally:
        c.close()
    return total, times, sum(t[1] for t in times)


for label, fn in (("новый коннект", fresh_conns), ("keep-alive", kept_conn)):
    total, times, el = fn()
    rate = total / el / 1024 if el else 0
    print(f"{label}:")
    for i, (size, t, st) in enumerate(times):
        print(f"  #{i}: {size:7} байт {t:6.1f}s {st}")
    print(f"  ИТОГО {total} байт за {el:.1f}s = {rate:.0f} КБ/с\n", flush=True)
