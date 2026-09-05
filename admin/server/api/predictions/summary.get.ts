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
  score_home: number | null
  score_away: number | null
  match_status: string | null
  sport: number | null
  match_date: string | null
}

function toNum(v: unknown): number | null {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function normalizePred(raw: string | null | undefined): {
  kind: string
  sel?: string
  side?: string
  line?: number
} | null {
  if (!raw) return null
  const p = String(raw).trim()
  if (!p || p === '-' || p === 'None') return null
  let u = p.toUpperCase().replace(/Х/g, 'X').replace(/х/g, 'X')
  u = u.replace(/П1/g, '1').replace(/П2/g, '2')
  const compact = u.replace(/\s+/g, '')

  if (['1', 'X', '2', '1X', 'X2', '12'].includes(compact)) {
    return { kind: '1x2', sel: compact }
  }
  if (u.includes('ОЗ') || u.includes('BTTS') || compact.includes('ОБЕЗАБ')) {
    const no = u.includes('НЕТ') || u.includes('NO')
    return { kind: 'btts', sel: no ? 'no' : 'yes' }
  }
  const ou = u.match(/(ТБ|ТМ|OVER|UNDER)\s*([0-9]+(?:[.,][0-9]+)?)/i)
  if (ou) {
    const side = ['ТБ', 'OVER'].includes(ou[1].toUpperCase()) ? 'over' : 'under'
    return { kind: 'ou', side, line: Number(ou[2].replace(',', '.')) }
  }
  const ah = u.match(/Ф([12])\s*\(([-+]?\d+(?:[.,]\d+)?)\)/)
  if (ah) {
    return {
      kind: 'ah',
      side: ah[1] === '1' ? 'home' : 'away',
      line: Number(ah[2].replace(',', '.')),
    }
  }
  const ah0 = u.match(/Ф([12])/)
  if (ah0) {
    return { kind: 'ah', side: ah0[1] === '1' ? 'home' : 'away', line: 0 }
  }
  return { kind: 'unknown', sel: p }
}

function settle1x2(h: number, a: number): '1' | 'X' | '2' {
  if (h > a) return '1'
  if (h < a) return '2'
  return 'X'
}

function settle(
  info: ReturnType<typeof normalizePred>,
  h: number,
  a: number,
): boolean | 'push' | null {
  if (!info) return null
  if (info.kind === '1x2' && info.sel) {
    const res = settle1x2(h, a)
    const map: Record<string, boolean> = {
      '1': res === '1',
      '2': res === '2',
      X: res === 'X',
      '1X': res === '1' || res === 'X',
      X2: res === 'X' || res === '2',
      '12': res === '1' || res === '2',
    }
    return map[info.sel] ?? null
  }
  if (info.kind === 'btts') {
    const both = h > 0 && a > 0
    return info.sel === 'yes' ? both : !both
  }
  if (info.kind === 'ou' && info.line != null && info.side) {
    const total = h + a
    if (Math.abs(info.line - Math.round(info.line)) < 1e-9 && total === info.line) return 'push'
    return info.side === 'over' ? total > info.line : total < info.line
  }
  if (info.kind === 'ah' && info.line != null && info.side) {
    const adj = info.side === 'home' ? h + info.line - a : a + info.line - h
    if (Math.abs(adj) < 1e-9) return 'push'
    return adj > 0
  }
  return null
}

function isFinished(status: string | null | undefined, h: number | null, a: number | null): boolean {
  if (h == null || a == null) return false
  const s = String(status || '').toLowerCase()
  return (
    s.includes('заверш') ||
    s.includes('законч') ||
    s.includes('finished') ||
    s.includes('ended') ||
    s.includes('после матч') ||
    s.includes('after')
  )
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

    const items = rows<PredRow>(
      db,
      `
      SELECT
        sp.id, sp.match_id, sp.strategy_id, s.name AS strategy_name,
        sp.prediction, sp.odds, sp.stake, sp.result, sp.profit,
        m.score_home, m.score_away, m.match_status, m.sport, m.match_date
      FROM strategy_predictions sp
      LEFT JOIN strategies s ON s.id = sp.strategy_id
      LEFT JOIN matches m ON m.match_id = sp.match_id
      WHERE ${where.join(' AND ')}
      `,
      params,
    )

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
      const finished = isFinished(item.match_status, h, a)

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

      const stake = toNum(item.stake) ?? stakeDefault
      const odds = toNum(item.odds) ?? 1
      const info = normalizePred(item.prediction)
      let outcome = settle(info, h, a)

      let profit = 0
      if (outcome === true) {
        profit = stake * (odds - 1)
        acc.wins += 1
        totalAcc.wins += 1
      } else if (outcome === false) {
        profit = -stake
        acc.losses += 1
        totalAcc.losses += 1
      } else if (outcome === 'push') {
        profit = 0
        acc.pushes += 1
        totalAcc.pushes += 1
      } else {
        const stored = String(item.result || '')
        const storedProfit = toNum(item.profit)
        if (stored.includes('Выигр') && storedProfit != null) {
          profit = storedProfit
          acc.wins += 1
          totalAcc.wins += 1
        } else if (stored.includes('Проигр') && storedProfit != null) {
          profit = storedProfit
          acc.losses += 1
          totalAcc.losses += 1
        } else {
          acc.unknown += 1
          totalAcc.unknown += 1
          continue
        }
      }

      acc.settled += 1
      totalAcc.settled += 1
      acc.stake_sum += stake
      totalAcc.stake_sum += stake
      acc.profit += profit
      totalAcc.profit += profit
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
