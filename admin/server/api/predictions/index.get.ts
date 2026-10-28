import { sqlOddsEdgeFilters, withStrategyEdge } from '../../utils/strategyNotes'
import { parseNumberList, sqlInList } from '../../utils/queryLists'
import {
  isFinished,
  settleRowProfit,
  toNum,
} from '../../utils/settle'

export default defineEventHandler((event) => {
  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const matchId = typeof q.match_id === 'string' ? q.match_id.trim() : ''
  // Мультивыбор: ?strategy_id=1,3,8 или ?strategy_id=1&strategy_id=3
  const strategyIds = parseNumberList(q.strategy_id)
  const sports = parseNumberList(q.sport)
  const dateFrom = typeof q.date_from === 'string' ? q.date_from.trim() : ''
  const dateTo = typeof q.date_to === 'string' ? q.date_to.trim() : ''
  const oddsMin = parseQueryNumber(q.odds_min)
  const oddsMax = parseQueryNumber(q.odds_max)
  const edgeMin = parseQueryNumber(q.edge_min)
  const edgeMax = parseQueryNumber(q.edge_max)
  const limit = Math.min(Math.max(Number(q.limit) || 100, 1), 500)
  const offset = Math.max(Number(q.offset) || 0, 0)

  // Конвертируем формат даты из YYYY-MM-DD в YYYY.MM.DD HH:MM
  function convertDate(dateStr: string): string {
    if (!dateStr) return ''
    const [year, month, day] = dateStr.split('-')
    return `${year}.${month}.${day} 00:00`
  }
  const dateFromConv = dateFrom ? convertDate(dateFrom) : ''
  const dateToConv = dateTo ? convertDate(dateTo) : ''

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
    const stratFilter = sqlInList('sp.strategy_id', strategyIds)
    if (stratFilter) {
      where.push(stratFilter.clause)
      params.push(...stratFilter.params)
    }
    const sportFilter = sqlInList('m.sport', sports)
    if (sportFilter) {
      where.push(sportFilter.clause)
      params.push(...sportFilter.params)
    }
    // Odds фильтры
    if (oddsMin != null) {
      where.push('sp.odds IS NOT NULL AND sp.odds >= ?')
      params.push(oddsMin)
    }
    if (oddsMax != null) {
      where.push('sp.odds IS NOT NULL AND sp.odds <= ?')
      params.push(oddsMax)
    }
    // Edge фильтры
    const edgeRaw = "CAST(COALESCE(json_extract(sp.notes, '$.difference'), json_extract(sp.notes, '$.edge')) AS REAL)"
    const edgePp = `(CASE WHEN ABS(${edgeRaw}) <= 1.5 THEN (${edgeRaw}) * 100.0 ELSE ${edgeRaw} END)`
    if (edgeMin != null) {
      where.push(`${edgeRaw} IS NOT NULL AND ${edgePp} >= ?`)
      params.push(edgeMin)
    }
    if (edgeMax != null) {
      where.push(`${edgeRaw} IS NOT NULL AND ${edgePp} <= ?`)
      params.push(edgeMax)
    }
    if (dateFromConv) {
      where.push('m.match_date >= ?')
      params.push(dateFromConv)
    }
    if (dateToConv) {
      where.push('m.match_date <= ?')
      params.push(dateToConv + ' 23:59')
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
