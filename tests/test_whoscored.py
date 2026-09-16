"""WhoScored preview parsing, league map, CS+AH combo."""

from __future__ import annotations

from unittest import TestCase

from src.strategies.whoscored import (
    WHOSCORED_STRATEGY_ID,
    extract_league_slug,
    favorite_slugs,
    handicap_from_score,
    parse_missing_players,
    parse_prediction_block,
    parse_preview_extras,
    parse_preview_lineups,
    parse_previews_index,
    parse_team_news,
    slug_to_delux,
    teams_match,
)


PREDICTION_HTML = """
<div id="preview-prediction" class="rc-b rc-r">
    <div class="home">
        <span class="predicted-score">1</span>
        <div class="team-name">
            <a href="/teams/276/show/italy-napoli" class="team-link">
                <span>Napoli</span>
            </a>
        </div>
    </div>
    <div class="away">
        <span class="predicted-score">2</span>
        <div class="team-name">
            <a href="/teams/13/show/england-arsenal" class="team-link">
                <span>Arsenal</span>
            </a>
        </div>
    </div>
</div>
"""

INDEX_HTML = """
<tr><td class="previews-date" colspan="99">09-09-2026, Wednesday</td></tr>
<tr><td colspan="99">
  <a href="/regions/108/tournaments/5/italy-serie-a" class="level-2">Serie A</a>
</td></tr>
<tr class="alt">
  <td class="time">19:45</td>
  <td colspan="99">
    <a href="/matches/1980955/preview/italy-serie-a-2026-2027-venezia-fiorentina">Venezia vs Fiorentina</a>
  </td>
</tr>
<tr><td colspan="99">
  <a href="/regions/252/tournaments/2/england-championship">Championship</a>
</td></tr>
<tr>
  <td class="time">19:45</td>
  <td><a href="/matches/1989202/preview/england-championship-2026-2027-norwich-birmingham">Norwich vs Birmingham</a></td>
</tr>
"""

EXTRAS_HTML = """
<div id="preview-lineups">
  <div class="pitch-formation-header">
    <div class="home"><span class="formation-label">3-5-2</span></div>
    <div class="away"><span class="formation-label">4-3-3</span></div>
  </div>
  <div class="pitch">
    <div class="home">
      <ul class="player" title="Filip Stankovic(GK)" data-playerId="391573">
        <li class="player-name-wrapper"><a class="player-name player-link" href="/players/391573/show/filip-stankovic">Stankovic</a></li>
        <li class="player-rating rc">6.53</li>
      </ul>
    </div>
    <div class="away">
      <ul class="player" title="David de Gea(GK)" data-playerId="79554">
        <li class="player-name-wrapper"><a class="player-name player-link" href="/players/79554/show/david-de-gea">Gea</a></li>
        <li class="player-rating rc">6.00</li>
      </ul>
    </div>
    <div class="info">WhoScored</div>
  </div>
</div>
<div id="missing-players">
  <div class="home-selector selected"></div>
  <div class="away-selector"></div>
  <div class="col12-xs-12 home small-display-on">
    <table class="grid">
      <thead><tr><th>Player</th></tr></thead>
      <tbody>
        <tr>
          <td class="pn"><a class="player-link" href="/players/322591/show/marin-sverko">Marin Sverko</a></td>
          <td class="reason"><span class="missing missing-injured" title="injured"></span></td>
          <td class="confirmed">Out</td>
          <td class="rating"><span class="info">N/A</span></td>
        </tr>
      </tbody>
    </table>
  </div>
  <div class="col12-xs-12 away small-display-off">
    <table class="grid">
      <thead><tr><th>Player</th></tr></thead>
      <tbody>
        <tr>
          <td class="pn"><a class="player-link" href="/players/423918/show/fabiano-parisi">Fabiano Parisi</a></td>
          <td class="reason"><span class="missing missing-injured" title="injured"></span></td>
          <td class="confirmed">Out</td>
          <td class="rating"><span class="info">N/A</span></td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
<div id="preview-team-news">
  <div class="home-selector selected"></div>
  <div class="preview-news-items">
    <div class="col12-xs-12 home small-display-on">
      <div class="note rc-b">
        <ul class="items"><li>Venezia remains stuck on zero points.</li></ul>
      </div>
    </div>
    <div class="col12-xs-12 away small-display-off">
      <div class="note rc-b">
        <ul class="items"><li>Paolo Vanoli coming in to replace him.</li></ul>
      </div>
    </div>
  </div>
</div>
"""


class TestWhoscored(TestCase):
    def test_strategy_id(self):
        self.assertEqual(WHOSCORED_STRATEGY_ID, 9)

    def test_slug_mapping(self):
        self.assertEqual(slug_to_delux("italy-serie-a"), "Италия: Серия А")
        self.assertEqual(extract_league_slug("italy-serie-a-2026-2027-venezia-fiorentina"), "italy-serie-a")
        self.assertIn("italy-serie-a", favorite_slugs(["Италия: Серия А"]))
        self.assertNotIn("italy-serie-a", favorite_slugs(["Англия: Премьер-лига"]))

    def test_parse_index_only_mapped_leagues(self):
        items = parse_previews_index(INDEX_HTML)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].slug, "italy-serie-a")
        self.assertEqual(items[0].list_home, "Venezia")
        self.assertEqual(items[0].time, "19:45")
        self.assertEqual(items[0].date, "2026.09.09")

    def test_parse_prediction(self):
        pred = parse_prediction_block(PREDICTION_HTML)
        self.assertEqual(pred["score_home"], 1)
        self.assertEqual(pred["score_away"], 2)
        self.assertEqual(pred["home"], "Napoli")
        self.assertEqual(pred["away"], "Arsenal")

    def test_handicap_from_score(self):
        ah = handicap_from_score(1, 2)
        self.assertEqual(ah["pred"], "Ф2(-0.5)")
        self.assertEqual(ah["market"], "HANDICAP AWAY -0.5")
        draw = handicap_from_score(1, 1)
        self.assertEqual(draw["pred"], "X")
        two = handicap_from_score(2, 0)
        self.assertEqual(two["pred"], "Ф1(-1.5)")

    def test_team_alias(self):
        self.assertTrue(teams_match("Наполи", "Арсенал", "Napoli", "Arsenal", {}))
        self.assertFalse(teams_match("Наполи", "Арсенал", "Napoli", "Chelsea", {}))

    def test_preview_extras_fixture(self):
        lineups = parse_preview_lineups(EXTRAS_HTML)
        self.assertEqual(lineups["home"]["formation"], "3-5-2")
        self.assertEqual(lineups["away"]["formation"], "4-3-3")
        self.assertEqual(lineups["home"]["players"][0]["name"], "Stankovic")
        self.assertEqual(lineups["home"]["players"][0]["player_id"], "391573")
        self.assertEqual(lineups["home"]["players"][0]["position"], "GK")
        self.assertEqual(lineups["home"]["players"][0]["rating"], 6.53)
        self.assertEqual(lineups["away"]["players"][0]["full_name"], "David de Gea")

        missing = parse_missing_players(EXTRAS_HTML)
        self.assertEqual(len(missing["home"]), 1)
        self.assertEqual(missing["home"][0]["name"], "Marin Sverko")
        self.assertEqual(missing["home"][0]["reason"], "injured")
        self.assertEqual(missing["home"][0]["status"], "Out")
        self.assertIsNone(missing["home"][0]["rating"])
        self.assertEqual(missing["away"][0]["name"], "Fabiano Parisi")
        self.assertEqual(missing["away"][0]["status"], "Out")

        news = parse_team_news(EXTRAS_HTML)
        self.assertEqual(len(news["home"]), 1)
        self.assertIn("zero points", news["home"][0])
        self.assertIn("Vanoli", news["away"][0])

        extras = parse_preview_extras(EXTRAS_HTML)
        self.assertEqual(extras["formation_home"], "3-5-2")
        self.assertEqual(extras["formation_away"], "4-3-3")

    def test_preview_extras_live_html(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "_ws_preview.html"
        if not path.exists():
            self.skipTest("no local WhoScored preview dump")
        html = path.read_text(encoding="utf-8", errors="replace")
        extras = parse_preview_extras(html)
        self.assertEqual(extras["formation_home"], "3-5-2")
        self.assertEqual(extras["formation_away"], "4-3-3")
        self.assertEqual(len(extras["lineups"]["home"]["players"]), 11)
        self.assertEqual(len(extras["lineups"]["away"]["players"]), 11)
        self.assertEqual(extras["lineups"]["home"]["players"][0]["name"], "Stankovic")
        self.assertGreaterEqual(len(extras["missing"]["home"]), 1)
        self.assertEqual(extras["missing"]["away"][0]["name"], "Fabiano Parisi")
        self.assertGreaterEqual(len(extras["team_news"]["home"]), 1)
        self.assertGreaterEqual(len(extras["team_news"]["away"]), 1)

