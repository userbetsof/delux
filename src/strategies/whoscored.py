"""Стратегия WhoScored (#9): точный счёт + фора в одной строке."""

from __future__ import annotations

import html as html_lib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.strategies.base import MatchContext, Strategy, StrategySignal

WHOSCORED_STRATEGY_ID = 9
WHOSCORED_PREVIEWS_URL = "https://www.whoscored.com/previews"
WHOSCORED_ORIGIN = "https://www.whoscored.com"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

# slug WhoScored → название лиги Flashscore (как в DELUX_LEAGUES)
LEAGUE_SLUG_TO_DELUX = {
    "england-premier-league": "Англия: Премьер-лига",
    "spain-laliga": "Испания: Примера",
    "spain-la-liga": "Испания: Примера",
    "spain-primera-division": "Испания: Примера",
    "italy-serie-a": "Италия: Серия А",
    "france-ligue-1": "Франция: Первая лига",
    "germany-bundesliga": "Германия: Бундеслига",
    "portugal-liga-portugal": "Португалия: Чемпионат Португалии",
    "portugal-primeira-liga": "Португалия: Чемпионат Португалии",
    "russia-premier-league": "РОССИЯ: Премьер-лига",
    "russia-premier-liga": "РОССИЯ: Премьер-лига",
}

# Flashscore (casefold) → WhoScored English (casefold). Дополняется teams.name_whoscored.
TEAM_TO_WS = {
    "венеция": "venezia",
    "фиорентина": "fiorentina",
    "генуя": "genoa",
    "фрозиноне": "frosinone",
    "наполи": "napoli",
    "арсенал": "arsenal",
    "ювентус": "juventus",
    "милан": "ac milan",
    "интер": "inter",
    "рома": "roma",
    "лацио": "lazio",
    "атлетико мадрид": "atletico madrid",
    "барселона": "barcelona",
    "реал мадрид": "real madrid",
    "манчестер сити": "manchester city",
    "манчестер юнайтед": "manchester united",
    "ливерпуль": "liverpool",
    "челси": "chelsea",
    "тоттенхэм": "tottenham",
    "бавария": "bayern munich",
    "боруссия дортмунд": "borussia dortmund",
    "пбк": "psg",
    "пари сен-жермен": "paris saint-germain",
    "бенфика": "benfica",
    "порту": "fc porto",
    "спортинг": "sporting cp",
    "зенит": "zenit st petersburg",
    "цска": "cska moscow",
    "спартак москва": "spartak moscow",
    "динамо москва": "dynamo moscow",
    "локомотив москва": "lokomotiv moscow",
    "краснодар": "krasnodar",
    "ростов": "rostov",
    "унион берлин": "union berlin",
    "шальке 04": "schalke 04",
}

_WS_INDEX: Optional[List["WsPreview"]] = None
_WS_FAIL = ""


@dataclass
class WsPreview:
    ws_id: str
    url: str
    slug: str
    league_delux: str
    date: str
    time: str
    list_home: str
    list_away: str
    home: str = ""
    away: str = ""
    score_home: Optional[int] = None
    score_away: Optional[int] = None
    extras: Dict[str, Any] = field(default_factory=dict)

    @property
    def kickoff(self) -> str:
        if not self.date:
            return ""
        return f"{self.date} {self.time}".strip()


def _norm(name: str) -> str:
    text = (name or "").strip().casefold()
    text = text.replace("ё", "е")
    text = re.sub(r"[.'’]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _core(name: str) -> str:
    n = _norm(name)
    n = re.sub(r"^(ac|as|afc|fc|cf|ssc|us|rc|sc)\s+", "", n)
    n = re.sub(r"\s+(fc|cf|ac)$", "", n)
    return n.strip()


def slug_to_delux(slug: str) -> Optional[str]:
    key = (slug or "").strip().casefold()
    if key in LEAGUE_SLUG_TO_DELUX:
        return LEAGUE_SLUG_TO_DELUX[key]
    for s, name in sorted(LEAGUE_SLUG_TO_DELUX.items(), key=lambda x: -len(x[0])):
        if key.startswith(s + "-") or key == s:
            return name
    return None


def extract_league_slug(preview_path: str) -> str:
    """italy-serie-a-2026-2027-venezia-fiorentina → italy-serie-a"""
    raw = (preview_path or "").strip().strip("/").casefold()
    raw = raw.split("/")[-1]
    raw = re.sub(r"\.html?$", "", raw)
    m = re.match(r"^(.+?)-(\d{4})(?:-\d{4})?-", raw)
    if m:
        return m.group(1)
    for slug in sorted(LEAGUE_SLUG_TO_DELUX, key=len, reverse=True):
        if raw.startswith(slug):
            return slug
    return raw


def favorite_slugs(delux_leagues: Optional[Iterable[str]]) -> Dict[str, str]:
    """slug → delux league name, только избранные."""
    allowed = None
    if delux_leagues is not None:
        allowed = {_norm(x) for x in delux_leagues if x}
    out: Dict[str, str] = {}
    for slug, name in LEAGUE_SLUG_TO_DELUX.items():
        if allowed is not None and _norm(name) not in allowed:
            continue
        out[slug] = name
    return out


def parse_previews_index(html: str) -> List[WsPreview]:
    rows = re.split(r"<tr\b", html, flags=re.I)
    current_date = ""
    current_slug = ""
    items: List[WsPreview] = []
    for row in rows:
        dm = re.search(
            r'class="previews-date"[^>]*>\s*(\d{2})-(\d{2})-(\d{4})',
            row,
            re.I,
        )
        if dm:
            current_date = f"{dm.group(3)}.{dm.group(2)}.{dm.group(1)}"
            continue
        tm = re.search(
            r'href="/regions/\d+/tournaments/\d+/([a-z0-9-]+)"',
            row,
            re.I,
        )
        if tm:
            current_slug = tm.group(1).casefold()
            continue
        pm = re.search(
            r'href="(/matches/(\d+)/preview/([^"]+))"[^>]*>\s*([^<]+?)\s*</a>',
            row,
            re.I,
        )
        if not pm:
            continue
        path, ws_id, tail, title = pm.group(1), pm.group(2), pm.group(3), pm.group(4)
        slug = extract_league_slug(tail) or current_slug
        league = slug_to_delux(slug)
        if not league:
            continue
        home, away = "", ""
        if " vs " in title.lower():
            parts = re.split(r"\s+vs\.?\s+", title, maxsplit=1, flags=re.I)
            if len(parts) == 2:
                home, away = parts[0].strip(), parts[1].strip()
        tm_row = re.search(r'class="time"[^>]*>\s*(\d{1,2}:\d{2})', row, re.I)
        clock = tm_row.group(1) if tm_row else ""
        items.append(
            WsPreview(
                ws_id=ws_id,
                url=WHOSCORED_ORIGIN + path,
                slug=slug,
                league_delux=league,
                date=current_date,
                time=clock,
                list_home=home,
                list_away=away,
                home=home,
                away=away,
            )
        )
    return items


def parse_prediction_block(html: str) -> Optional[Dict[str, Any]]:
    start = html.find('id="preview-prediction"')
    if start < 0:
        return None
    nxt = html.find('id="', start + 10)
    block = html[start : nxt if nxt > start else start + 5000]
    hm = re.search(
        r'class="home".*?class="predicted-score">\s*(\d+)\s*<.*?<span>\s*([^<]+?)\s*</span>',
        block,
        re.S | re.I,
    )
    am = re.search(
        r'class="away".*?class="predicted-score">\s*(\d+)\s*<.*?<span>\s*([^<]+?)\s*</span>',
        block,
        re.S | re.I,
    )
    if not hm or not am:
        return None
    return {
        "score_home": int(hm.group(1)),
        "score_away": int(am.group(1)),
        "home": hm.group(2).strip(),
        "away": am.group(2).strip(),
    }


_PREVIEW_SECTION_IDS = (
    "preview-lineups",
    "probable-lineup-stats",
    "missing-players",
    "preview-team-news",
    "preview-prediction",
    "external-placeholder1",
    "external-placeholder2",
)


def _strip_tags(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text or "")
    cleaned = html_lib.unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _section_html(page: str, section_id: str) -> str:
    needle = f'id="{section_id}"'
    start = page.find(needle)
    if start < 0:
        return ""
    tag = page.rfind("<", 0, start)
    if tag < 0:
        tag = start
    end = len(page)
    for other in _PREVIEW_SECTION_IDS:
        if other == section_id:
            continue
        pos = page.find(f'id="{other}"', start + len(needle))
        if pos > start:
            end = min(end, pos)
    return page[tag:end]


def parse_preview_lineups(html: str) -> Dict[str, Any]:
    block = _section_html(html, "preview-lineups")
    empty: Dict[str, Any] = {
        "home": {"formation": "", "players": []},
        "away": {"formation": "", "players": []},
    }
    if not block:
        return empty

    def formation(side: str) -> str:
        m = re.search(
            rf'<div class="{side}">.*?<span class="formation-label">\s*([^<]+?)\s*</span>',
            block,
            re.S | re.I,
        )
        return m.group(1).strip() if m else ""

    def players(side: str) -> List[Dict[str, Any]]:
        pitch = re.search(
            rf'<div class="pitch">.*?<div class="{side}">(.*?)</div>\s*<div class="(?:away|info|home)',
            block,
            re.S | re.I,
        )
        chunk = pitch.group(1) if pitch else ""
        out: List[Dict[str, Any]] = []
        for ul in re.finditer(
            r'<ul\b([^>]*\bclass="[^"]*\bplayer\b[^"]*"[^>]*)>(.*?)</ul>',
            chunk,
            re.S | re.I,
        ):
            attrs = ul.group(1)
            body = ul.group(2)
            pid_m = re.search(r'data-playerid="(\d+)"', attrs, re.I)
            pid = pid_m.group(1) if pid_m else ""
            title_m = re.search(r'\btitle="([^"]*)"', attrs, re.I)
            title = html_lib.unescape(title_m.group(1).strip()) if title_m else ""
            pos = ""
            full = title
            pos_m = re.search(r"\(([^)]+)\)\s*$", title)
            if pos_m:
                pos = pos_m.group(1).strip()
                full = title[: pos_m.start()].strip()
            name_m = re.search(r'class="player-name[^"]*"[^>]*>([^<]+)</a>', body, re.I)
            short = html_lib.unescape(name_m.group(1).strip()) if name_m else full
            rating = None
            rm = re.search(r'class="player-rating[^"]*"[^>]*>\s*([^<]+)', body, re.I)
            if rm:
                try:
                    rating = float(rm.group(1).strip())
                except ValueError:
                    rating = None
            if not pid:
                href = re.search(r'href="/players/(\d+)/', body, re.I)
                pid = href.group(1) if href else ""
            if not short and not full:
                continue
            out.append(
                {
                    "player_id": pid,
                    "name": short or full,
                    "full_name": full or short,
                    "position": pos,
                    "rating": rating,
                }
            )
        return out

    return {
        "home": {"formation": formation("home"), "players": players("home")},
        "away": {"formation": formation("away"), "players": players("away")},
    }


def parse_missing_players(html: str) -> Dict[str, List[Dict[str, Any]]]:
    block = _section_html(html, "missing-players")
    if not block:
        return {"home": [], "away": []}

    def side_players(side: str) -> List[Dict[str, Any]]:
        sm = re.search(
            rf'<div\b[^>]*class="[^"]*\b{side}(?:\s|")[^"]*"[^>]*>(.*?)</table>\s*</div>',
            block,
            re.S | re.I,
        )
        chunk = sm.group(1) if sm else ""
        rows: List[Dict[str, Any]] = []
        for tr in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", chunk, re.S | re.I):
            cell = tr.group(1)
            if re.search(r"<th\b", cell, re.I):
                continue
            pm = re.search(r'href="/players/(\d+)/[^"]*"[^>]*>([^<]+)</a>', cell, re.I)
            if not pm:
                continue
            reason_m = re.search(r'class="missing[^"]*"[^>]*title="([^"]*)"', cell, re.I)
            status_m = re.search(r'class="confirmed"[^>]*>([^<]+)', cell, re.I)
            rating: Any = None
            rm = re.search(
                r'class="rating"[^>]*>\s*(?:<span[^>]*>)?\s*([^<]+)',
                cell,
                re.I,
            )
            if rm:
                raw = rm.group(1).strip()
                if raw.upper() != "N/A":
                    try:
                        rating = float(raw)
                    except ValueError:
                        rating = None
            rows.append(
                {
                    "player_id": pm.group(1),
                    "name": html_lib.unescape(pm.group(2).strip()),
                    "reason": html_lib.unescape(reason_m.group(1).strip()) if reason_m else "",
                    "status": (status_m.group(1).strip() if status_m else ""),
                    "rating": rating,
                }
            )
        return rows

    return {"home": side_players("home"), "away": side_players("away")}


def parse_team_news(html: str) -> Dict[str, List[str]]:
    block = _section_html(html, "preview-team-news")
    if not block:
        return {"home": [], "away": []}

    def bullets(side: str) -> List[str]:
        sm = re.search(
            rf'<div\b[^>]*class="[^"]*\b{side}(?:\s|")[^"]*"[^>]*>\s*<div class="note[^"]*"[^>]*>\s*<ul class="items">(.*?)</ul>',
            block,
            re.S | re.I,
        )
        if not sm:
            return []
        items = []
        for li in re.findall(r"<li>(.*?)</li>", sm.group(1), re.S | re.I):
            text = _strip_tags(li)
            if text:
                items.append(text)
        return items

    return {"home": bullets("home"), "away": bullets("away")}


def parse_preview_extras(html: str) -> Dict[str, Any]:
    lineups = parse_preview_lineups(html)
    return {
        "team_news": parse_team_news(html),
        "missing": parse_missing_players(html),
        "lineups": lineups,
        "formation_home": (lineups.get("home") or {}).get("formation") or "",
        "formation_away": (lineups.get("away") or {}).get("formation") or "",
    }


def extras_present(extras: Optional[Dict[str, Any]]) -> bool:
    data = extras or {}
    lineups = data.get("lineups") or {}
    missing = data.get("missing") or {}
    news = data.get("team_news") or {}
    for side in ("home", "away"):
        block = lineups.get(side) or {}
        if block.get("players") or block.get("formation"):
            return True
        if missing.get(side) or news.get(side):
            return True
    return False


def save_whoscored_card(match_id: str, preview: "WsPreview") -> None:
    if not match_id:
        return
    from db import upsert_whoscored_preview

    extras = preview.extras or {}
    lineups = extras.get("lineups") or {}
    upsert_whoscored_preview(
        match_id,
        {
            "ws_id": preview.ws_id,
            "ws_url": preview.url,
            "home_name": preview.home or preview.list_home,
            "away_name": preview.away or preview.list_away,
            "score_home": preview.score_home,
            "score_away": preview.score_away,
            "formation_home": extras.get("formation_home")
            or (lineups.get("home") or {}).get("formation")
            or "",
            "formation_away": extras.get("formation_away")
            or (lineups.get("away") or {}).get("formation")
            or "",
            "team_news": extras.get("team_news") or {"home": [], "away": []},
            "missing": extras.get("missing") or {"home": [], "away": []},
            "lineups": lineups,
        },
    )


def handicap_from_score(home: int, away: int) -> Optional[Dict[str, Any]]:
    """Победитель по ТС → азиатская фора -(маржа-0.5). Ничья → X."""
    diff = int(home) - int(away)
    if diff == 0:
        return {
            "pred": "X",
            "side": None,
            "line": None,
            "market": "1X2_X",
        }
    margin = abs(diff)
    line = -(margin - 0.5)
    if diff > 0:
        return {
            "pred": f"Ф1({line:g})",
            "side": "home",
            "line": line,
            "market": f"HANDICAP HOME {line:g}",
        }
    return {
        "pred": f"Ф2({line:g})",
        "side": "away",
        "line": line,
        "market": f"HANDICAP AWAY {line:g}",
    }


def cs_market(home: int, away: int) -> str:
    return f"CS {int(home)}:{int(away)}"


def fetch_url(url: str, timeout: int = 30) -> str:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if curl:
        proc = subprocess.run(
            [
                curl,
                "-sS",
                "-L",
                "-A",
                UA,
                "-H",
                "Accept: text/html,application/xhtml+xml",
                "-H",
                "Accept-Language: en-US,en;q=0.9",
                "--max-time",
                str(timeout),
                url,
            ],
            capture_output=True,
            timeout=timeout + 10,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout.decode("utf-8", errors="replace")
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace")[:300] or f"curl {proc.returncode}")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def last_whoscored_error() -> str:
    return _WS_FAIL


def load_whoscored_index(
    delux_leagues: Optional[Iterable[str]] = None,
    *,
    force: bool = False,
    sleep_s: float = 0.35,
) -> Optional[List[WsPreview]]:
    global _WS_INDEX, _WS_FAIL
    if force:
        _WS_INDEX = None
        _WS_FAIL = ""
    if _WS_INDEX is not None:
        return _WS_INDEX
    slugs = favorite_slugs(delux_leagues)
    try:
        html = fetch_url(WHOSCORED_PREVIEWS_URL)
        listed = parse_previews_index(html)
        picked = [p for p in listed if p.slug in slugs]
        out: List[WsPreview] = []
        for i, prev in enumerate(picked):
            if i:
                time.sleep(max(0.0, sleep_s))
            page = fetch_url(prev.url)
            extras = parse_preview_extras(page)
            pred = parse_prediction_block(page)
            if pred:
                prev.home = str(pred["home"])
                prev.away = str(pred["away"])
                prev.score_home = int(pred["score_home"])
                prev.score_away = int(pred["score_away"])
            prev.extras = extras
            if not pred and not extras_present(extras):
                continue
            out.append(prev)
        _WS_INDEX = out
        _WS_FAIL = ""
        return out
    except Exception as exc:
        _WS_FAIL = f"{type(exc).__name__}: {exc}"
        if os.environ.get("WHOSCORED_ALLOW_FAIL", "1").strip() not in ("0", "false", "no"):
            return None
        raise


def _team_aliases(flashscore_name: str, db_map: Dict[str, str]) -> List[str]:
    keys = [_norm(flashscore_name), _core(flashscore_name)]
    alias = db_map.get(_norm(flashscore_name)) or TEAM_TO_WS.get(_norm(flashscore_name))
    if alias:
        keys.append(_norm(alias))
        keys.append(_core(alias))
    return [k for k in keys if k]


def teams_match(fs_home: str, fs_away: str, ws_home: str, ws_away: str, db_map: Dict[str, str]) -> bool:
    wh, wa = _norm(ws_home), _norm(ws_away)
    hc, ac = _core(ws_home), _core(ws_away)
    home_ok = wh in _team_aliases(fs_home, db_map) or hc in _team_aliases(fs_home, db_map)
    away_ok = wa in _team_aliases(fs_away, db_map) or ac in _team_aliases(fs_away, db_map)
    if home_ok and away_ok:
        return True

    # Fallback: fuzzy match using transliteration
    from difflib import SequenceMatcher

    def transliterate(text: str) -> str:
        mapping = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh',
            'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
            'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
            'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu',
            'я': 'ya'
        }
        return "".join(mapping.get(c, c) for c in text.lower())

    def clean_name(name: str) -> str:
        n = name.lower().replace("ё", "е").replace("-", " ")
        for word in ["fk", "fc", "cf", "u21", "u19", "youth", "reserve", "пк", "фк", "ск"]:
            n = n.replace(f" {word} ", " ").replace(f" {word}", "").replace(f"{word} ", "")
        return n.strip()

    home_trans = clean_name(transliterate(fs_home))
    away_trans = clean_name(transliterate(fs_away))
    ws_h_clean = clean_name(ws_home)
    ws_a_clean = clean_name(ws_away)

    score_h = SequenceMatcher(None, home_trans, ws_h_clean).ratio()
    score_a = SequenceMatcher(None, away_trans, ws_a_clean).ratio()

    return bool(score_h >= 0.75 and score_a >= 0.75)


def _date_prefix(value: str) -> str:
    s = (value or "").strip().replace("-", ".")
    return s[:10]


def match_preview_to_delux(
    preview: WsPreview,
    candidates: List[Any],
    db_map: Optional[Dict[str, str]] = None,
) -> Optional[Any]:
    """Найти матч DeluX: лига + дата/время, иначе имена."""
    db_map = db_map or {}
    league_n = _norm(preview.league_delux)
    same_league = []
    for q in candidates:
        tour = _norm(getattr(q, "tour_name", "") or "")
        if tour != league_n:
            continue
        same_league.append(q)
    if not same_league:
        return None

    kick = preview.kickoff
    if kick:
        exact = [
            q
            for q in same_league
            if (getattr(q, "date_match", "") or "").strip()[:16] == kick[:16]
            or (
                (getattr(q, "date_match", "") or "").strip()[:10] == preview.date
                and bool(preview.time)
                and preview.time in (getattr(q, "date_match", "") or "")
            )
        ]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            same_league = exact

    named = [
        q
        for q in same_league
        if teams_match(
            getattr(q, "home_name", "") or "",
            getattr(q, "away_name", "") or "",
            preview.home or preview.list_home,
            preview.away or preview.list_away,
            db_map,
        )
    ]
    if len(named) == 1:
        return named[0]

    same_day = [
        q
        for q in same_league
        if _date_prefix(getattr(q, "date_match", "") or "") == preview.date
    ]
    if len(same_day) == 1:
        return same_day[0]
    return named[0] if len(named) == 1 else None


def max_market_odds(odds_data, market: str) -> Optional[float]:
    if not odds_data or not market:
        return None
    best = 0.0
    key = market.strip().upper()
    for bk in getattr(odds_data, "bookmakers", []) or []:
        m = (bk.markets or {}).get(key) or (bk.markets or {}).get(market)
        if m and getattr(m, "current", None):
            try:
                best = max(best, float(m.current))
            except (TypeError, ValueError):
                continue
    return best or None


def lookup_odds_in_db(match_id: str, market: str) -> Optional[float]:
    if not match_id or not market:
        return None
    try:
        from db import get_db_connection
    except Exception:
        return None
    want = market.strip().upper()
    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT MAX(odds_value) AS o
            FROM odds
            WHERE match_id = ? AND UPPER(TRIM(market_name)) = ?
              AND odds_value IS NOT NULL AND odds_value > 1
            """,
            (match_id, want),
        ).fetchone()
    if not row:
        return None
    val = row["o"] if hasattr(row, "keys") else row[0]
    try:
        n = float(val)
    except (TypeError, ValueError):
        return None
    return n if n > 1 else None


def build_whoscored_signal(
    preview: WsPreview,
    *,
    match_id: str,
    odds_data=None,
) -> Optional[Dict[str, Any]]:
    if preview.score_home is None or preview.score_away is None:
        return None
    h, a = int(preview.score_home), int(preview.score_away)
    ah = handicap_from_score(h, a)
    if not ah:
        return None
    cs_mkt = cs_market(h, a)
    cs_odds = lookup_odds_in_db(match_id, cs_mkt) or max_market_odds(odds_data, cs_mkt)
    ah_odds = lookup_odds_in_db(match_id, ah["market"]) or max_market_odds(odds_data, ah["market"])
    cs_pred = f"{h}:{a}"
    prediction = f"{cs_pred} / {ah['pred']}"
    notes = {
        "source": "whoscored",
        "cs": {"pred": cs_pred, "odds": cs_odds, "market": cs_mkt},
        "ah": {"pred": ah["pred"], "odds": ah_odds, "market": ah["market"]},
        "ws_home": preview.home,
        "ws_away": preview.away,
        "ws_url": preview.url,
        "league_slug": preview.slug,
        "score_home": h,
        "score_away": a,
    }
    return {
        "prediction": prediction,
        "odds": cs_odds or ah_odds,
        "notes": json.dumps(notes, ensure_ascii=False),
        "cs_pred": cs_pred,
        "ah_pred": ah["pred"],
        "cs_odds": cs_odds,
        "ah_odds": ah_odds,
    }


def compute_whoscored_prediction(
    match_id: str,
    home: str,
    away: str,
    tour_name: str,
    date_match: str = "",
    *,
    sport: int = 1,
    odds_data=None,
    previews: Optional[List[WsPreview]] = None,
    db_map: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    if int(sport or 1) != 1:
        return None
    index = previews
    if index is None:
        index = _WS_INDEX or []
    if not index:
        return None

    class _Q:
        def __init__(self):
            self.match_id = match_id
            self.home_name = home
            self.away_name = away
            self.tour_name = tour_name
            self.date_match = date_match

    q = _Q()
    db_map = db_map if db_map is not None else _load_ws_team_map()
    for prev in index:
        hit = match_preview_to_delux(prev, [q], db_map)
        if hit:
            save_whoscored_card(match_id, prev)
            return build_whoscored_signal(prev, match_id=match_id, odds_data=odds_data)
    return None


def _load_ws_team_map() -> Dict[str, str]:
    try:
        from db import load_team_name_map

        return load_team_name_map("whoscored")
    except Exception:
        return {}


class WhoscoredStrategy(Strategy):
    id = WHOSCORED_STRATEGY_ID
    name = "WhoScored"
    description = "Точный счёт WhoScored + фора (2 прогноза в 1 строке)"

    def calculate_signals(self, ctx: MatchContext) -> Optional[StrategySignal]:
        extra = ctx.extra or {}
        data = compute_whoscored_prediction(
            ctx.match_id,
            ctx.home,
            ctx.away,
            str(extra.get("tour_name") or extra.get("league") or ""),
            str(extra.get("date_match") or extra.get("date") or ""),
            sport=ctx.sport,
            odds_data=ctx.odds_data,
            previews=extra.get("whoscored_index"),
        )
        return StrategySignal.from_dict(data)
