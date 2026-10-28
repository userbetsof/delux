import { openDb } from '../../utils/db'

export default defineEventHandler((event) => {
  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const sport = q.sport != null && q.sport !== '' ? Number(q.sport) : null
  const qSearch = typeof q.q === 'string' ? q.q.trim() : ''
  const sort = typeof q.sort === 'string' ? q.sort : 'rating'
  const order = typeof q.order === 'string' ? q.order : 'desc'
  const limit = Math.min(Math.max(Number(q.limit) || 100, 1), 500)
  const offset = Math.max(Number(q.offset) || 0, 0)

  const sortColMap: Record<string, string> = {
    team_name: 't.name',
    rating: '(osr.mu - 3.0 * osr.sigma)',
    mu: 'osr.mu',
    sigma: 'osr.sigma',
    matches_played: 'osr.matches_played',
    wins: 'osr.wins',
    draws: 'osr.draws',
    losses: 'osr.losses',
  }
  const orderBy = `${sortColMap[sort] || '(osr.mu - 3.0 * osr.sigma)'} ${order.toUpperCase() === 'ASC' ? 'ASC' : 'DESC'}`

  const whereClauses: string[] = ['1=1']
  const params: unknown[] = []
  if (sport != null) {
    whereClauses.push('osr.sport = ?')
    params.push(sport)
  }
  if (qSearch) {
    whereClauses.push('t.name LIKE ?')
    params.push(`%${qSearch}%`)
  }
  const whereSql = whereClauses.join(' AND ')

  const db = openDb(dbName)
  try {
    const totalRow = db.prepare(
      'SELECT COUNT(*) AS c FROM openskill_ratings osr JOIN teams t ON t.id = osr.team_id WHERE ' + whereSql,
    ).get(...params) as { c: number }
    const total = Number(totalRow?.c || 0)

    const items = db.prepare(`
      SELECT osr.team_id, t.name AS team_name, osr.sport,
             osr.mu, osr.sigma, (osr.mu - 3.0 * osr.sigma) AS rating,
             osr.matches_played, osr.wins, osr.draws, osr.losses,
             osr.last_updated
      FROM openskill_ratings osr
      JOIN teams t ON t.id = osr.team_id
      WHERE ${whereSql}
      ORDER BY ${orderBy}
      LIMIT ? OFFSET ?
    `).all(...params, limit, offset) as Record<string, unknown>[]

    return { items, total, limit, offset }
  } finally {
    db.close()
  }
})
