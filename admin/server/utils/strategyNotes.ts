export function parseStrategyEdge(notes: unknown): number | null {
  if (notes == null || notes === '') return null
  let obj: Record<string, unknown> | null = null
  if (typeof notes === 'string') {
    const s = notes.trim()
    if (!s.startsWith('{') && !s.startsWith('[')) return null
    try {
      obj = JSON.parse(s) as Record<string, unknown>
    } catch {
      return null
    }
  } else if (typeof notes === 'object') {
    obj = notes as Record<string, unknown>
  }
  if (!obj) return null
  const raw = obj.difference ?? obj.edge
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}

export function withStrategyEdge<T extends Record<string, unknown>>(row: T): T & { edge: number | null } {
  return { ...row, edge: parseStrategyEdge(row.notes) }
}

export function parseQueryNumber(v: unknown): number | null {
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

export function edgeAsPp(n: number): number {
  return Math.abs(n) <= 1.5 ? n * 100 : n
}

/** SQL-фрагмент: кф и edge (edge в пунктах, как на экране). */
export function sqlOddsEdgeFilters(
  q: Record<string, unknown>,
): { clauses: string[]; params: unknown[] } {
  const clauses: string[] = []
  const params: unknown[] = []
  const oddsMin = parseQueryNumber(q.odds_min)
  const oddsMax = parseQueryNumber(q.odds_max)
  const edgeMin = parseQueryNumber(q.edge_min)
  const edgeMax = parseQueryNumber(q.edge_max)
  const edgeRaw =
    "CAST(COALESCE(json_extract(sp.notes, '$.difference'), json_extract(sp.notes, '$.edge')) AS REAL)"
  // как на экране: доля 0.05 → 5 pp, уже пункты (>1.5) оставляем как есть
  const edgePp = `(CASE WHEN ABS(${edgeRaw}) <= 1.5 THEN (${edgeRaw}) * 100.0 ELSE ${edgeRaw} END)`
  if (oddsMin != null) {
    clauses.push('sp.odds IS NOT NULL AND sp.odds >= ?')
    params.push(oddsMin)
  }
  if (oddsMax != null) {
    clauses.push('sp.odds IS NOT NULL AND sp.odds <= ?')
    params.push(oddsMax)
  }
  if (edgeMin != null) {
    clauses.push(`${edgeRaw} IS NOT NULL AND ${edgePp} >= ?`)
    params.push(edgeMin)
  }
  if (edgeMax != null) {
    clauses.push(`${edgeRaw} IS NOT NULL AND ${edgePp} <= ?`)
    params.push(edgeMax)
  }
  return { clauses, params }
}
