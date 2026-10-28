import { openDb } from '../../utils/db'

export default defineEventHandler((event) => {
  const dbName = typeof getQuery(event).db === 'string' ? getQuery(event).db : 'matches'
  const matchId = event.context.params?.matchId || ''

  if (!matchId) {
    throw createError({ statusCode: 400, statusMessage: 'matchId is required' })
  }

  const db = openDb(dbName)
  try {
    const matchRow = db.prepare(`
      SELECT m.match_id, m.sport, m.score_home, m.score_away,
             m.home_team_id, m.away_team_id,
             th.name AS home_name, ta.name AS away_name
      FROM matches m
      JOIN teams th ON th.id = m.home_team_id
      JOIN teams ta ON ta.id = m.away_team_id
      WHERE m.match_id = ?
    `).get(matchId) as Record<string, unknown> | null

    if (!matchRow) return null

    const sport = Number(matchRow.sport)

    function load(teamId: unknown, side: 'home' | 'away') {
      if (teamId == null) return null
      const r = db.prepare(`
        SELECT mu, sigma, matches_played, wins, draws, losses, last_updated
        FROM openskill_ratings WHERE team_id = ? AND sport = ?
      `).get(teamId, sport) as Record<string, unknown> | undefined
      if (!r) return null
      return {
        side,
        team_id: Number(teamId),
        mu: Number(r.mu),
        sigma: Number(r.sigma),
        rating: Number(r.mu) - 3 * Number(r.sigma),
        matches_played: Number(r.matches_played),
        wins: Number(r.wins),
        draws: Number(r.draws),
        losses: Number(r.losses),
        last_updated: (r.last_updated as string) || null,
      }
    }

    return {
      match_id: matchRow.match_id as string,
      sport,
      home_team: matchRow.home_name as string,
      away_team: matchRow.away_name as string,
      score_home: matchRow.score_home != null ? Number(matchRow.score_home) : null,
      score_away: matchRow.score_away != null ? Number(matchRow.score_away) : null,
      home: load(matchRow.home_team_id, 'home'),
      away: load(matchRow.away_team_id, 'away'),
    }
  } finally {
    db.close()
  }
})
