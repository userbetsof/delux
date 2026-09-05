export type DbName = 'matches' | 'parity_excel' | 'parity_python' | string

export interface StatsResponse {
  db: string
  path: string
  label: string
  available: string[]
  counts: Record<string, number>
  recent: MatchRow[]
}

export interface MatchRow {
  match_id: string
  match_date: string
  prediction?: string | null
  match_status?: string | null
  minute?: string | null
  segment?: string | null
  score_home?: number | null
  score_away?: number | null
  profit?: number | null
  sport?: number | null
  home_team?: string | null
  away_team?: string | null
  league_name?: string | null
  country_name?: string | null
}

export interface Paginated<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface MatchDetail {
  match: MatchRow & Record<string, unknown>
  odds: Record<string, unknown>[]
  predictions: Record<string, unknown>[]
  outcomes: Record<string, unknown>[]
  goals: Record<string, unknown> | null
}

export const SPORT_LABELS: Record<number, string> = {
  1: 'Футбол',
  3: 'Баскетбол',
  4: 'Хоккей',
  6: 'Бейсбол',
}

export function sportLabel(sport?: number | null): string {
  if (sport == null) return '—'
  return SPORT_LABELS[sport] || String(sport)
}
