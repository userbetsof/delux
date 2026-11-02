"""Проверка tool calling у модели Ollama через /api/chat."""

import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen3.5:4b"
URL = "http://127.0.0.1:11434/api/chat"

payload = {
    "model": MODEL,
    "messages": [
        {"role": "user", "content": "Какая сейчас погода в Москве?"}
    ],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Узнать погоду в городе",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "Название города"}
                    },
                    "required": ["city"],
                },
            },
        }
    ],
    "stream": False,
}

req = urllib.request.Request(
    URL,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)

try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
except Exception as exc:  # noqa: BLE001
    print(f"[!] ошибка: {exc}")
    raise SystemExit(1)

msg = data.get("message", {})
calls = msg.get("tool_calls") or []

print(f"модель: {MODEL}")
if calls:
    print("[+] tool calling РАБОТАЕТ")
    for c in calls:
        fn = c.get("function", {})
        print(f"    вызвана функция: {fn.get('name')}")
        print(f"    аргументы: {fn.get('arguments')}")
else:
    print("[!] tool_calls пусто")
    print(f"    ответ модели: {str(msg.get('content'))[:300]}")
