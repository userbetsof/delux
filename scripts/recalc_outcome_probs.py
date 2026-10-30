"""Пересчёт outcome_probabilities для матчей с нулевыми вероятностями.

Зачем: у части матчей в outcome_probabilities записаны нули (0/0/0),
хотя goal_probabilities есть. Такие матчи анализировались до исправления
движка и в БД остался мусор — в админке видно «1 пр» и «poisson»
с нулевыми вероятностями.

Скрипт для каждого затронутого матча:
  1. Загружает данные (таблица/форма/H2H/история).
  2. Считает вероятности движком.
  3. Пишет только строки, которые реально стали ненулевыми.
  4. Не трогает матчи, где расчёт тоже даёт нули (значит нет данных).

    py -3 scripts/recalc_outcome_probs.py --dry-run
    py -3 scripts/recalc_outcome_probs.py
    py -3 scripts/recalc_outcome_probs.py --limit 20 --strategy 1
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db import get_database_path, insert_outcome_probabilities_from_values  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def _current_nonzero(match_id: str) -> int:
    """Сколько стратегий у матча сейчас имеют ненулевые вероятности."""
    with sqlite3.connect(str(get_database_path()), timeout=30) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM outcome_probabilities "
            "WHERE match_id = ? "
            "AND (COALESCE(home_win_prob,0) + COALESCE(draw_prob,0) "
            "     + COALESCE(away_win_prob,0)) > 0",
            (match_id,),
        ).fetchone()
    return int(row[0]) if row else 0


def _zero_matches(conn: sqlite3.Connection, strategy_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT o.match_id
        FROM outcome_probabilities o
        JOIN matches m ON m.match_id = o.match_id
        WHERE o.strategy_id = ?
          AND (COALESCE(o.home_win_prob,0) + COALESCE(o.draw_prob,0)
               + COALESCE(o.away_win_prob,0)) = 0
        ORDER BY m.match_date
        """,
        (strategy_id,),
    ).fetchall()
    return [r[0] for r in rows]


def _payload_from_snapshot(match_id: str, sport: int, cfg=None):
    """Собрать payload из сохранённого снимка (таблица + форма) — без сети.

    Для пересчёта вероятностей исходов нужны только standings_json и
    form_json; H2H и история команд на исходы не влияют. Чтение снимка
    занимает миллисекунды вместо ~65 секунд загрузки из фидов.
    """
    import json

    from analysis_data import AnalysisPayload, MatchInfo, TableRow, build_settings

    with sqlite3.connect(str(get_database_path()), timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT standings_json, form_json FROM match_snapshot WHERE match_id = ?",
            (match_id,),
        ).fetchone()
    if row is None:
        return None

    def _to_table_rows(entries):
        """[dict, ...] из JSON снимка → [TableRow, ...]."""
        if isinstance(entries, dict):
            entries = [entries]
        out = []
        for item in entries or []:
            if not isinstance(item, dict) or not item.get("team"):
                continue
            out.append(
                TableRow(
                    rank=str(item.get("rank", "")),
                    team=str(item.get("team", "")),
                    played=str(item.get("played", "")),
                    wins=str(item.get("wins", "")),
                    draws=str(item.get("draws", "")),
                    losses=str(item.get("losses", "")),
                    scored=str(item.get("scored", "")),
                    conceded=str(item.get("conceded", "")),
                    points=str(item.get("points", "")),
                )
            )
        return out

    def _section(raw, key):
        """Достать секцию (overall/home/away) из JSON снимка."""
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return []
        if not isinstance(data, dict):
            return []
        return _to_table_rows(data.get(key) or [])

    payload = AnalysisPayload(match=MatchInfo(match_id=match_id), settings=None)
    # Все три среза таблицы и все три среза формы — движку нужны все шесть
    # (Расчеты! берут и overall, и home/away).
    payload.table_overall = _section(row["standings_json"], "overall")
    payload.table_home = _section(row["standings_json"], "home")
    payload.table_away = _section(row["standings_json"], "away")
    payload.form_overall = _section(row["form_json"], "overall")
    payload.form_home = _section(row["form_json"], "home")
    payload.form_away = _section(row["form_json"], "away")

    if not any(
        (
            payload.table_overall,
            payload.table_home,
            payload.table_away,
            payload.form_overall,
            payload.form_home,
            payload.form_away,
        )
    ):
        return None

    # Без формы стратегии дают 0/0/0 — догружаем её из сети только когда
    # в снимке её нет (старые записи). Это медленно, поэтому лишь при нужде.
    if not payload.form_overall:
        try:
            from analysis_data import fetch_table

            ms = build_settings(
                sport=sport,
                source=cfg.source,
                tz_base=cfg.tz_base,
                dayzone_base=cfg.dayzone_base,
                time_offset=cfg.time_offset,
            )
            payload.form_overall = fetch_table(ms, match_id, "form_overall")
            payload.form_home = fetch_table(ms, match_id, "form_home")
            payload.form_away = fetch_table(ms, match_id, "form_away")
            if payload.form_overall:
                # Дозаписываем в снимок, чтобы больше не ходить в сеть.
                try:
                    from db import upsert_match_snapshot
                    from match_snapshot import build_payload_snapshot

                    snap = build_payload_snapshot(payload)
                    if snap.get("form_json"):
                        upsert_match_snapshot(match_id, {"form_json": snap["form_json"]})
                except Exception:  # noqa: BLE001
                    pass
        except Exception as exc:  # noqa: BLE001
            print(f'    [!] форма из сети: {exc}')

    return payload


def _kickoff_label(start_ts) -> str:
    """Дата начала матча как 'YYYY.MM.DD HH:MM' — граница «только прошлое»."""
    if not start_ts:
        return ""
    try:
        import datetime

        return datetime.datetime.fromtimestamp(int(start_ts)).strftime(
            "%Y.%m.%d %H:%M"
        )
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


# Кэш полной загрузки по командам: у матчей одного сезона команды
# повторяются, и без кэша каждый матч заново тянет pr_ фиды по сети.
_FULL_CACHE: dict[tuple, object] = {}
_MAX_CACHE = 80


def _team_names_of(match_id: str) -> tuple[str, str]:
    """Имена хозяев и гостей (для ключа кэша)."""
    with sqlite3.connect(str(get_database_path()), timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT ht.name AS h, at.name AS a FROM matches m "
            "JOIN teams ht ON ht.id = m.home_team_id "
            "JOIN teams at ON at.id = m.away_team_id "
            "WHERE m.match_id = ?",
            (match_id,),
        ).fetchone()
    if row is None:
        return "", ""
    return row["h"] or "", row["a"] or ""


def _load_full_cached(match_id: str, info, ms):
    """load_analysis_data с кэшем по паре команд.

    Берём первый матч каждой пары команд и переиспользуем найденную
    историю. Даты всё равно обрезаются до кик-оффа текущего матча,
    поэтому кэш безопасен.
    """
    from analysis_data import load_analysis_data

    home, away = _team_names_of(match_id)
    key = (home, away, getattr(ms, "sport", 1))
    if key in _FULL_CACHE:
        return _FULL_CACHE[key]

    payload = load_analysis_data(info, ms)
    if len(_FULL_CACHE) >= _MAX_CACHE:
        _FULL_CACHE.clear()
    _FULL_CACHE[key] = payload
    return payload


def _tighten_feed_timeout(seconds: int = 12) -> None:
    """Сократить таймаут фидов: одна зависшая попытка стоит ~170 с.

    Сеть до flashscore.ninja периодически «подвисает» на первом запросе и
    отвечает только со второй-третьей попытки. Для пакетного пересчёта
    лучше быстро упасть и повторить, чем ждать три минуты.
    """
    import flashscore_feed

    original = flashscore_feed.fetch_feed

    def _wrapped(url, *args, **kwargs):
        kwargs.setdefault("timeout", seconds)
        kwargs.setdefault("retries", 3)
        return original(url, *args, **kwargs)

    flashscore_feed.fetch_feed = _wrapped
    # Модули анализа импортируют имя напрямую — подменяем и там.
    try:
        import analysis_data

        analysis_data.fetch_feed = _wrapped
    except Exception:  # noqa: BLE001
        pass


def _skip_daily_feed_lookup() -> None:
    """Не искать матч в дневных лентах (f_1_N): это ~1 МБ и 130-150 с каждая.

    load_analysis_data подтягивает дневные ленты, чтобы определить страну,
    лигу и имена команд, когда страница матча недоступна. Для пересчёта
    всё это уже есть в БД (matches + leagues + teams), а сами ленты —
    самая дорогая часть запроса.
    """
    import analysis_data as ad

    def _no_meta(match_id, settings, dayzone=0):
        return ("", "", "", "")

    for name in ("resolve_match_meta_from_feed", "_list_league_match_ids"):
        if hasattr(ad, name):
            setattr(ad, name, _no_meta if name.startswith("resolve") else (lambda *a, **k: []))


def _skip_slow_page_fetch() -> None:
    """Не ходить на страницу матча: для пересчёта её данные не нужны.

    load_analysis_data начинается с detect_sport_from_match_page и
    fetch_match_page_ids — оба тянут HTML страницы. На этом хосте они
    стабильно висят ~30 с и заканчиваются таймаутом. Вид спорта и id
    участников уже есть в БД, поэтому подменяем эти вызовы на заглушки.
    """
    import analysis_data as ad

    def _no_sport(match_id: str):
        return None

    def _no_ids(match_id, **kwargs):
        return ("", "", "", "", "")

    ad.detect_sport_from_match_page = _no_sport
    ad.fetch_match_page_ids = _no_ids


def _history_from_snapshot(match_id: str):
    """H2H и матчи команд из снимка — стратегии #1/#4 строят из них форму.

    ВАЖНО про порядок. В снимке матчи лежат от НОВЫХ к старым, а движок
    берёт home_all[-40:] — то есть «последние 40» в порядке возрастания даты.
    Если отдать снимок как есть, срез упадёт на самые СТАРЫЕ матчи (2008 год),
    форма получится нулевой и стратегии #1/#4 вернут 0/0/0.
    Поэтому сортируем по дате по возрастанию.

    Возвращает dict: h2h / home_all / away_all (пустые списки, если нет).
    """
    import json

    with sqlite3.connect(str(get_database_path()), timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT h2h_json, team_matches_json FROM match_snapshot "
            "WHERE match_id = ?",
            (match_id,),
        ).fetchone()
    out: dict = {
        "h2h": [],
        "h2h_home": [],
        "home_all": [],
        "home_home": [],
        "home_away": [],
        "away_all": [],
        "away_home": [],
        "away_away": [],
    }
    if row is None:
        return out

    def _load(raw):
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _sorted(items):
        """По возрастанию даты (движок срезает хвост как «последние»)."""
        def _key(item):
            return str(item.get("date") or "")

        return sorted(
            (x for x in items if isinstance(x, dict)), key=_key
        )

    h2h_data = _load(row["h2h_json"])
    out["h2h"] = _sorted(h2h_data.get("all") or [])
    out["h2h_home"] = _sorted(h2h_data.get("home") or [])

    tm = _load(row["team_matches_json"])
    for side in ("home", "away"):
        block = tm.get(side) or {}
        if not isinstance(block, dict):
            continue
        # Движку нужны все три среза: all / home / away.
        for part in ("all", "home", "away"):
            out[f"{side}_{part}"] = _sorted(block.get(part) or [])
    return out


def _recalc_one(match_id: str, cfg) -> list[dict] | None:
    """Посчитать вероятности для матча. None — не удалось."""
    from analysis_data import MatchInfo, build_settings, load_analysis_data
    from calc_backend import get_calc_engine

    row = None
    with sqlite3.connect(str(get_database_path()), timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT match_status, start_ts, sport FROM matches WHERE match_id = ?",
            (match_id,),
        ).fetchone()
    if row is None:
        return None

    sport = row["sport"] or 1
    ms = build_settings(
        sport=sport,
        source=cfg.source,
        tz_base=cfg.tz_base,
        dayzone_base=cfg.dayzone_base,
        time_offset=cfg.time_offset,
    )

    # Гибрид: сначала быстрый путь (снимок). Если ключевые стратегии
    # остались нулевыми — полная загрузка из сети, как при анализе.
    payload = _payload_from_snapshot(match_id, sport, cfg)

    if payload is None:
        info = MatchInfo(match_id=match_id)
        info.status = row["match_status"]
        info.start_ts = row["start_ts"]
        payload = load_analysis_data(info, ms)
        if not payload.table_overall and not payload.form_overall:
            return None

    payload.settings = ms
    payload.match = MatchInfo(match_id=match_id)
    payload.match.status = row["match_status"]
    payload.match.start_ts = row["start_ts"]

    # H2H и матчи команд: стратегии #1/#4 строят из них форму на дату матча.
    if not payload.h2h and not payload.home_all:
        try:
            from analysis_data import HistoryMatch

            hist = _history_from_snapshot(match_id)

            def _to_hm(item):
                if isinstance(item, HistoryMatch):
                    return item
                if not isinstance(item, dict):
                    return None
                try:
                    return HistoryMatch(**{
                        k: item.get(k, "")
                        for k in HistoryMatch.__dataclass_fields__
                    })
                except Exception:  # noqa: BLE001
                    return None

            def _convert(key):
                return [h for h in (_to_hm(x) for x in hist.get(key) or []) if h]

            # Раскладка как у load_analysis_data: движок сам делит
            # home_all на «дома/в гостях», а готовые срезы home_home /
            # home_away заполнять НЕЛЬЗЯ — иначе форма считается дважды
            # и стратегии #1/#4 возвращают нули.
            payload.h2h = _convert("h2h")
            payload.h2h_home = _convert("h2h_home")
            payload.home_all = _convert("home_all")
            payload.away_all = _convert("away_all")
            payload.home_home = []
            payload.home_away = []
            payload.away_home = []
            payload.away_away = []
        except Exception as exc:  # noqa: BLE001
            print(f"    [!] история из снимка: {exc}")

    from odds_service import load_odds

    try:
        _code, odds_data = load_odds(match_id, cfg.source)
    except Exception:  # noqa: BLE001
        odds_data = None
    # Без линии БК движок падает ('NoneType' has no attribute 'home_id') —
    # такие матчи пропускаем, коэффициенты для них взять неоткуда.
    if odds_data is None:
        return None

    eng = get_calc_engine(cfg)
    res = eng.run(payload, odds_data, list_odds=[])
    probs = res.get("outcome_probabilities") or []

    def _nonzero_count(items) -> int:
        return sum(
            1
            for p in items or []
            if (p.get("home_prob") or 0)
            + (p.get("draw_prob") or 0)
            + (p.get("away_prob") or 0)
            > 0
        )

    # Быстрого пути не хватило — полная загрузка. ВАЖНО: она отдаёт матчи
    # команды БЕЗ фильтра по дате (в т.ч. сыгранные позже анализируемого),
    # поэтому обрезаем историю строго до кик-оффа.
    # Порог = 10: если хоть одна стратегия нулевая, пробуем полную загрузку.
    if _nonzero_count(probs) < 10:
        try:
            info = MatchInfo(match_id=match_id)
            info.status = row["match_status"]
            info.start_ts = row["start_ts"]
            full = load_analysis_data(info, ms)
            if full.table_overall or full.form_overall:
                cut = _kickoff_label(row["start_ts"])
                if cut:
                    full.home_all = [
                        h for h in (full.home_all or []) if str(h.date) < cut
                    ]
                    full.away_all = [
                        h for h in (full.away_all or []) if str(h.date) < cut
                    ]
                    full.h2h = [h for h in (full.h2h or []) if str(h.date) < cut]
                full.settings = ms
                full.match = info
                res_full = eng.run(full, odds_data, list_odds=[])
                probs_full = res_full.get("outcome_probabilities") or []
                if _nonzero_count(probs_full) > _nonzero_count(probs):
                    probs = probs_full
        except Exception as exc:  # noqa: BLE001
            print(f"    [!] полная загрузка: {exc}")

    return probs if probs else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Пересчёт нулевых outcome_probabilities"
    )
    parser.add_argument("--dry-run", action="store_true", help="только показать")
    parser.add_argument("--limit", type=int, default=0, help="ограничить число матчей")
    parser.add_argument(
        "--strategy",
        type=int,
        default=0,
        help="пересчитывать только если нули у этой стратегии (#1 или #4; 0 = обе)",
    )
    args = parser.parse_args()

    from settings import DeluxSettings

    # Фиды печатают служебные строки (переключение на ninja) — гасим их,
    # иначе лог пересчёта теряется среди них.
    import contextlib
    import io

    cfg = DeluxSettings.from_env()

    # Основной хост flashscorekz.com часто отдаёт SSL-таймаут (~30 с на
    # каждый матч). Для пакетного пересчёта сразу берём рабочее зеркало
    # .ninja — фиды там те же, но без ожидания.
    try:
        import flashscore_feed

        flashscore_feed._MAIN_HOST_DEAD = True
    except Exception:  # noqa: BLE001
        pass

    # Страница матча для пересчёта не нужна (её данные уже в БД), а запрос
    # к ней стабильно висит ~30 с. Отключаем эти два вызова.
    _skip_slow_page_fetch()

    # Короткий таймаут фидов: зависший запрос стоит ~170 с, лучше повторить.
    _tighten_feed_timeout(12)

    conn = sqlite3.connect(str(get_database_path()), timeout=60)
    try:
        targets: list[str] = []
        for sid in ([args.strategy] if args.strategy else [1, 4]):
            for mid in _zero_matches(conn, sid):
                if mid not in targets:
                    targets.append(mid)
    finally:
        conn.close()

    print(f"Матчей с нулевыми вероятностями: {len(targets)}")
    if args.limit:
        targets = targets[: args.limit]
        print(f"Ограничено до: {len(targets)}")
    if targets:
        print("Можно прервать (Ctrl+C) и запустить снова — уже исправленные")
        print("матчи повторно не обрабатываются.")
        print()

    fixed = 0
    skipped = 0
    failed = 0
    started = time.time()

    for idx, mid in enumerate(targets, 1):
        # Прогресс с ETA, чтобы было видно, сколько ждать.
        done = idx - 1
        per_match = (time.time() - started) / done if done else 0
        eta = per_match * (len(targets) - done)
        eta_txt = (
            f"осталось ~{eta/60:.0f} мин" if eta >= 60 else f"осталось ~{eta:.0f} с"
        )
        print(
            f"[{idx}/{len(targets)}] {mid} "
            f"({per_match:.0f} с/матч, {eta_txt})",
            end="",
            flush=True,
        )

        try:
            with contextlib.redirect_stdout(io.StringIO()):
                probs = _recalc_one(mid, cfg)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f": ошибка — {exc}")
            continue

        if not probs:
            skipped += 1
            print(": пропуск (нет данных)")
            continue

        nonzero = sum(
            1
            for p in probs
            if (p.get("home_prob") or 0)
            + (p.get("draw_prob") or 0)
            + (p.get("away_prob") or 0)
            > 0
        )
        # Не ухудшаем данные: если сейчас в БД ненулевых больше, чем даёт
        # расчёт, писать нечего — иначе перезапишем хорошие строки нулями.
        current = _current_nonzero(mid)
        if nonzero <= current:
            skipped += 1
            print(f": пропуск (в БД уже {current} ненулевых, расчёт дал {nonzero})")
            continue

        if args.dry_run:
            fixed += 1
            print(f": [dry-run] было {current}, станет {nonzero}")
            continue

        if insert_outcome_probabilities_from_values(mid, probs):
            fixed += 1
            print(f": записано, ненулевых {current} -> {nonzero}")
        else:
            failed += 1
            print(": не записалось")

    elapsed = time.time() - started
    print()
    print(f"[+] Исправлено: {fixed}, пропущено: {skipped}, ошибок: {failed}")
    print(f"    время: {elapsed:.1f} c")
    if args.dry_run:
        print("    [dry-run] база не изменялась")
    return 0


if __name__ == "__main__":
    sys.exit(main())
