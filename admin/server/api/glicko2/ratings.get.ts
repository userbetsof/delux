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
    rating: 'gr.rating',
    rd: 'gr.rd',
    volatility: 'gr.volatility',
    matches_played: 'gr.matches_played',
    wins: 'gr.wins',
  }
  const orderBy = `${sortColMap[sort] || 'gr.rating'} ${order.toUpperCase() === 'ASC' ? 'ASC' : 'DESC'}`

  const whereClauses: string[] = ['1=1']
  const params: unknown[] = []
  if (sport != null) {
    whereClauses.push('gr.sport = ?')
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
      'SELECT COUNT(*) AS c FROM glicko2_ratings gr JOIN teams t ON t.id = gr.team_id WHERE ' + whereSql,
    ).get(...params) as { c: number }
    const total = Number(totalRow?.c || 0)

    const items = db.prepare(`
      SELECT gr.team_id, t.name AS team_name, gr.sport,
             gr.rating, gr.rd, gr.volatility,
             gr.matches_played, gr.wins, gr.draws, gr.losses,
             gr.last_updated
      FROM glicko2_ratings gr
      JOIN teams t ON t.id = gr.team_id
      WHERE ${whereSql}
      ORDER BY ${orderBy}
      LIMIT ? OFFSET ?
    `).all(...params, limit, offset) as Record<string, unknown>[]

    return { items, total, limit, offset }
  } finally {
    db.close()
  }
})
