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

export interface WsLineupPlayer {
  player_id?: string
  name?: string
  full_name?: string
  position?: string
  rating?: number | null
}

export interface WsMissingPlayer {
  player_id?: string
  name?: string
  reason?: string
  status?: string
  rating?: number | null
}

export interface WhoscoredPreview {
  match_id: string
  ws_id?: string | null
  ws_url?: string | null
  home_name?: string | null
  away_name?: string | null
  score_home?: number | null
  score_away?: number | null
  formation_home?: string | null
  formation_away?: string | null
  fetched_at?: string | null
  team_news: { home: string[]; away: string[] }
  missing: { home: WsMissingPlayer[]; away: WsMissingPlayer[] }
  lineups: {
    home: { formation?: string; players: WsLineupPlayer[] }
    away: { formation?: string; players: WsLineupPlayer[] }
  }
}

export interface SnapshotTableRow {
  rank?: string
  team?: string
  played?: string
  wins?: string
  draws?: string
  losses?: string
  scored?: string
  conceded?: string
  points?: string
}

export interface SnapshotHistoryMatch {
  tour_name?: string
  date?: string
  home_name?: string
  away_name?: string
  home_ht?: number
  away_ht?: number
  home_st?: number
  away_st?: number
  venue?: string
}

export type SnapshotSides<T> = { overall?: T[]; home?: T[]; away?: T[] }

export interface MatchWeather {
  id?: number
  match_id?: string
  kind?: 'forecast' | 'actual' | string
  valid_at?: string | null
  weather_at?: string | null
  fetched_at?: string | null
  lead_hours?: number | null
  temperature_c?: number | null
  apparent_temperature_c?: number | null
  wind_ms?: number | null
  gust_ms?: number | null
  precipitation_mm?: number | null
  precipitation_probability?: number | null
  snowfall_cm?: number | null
  cloud_pct?: number | null
  humidity_pct?: number | null
  weather_code?: number | null
  latitude?: number | null
  longitude?: number | null
  provider?: string | null
  venue?: string | null
  town?: string | null
  location_timezone?: string | null
  roof?: boolean | number | null
}

export interface MatchSnapshot {
  match_id: string
  referee?: string | null
  referee_country?: string | null
  referee_country_id?: string | null
  venue?: string | null
  town?: string | null
  capacity?: number | null
  attendance?: number | null
  raw_json?: string | null
  fetched_at?: string | null
  standings?: SnapshotSides<SnapshotTableRow> | null
  form?: SnapshotSides<SnapshotTableRow> | null
  h2h?: { all?: SnapshotHistoryMatch[]; home?: SnapshotHistoryMatch[] } | null
  team_matches?: {
    home?: SnapshotSides<SnapshotHistoryMatch>
    away?: SnapshotSides<SnapshotHistoryMatch>
  } | null
  weather?: MatchWeather | null
}

export interface MatchDetail {
  match: MatchRow & Record<string, unknown>
  odds: Record<string, unknown>[]
  predictions: Record<string, unknown>[]
  outcomes: Record<string, unknown>[]
  goals: Record<string, unknown> | null
  snapshot?: MatchSnapshot | null
  weather?: {
    snapshot: MatchWeather | null
    latest: MatchWeather | null
    actual: MatchWeather | null
    history: MatchWeather[]
  }
  whoscored?: WhoscoredPreview | null
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
