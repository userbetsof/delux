export default defineEventHandler((event) => {
  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const limit = Math.min(Math.max(Number(q.limit) || 100, 1), 500)
  const offset = Math.max(Number(q.offset) || 0, 0)

  const db = openDb(dbName)
  try {
    if (!tableExists(db, 'goal_probabilities')) {
      return { items: [], total: 0, limit, offset }
    }
    const items = rows(
      db,
      `SELECT * FROM goal_probabilities ORDER BY id DESC LIMIT ? OFFSET ?`,
      [limit, offset],
    )
    const totalRow = row<{ c: number }>(db, `SELECT COUNT(*) AS c FROM goal_probabilities`)
    return { items, total: Number(totalRow?.c || 0), limit, offset }
  } finally {
    db.close()
  }
})
