export default defineEventHandler((event) => {
  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const matchId = typeof q.match_id === 'string' ? q.match_id.trim() : ''
  const limit = Math.min(Math.max(Number(q.limit) || 100, 1), 500)
  const offset = Math.max(Number(q.offset) || 0, 0)

  const db = openDb(dbName)
  try {
    if (!tableExists(db, 'odds')) {
      return { items: [], total: 0, limit, offset }
    }
    const where = matchId ? 'WHERE o.match_id = ?' : ''
    const params: unknown[] = matchId ? [matchId] : []
    const items = rows(
      db,
      `
      SELECT o.*, m.match_date, m.prediction, m.match_status
      FROM odds o
      LEFT JOIN matches m ON m.match_id = o.match_id
      ${where}
      ORDER BY o.id DESC
      LIMIT ? OFFSET ?
      `,
      [...params, limit, offset],
    )
    const totalRow = row<{ c: number }>(
      db,
      `SELECT COUNT(*) AS c FROM odds o ${where}`,
      params,
    )
    return { items, total: Number(totalRow?.c || 0), limit, offset }
  } finally {
    db.close()
  }
})
