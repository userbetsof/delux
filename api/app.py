import os
import sqlite3
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

DATABASE_PATH = os.environ.get("DATABASE_PATH", "C:\\papki\\work\\bets\\delux\\matches.db")
ADMIN_CORS_ORIGINS = os.environ.get("ADMIN_CORS_ORIGINS", "*")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(cur: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(r) for r in cur.fetchall()]


app = FastAPI(title="DeluX Admin API", version="0.1.0")

origins = ["*"] if ADMIN_CORS_ORIGINS.strip() == "*" else [o.strip() for o in ADMIN_CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/matches")
def list_matches(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    where = ""
    params: list[Any] = []
    if status:
        where = "WHERE match_status = ?"
        params.append(status)

    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT match_id, match_date, prediction, match_status, minute, segment, score_home, score_away, profit, sport
        FROM matches
        {where}
        ORDER BY match_date DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    )
    items = _rows(cur)

    cur.execute(f"SELECT COUNT(*) as cnt FROM matches {where}", params)
    total = int(cur.fetchone()["cnt"])
    conn.close()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@app.get("/matches/{match_id}")
def get_match(match_id: str):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM matches
        WHERE match_id = ?
        """,
        (match_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Match not found")
    return dict(row)


@app.get("/matches/{match_id}/odds")
def get_match_odds(match_id: str):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM odds
        WHERE match_id = ?
        ORDER BY id DESC
        """,
        (match_id,),
    )
    items = _rows(cur)
    conn.close()
    return {"items": items}


@app.get("/matches/{match_id}/outcome-probabilities")
def get_outcome_probabilities(match_id: str):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT o.*, s.strategy_name
        FROM outcome_probabilities o
        LEFT JOIN sub_strategies s ON s.id = o.strategy_id
        WHERE o.match_id = ?
        ORDER BY o.strategy_id ASC
        """,
        (match_id,),
    )
    items = _rows(cur)
    conn.close()
    return {"items": items}


@app.get("/matches/{match_id}/goal-probabilities")
def get_goal_probabilities(match_id: str):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM goal_probabilities
        WHERE match_id = ?
        """,
        (match_id,),
    )
    row = cur.fetchone()
    conn.close()
    return {"item": dict(row) if row else None}


@app.get("/countries")
def list_countries():
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name
        FROM countries
        ORDER BY name
        """
    )
    items = _rows(cur)
    conn.close()
    return {"items": items}


@app.get("/leagues")
def list_leagues(country_id: Optional[int] = None):
    conn = _connect()
    cur = conn.cursor()
    if country_id is not None:
        cur.execute(
            """
            SELECT l.id, l.name, l.country_id, c.name AS country_name
            FROM leagues l
            LEFT JOIN countries c ON c.id = l.country_id
            WHERE l.country_id = ?
            ORDER BY l.name
            """,
            (country_id,),
        )
    else:
        cur.execute(
            """
            SELECT l.id, l.name, l.country_id, c.name AS country_name
            FROM leagues l
            LEFT JOIN countries c ON c.id = l.country_id
            ORDER BY c.name, l.name
            """
        )
    items = _rows(cur)
    conn.close()
    return {"items": items}


@app.get("/teams")
def list_teams():
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name
        FROM teams
        ORDER BY name
        """
    )
    items = _rows(cur)
    conn.close()
    return {"items": items}


@app.get("/odds")
def list_odds(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT o.*, m.match_date, m.prediction, m.match_status, m.score_home, m.score_away
        FROM odds o
        LEFT JOIN matches m ON m.match_id = o.match_id
        ORDER BY o.id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    items = _rows(cur)
    cur.execute("SELECT COUNT(*) as cnt FROM odds")
    total = int(cur.fetchone()["cnt"])
    conn.close()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@app.get("/goal-probabilities")
def list_goal_probabilities(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM goal_probabilities
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    items = _rows(cur)
    cur.execute("SELECT COUNT(*) as cnt FROM goal_probabilities")
    total = int(cur.fetchone()["cnt"])
    conn.close()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@app.get("/sub-strategies")
def list_sub_strategies():
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, strategy_name, description
        FROM sub_strategies
        ORDER BY id ASC
        """
    )
    items = _rows(cur)
    conn.close()
    return {"items": items}


@app.get("/strategies")
def list_strategies():
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, description
        FROM strategies
        ORDER BY id ASC
        """
    )
    items = _rows(cur)
    conn.close()
    return {"items": items}


class StrategyPayload(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: Optional[str] = None


@app.post("/strategies")
def create_strategy(payload: StrategyPayload):
    conn = _connect()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO strategies (name, description)
            VALUES (?, ?)
            """,
            (payload.name.strip(), payload.description),
        )
        strategy_id = cur.lastrowid
        conn.commit()
        cur.execute("SELECT id, name, description FROM strategies WHERE id = ?", (strategy_id,))
        row = cur.fetchone()
        return {"item": dict(row)}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Strategy with this name already exists")
    finally:
        conn.close()


@app.put("/strategies/{strategy_id}")
def update_strategy(strategy_id: int, payload: StrategyPayload):
    conn = _connect()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE strategies
            SET name = ?, description = ?
            WHERE id = ?
            """,
            (payload.name.strip(), payload.description, strategy_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Strategy not found")
        conn.commit()
        cur.execute("SELECT id, name, description FROM strategies WHERE id = ?", (strategy_id,))
        row = cur.fetchone()
        return {"item": dict(row)}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Strategy with this name already exists")
    finally:
        conn.close()


@app.delete("/strategies/{strategy_id}")
def delete_strategy(strategy_id: int):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Strategy not found")
    conn.commit()
    conn.close()
    return {"ok": True}


class StrategyPredictionPayload(BaseModel):
    match_id: str = Field(min_length=1, max_length=8)
    strategy_id: int
    prediction: Optional[str] = None
    odds: Optional[float] = None
    stake: Optional[float] = None
    result: Optional[str] = None
    profit: Optional[float] = None
    notes: Optional[str] = None


@app.get("/strategy-predictions")
def list_strategy_predictions(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT sp.*, s.name AS strategy_name
        FROM strategy_predictions sp
        LEFT JOIN strategies s ON s.id = sp.strategy_id
        ORDER BY sp.id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    items = _rows(cur)
    cur.execute("SELECT COUNT(*) as cnt FROM strategy_predictions")
    total = int(cur.fetchone()["cnt"])
    conn.close()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@app.post("/strategy-predictions")
def create_strategy_prediction(payload: StrategyPredictionPayload):
    conn = _connect()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM matches WHERE match_id = ?", (payload.match_id.strip(),))
        if not cur.fetchone():
            raise HTTPException(status_code=400, detail="Match not found")

        cur.execute("SELECT 1 FROM strategies WHERE id = ?", (payload.strategy_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=400, detail="Strategy not found")

        cur.execute(
            """
            INSERT INTO strategy_predictions
            (match_id, strategy_id, prediction, odds, stake, result, profit, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.match_id.strip(),
                payload.strategy_id,
                payload.prediction,
                payload.odds,
                payload.stake,
                payload.result,
                payload.profit,
                payload.notes,
            ),
        )
        row_id = cur.lastrowid
        conn.commit()
        cur.execute("SELECT * FROM strategy_predictions WHERE id = ?", (row_id,))
        row = cur.fetchone()
        return {"item": dict(row)}
    finally:
        conn.close()


@app.put("/strategy-predictions/{prediction_id}")
def update_strategy_prediction(prediction_id: int, payload: StrategyPredictionPayload):
    conn = _connect()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM matches WHERE match_id = ?", (payload.match_id.strip(),))
        if not cur.fetchone():
            raise HTTPException(status_code=400, detail="Match not found")

        cur.execute("SELECT 1 FROM strategies WHERE id = ?", (payload.strategy_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=400, detail="Strategy not found")

        cur.execute(
            """
            UPDATE strategy_predictions
            SET match_id = ?, strategy_id = ?, prediction = ?, odds = ?, stake = ?, result = ?, profit = ?, notes = ?
            WHERE id = ?
            """,
            (
                payload.match_id.strip(),
                payload.strategy_id,
                payload.prediction,
                payload.odds,
                payload.stake,
                payload.result,
                payload.profit,
                payload.notes,
                prediction_id,
            ),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Strategy prediction not found")
        conn.commit()
        cur.execute("SELECT * FROM strategy_predictions WHERE id = ?", (prediction_id,))
        row = cur.fetchone()
        return {"item": dict(row)}
    finally:
        conn.close()


@app.delete("/strategy-predictions/{prediction_id}")
def delete_strategy_prediction(prediction_id: int):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM strategy_predictions WHERE id = ?", (prediction_id,))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Strategy prediction not found")
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/outcome-probabilities")
def list_outcome_probabilities(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT o.*, s.strategy_name
        FROM outcome_probabilities o
        LEFT JOIN sub_strategies s ON s.id = o.strategy_id
        ORDER BY o.id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    items = _rows(cur)
    cur.execute("SELECT COUNT(*) as cnt FROM outcome_probabilities")
    total = int(cur.fetchone()["cnt"])
    conn.close()
    return {"items": items, "total": total, "limit": limit, "offset": offset}

if __name__ == "__main__":
    import uvicorn
    print("Запуск сервера на http://0.0.0.0:8000")
    print("Документация API: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)