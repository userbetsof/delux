import http.client
import ssl
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

HOST = "46.flashscore.ninja"
HEADERS = {"x-fsign": "SW9D1eZo"}
URLS = [
    ("маленький f_1_0", "/46/x/feed/f_1_0_-7_ru_1"),
    ("средний df_hh", "/46/x/feed/df_hh_1_6mdpltmc"),
    ("большой f_1_2", "/46/x/feed/f_1_2_-7_ru_1"),
]

ctx = ssl.create_default_context()

for label, path in URLS:
    # Один коннект на запрос, замеряем прогресс по чанкам
    t0 = time.time()
    conn = http.client.HTTPSConnection(HOST, 443, timeout=30, context=ctx)
    try:
        conn.request("GET", path, headers=HEADERS)
        resp = conn.getresponse()
        chunks = []
        first_at = None
        while True:
            chunk = resp.read(16384)
            if not chunk:
                break
            if first_at is None:
                first_at = time.time() - t0
            chunks.append(chunk)
        total = time.time() - t0
        size = sum(len(c) for c in chunks)
        rate = size / total / 1024 if total else 0
        print(
            f"{label:18}: {size:7} байт за {total:6.1f}s "
            f"(первый чанк {first_at:.2f}s, {rate:.0f} КБ/с)",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"{label:18}: ERR {type(exc).__name__} за {time.time()-t0:.1f}s")
    finally:
        conn.close()
