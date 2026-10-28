import { openDb } from '../../utils/db'

export default defineEventHandler((event) => {
  const dbName = typeof getQuery(event).db === 'string' ? getQuery(event).db : 'matches'
  const matchId = event.context.params?.matchId || ''

  if (!matchId) {
    throw createError({ statusCode: 400, statusMessage: 'matchId is required' })
  }

  const db = openDb(dbName)
  try {
    // Получаем историю ELO для матча
    const history = db.prepare(`
      SELECT erh.*, t.name AS team_name
      FROM elo_rating_history erh
      JOIN teams t ON t.id = erh.team_id
      WHERE erh.match_id = ?
      ORDER BY erh.team_id ASC
    `).all(matchId) as Record<string, unknown>[]

    if (history.length === 0) {
      return null
    }

    // Получаем данные матча
    const matchRow = db.prepare(`
      SELECT m.match_id, m.sport, m.score_home, m.score_away,
             th.name AS home_name, ta.name AS away_name
      FROM matches m
      JOIN teams th ON th.id = m.home_team_id
      JOIN teams ta ON ta.id = m.away_team_id
      WHERE m.match_id = ?
    `).get(matchId) as Record<string, unknown> | null

    if (!matchRow) {
      return null
    }

    const homeRecord = history.find((r) => (r.team_name as string) === (matchRow.home_name as string))
    const awayRecord = history.find((r) => (r.team_name as string) === (matchRow.away_name as string))

    return {
      match_id: matchRow.match_id as string,
      sport: Number(matchRow.sport),
      home_team: matchRow.home_name as string,
      away_team: matchRow.away_name as string,
      score_home: matchRow.score_home != null ? Number(matchRow.score_home) : null,
      score_away: matchRow.score_away != null ? Number(matchRow.score_away) : null,
      elo_before: {
        home: homeRecord ? Number(homeRecord.rating_before) : 0,
        away: awayRecord ? Number(awayRecord.rating_before) : 0,
      },
      elo_after: {
        home: homeRecord ? Number(homeRecord.rating_after) : 0,
        away: awayRecord ? Number(awayRecord.rating_after) : 0,
      },
      delta: {
        home: homeRecord ? Number(homeRecord.rating_delta) : 0,
        away: awayRecord ? Number(awayRecord.rating_delta) : 0,
      },
    }
  } finally {
    db.close()
  }
})
