export default defineEventHandler((event) => {
  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const status = typeof q.status === 'string' ? q.status.trim() : ''
  const search = typeof q.q === 'string' ? q.q.trim() : ''
  const sport = q.sport !== undefined && q.sport !== '' ? Number(q.sport) : null
  const dateFrom = typeof q.date_from === 'string' ? q.date_from.trim() : ''
  const dateTo = typeof q.date_to === 'string' ? q.date_to.trim() : ''
  const limit = Math.min(Math.max(Number(q.limit) || 50, 1), 500)
  const offset = Math.max(Number(q.offset) || 0, 0)

  const db = openDb(dbName)
  try {
    if (!tableExists(db, 'matches')) {
      return { items: [], total: 0, limit, offset }
    }

    const where: string[] = []
    const params: unknown[] = []
    if (status) {
      where.push('m.match_status = ?')
      params.push(status)
    }
    if (sport !== null && !Number.isNaN(sport)) {
      where.push('m.sport = ?')
      params.push(sport)
    }
    if (search) {
      where.push(
        `(m.match_id LIKE ? OR ht.name LIKE ? OR at.name LIKE ? OR l.name LIKE ? OR m.prediction LIKE ?)`,
      )
      const like = `%${search}%`
      params.push(like, like, like, like, like)
    }
    if (dateFrom) {
      where.push('m.match_date >= ?')
      params.push(dateFrom)
    }
    if (dateTo) {
      where.push('m.match_date <= ?')
      params.push(dateTo)
    }
    const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : ''

    const items = rows(
      db,
      `
      SELECT m.match_id, m.match_date, m.prediction, m.match_status, m.minute, m.segment,
             m.score_home, m.score_away, m.profit, m.sport,
             ht.name AS home_team, at.name AS away_team,
             l.name AS league_name, c.name AS country_name
      FROM matches m
      LEFT JOIN teams ht ON ht.id = m.home_team_id
      LEFT JOIN teams at ON at.id = m.away_team_id
      LEFT JOIN leagues l ON l.id = m.league_id
      LEFT JOIN countries c ON c.id = l.country_id
      ${whereSql}
      ORDER BY m.match_date DESC, m.id DESC
      LIMIT ? OFFSET ?
      `,
      [...params, limit, offset],
    )

    const totalRow = row<{ c: number }>(
      db,
      `
      SELECT COUNT(*) AS c
      FROM matches m
      LEFT JOIN teams ht ON ht.id = m.home_team_id
      LEFT JOIN teams at ON at.id = m.away_team_id
      LEFT JOIN leagues l ON l.id = m.league_id
      ${whereSql}
      `,
      params,
    )

    return { items, total: Number(totalRow?.c || 0), limit, offset }
  } finally {
    db.close()
  }
})
