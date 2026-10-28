import { openDb } from '../../utils/db'

export default defineEventHandler((event) => {
  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const sport = q.sport != null && q.sport !== '' ? Number(q.sport) : null

  const db = openDb(dbName)
  try {
    const where = sport != null ? 'WHERE osr.sport = ?' : 'WHERE 1=1'
    const params = sport != null ? [sport] : []

    const stats = db.prepare(`
      SELECT
        COUNT(*) AS total_teams,
        AVG(osr.mu) AS avg_mu,
        AVG(osr.sigma) AS avg_sigma,
        SUM(osr.matches_played) AS total_matches
      FROM openskill_ratings osr
      ${where}
    `).get(...params) as Record<string, unknown> | null

    if (!stats || Number(stats.total_teams) === 0) {
      return {
        total_teams: 0,
        avg_mu: 0,
        avg_sigma: 0,
        total_matches: 0,
      }
    }

    return {
      total_teams: Number(stats.total_teams),
      avg_mu: Number(stats.avg_mu || 0).toFixed(2),
      avg_sigma: Number(stats.avg_sigma || 0).toFixed(2),
      total_matches: Number(stats.total_matches || 0),
    }
  } finally {
    db.close()
  }
})
