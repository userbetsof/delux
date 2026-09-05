"""Flashscore pq_graphql — отсутствующие игроки (_hash=dmpe2)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from flashscore_feed import API_HEADERS

GRAPHQL_BASE = "https://{project_id}.ds.lsapp.eu/pq_graphql"
DEFAULT_PROJECT_ID = "46"

INJURY_KEYWORDS = (
    "травм",
    "injury",
    "muscle",
    "мышеч",
    "колен",
    "лодыж",
    "spine",
    "спин",
    "плеч",
    "бедр",
    "голен",
    "сухожил",
    "illness",
    "болезн",
)


@dataclass
class MissingPlayer:
    match_id: str
    side: str
    player_id: str
    player_name: str
    team_name: str
    reason: str
    category: str
    is_unsure: bool = False
    list_name: str = ""
    participant_url: str = ""
    team_logos: List[Dict[str, Any]] = field(default_factory=list)
    event_participant_id: str = ""
    source_bucket: str = ""
    raw_json: str = ""

    def to_dict(self) -> dict:
        return {
            "match_id": self.match_id,
            "side": self.side,
            "player_id": self.player_id,
            "player_name": self.player_name,
            "list_name": self.list_name,
            "team_name": self.team_name,
            "participant_url": self.participant_url,
            "team_logos": self.team_logos,
            "reason": self.reason,
            "category": self.category,
            "is_unsure": self.is_unsure,
            "event_participant_id": self.event_participant_id,
            "source_bucket": self.source_bucket,
        }


@dataclass
class MatchMissingPlayers:
    match_id: str
    players: List[MissingPlayer] = field(default_factory=list)
    fetch_error: Optional[str] = None

    @property
    def injury_count(self) -> int:
        return sum(1 for p in self.players if p.category == "injury")

    @property
    def confirmed_injury_count(self) -> int:
        return sum(1 for p in self.players if p.category == "injury" and not p.is_unsure)


def classify_reason(reason: str) -> str:
    text = (reason or "").strip().lower()
    if not text:
        return "other"
    if "травм" in text or "injury" in text or any(k in text for k in INJURY_KEYWORDS):
        return "injury"
    if "красн" in text or "red card" in text or "дисквалиф" in text or "suspension" in text:
        return "suspension"
    if "transfer" in text or "переговор" in text:
        return "transfer"
    return "other"


def _parse_player_item(
    event_id: str,
    side: str,
    event_participant_id: str,
    item: dict,
    *,
    is_unsure: bool,
    source_bucket: str,
) -> MissingPlayer:
    player = item.get("player") or {}
    participant = player.get("participant") or {}
    logos = player.get("teamLogo") or []
    reason = str(item.get("reason") or "").strip()
    return MissingPlayer(
        match_id=event_id,
        side=side,
        player_id=str(player.get("participantId") or ""),
        player_name=str(player.get("name") or player.get("listName") or "").strip(),
        list_name=str(player.get("listName") or "").strip(),
        team_name=str(player.get("teamName") or "").strip(),
        participant_url=str(participant.get("url") or "").strip(),
        team_logos=list(logos) if isinstance(logos, list) else [],
        reason=reason,
        category=classify_reason(reason),
        is_unsure=is_unsure,
        event_participant_id=event_participant_id,
        source_bucket=source_bucket,
        raw_json=json.dumps(item, ensure_ascii=False),
    )


def missing_players_url(
    event_id: str,
    *,
    project_id: str = DEFAULT_PROJECT_ID,
) -> str:
    params = {
        "_hash": "dmpe2",
        "eventId": event_id,
        "projectId": project_id,
    }
    return f"{GRAPHQL_BASE.format(project_id=project_id)}?{urllib.parse.urlencode(params)}"


def fetch_missing_players(
    event_id: str,
    *,
    project_id: str = DEFAULT_PROJECT_ID,
    retries: int = 3,
    timeout: int = 30,
) -> MatchMissingPlayers:
    url = missing_players_url(event_id, project_id=project_id)
    headers = dict(API_HEADERS)
    headers["Accept"] = "application/json"

    last_err: Optional[Exception] = None
    for attempt in range(max(1, retries)):
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            return parse_missing_players_response(event_id, payload)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last_err = exc
            time.sleep(0.5 * (attempt + 1))

    return MatchMissingPlayers(match_id=event_id, fetch_error=str(last_err))


def parse_missing_players_response(event_id: str, payload: dict) -> MatchMissingPlayers:
    event = (payload.get("data") or {}).get("findEventById")
    if not event:
        errors = payload.get("errors")
        msg = errors[0].get("message") if errors else "findEventById пуст"
        return MatchMissingPlayers(match_id=event_id, fetch_error=msg)

    players: List[MissingPlayer] = []
    for participant in event.get("eventParticipants") or []:
        side = ((participant.get("type") or {}).get("side") or "").upper()
        event_participant_id = str(participant.get("id") or "")
        lineup = participant.get("lineup") or {}
        for bucket, is_unsure in (("missingPlayers", False), ("unsureMissingPlayers", True)):
            for item in lineup.get(bucket) or []:
                players.append(
                    _parse_player_item(
                        event_id,
                        side,
                        event_participant_id,
                        item,
                        is_unsure=is_unsure,
                        source_bucket=bucket,
                    )
                )

    return MatchMissingPlayers(match_id=event_id, players=players)


def side_injury_totals(players: List[MissingPlayer], side: str) -> dict:
    side = side.upper()
    subset = [p for p in players if p.side == side and p.category != "none"]
    injuries = [p for p in subset if p.category == "injury"]
    return {
        "total": len(subset),
        "injuries": len(injuries),
        "confirmed_injuries": sum(1 for p in injuries if not p.is_unsure),
        "unsure_injuries": sum(1 for p in injuries if p.is_unsure),
    }
