export type PredKind =
  | { kind: '1x2'; sel: string }
  | { kind: 'btts'; sel: 'yes' | 'no' }
  | { kind: 'ou'; side: 'over' | 'under'; line: number }
  | { kind: 'ah'; side: 'home' | 'away'; line: number }
  | { kind: 'cs'; home: number; away: number }
  | { kind: 'combo'; legs: PredKind[] }
  | { kind: 'unknown'; sel: string }

export type SettleOutcome = boolean | 'push' | null

const FINISHED_RE =
  /заверш|законч|finished|ended|после овертайм|после буллит|after extra|after penalt|тех\.?\s*пораж|неявк/i
const VOID_RE = /перенес|отмен|прерван|задержк|будет доигран/i
const NOT_STARTED_RE = /не начал|ждем|неизвестный \(1\)|неизвестный статус \(1\)/i
const LIVE_RE =
  /\blive\b|1-й тайм|2-й тайм|1-й период|2-й период|3-й период|^овертайм|буллит|перерыв|иннинг|неизвестный \(2[6-9]\)|неизвестный \(3[0-5]\)|неизвестный статус \(2[6-9]\)|неизвестный статус \(3[0-5]\)/i
const INNING_RE =
  /иннинг|неизвестный \(2[6-9]\)|неизвестный \(3[0-5]\)|неизвестный статус \(2[6-9]\)|неизвестный статус \(3[0-5]\)/i

const SETTLE_AFTER_MS: Record<number, number> = {
  1: 2.5 * 3600_000,
  3: 2.5 * 3600_000,
  4: 3 * 3600_000,
  6: 4 * 3600_000,
}

export function toNum(v: unknown): number | null {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

export function normalizePred(raw: string | null | undefined): PredKind | null {
  if (!raw) return null
  const p = String(raw).trim()
  if (!p || p === '-' || p === 'None') return null
  let u = p.toUpperCase().replace(/Х/g, 'X').replace(/х/g, 'X')
  u = u.replace(/П1/g, '1').replace(/П2/g, '2')
  if (p.includes('/')) {
    const parts = p.split('/').map((x) => x.trim()).filter(Boolean)
    if (parts.length >= 2) {
      const legs = parts
        .map((x) => normalizePred(x))
        .filter((x): x is PredKind => !!x && x.kind !== 'combo' && x.kind !== 'unknown')
      if (legs.length >= 2) return { kind: 'combo', legs }
    }
  }
  const compact = u.replace(/\s+/g, '')
  const cs = compact.match(/^(\d+)[:\-.](\d+)$/)
  if (cs) {
    return { kind: 'cs', home: Number(cs[1]), away: Number(cs[2]) }
  }

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

export function settle1x2(h: number, a: number): '1' | 'X' | '2' {
  if (h > a) return '1'
  if (h < a) return '2'
  return 'X'
}

export function settle(info: PredKind | null, h: number, a: number): SettleOutcome {
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
  if (info.kind === 'cs') {
    return h === info.home && a === info.away
  }
  if (info.kind === 'combo') {
    const outs = info.legs.map((leg) => settle(leg, h, a))
    if (outs.some((o) => o == null)) return null
    const wins = outs.filter((o) => o === true).length
    const losses = outs.filter((o) => o === false).length
    const pushes = outs.filter((o) => o === 'push').length
    if (!wins && !losses) return 'push'
    if (losses === 0 && wins > 0) return true
    if (wins === 0 && losses > 0 && pushes === 0) return false
    return wins > losses
  }
  return null
}

export function oddsMarketForPred(info: PredKind | null): string | null {
  if (!info) return null
  if (info.kind === '1x2') {
    const map: Record<string, string> = {
      '1': '1X2_1',
      '2': '1X2_2',
      X: '1X2_X',
      '1X': 'DC_1X',
      X2: 'DC_X2',
      '12': 'DC_12',
    }
    return map[info.sel] || null
  }
  if (info.kind === 'btts') return info.sel === 'yes' ? 'BTTS_YES' : 'BTTS_NO'
  if (info.kind === 'cs') return `CS ${info.home}:${info.away}`
  if (info.kind === 'ah') {
    const side = info.side === 'home' ? 'HOME' : 'AWAY'
    const line = info.line == null ? '0' : String(info.line)
    return `HANDICAP ${side} ${line}`
  }
  return null
}

function parseMatchDate(raw: string | null | undefined): Date | null {
  if (!raw) return null
  const s = String(raw).trim()
  if (!s) return null
  const normalized = s.replace(/\./g, '-').replace(' ', 'T')
  const d = new Date(normalized)
  return Number.isNaN(d.getTime()) ? null : d
}

const UNKNOWN_CODE_RE = /неизвестный(?: статус)?\s*\((\d+)\)/i
const FLASH_STATUS: Record<string, string> = {
  '1': 'Не начался',
  '3': 'Завершен',
  '9': 'Неявка',
  '10': 'После овертайма',
  '11': 'После буллитов',
  '54': 'Тех. поражение',
}

function canonicalStatus(status: string | null | undefined): string {
  const raw = String(status || '').trim()
  if (!raw) return ''
  const unknown = raw.match(UNKNOWN_CODE_RE)
  if (unknown && FLASH_STATUS[unknown[1]]) return FLASH_STATUS[unknown[1]]
  return raw
}

export function isFinished(opts: {
  status?: string | null
  scoreHome?: number | null
  scoreAway?: number | null
  matchDate?: string | null
  sport?: number | null
}): boolean {
  const h = opts.scoreHome
  const a = opts.scoreAway
  if (h == null || a == null) return false
  const total = h + a
  const s = canonicalStatus(opts.status)
  if (VOID_RE.test(s)) return false
  if (FINISHED_RE.test(s)) return true
  if (!s || NOT_STARTED_RE.test(s)) return total > 0

  if (LIVE_RE.test(s)) {
    if (total <= 0) return false
    // Бейсбол: Flashscore часто оставляет код иннинга вместо «Завершен».
    if (INNING_RE.test(s)) return true
    const kickoff = parseMatchDate(opts.matchDate || null)
    if (!kickoff) return false
    const wait = SETTLE_AFTER_MS[Number(opts.sport) || 1] ?? 3 * 3600_000
    return Date.now() > kickoff.getTime() + wait
  }

  return total > 0
}

export function profitForOutcome(
  outcome: SettleOutcome,
  stake: number,
  odds: number | null,
): number | null {
  if (outcome === 'push') return 0
  if (outcome === false) return -stake
  if (outcome === true) {
    if (odds == null || odds <= 1) return null
    return stake * (odds - 1)
  }
  return null
}

function parseNotesObj(notes: unknown): Record<string, unknown> | null {
  if (notes == null || notes === '') return null
  if (typeof notes === 'object') return notes as Record<string, unknown>
  if (typeof notes !== 'string') return null
  const s = notes.trim()
  if (!s.startsWith('{')) return null
  try {
    return JSON.parse(s) as Record<string, unknown>
  } catch {
    return null
  }
}

function noteLegOdds(notes: Record<string, unknown> | null, key: string): number | null {
  const block = notes?.[key]
  if (!block || typeof block !== 'object') return null
  return toNum((block as { odds?: unknown }).odds)
}

/** Профит по строке: WhoScored = две ставки (ТС + фора). */
export function settleRowProfit(
  prediction: string | null | undefined,
  h: number,
  a: number,
  stake: number,
  odds: number | null,
  notes?: unknown,
  lookupMarket?: (market: string) => number | null,
): { outcome: SettleOutcome; profit: number | null; stakeSum: number; label: string } {
  const info = normalizePred(prediction)
  if (!info) return { outcome: null, profit: null, stakeSum: 0, label: '' }
  if (info.kind !== 'combo') {
    const outcome = settle(info, h, a)
    let useOdds = odds
    if ((useOdds == null || useOdds <= 1) && lookupMarket) {
      const m = oddsMarketForPred(info)
      if (m) useOdds = lookupMarket(m)
    }
    const profit = profitForOutcome(outcome, stake, useOdds ?? odds)
    const label =
      outcome === true ? 'Выигрыш' : outcome === false ? 'Проигрыш' : outcome === 'push' ? 'Возврат' : ''
    return { outcome, profit, stakeSum: outcome == null ? 0 : stake, label }
  }

  const obj = parseNotesObj(notes)
  const keys = ['cs', 'ah']
  let profit = 0
  let stakeSum = 0
  let known = 0
  const bits: string[] = []
  for (let i = 0; i < info.legs.length; i++) {
    const leg = info.legs[i]
    const out = settle(leg, h, a)
    if (out == null) continue
    let legOdds = noteLegOdds(obj, keys[i] || '')
    if ((legOdds == null || legOdds <= 1) && lookupMarket) {
      const m =
        (obj?.[keys[i]] as { market?: string } | undefined)?.market || oddsMarketForPred(leg)
      if (m) legOdds = lookupMarket(String(m).toUpperCase())
    }
    if (i === 0 && (legOdds == null || legOdds <= 1)) legOdds = odds
    const p = profitForOutcome(out, stake, out === false ? 1 : legOdds)
    if (p == null && out === true) continue
    known += 1
    stakeSum += stake
    profit += Number(p || 0)
    bits.push(out === true ? 'W' : out === 'push' ? 'P' : 'L')
  }
  if (!known) return { outcome: null, profit: null, stakeSum: 0, label: '' }
  const outcome: SettleOutcome = profit > 0 ? true : profit < 0 ? false : 'push'
  return { outcome, profit, stakeSum, label: bits.join('/') }
}
