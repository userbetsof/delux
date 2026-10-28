import { openDb } from '../../utils/db'

export default defineEventHandler((event) => {
  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const sport = q.sport != null && q.sport !== '' ? Number(q.sport) : null

  const db = openDb(dbName)
  try {
    const where = sport != null ? 'WHERE ter.sport = ?' : 'WHERE 1=1'
    const params = sport != null ? [sport] : []

    const stats = db.prepare(`
      SELECT
        COUNT(*) AS total_teams,
        AVG(ter.rating) AS avg_rating,
        MIN(ter.rating) AS min_rating,
        MAX(ter.rating) AS max_rating,
        SUM(ter.matches_played) AS total_matches
      FROM team_elo_ratings ter
      ${where}
    `).get(...params) as Record<string, unknown> | null

    if (!stats || Number(stats.total_teams) === 0) {
      return {
        total_teams: 0,
        avg_rating: 0,
        median_rating: 0,
        min_rating: 0,
        max_rating: 0,
        total_matches: 0,
        by_tier: { champion: 0, strong: 0, average: 0, weak: 0 },
      }
    }

    // Tier breakdown
    const tiers = db.prepare(`
      SELECT
        SUM(CASE WHEN ter.rating >= 1800 THEN 1 ELSE 0 END) AS champion,
        SUM(CASE WHEN ter.rating >= 1600 AND ter.rating < 1800 THEN 1 ELSE 0 END) AS strong,
        SUM(CASE WHEN ter.rating >= 1400 AND ter.rating < 1600 THEN 1 ELSE 0 END) AS average,
        SUM(CASE WHEN ter.rating < 1400 THEN 1 ELSE 0 END) AS weak
      FROM team_elo_ratings ter
      ${where}
    `).get(...params) as Record<string, unknown>

    // Median via subquery
    const mid = Math.ceil(Number(stats.total_teams) / 2)
    const medianRow = db.prepare(`
      SELECT rating FROM team_elo_ratings ter ${where} ORDER BY ter.rating ASC LIMIT 1 OFFSET ?
    `).get(...[...params, mid - 1]) as { rating: number } | null

    return {
      total_teams: Number(stats.total_teams),
      avg_rating: Number(stats.avg_rating || 0).toFixed(1),
      median_rating: Number(medianRow?.rating || 0).toFixed(1),
      min_rating: Number(stats.min_rating || 0).toFixed(1),
      max_rating: Number(stats.max_rating || 0).toFixed(1),
      total_matches: Number(stats.total_matches || 0),
      by_tier: {
        champion: Number(tiers?.champion || 0),
        strong: Number(tiers?.strong || 0),
        average: Number(tiers?.average || 0),
        weak: Number(tiers?.weak || 0),
      },
    }
  } finally {
    db.close()
  }
})
