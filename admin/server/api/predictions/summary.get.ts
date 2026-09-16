import { sqlOddsEdgeFilters } from '../../utils/strategyNotes'
import {
  isFinished,
  settleRowProfit,
  toNum,
} from '../../utils/settle'

type PredRow = {
  id: number
  match_id: string
  strategy_id: number
  strategy_name: string | null
  prediction: string | null
  odds: number | null
  stake: number | null
  result: string | null
  profit: number | null
  notes: string | null
  score_home: number | null
  score_away: number | null
  match_status: string | null
  sport: number | null
  match_date: string | null
}

type OddsRow = {
  match_id: string
  market_name: string
  odds_value: number | null
}

export default defineEventHandler((event) => {
  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const matchId = typeof q.match_id === 'string' ? q.match_id.trim() : ''
  const strategyId = q.strategy_id != null && q.strategy_id !== '' ? Number(q.strategy_id) : null
  const sport = q.sport != null && q.sport !== '' ? Number(q.sport) : null
  const settledOnly = String(q.settled || '') === '1' || String(q.settled || '').toLowerCase() === 'true'
  const stakeDefault = Math.max(toNum(q.stake) ?? 1, 0.01)

  const db = openDb(dbName)
  try {
    if (!tableExists(db, 'strategy_predictions')) {
      return {
        total: 0,
        settled: 0,
        pending: 0,
        wins: 0,
        losses: 0,
        pushes: 0,
        unknown: 0,
        stake_sum: 0,
        profit: 0,
        roi: 0,
        stake_unit: stakeDefault,
        by_strategy: [],
      }
    }

    const where: string[] = ["TRIM(COALESCE(sp.prediction, '')) != ''"]
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

    const items = rows<PredRow>(
      db,
      `
      SELECT
        sp.id, sp.match_id, sp.strategy_id, s.name AS strategy_name,
        sp.prediction, sp.odds, sp.stake, sp.result, sp.profit, sp.notes,
        m.score_home, m.score_away, m.match_status, m.sport, m.match_date
      FROM strategy_predictions sp
      LEFT JOIN strategies s ON s.id = sp.strategy_id
      LEFT JOIN matches m ON m.match_id = sp.match_id
      WHERE ${where.join(' AND ')}
      `,
      params,
    )

    const oddsByMatch = new Map<string, Map<string, number>>()
    if (tableExists(db, 'odds')) {
      const oddsRows = rows<OddsRow>(
        db,
        `
        SELECT match_id, UPPER(market_name) AS market_name, MAX(odds_value) AS odds_value
        FROM odds
        WHERE odds_value IS NOT NULL AND odds_value > 1
        GROUP BY match_id, UPPER(market_name)
        `,
      )
      for (const r of oddsRows) {
        const odds = toNum(r.odds_value)
        if (!odds) continue
        let m = oddsByMatch.get(r.match_id)
        if (!m) {
          m = new Map()
          oddsByMatch.set(r.match_id, m)
        }
        m.set(String(r.market_name || '').toUpperCase(), odds)
      }
    }

    type Acc = {
      strategy_id: number
      strategy_name: string
      total: number
      settled: number
      pending: number
      wins: number
      losses: number
      pushes: number
      unknown: number
      stake_sum: number
      profit: number
    }

    const byMap = new Map<number, Acc>()
    const totalAcc: Acc = {
      strategy_id: 0,
      strategy_name: 'ALL',
      total: 0,
      settled: 0,
      pending: 0,
      wins: 0,
      losses: 0,
      pushes: 0,
      unknown: 0,
      stake_sum: 0,
      profit: 0,
    }

    const touch = (sid: number, name: string | null) => {
      if (!byMap.has(sid)) {
        byMap.set(sid, {
          strategy_id: sid,
          strategy_name: String(name || `#${sid}`),
          total: 0,
          settled: 0,
          pending: 0,
          wins: 0,
          losses: 0,
          pushes: 0,
          unknown: 0,
          stake_sum: 0,
          profit: 0,
        })
      }
      return byMap.get(sid)!
    }

    for (const item of items) {
      const sid = Number(item.strategy_id)
      const acc = touch(sid, item.strategy_name)
      const h = toNum(item.score_home)
      const a = toNum(item.score_away)
      const finished = isFinished({
        status: item.match_status,
        scoreHome: h,
        scoreAway: a,
        matchDate: item.match_date,
        sport: toNum(item.sport),
      })

      if (!finished || h == null || a == null) {
        if (settledOnly) continue
        acc.total += 1
        totalAcc.total += 1
        acc.pending += 1
        totalAcc.pending += 1
        continue
      }

      acc.total += 1
      totalAcc.total += 1

      const lookup = (market: string) =>
        oddsByMatch.get(item.match_id)?.get(String(market || '').toUpperCase()) ?? null
      const settled = settleRowProfit(
        item.prediction,
        h,
        a,
        toNum(item.stake) ?? stakeDefault,
        toNum(item.odds),
        item.notes,
        lookup,
      )
      if (settled.outcome == null) {
        acc.unknown += 1
        totalAcc.unknown += 1
        continue
      }

      acc.settled += 1
      totalAcc.settled += 1
      acc.stake_sum += settled.stakeSum
      totalAcc.stake_sum += settled.stakeSum
      const profit = settled.profit ?? 0
      acc.profit += profit
      totalAcc.profit += profit
      if (settled.outcome === true) {
        acc.wins += 1
        totalAcc.wins += 1
      } else if (settled.outcome === false) {
        acc.losses += 1
        totalAcc.losses += 1
      } else {
        acc.pushes += 1
        totalAcc.pushes += 1
      }
    }

    const by_strategy = [...byMap.values()]
      .map((x) => ({
        ...x,
        stake_sum: Number(x.stake_sum.toFixed(2)),
        profit: Number(x.profit.toFixed(2)),
        roi: x.stake_sum > 0 ? Number(((x.profit / x.stake_sum) * 100).toFixed(2)) : 0,
      }))
      .sort((a, b) => a.strategy_id - b.strategy_id)

    return {
      total: totalAcc.total,
      settled: totalAcc.settled,
      pending: totalAcc.pending,
      wins: totalAcc.wins,
      losses: totalAcc.losses,
      pushes: totalAcc.pushes,
      unknown: totalAcc.unknown,
      stake_sum: Number(totalAcc.stake_sum.toFixed(2)),
      profit: Number(totalAcc.profit.toFixed(2)),
      roi: totalAcc.stake_sum > 0
        ? Number(((totalAcc.profit / totalAcc.stake_sum) * 100).toFixed(2))
        : 0,
      stake_unit: stakeDefault,
      by_strategy,
    }
  } finally {
    db.close()
  }
})
