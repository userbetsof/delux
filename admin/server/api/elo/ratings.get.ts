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

  const validSort = ['rating', 'matches_played', 'wins', 'draws', 'losses', 'team_name']
  const sortColMap: Record<string, string> = {
    team_name: 't.name',
    rating: 'ter.rating',
    matches_played: 'ter.matches_played',
    wins: 'ter.wins',
    draws: 'ter.draws',
    losses: 'ter.losses',
  }

  const orderBy = `${sortColMap[sort] || 'ter.rating'} ${order.toUpperCase() === 'ASC' ? 'ASC' : 'DESC'}`

  const whereClauses: string[] = ['1=1']
  const params: unknown[] = []

  if (sport != null) {
    whereClauses.push('ter.sport = ?')
    params.push(sport)
  }
  if (qSearch) {
    whereClauses.push('t.name LIKE ?')
    params.push(`%${qSearch}%`)
  }

  const whereSql = whereClauses.join(' AND ')

  const db = openDb(dbName)
  try {
    const totalRow = db.prepare('SELECT COUNT(*) AS c FROM team_elo_ratings ter JOIN teams t ON t.id = ter.team_id WHERE ' + whereSql).get(...params) as { c: number }
    const total = Number(totalRow?.c || 0)

    const items = db.prepare(`
      SELECT ter.team_id, t.name AS team_name, ter.sport,
             ter.rating, ter.matches_played, ter.wins, ter.draws, ter.losses,
             ter.last_updated
      FROM team_elo_ratings ter
      JOIN teams t ON t.id = ter.team_id
      WHERE ${whereSql}
      ORDER BY ${orderBy}
      LIMIT ? OFFSET ?
    `).all(...params, limit, offset) as Record<string, unknown>[]

    return { items, total, limit, offset }
  } finally {
    db.close()
  }
})
