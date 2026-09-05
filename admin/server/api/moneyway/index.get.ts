export default defineEventHandler((event) => {
  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const matchId = typeof q.match_id === 'string' ? q.match_id.trim() : ''
  const signal = typeof q.signal === 'string' ? q.signal.trim() : ''
  const found = typeof q.found === 'string' ? q.found.trim() : ''
  const limit = Math.min(Math.max(Number(q.limit) || 100, 1), 500)
  const offset = Math.max(Number(q.offset) || 0, 0)

  const db = openDb(dbName)
  try {
    if (!tableExists(db, 'moneyway')) {
      return { items: [], total: 0, limit, offset }
    }
    const where: string[] = []
    const params: unknown[] = []
    if (matchId) {
      where.push('mw.match_id = ?')
      params.push(matchId)
    }
    if (signal === '1' || signal === 'true') {
      where.push('mw.has_signal = 1')
    } else if (signal === '0' || signal === 'false') {
      where.push('mw.has_signal = 0')
    }
    if (found === '1' || found === 'true') {
      where.push('mw.found = 1')
    } else if (found === '0' || found === 'false') {
      where.push('mw.found = 0')
    }
    const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : ''
    const items = rows(
      db,
      `
      SELECT
        mw.*,
        m.match_date,
        m.match_status,
        m.score_home,
        m.score_away,
        th.name AS home_team,
        ta.name AS away_team
      FROM moneyway mw
      LEFT JOIN matches m ON m.match_id = mw.match_id
      LEFT JOIN teams th ON th.id = m.home_team_id
      LEFT JOIN teams ta ON ta.id = m.away_team_id
      ${whereSql}
      ORDER BY mw.fetched_at DESC
      LIMIT ? OFFSET ?
      `,
      [...params, limit, offset],
    )
    const totalRow = row<{ c: number }>(
      db,
      `SELECT COUNT(*) AS c FROM moneyway mw ${whereSql}`,
      params,
    )
    return { items, total: Number(totalRow?.c || 0), limit, offset }
  } finally {
    db.close()
  }
})
