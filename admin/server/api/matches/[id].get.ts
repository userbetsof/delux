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
        )
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

    return { match, odds, predictions, outcomes, goals }
  } finally {
    db.close()
  }
})
