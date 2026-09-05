export default defineEventHandler((event) => {
  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const path = resolveDbPath(dbName)
  const db = openDb(dbName)

  try {
    const count = (table: string) => {
      if (!tableExists(db, table)) return 0
      const r = row<{ c: number }>(db, `SELECT COUNT(*) AS c FROM ${table}`)
      return Number(r?.c || 0)
    }

    return {
      db: dbName,
      path,
      label: dbLabel(path),
      available: Object.keys(DB_ALIASES),
      counts: {
        matches: count('matches'),
        match_queue: count('match_queue'),
        odds: count('odds'),
        countries: count('countries'),
        leagues: count('leagues'),
        teams: count('teams'),
        strategies: count('strategies'),
        strategy_predictions: count('strategy_predictions'),
        sub_strategies: count('sub_strategies'),
        outcome_probabilities: count('outcome_probabilities'),
        goal_probabilities: count('goal_probabilities'),
      },
      recent: tableExists(db, 'matches')
        ? rows(
            db,
            `
            SELECT m.match_id, m.match_date, m.prediction, m.match_status, m.sport,
                   m.score_home, m.score_away,
                   ht.name AS home_team, at.name AS away_team,
                   l.name AS league_name, c.name AS country_name
            FROM matches m
            LEFT JOIN teams ht ON ht.id = m.home_team_id
            LEFT JOIN teams at ON at.id = m.away_team_id
            LEFT JOIN leagues l ON l.id = m.league_id
            LEFT JOIN countries c ON c.id = l.country_id
            ORDER BY m.match_date DESC, m.id DESC
            LIMIT 8
            `,
          )
        : [],
    }
  } finally {
    db.close()
  }
})
