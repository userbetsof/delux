export default defineEventHandler((event) => {
  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const search = typeof q.q === 'string' ? q.q.trim() : ''
  const sport = q.sport !== undefined && q.sport !== '' ? Number(q.sport) : null
  const limit = Math.min(Math.max(Number(q.limit) || 100, 1), 500)
  const offset = Math.max(Number(q.offset) || 0, 0)

  const db = openDb(dbName)
  try {
    if (!tableExists(db, 'match_queue')) {
      return { items: [], total: 0, limit, offset }
    }

    const where: string[] = []
    const params: unknown[] = []
    if (sport !== null && !Number.isNaN(sport)) {
      where.push('sport = ?')
      params.push(sport)
    }
    if (search) {
      where.push(`(match_id LIKE ? OR tour_name LIKE ? OR home_name LIKE ? OR away_name LIKE ?)`)
      const like = `%${search}%`
      params.push(like, like, like, like)
    }
    const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : ''

    const items = rows(
      db,
      `
      SELECT *
      FROM match_queue
      ${whereSql}
      ORDER BY date_match, match_id
      LIMIT ? OFFSET ?
      `,
      [...params, limit, offset],
    )
    const totalRow = row<{ c: number }>(
      db,
      `SELECT COUNT(*) AS c FROM match_queue ${whereSql}`,
      params,
    )
    return { items, total: Number(totalRow?.c || 0), limit, offset }
  } finally {
    db.close()
  }
})
