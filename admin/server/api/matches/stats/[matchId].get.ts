export default defineEventHandler((event) => {
  const matchId = getRouterParam(event, 'matchId')
  if (!matchId) {
    throw createError({ statusCode: 400, statusMessage: 'matchId required' })
  }

  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const db = openDb(dbName)

  try {
    if (!tableExists(db, 'match_stats')) {
      return { stats: null }
    }

    const statsRow = row(db, `SELECT stats_json FROM match_stats WHERE match_id = ?`, [matchId])
    const stats = statsRow ? parseJson(statsRow.stats_json, null) : null

    return { stats }
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
