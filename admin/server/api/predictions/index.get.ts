import { sqlOddsEdgeFilters, withStrategyEdge } from '../../utils/strategyNotes'
import {
  isFinished,
  settleRowProfit,
  toNum,
} from '../../utils/settle'

export default defineEventHandler((event) => {
  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const matchId = typeof q.match_id === 'string' ? q.match_id.trim() : ''
  const strategyId = q.strategy_id != null && q.strategy_id !== '' ? Number(q.strategy_id) : null
  const sport = q.sport != null && q.sport !== '' ? Number(q.sport) : null
  const dateFrom = typeof q.date_from === 'string' ? q.date_from.trim() : ''
  const dateTo = typeof q.date_to === 'string' ? q.date_to.trim() : ''
  const limit = Math.min(Math.max(Number(q.limit) || 100, 1), 500)
  const offset = Math.max(Number(q.offset) || 0, 0)

  const db = openDb(dbName)
  try {
    if (!tableExists(db, 'strategy_predictions')) {
      return { items: [], total: 0, limit, offset }
    }
    const where: string[] = []
    const params: unknown[] = []
    if (matchId) {
      where.push('sp.match_id = ?')
      params.push(matchId)
    }
    if (strategyId != null && Number.isFinite(strategyId)) {
      where.push('sp.strategy_id = ?')
      params.push(strategyId)
    }
    if (sport != null && Number.isFinite(sport)) {
      where.push('m.sport = ?')
      params.push(sport)
    }
    const extra = sqlOddsEdgeFilters(q as Record<string, unknown>)
    where.push(...extra.clauses)
    params.push(...extra.params)
    if (dateFrom) {
      where.push('m.match_date >= ?')
      params.push(dateFrom)
    }
    if (dateTo) {
      where.push('m.match_date <= ?')
      params.push(dateTo)
    }
    const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : ''
    const items = rows<Record<string, unknown>>(
      db,
      `
      SELECT sp.*, s.name AS strategy_name,
             m.score_home, m.score_away, m.match_status, m.sport, m.match_date
      FROM strategy_predictions sp
      LEFT JOIN strategies s ON s.id = sp.strategy_id
      LEFT JOIN matches m ON m.match_id = sp.match_id
      ${whereSql}
      ORDER BY sp.id DESC
      LIMIT ? OFFSET ?
      `,
      [...params, limit, offset],
    )
    const totalRow = row<{ c: number }>(
      db,
      `
      SELECT COUNT(*) AS c
      FROM strategy_predictions sp
      LEFT JOIN matches m ON m.match_id = sp.match_id
      ${whereSql}
      `,
      params,
    )

    const decorated = items.map((item) => {
      const base = withStrategyEdge(item)
      const h = toNum(item.score_home)
      const a = toNum(item.score_away)
      const finished = isFinished({
        status: item.match_status as string | null,
        scoreHome: h,
        scoreAway: a,
        matchDate: item.match_date as string | null,
        sport: toNum(item.sport),
      })
      if (!finished || h == null || a == null) {
        return { ...base, result: item.result ?? null, profit: null, settled: false }
      }
      const settled = settleRowProfit(
        String(item.prediction || ''),
        h,
        a,
        toNum(item.stake) ?? 1,
        toNum(item.odds),
        item.notes,
      )
      if (settled.outcome == null) {
        return { ...base, settled: false }
      }
      return {
        ...base,
        result: settled.label || item.result,
        profit: settled.profit,
        settled: true,
      }
    })

    return { items: decorated, total: Number(totalRow?.c || 0), limit, offset }
  } finally {
    db.close()
  }
})
