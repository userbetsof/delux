import { withStrategyEdge } from '../../utils/strategyNotes'

function parseJson<T>(raw: unknown, fallback: T): T {
  if (raw == null || raw === '') return fallback
  if (typeof raw === 'object') return raw as T
  try {
    return JSON.parse(String(raw)) as T
  } catch {
    return fallback
  }
}

export default defineEventHandler((event) => {
  const matchId = getRouterParam(event, 'id')
  if (!matchId) {
    throw createError({ statusCode: 400, statusMessage: 'match id required' })
  }
  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const db = openDb(dbName)

  try {
    const match = row(
      db,
      `
      SELECT m.*,
             ht.name AS home_team, at.name AS away_team,
             l.name AS league_name, c.name AS country_name
      FROM matches m
      LEFT JOIN teams ht ON ht.id = m.home_team_id
      LEFT JOIN teams at ON at.id = m.away_team_id
      LEFT JOIN leagues l ON l.id = m.league_id
      LEFT JOIN countries c ON c.id = l.country_id
      WHERE m.match_id = ?
      `,
      [matchId],
    )
    if (!match) {
      throw createError({ statusCode: 404, statusMessage: 'Match not found' })
    }

    const odds = tableExists(db, 'odds')
      ? rows(db, `SELECT * FROM odds WHERE match_id = ? ORDER BY id`, [matchId])
      : []

    const predictions = tableExists(db, 'strategy_predictions')
      ? rows(
          db,
          `
          SELECT sp.*, s.name AS strategy_name
          FROM strategy_predictions sp
          LEFT JOIN strategies s ON s.id = sp.strategy_id
          WHERE sp.match_id = ?
          ORDER BY sp.strategy_id
          `,
          [matchId],
        ).map((row) => withStrategyEdge(row))
      : []

    const outcomes = tableExists(db, 'outcome_probabilities')
      ? rows(
          db,
          `
          SELECT o.*, ss.strategy_name
          FROM outcome_probabilities o
          LEFT JOIN sub_strategies ss ON ss.id = o.strategy_id
          WHERE o.match_id = ?
          ORDER BY o.strategy_id
          `,
          [matchId],
        )
      : []

    const goals = tableExists(db, 'goal_probabilities')
      ? row(db, `SELECT * FROM goal_probabilities WHERE match_id = ?`, [matchId])
      : null

    const snapRow = tableExists(db, 'match_snapshot')
      ? row(db, `SELECT * FROM match_snapshot WHERE match_id = ?`, [matchId])
      : null
    const snapshot = snapRow
      ? {
          ...snapRow,
          standings: parseJson(snapRow.standings_json, null),
          form: parseJson(snapRow.form_json, null),
          h2h: parseJson(snapRow.h2h_json, null),
          team_matches: parseJson(snapRow.team_matches_json, null),
          weather: parseJson(snapRow.weather_json, null),
        }
      : null

    const weatherHistory = tableExists(db, 'match_weather')
      ? rows(
          db,
          `SELECT * FROM match_weather WHERE match_id = ? ORDER BY fetched_at DESC`,
          [matchId],
        )
      : []
    const weather = {
      snapshot: snapshot?.weather || null,
      latest: weatherHistory.find((item) => item.kind === 'forecast') || null,
      actual: weatherHistory.find((item) => item.kind === 'actual') || null,
      history: weatherHistory,
    }

    const emptySides = { home: [] as unknown[], away: [] as unknown[] }
    const emptyLineups = {
      home: { formation: '', players: [] as unknown[] },
      away: { formation: '', players: [] as unknown[] },
    }
    const wsRow = tableExists(db, 'whoscored_preview')
      ? row(db, `SELECT * FROM whoscored_preview WHERE match_id = ?`, [matchId])
      : null
    const whoscored = wsRow
      ? {
          match_id: wsRow.match_id,
          ws_id: wsRow.ws_id,
          ws_url: wsRow.ws_url,
          home_name: wsRow.home_name,
          away_name: wsRow.away_name,
          score_home: wsRow.score_home,
          score_away: wsRow.score_away,
          formation_home: wsRow.formation_home,
          formation_away: wsRow.formation_away,
          fetched_at: wsRow.fetched_at,
          team_news: parseJson(wsRow.team_news_json, emptySides),
          missing: parseJson(wsRow.missing_json, emptySides),
          lineups: parseJson(wsRow.lineups_json, emptyLineups),
        }
      : null

    const statsRow = tableExists(db, 'match_stats')
      ? row(db, `SELECT stats_json, fetched_at FROM match_stats WHERE match_id = ?`, [matchId])
      : null
    const matchStats = statsRow
      ? {
          ...parseJson(statsRow.stats_json, {}),
          fetched_at: statsRow.fetched_at,
        }
      : null

    return { match, odds, predictions, outcomes, goals, snapshot, weather, whoscored, matchStats }
  } finally {
    db.close()
  }
})
