export default defineEventHandler((event) => {
  const matchId = getRouterParam(event, 'id')
  if (!matchId) {
    throw createError({ statusCode: 400, statusMessage: 'match id required' })
  }

  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const db = openDb(dbName)

  try {
    // Получаем информацию о матче
    const match = row(
      db,
      `SELECT m.*, ht.name AS home_team, at.name AS away_team
       FROM matches m
       LEFT JOIN teams ht ON ht.id = m.home_team_id
       LEFT JOIN teams at ON at.id = m.away_team_id
       WHERE m.match_id = ?`,
      [matchId],
    )

    if (!match) {
      throw createError({ statusCode: 404, statusMessage: 'Match not found' })
    }

    // Получаем формы команд
    const homeForm = tableExists(db, 'team_form_stats')
      ? row(db, `SELECT stats_json FROM team_form_stats WHERE team_name = ?`, [match.home_team])
      : null

    const awayForm = tableExists(db, 'team_form_stats')
      ? row(db, `SELECT stats_json FROM team_form_stats WHERE team_name = ?`, [match.away_team])
      : null

    const homeFormParsed = homeForm ? parseJson(homeForm.stats_json, null) : null
    const awayFormParsed = awayForm ? parseJson(awayForm.stats_json, null) : null

    return {
      match: {
        home_team: match.home_team,
        away_team: match.away_team,
      },
      home_form: homeFormParsed,
      away_form: awayFormParsed,
    }
  } finally {
    db.close()
  }
})

function parseJson<T>(raw: unknown, fallback: T): T {
  if (raw == null || raw === '') return fallback
  if (typeof raw === 'object') return raw as T
  try {
    return JSON.parse(String(raw)) as T
  } catch {
    return fallback
  }
}
