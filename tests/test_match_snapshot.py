"""Снимок инфо о матче из фида df_sui: судья, стадион, город, зрители."""

from __future__ import annotations

import json
from unittest import TestCase

from analysis_data import AnalysisPayload, HistoryMatch, MatchInfo, MatchSettings, TableRow
from match_snapshot import (
    build_payload_snapshot,
    describe_match_info,
    describe_payload_snapshot,
    info_feed_url,
    parse_info_pairs,
    parse_match_info,
)

# Ответ df_sui_1_21qdVdR6 (Бавария — Будё/Глимт, матч ещё не начался: ATT нет)
UPCOMING_FEED = (
    "MIT÷REF¬MIV÷Obrenovic R.¬MIT÷RCO¬MIV÷172¬MIT÷RTY¬MIV÷23¬MIT÷RCC¬MIV÷Слн¬"
    "MIT÷VEN¬MIV÷Альянц Арена¬MIT÷TWN¬MIV÷Мюнхен¬MIT÷CAP¬MIV÷75 024¬TVT÷¬TVB÷¬~~A1÷¬~"
)

# Завершённый матч: события + блок инфо с ATT
FINISHED_FEED = (
    "AC÷1-й тайм¬IG÷2¬IH÷1¬~III÷l2UaV2T1¬IA÷2¬IB÷11'¬IK÷Желтая карточка¬~"
    "MIT÷REF¬MIV÷Хупер С.¬MIT÷RCO¬MIV÷198¬MIT÷RTY¬MIV÷23¬MIT÷RCC¬MIV÷Анг¬"
    "MIT÷VEN¬MIV÷Энфилд¬MIT÷TWN¬MIV÷Ливерпуль¬MIT÷ATT¬MIV÷60 416¬MIT÷CAP¬MIV÷61 276¬A1÷¬~"
)


class TestMatchSnapshot(TestCase):
    def test_feed_url(self):
        self.assertEqual(
            info_feed_url("21qdVdR6", sourcer="www.flashscorekz.com/"),
            "https://www.flashscorekz.com/x/feed/df_sui_1_21qdVdR6",
        )

    def test_parse_upcoming(self):
        info = parse_match_info(UPCOMING_FEED)
        self.assertEqual(info["referee"], "Obrenovic R.")
        self.assertEqual(info["referee_country"], "Слн")
        self.assertEqual(info["referee_country_id"], "172")
        self.assertEqual(info["venue"], "Альянц Арена")
        self.assertEqual(info["town"], "Мюнхен")
        self.assertEqual(info["capacity"], 75024)
        self.assertNotIn("attendance", info)

    def test_parse_finished_with_attendance(self):
        info = parse_match_info(FINISHED_FEED)
        self.assertEqual(info["venue"], "Энфилд")
        self.assertEqual(info["attendance"], 60416)
        self.assertEqual(info["capacity"], 61276)
        self.assertEqual(info["referee"], "Хупер С.")

    def test_raw_pairs_keep_unknown_keys(self):
        pairs = parse_info_pairs(UPCOMING_FEED)
        self.assertEqual(pairs["RTY"], "23")
        self.assertEqual(pairs["CAP"], "75 024")
        self.assertNotIn("TVT", pairs)

    def test_empty_feed(self):
        self.assertEqual(parse_match_info(""), {})
        self.assertEqual(parse_match_info("~~A1÷¬~"), {})

    def test_describe(self):
        text = describe_match_info(parse_match_info(FINISHED_FEED))
        self.assertIn("Энфилд / Ливерпуль", text)
        self.assertIn("зрителей 60416", text)
        self.assertIn("судья Хупер С. (Анг)", text)


def _payload() -> AnalysisPayload:
    game = HistoryMatch(
        tour_name="Англия: Премьер-лига",
        date="31.01.26 23:00",
        home_name="Ливерпуль",
        away_name="Ньюкасл",
        home_ht=4,
        away_ht=1,
        home_st=0,
        away_st=0,
    )
    row = TableRow(
        rank="1",
        team="Ливерпуль",
        played="22",
        wins="15",
        draws="4",
        losses="3",
        scored="48",
        conceded="21",
        points="49",
    )
    return AnalysisPayload(
        match=MatchInfo(match_id="bTitnz7m", home="Ливерпуль", away="Ньюкасл"),
        settings=MatchSettings(),
        h2h=[game],
        h2h_home=[game],
        home_all=[game],
        home_home=[game],
        away_all=[game],
        table_overall=[row],
        form_overall=[row],
    )


class TestPayloadSnapshot(TestCase):
    def test_sections_serialized(self):
        data = build_payload_snapshot(_payload())

        standings = json.loads(data["standings_json"])
        self.assertEqual(standings["overall"][0]["team"], "Ливерпуль")
        self.assertEqual(standings["overall"][0]["points"], "49")
        self.assertEqual(standings["home"], [])

        self.assertEqual(len(json.loads(data["form_json"])["overall"]), 1)

        h2h = json.loads(data["h2h_json"])
        self.assertEqual(h2h["all"][0]["home_name"], "Ливерпуль")
        self.assertEqual(h2h["all"][0]["home_ht"], 4)
        self.assertEqual(len(h2h["home"]), 1)

        matches = json.loads(data["team_matches_json"])
        self.assertEqual(len(matches["home"]["all"]), 1)
        self.assertEqual(len(matches["home"]["home"]), 1)
        self.assertEqual(matches["home"]["away"], [])
        self.assertEqual(len(matches["away"]["all"]), 1)

    def test_empty_payload_writes_nothing(self):
        empty = AnalysisPayload(match=MatchInfo(match_id="x"), settings=MatchSettings())
        data = build_payload_snapshot(empty)
        self.assertEqual(set(data.values()), {None})

    def test_describe(self):
        text = describe_payload_snapshot(_payload())
        self.assertIn("таблица 1", text)
        self.assertIn("H2H 1", text)
        self.assertIn("матчи 1/1", text)
