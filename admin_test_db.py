"""Flask API для админки тестовой БД Flashscore.

Запуск:
    python admin_test_db.py

Открыть:
    http://localhost:8765/admin_test_db.html
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)

HTML_PATH = Path(__file__).parent / "admin_test_db.html"
MATCH_HTML_PATH = Path(__file__).parent / "match_detail.html"


@app.route("/")
@app.route("/admin_test_db.html")
def serve_ui():
    """Раздача HTML интерфейса."""
    return HTML_PATH.read_text(encoding="utf-8")


@app.route("/match/<match_id>")
def serve_match_page(match_id: str):
    """Страница отдельного матча (таблица лиги)."""
    return MATCH_HTML_PATH.read_text(encoding="utf-8")

DB_PATH = Path(__file__).parent / "test_flashscore.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/api/testdb/data")
def get_data() -> Any:
    """Все данные из БД."""
    conn = get_db()
    try:
        matches = [dict(m) for m in conn.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.score_home,
                m.score_away,
                m.match_status,
                th.name AS home_team,
                ta.name AS away_team
            FROM matches m
            JOIN teams th ON th.id = m.home_team_id
            JOIN teams ta ON ta.id = m.away_team_id
            ORDER BY m.match_date DESC, m.match_id DESC
        """).fetchall()]
        
        # Debug: покажу первые 3 матча
        if matches:
            print(f"[DEBUG] First match: {matches[0]}")
            print(f"[DEBUG] All match dates: {[m.get('match_date') for m in matches[:5]]}")

        teams = [dict(t) for t in conn.execute(
            "SELECT id, name, tournament_id FROM teams ORDER BY name"
        ).fetchall()]

        feeds = [dict(f) for f in conn.execute("""
            SELECT id, feed_type, feed_url, parsed_at
            FROM feed_snapshots
            ORDER BY parsed_at DESC
        """).fetchall()]

        snapshots = [dict(s) for s in conn.execute("""
            SELECT match_id, MIN(snapshot_date) AS snapshot_date
            FROM standings_snapshot
            GROUP BY match_id
            ORDER BY snapshot_date DESC, match_id DESC
        """).fetchall()]

        return jsonify({
            "matches": matches,
            "teams": teams,
            "feed_snapshots": feeds,
            "standings_snapshots": snapshots,
        })
    finally:
        conn.close()


@app.route("/api/testdb/standings")
def get_standings() -> Any:
    """Таблица лиги на момент матча (type: overall/home/away)."""
    match_id = request.args.get("match_id", "")
    table_type = request.args.get("type", "overall")
    if not match_id:
        return jsonify([])

    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT team_name, rank, played, wins, draws, losses,
                   scored, conceded, points
            FROM standings_snapshot
            WHERE match_id = ? AND table_type = ?
            ORDER BY rank ASC
        """, (match_id, table_type)).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/api/testdb/matches/<match_id>")
def get_match(match_id: str) -> Any:
    """Детальная информация о матче."""
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.score_home,
                m.score_away,
                m.match_status,
                th.name AS home_team,
                ta.name AS away_team
            FROM matches m
            JOIN teams th ON th.id = m.home_team_id
            JOIN teams ta ON ta.id = m.away_team_id
            WHERE m.match_id = ?
        """, (match_id,)).fetchone()

        if not row:
            return jsonify({"error": "Not found"}), 404

        result = dict(row)

        # Feed snapshots для матча
        feeds = [dict(f) for f in conn.execute("""
            SELECT feed_type, feed_url, parsed_at
            FROM feed_snapshots
            WHERE match_id = ?
            ORDER BY parsed_at DESC
        """, (match_id,)).fetchall()]
        result["feeds"] = feeds

        return jsonify(result)
    finally:
        conn.close()


@app.route("/api/testdb/glicko2")
def get_glicko2() -> Any:
    """Glicko-2 рейтинги команд матча (из matches.db)."""
    match_id = request.args.get("match_id", "")
    if not match_id:
        return jsonify([])

    from db import database_path, get_db_connection

    rows_out: List[Dict[str, Any]] = []
    with database_path("matches.db"):
        with get_db_connection() as conn:
            match = conn.execute(
                """
                SELECT m.sport, m.home_team_id, m.away_team_id,
                       th.name AS home_name, ta.name AS away_name
                FROM matches m
                JOIN teams th ON th.id = m.home_team_id
                JOIN teams ta ON ta.id = m.away_team_id
                WHERE m.match_id = ?
                """,
                (match_id,),
            ).fetchone()
            if not match:
                return jsonify([])

            sport = match["sport"]
            for team_id, side in ((match["home_team_id"], "home"), (match["away_team_id"], "away")):
                row = conn.execute(
                    """
                    SELECT gr.*, t.name AS team_name
                    FROM glicko2_ratings gr
                    JOIN teams t ON t.id = gr.team_id
                    WHERE gr.team_id = ? AND gr.sport = ?
                    """,
                    (team_id, sport),
                ).fetchone()
                if row:
                    d = dict(row)
                    d["side"] = side
                    rows_out.append(d)

    return jsonify(rows_out)


def main():
    host = "0.0.0.0"
    port = 8765
    print(f"\n  Flask API: http://localhost:{port}")
    print(f"  HTML UI:   http://localhost:{port}/admin_test_db.html\n")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
