"""
Моковый API для проверки результатов матчей.
Отдаёт список незавершённых матчей с полями: match_id, score_home, score_away, minute, segment, match_status, profit.
Запуск: python mock_match_api.py
"""
import os
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify

load_dotenv()

app = Flask(__name__)
MOCK_API_PORT = int(os.environ.get("MOCK_MATCH_API_PORT", "5000"))


def get_mock_unfinished_matches() -> list[dict[str, Any]]:
    """Пример данных: незавершённые матчи с текущим счётом и статусом."""
    return [
        {
            "match_id": "1001",
            "score_home": 1,
            "score_away": 0,
            "minute": "67",
            "segment": "2",
            "match_status": "Идёт",
            "profit": 0.0,
        },
        {
            "match_id": "1002",
            "score_home": 2,
            "score_away": 2,
            "minute": "90+",
            "segment": "3",
            "match_status": "Идёт",
            "profit": 0.0,
        },
        {
            "match_id": "1003",
            "score_home": 0,
            "score_away": 1,
            "minute": "23",
            "segment": "1",
            "match_status": "Идёт",
            "profit": 0.0,
        },
    ]


@app.route("/unfinished-matches", methods=["GET"])
def unfinished_matches():
    """Список незавершённых матчей для обновления в БД."""
    matches = get_mock_unfinished_matches()
    return jsonify(matches)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=MOCK_API_PORT, debug=False)
