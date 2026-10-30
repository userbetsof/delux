import socket
import ssl
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

HOST = "46.flashscore.ninja"
URL = f"https://{HOST}/46/x/feed/f_1_0_-7_ru_1"
HEADERS = {"x-fsign": "SW9D1eZo"}


def dns_lookup():
    """Сколько занимает резолв имени."""
    times = []
    for _ in range(3):
        t0 = time.time()
        try:
            ips = socket.getaddrinfo(HOST, 443, proto=socket.IPPROTO_TCP)
            times.append((time.time() - t0, ips[0][4][0]))
        except Exception as exc:  # noqa: BLE001
            times.append((time.time() - t0, f"ERR {exc}"))
    return times


def tcp_connect(ip):
    """Время установки TCP-соединения."""
    t0 = time.time()
    try:
        s = socket.create_connection((ip, 443), timeout=10)
        s.close()
        return time.time() - t0, "ok"
    except Exception as exc:  # noqa: BLE001
        return time.time() - t0, type(exc).__name__


def tls_handshake(ip):
    """Время TLS-рукопожатия."""
    ctx = ssl.create_default_context()
    t0 = time.time()
    try:
        with socket.create_connection((ip, 443), timeout=10) as raw:
            with ctx.wrap_socket(raw, server_hostname=HOST):
                pass
        return time.time() - t0, "ok"
    except Exception as exc:  # noqa: BLE001
        return time.time() - t0, type(exc).__name__


def download(ip=None):
    """Полный запрос: заголовки + тело."""
    t0 = time.time()
    try:
        req = urllib.request.Request(URL, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            first = time.time() - t0
            body = resp.read()
            total = time.time() - t0
        return first, total, len(body), "ok"
    except Exception as exc:  # noqa: BLE001
        return 0, time.time() - t0, 0, type(exc).__name__


print("=== DNS ===")
for el, ip in dns_lookup():
    print(f"  {el:6.2f}s  {ip}")

ips = [ip for _, ip in dns_lookup() if not ip.startswith("ERR")]
if ips:
    ip = ips[0]
    print(f"\n=== TCP / TLS к {ip} ===")
    for i in range(3):
        el, st = tcp_connect(ip)
        print(f"  TCP  #{i+1}: {el:6.2f}s {st}")
    for i in range(3):
        el, st = tls_handshake(ip)
        print(f"  TLS  #{i+1}: {el:6.2f}s {st}")

print("\n=== полный запрос ===")
for i in range(3):
    first, total, size, st = download()
    print(f"  #{i+1}: заголовки {first:5.2f}s, всего {total:6.2f}s, {size} байт, {st}")
