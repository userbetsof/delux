export default defineEventHandler((event) => {
  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const matchId = typeof q.match_id === 'string' ? q.match_id.trim() : ''
  const strategyId = q.strategy_id != null && q.strategy_id !== '' ? Number(q.strategy_id) : null
  const sport = q.sport != null && q.sport !== '' ? Number(q.sport) : null
  const limit = Math.min(Math.max(Number(q.limit) || 100, 1), 500)
  const offset = Math.max(Number(q.offset) || 0, 0)

  const db = openDb(dbName)
  try {
    if (!tableExists(db, 'strategy_predictions')) {
      return { items: [], total: 0, limit, offset }
    }
    const where: string[] = []
    const params: unknown[] = []
    if (matchId) {
      where.push('sp.match_id = ?')
      params.push(matchId)
    }
    if (strategyId != null && Number.isFinite(strategyId)) {
      where.push('sp.strategy_id = ?')
      params.push(strategyId)
    }
    if (sport != null && Number.isFinite(sport)) {
      where.push('m.sport = ?')
      params.push(sport)
    }
    const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : ''
    const items = rows(
      db,
      `
      SELECT sp.*, s.name AS strategy_name,
             m.score_home, m.score_away, m.match_status, m.sport, m.match_date
      FROM strategy_predictions sp
      LEFT JOIN strategies s ON s.id = sp.strategy_id
      LEFT JOIN matches m ON m.match_id = sp.match_id
      ${whereSql}
      ORDER BY sp.id DESC
      LIMIT ? OFFSET ?
      `,
      [...params, limit, offset],
    )
    const totalRow = row<{ c: number }>(
      db,
      `
      SELECT COUNT(*) AS c
      FROM strategy_predictions sp
      LEFT JOIN matches m ON m.match_id = sp.match_id
      ${whereSql}
      `,
      params,
    )
    return { items, total: Number(totalRow?.c || 0), limit, offset }
  } finally {
    db.close()
  }
})
