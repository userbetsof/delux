"""Загрузка и парсинг предыдущих матчей команды (feed pr_).

Feed pr_ отдаёт прошлые матчи команды от свежих к старым, пагинированно.
Используется для реконструкции «что было до конкретной игры» — последние N
матчей команды по состоянию на момент кик-оффа.

Формат URL:
    pr_{sport}_{country}_{team_key}_{page}_{filter}_ru-kz_1
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from flashscore_feed import FIELD_SEP, ROW_SEP, fetch_feed

DEFAULT_COUNTRY = 81  # Германия (пример: Боруссия Дортмунд nP1i5US1)
DEFAULT_SPORT = 1
DEFAULT_LIMIT = 40


def pr_feed_url(sport: int, country: int, team_key: str, page: int) -> str:
    return (
        f"https://46.flashscore.ninja/46/x/feed/"
        f"pr_{int(sport)}_{int(country)}_{team_key}_{int(page)}_3_ru-kz_1"
    )


def _to_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _build_match(
    parsed: Dict[str, str],
    competition: str,
    competition_key: str,
    country: str,
) -> Dict[str, Any]:
    # KL — полный счёт матча (формат "X:Y"), приоритет.
    # AG/AH — финальный счёт, AT/AU — первый тайм.
    kl = parsed.get("KL", "")
    if kl and ":" in kl:
        parts = kl.split(":")
        home_score = _to_int(parts[0]) if len(parts) > 0 else 0
        away_score = _to_int(parts[1]) if len(parts) > 1 else 0
    else:
        home_score = _to_int(parsed.get("AG") or parsed.get("AT"))
        away_score = _to_int(parsed.get("AH") or parsed.get("AU"))
    return {
        "match_id": parsed.get("AA", ""),
        "kickoff_ts": _to_int(parsed.get("AD") or parsed.get("ADE") or 0) or 0,
        "home_name": parsed.get("AE", ""),
        "away_name": parsed.get("AF", ""),
        "home_key": parsed.get("PX", ""),
        "away_key": parsed.get("PY", ""),
        "home_score": home_score,
        "away_score": away_score,
        "competition": competition,
        "competition_key": competition_key,
        "country": country,
    }


def parse_pr_feed(text: str) -> List[Dict[str, Any]]:
    """Разобрать pr_ feed в список матчей (в порядке «свежие → старые»).

    Заголовок турнира (ZA) применяется ко всем последующим матчам (AA),
    пока не встретится следующий ZA.
    """
    matches: List[Dict[str, Any]] = []
    competition = ""
    competition_key = ""
    country = ""

    for record in text.split("~"):
        if not record.strip():
            continue
        fields = record.split(ROW_SEP)
        if not fields:
            continue
        head = fields[0].split(FIELD_SEP)
        if len(head) < 2:
            continue
        first_key = head[0]

        parsed: Dict[str, str] = {}
        for field in fields:
            key, sep, value = field.partition(FIELD_SEP)
            if sep:
                parsed[key] = value

        if first_key == "AA":
            matches.append(_build_match(parsed, competition, competition_key, country))
        elif first_key == "ZA":
            competition = parsed.get("ZA", "")
            competition_key = parsed.get("ZEE", "")
            country = parsed.get("ZY", "")

    return matches


def fetch_team_matches(
    team_key: str,
    *,
    country: int = DEFAULT_COUNTRY,
    sport: int = DEFAULT_SPORT,
    limit: int = DEFAULT_LIMIT,
    max_pages: int = 20,
) -> List[Dict[str, Any]]:
    """Загрузить последние `limit` матчей команды, в хронологическом порядке (старые → новые).

    Возвращает список матчей, отсортированный по времени кик-оффа по возрастанию.
    """
    collected: Dict[str, Dict[str, Any]] = {}

    for page in range(max_pages):
        text = fetch_feed(pr_feed_url(sport, country, team_key, page))
        matches = parse_pr_feed(text)
        if not matches:
            break
        for match in matches:
            collected.setdefault(match["match_id"], match)
        if len(collected) >= limit:
            break

    ordered = sorted(
        collected.values(),
        key=lambda m: (m["kickoff_ts"], m["match_id"]),
    )
    return ordered[-limit:]


def fetch_team_matches_before(
    team_key: str,
    kickoff_ts: int,
    *,
    country: int = DEFAULT_COUNTRY,
    sport: int = DEFAULT_SPORT,
    limit: int = DEFAULT_LIMIT,
    max_pages: int = 200,
    require_history_ts: int = 0,
) -> List[Dict[str, Any]]:
    """Последние `limit` матчей команды, сыгранных строго ДО `kickoff_ts`.

    Идёт по страницам pr_ фида ВГЛУБЬ (чем больше страница, тем более давние
    матчи), пока не наберёт `limit` матчей, удовлетворяющих условию
    `kickoff_ts < target`. Для очень давних матчей пролистывает до max_pages.

    `require_history_ts` — если > 0, дополнительно требуем, чтобы собранные
    матчи покрывали историю вплоть до этого таймстампа (иначе продолжаем
    пагинацию глубже). Возвращает хронологический список (старые → новые).
    """
    collected: Dict[str, Dict[str, Any]] = {}
    deepest_ts = 0

    for page in range(max_pages):
        try:
            text = fetch_feed(pr_feed_url(sport, country, team_key, page), retries=2, timeout=40)
        except Exception as exc:  # noqa: BLE001
            print(f"[!] pr_ страница {page} не загружена: {exc}")
            break
        matches = parse_pr_feed(text)
        if not matches:
            break  # история закончилась

        page_before = [m for m in matches if m["kickoff_ts"] and m["kickoff_ts"] < kickoff_ts]
        for match in page_before:
            collected.setdefault(match["match_id"], match)
        if matches and matches[0].get("kickoff_ts"):
            deepest_ts = matches[0]["kickoff_ts"]

        # достаточно матчей до целевого И (не нужна более глубокая история
        # или уже дошли до требуемого таймстампа)
        enough = len(collected) >= limit
        reached_history = (require_history_ts <= 0) or (
            require_history_ts > 0
            and deepest_ts
            and deepest_ts <= require_history_ts
        )
        if enough and reached_history:
            break
        # если на этой странице уже нет матчей старше целевого — дальше только древнее
        if page_before and all(m["kickoff_ts"] == page_before[-1]["kickoff_ts"] for m in page_before):
            # процесс идёт; продолжаем
            pass

    ordered = sorted(
        collected.values(),
        key=lambda m: (m["kickoff_ts"], m["match_id"]),
    )
    return ordered[-limit:]


def matches_before(matches: List[Dict[str, Any]], kickoff_ts: int) -> List[Dict[str, Any]]:
    """Матчи, сыгранные строго раньше указанного момента (реконструкция «до игры»)."""
    return [m for m in matches if m["kickoff_ts"] < kickoff_ts]


def get_team_archived_matches(
    team_name: str,
    *,
    before_ts: int = 0,
    limit: int = DEFAULT_LIMIT,
) -> List[Dict[str, Any]]:
    """Прочитать кэш матчей команды из `team_matches_cache` (НЕ из matches).

    Возвращает матчи в формате fetch_team_matches_before (id, kickoff_ts,
    имена, счёт, турнир), хронологически (старые→новые), строго до before_ts
    (если > 0), последние limit.
    """
    from db import get_db_connection

    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT match_id, kickoff_ts, home_name, away_name, home_score, away_score,
                   competition, team_key, home_key, away_key
            FROM team_matches_cache
            WHERE team_name = ?
            ORDER BY kickoff_ts ASC
            """,
            (team_name,),
        ).fetchall()

    result: List[Dict[str, Any]] = []
    for r in rows:
        ts = r["kickoff_ts"] or 0
        if before_ts and ts >= before_ts:
            continue
        result.append({
            "match_id": r["match_id"],
            "kickoff_ts": ts,
            "home_name": r["home_name"] or "",
            "away_name": r["away_name"] or "",
            "home_score": r["home_score"],
            "away_score": r["away_score"],
            "competition": r["competition"] or "",
            "home_key": r["home_key"] or "",
            "away_key": r["away_key"] or "",
            "team_key": r["team_key"] or "",
            "country": "",
        })
    return result[-limit:]


def save_team_matches_cache(
    team_key: str,
    team_name: str,
    matches: List[Dict[str, Any]],
) -> int:
    """Записать матчи команды в кэш `team_matches_cache` (INSERT OR IGNORE).

    НЕ трогает таблицу matches. Возвращает число новых записей.
    """
    from db import get_db_connection

    saved = 0
    with get_db_connection() as conn:
        for m in matches:
            if not m.get("match_id") or not m.get("home_name") or not m.get("away_name"):
                continue
            is_home = 1 if m.get("home_key") == team_key or m.get("home_name") == team_name else 0
            # если home_key пустой (БД-кэш), определяем is_home по имени
            if not m.get("home_key"):
                is_home = 1 if (m.get("home_name") or "") == team_name else 0
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO team_matches_cache
                (team_key, team_name, match_id, kickoff_ts, match_date, competition,
                 home_key, home_name, away_key, away_name, home_score, away_score, is_home)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team_key,
                    team_name,
                    m["match_id"],
                    m.get("kickoff_ts") or 0,
                    format_match_date(m.get("kickoff_ts") or 0),
                    m.get("competition") or "",
                    m.get("home_key") or "",
                    m.get("home_name") or "",
                    m.get("away_key") or "",
                    m.get("away_name") or "",
                    m.get("home_score"),
                    m.get("away_score"),
                    is_home,
                ),
            )
            saved += cur.rowcount
        conn.commit()
    return saved


def format_match_date(kickoff_ts: int) -> str:
    if not kickoff_ts:
        return ""
    try:
        return datetime.fromtimestamp(kickoff_ts).strftime("%Y.%m.%d %H:%M")
    except (ValueError, OSError):
        return ""


def fetch_team_tournament_matches(
    team_key: str,
    *,
    country: int = DEFAULT_COUNTRY,
    sport: int = DEFAULT_SPORT,
    competition_substr: str,
    limit: int = DEFAULT_LIMIT,
    max_pages: int = 20,
) -> List[Dict[str, Any]]:
    """Матчи команды только в одном турнире (фильтр по подстроке названия).

    Пагинирует pr_ feed, отбирая матчи, где competition содержит
    `competition_substr`. Возвращает хронологический список (старые → новые).
    """
    collected: Dict[str, Dict[str, Any]] = {}
    needle = (competition_substr or "").strip().casefold()

    for page in range(max_pages):
        text = fetch_feed(pr_feed_url(sport, country, team_key, page))
        matches = parse_pr_feed(text)
        if not matches:
            break
        for match in matches:
            if needle and needle not in (match["competition"] or "").casefold():
                continue
            collected.setdefault(match["match_id"], match)
        if len(collected) >= limit:
            break

    ordered = sorted(
        collected.values(),
        key=lambda m: (m["kickoff_ts"], m["match_id"]),
    )
    return ordered[-limit:]


def reconstruct_team_tournament(
    team_key: str,
    matches: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Хронологическая реконструкция выступления команды в турнире.

    Для каждого матча: соперник, дома/гости, счёт, результат (В/Н/П),
    набранные очки, накопленные очки и форма за последние 5.
    """
    rows: List[Dict[str, Any]] = []
    total_points = 0
    form: List[str] = []

    for m in matches:
        is_home = m["home_key"] == team_key
        gf = m["home_score"] if is_home else m["away_score"]
        ga = m["away_score"] if is_home else m["home_score"]
        opponent = m["away_name"] if is_home else m["home_name"]

        if gf is None or ga is None:
            result, gained = "-", 0
        elif gf > ga:
            result, gained = "В", 3
        elif gf < ga:
            result, gained = "П", 0
        else:
            result, gained = "Н", 1

        total_points += gained
        form.append(result)
        rows.append({
            "match_id": m["match_id"],
            "kickoff_ts": m["kickoff_ts"],
            "match_date": format_match_date(m["kickoff_ts"]),
            "opponent": opponent,
            "venue": "дома" if is_home else "гости",
            "score": f"{gf}:{ga}" if gf is not None and ga is not None else "-:-",
            "result": result,
            "points_gained": gained,
            "total_points": total_points,
            "form_last5": "".join(form[-5:]),
        })
    return rows
