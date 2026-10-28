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

    if (!matchRow) {
      return null
    }

    const sport = Number(matchRow.sport)

    function loadRating(teamId: unknown, side: 'home' | 'away') {
      if (teamId == null) return null
      const r = db.prepare(`
        SELECT rating, rd, volatility, matches_played, wins, draws, losses, last_updated
        FROM glicko2_ratings
        WHERE team_id = ? AND sport = ?
      `).get(teamId, sport) as Record<string, unknown> | undefined
      if (!r) return null
      return {
        side,
        team_id: Number(teamId),
        rating: Number(r.rating),
        rd: Number(r.rd),
        volatility: Number(r.volatility),
        matches_played: Number(r.matches_played),
        wins: Number(r.wins),
        draws: Number(r.draws),
        losses: Number(r.losses),
        last_updated: (r.last_updated as string) || null,
      }
    }

    const home = loadRating(matchRow.home_team_id, 'home')
    const away = loadRating(matchRow.away_team_id, 'away')

    // История Glicko-2 для этого матча (rating_before/after, delta, expected, actual)
    const history = db.prepare(`
      SELECT team_id, rating_before, rating_after, rating_delta, expected, actual
      FROM glicko2_rating_history
      WHERE match_id = ? AND sport = ?
    `).all(matchId, sport) as Record<string, unknown>[]

    return {
      match_id: matchRow.match_id as string,
      sport,
      home_team: matchRow.home_name as string,
      away_team: matchRow.away_name as string,
      score_home: matchRow.score_home != null ? Number(matchRow.score_home) : null,
      score_away: matchRow.score_away != null ? Number(matchRow.score_away) : null,
      home,
      away,
      history: history.map((h) => ({
        team_id: Number(h.team_id),
        rating_before: Number(h.rating_before),
        rating_after: Number(h.rating_after),
        rating_delta: Number(h.rating_delta),
        expected: Number(h.expected),
        actual: Number(h.actual),
      })),
    }
  } finally {
    db.close()
  }
})
