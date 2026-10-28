<script setup lang="ts">
import type {
  MatchDetail,
  MatchWeather,
  SnapshotHistoryMatch,
  SnapshotTableRow,
  WsLineupPlayer,
  WsMissingPlayer,
} from '~/types/db'
import { sportLabel, eloTier } from '~/types/db'

const route = useRoute()
const { dbQuery } = useAdminDb()
const matchId = computed(() => String(route.params.id))

const { data, pending, error, refresh } = await useFetch<MatchDetail>(
  () => `/api/matches/${matchId.value}`,
  { query: dbQuery, watch: [matchId, dbQuery] },
)

const m = computed(() => data.value?.match)
const snap = computed(() => data.value?.snapshot || null)
const weather = computed(() => data.value?.weather || null)
const ws = computed(() => data.value?.whoscored || null)
const matchStats = computed(() => data.value?.matchStats || null)

// ELO delta for this match
const { data: eloDelta, pending: eloPending } = await useFetch<{
  elo_before: { home: number; away: number }
  elo_after: { home: number; away: number }
  delta: { home: number; away: number }
  home_team: string
  away_team: string
  score_home: number | null
  score_away: number | null
}>(`/api/elo/${matchId.value}`, {
  query: { ...dbQuery.value },
  watch: [matchId, dbQuery],
})

// Glicko-2 рейтинги команд матча
interface Glicko2Rating {
  side: 'home' | 'away'
  team_id: number
  rating: number
  rd: number
  volatility: number
  matches_played: number
  wins: number
  draws: number
  losses: number
  last_updated: string | null
}
const { data: glicko2Data, pending: glicko2Pending } = await useFetch<{
  home_team: string
  away_team: string
  score_home: number | null
  score_away: number | null
  home: Glicko2Rating | null
  away: Glicko2Rating | null
}>(`/api/glicko2/${matchId.value}`, {
  query: { ...dbQuery.value },
  watch: [matchId, dbQuery],
})

// OpenSkill рейтинги команд матча
interface OpenSkillRating {
  side: 'home' | 'away'
  team_id: number
  mu: number
  sigma: number
  rating: number
  matches_played: number
  wins: number
  draws: number
  losses: number
  last_updated: string | null
}
const { data: openskillData, pending: openskillPending } = await useFetch<{
  home_team: string
  away_team: string
  score_home: number | null
  score_away: number | null
  home: OpenSkillRating | null
  away: OpenSkillRating | null
}>(`/api/openskill/${matchId.value}`, {
  query: { ...dbQuery.value },
  watch: [matchId, dbQuery],
})

// Форма команд (последние 5 матчей)
const { data: formResponse } = await useFetch<{
  home_team: string
  away_team: string
  home_form: Record<string, any> | null
  away_form: Record<string, any> | null
}>(`/api/matches/${matchId.value}/form`, {
  query: { ...dbQuery.value },
  watch: [matchId, dbQuery],
})

const homeForm = computed(() => formResponse.value?.home_form || null)
const awayForm = computed(() => formResponse.value?.away_form || null)

function fmtCount(v: unknown) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  return Number.isNaN(n) ? String(v) : n.toLocaleString('ru-RU')
}

function fmtWeatherNumber(v: unknown, suffix: string) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  return `${Number.isNaN(n) ? String(v) : n.toFixed(1)} ${suffix}`
}

function weatherText(code: unknown) {
  const n = Number(code)
  if (n === 0) return 'Ясно'
  if ([1, 2, 3].includes(n)) return 'Облачно'
  if ([45, 48].includes(n)) return 'Туман'
  if ([51, 53, 55, 56, 57].includes(n)) return 'Морось'
  if ([61, 63, 65, 66, 67, 80, 81, 82].includes(n)) return 'Дождь'
  if ([71, 73, 75, 77, 85, 86].includes(n)) return 'Снег'
  if ([95, 96, 99].includes(n)) return 'Гроза'
  return code == null ? '—' : `Код ${code}`
}

function weatherTitle(item: MatchWeather | null, fallback: string) {
  if (!item) return fallback
  if (item.kind === 'actual') return 'Факт'
  return item.lead_hours == null ? fallback : `${fallback} (за ${item.lead_hours} ч)`
}

const refereeLabel = computed(() => {
  const s = snap.value
  if (!s?.referee) return '—'
  return s.referee_country ? `${s.referee} (${s.referee_country})` : s.referee
})

const weatherCards = computed(() => {
  const snapshot = weather.value?.snapshot || null
  const latest = weather.value?.latest || null
  const cards: { key: string; title: string; item: MatchWeather }[] = []
  if (snapshot) {
    cards.push({ key: 'snapshot', title: weatherTitle(snapshot, 'На момент анализа'), item: snapshot })
  }
  if (latest && latest.fetched_at !== snapshot?.fetched_at) {
    cards.push({ key: 'latest', title: weatherTitle(latest, 'Последний прогноз'), item: latest })
  }
  if (weather.value?.actual) {
    cards.push({ key: 'actual', title: 'Факт', item: weather.value.actual })
  }
  return cards
})

type SnapSide = 'overall' | 'home' | 'away'

const snapTableHeaders = [
  { title: '#', key: 'rank', width: '56px' },
  { title: 'Команда', key: 'team' },
  { title: 'И', key: 'played' },
  { title: 'В', key: 'wins' },
  { title: 'Н', key: 'draws' },
  { title: 'П', key: 'losses' },
  { title: 'ЗМ', key: 'scored' },
  { title: 'ПМ', key: 'conceded' },
  { title: 'О', key: 'points' },
]

const historyHeaders = [
  { title: 'Дата', key: 'date' },
  { title: 'Турнир', key: 'tour_name' },
  { title: 'Матч', key: 'teams' },
  { title: 'Счёт', key: 'score' },
]

const standingsSide = ref<SnapSide>('overall')
const formSide = ref<SnapSide>('overall')
const matchesTeam = ref<'home' | 'away'>('home')
const matchesSide = ref<SnapSide>('overall')

const sideItems = [
  { title: 'Общая', value: 'overall' },
  { title: 'Дома', value: 'home' },
  { title: 'В гостях', value: 'away' },
]

const standingsRows = computed<SnapshotTableRow[]>(
  () => snap.value?.standings?.[standingsSide.value] || [],
)
const formRows = computed<SnapshotTableRow[]>(() => snap.value?.form?.[formSide.value] || [])
const h2hRows = computed<SnapshotHistoryMatch[]>(() => snap.value?.h2h?.all || [])
const teamMatchRows = computed<SnapshotHistoryMatch[]>(
  () => {
    if (!snap.value?.team_matches) return []
    const teamData = snap.value.team_matches[matchesTeam.value]
    if (!teamData) return []
    // JSON uses 'all' key, UI uses 'overall'
    const sideKey = matchesSide.value === 'overall' ? 'all' : matchesSide.value
    return teamData[sideKey as keyof typeof teamData] || []
  },
)

const hasSnapshotData = computed(() =>
  Boolean(
    snap.value &&
      (snap.value.standings || snap.value.form || snap.value.h2h || snap.value.team_matches),
  ),
)

function historyScore(g: SnapshotHistoryMatch) {
  if (g.home_ht == null || g.away_ht == null) return '—'
  return `${g.home_ht}:${g.away_ht}`
}

function fmtRating(v: unknown) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  return Number.isNaN(n) ? String(v) : n.toFixed(2)
}

function missingRows(side: 'home' | 'away'): WsMissingPlayer[] {
  return ws.value?.missing?.[side] || []
}

function newsItems(side: 'home' | 'away'): string[] {
  return ws.value?.team_news?.[side] || []
}

function lineupPlayers(side: 'home' | 'away'): WsLineupPlayer[] {
  return ws.value?.lineups?.[side]?.players || []
}

const predHeaders = [
  { title: 'Стратегия', key: 'strategy_name' },
  { title: 'ID', key: 'strategy_id' },
  { title: 'Прогноз', key: 'prediction' },
  { title: 'Кф', key: 'odds' },
  { title: 'Edge', key: 'edge' },
  { title: 'Ставка', key: 'stake' },
  { title: 'Результат', key: 'result' },
  { title: 'Профит', key: 'profit' },
]

function fmtEdge(v: unknown) {
  const n = Number(v)
  if (v == null || v === '' || Number.isNaN(n)) return '—'
  const pp = Math.abs(n) <= 1.5 ? n * 100 : n
  const sign = pp > 0 ? '+' : ''
  return `${sign}${pp.toFixed(1)} pp`
}

function edgeClass(v: unknown) {
  const n = Number(v)
  if (v == null || v === '' || Number.isNaN(n)) return ''
  if (n > 0) return 'text-success'
  if (n < 0) return 'text-error'
  return ''
}

const outcomeHeaders = [
  { title: 'Стратегия', key: 'strategy_name' },
  { title: 'ID', key: 'strategy_id' },
  { title: 'П1 %', key: 'home_win_prob' },
  { title: 'X %', key: 'draw_prob' },
  { title: 'П2 %', key: 'away_win_prob' },
]

const oddsHeaders = [
  { title: 'Рынок', key: 'market_name' },
  { title: 'Исход', key: 'outcome' },
  { title: 'Сторона', key: 'side' },
  { title: 'Линия', key: 'line_value' },
  { title: 'Кф', key: 'odds_value' },
]

const goalRows = computed(() => {
  const g = data.value?.goals
  if (!g) return []
  return Array.from({ length: 13 }, (_, n) => ({
    goals: n === 12 ? '12+' : n,
    home: g[`home_goals_${n}` as keyof typeof g],
    away: g[`away_goals_${n}` as keyof typeof g],
  }))
})

// Словарь для перевода названий статистики
const STAT_LABELS: Record<string, string> = {
  'Главное_Удары': 'Удары',
  'Главное_Удары в створ': 'Удары в створ',
  'Главное_Владение мячом': 'Владение %',
  'Главное_Угловые': 'Угловые',
  'Главное_Офсайды': 'Офсайды',
  'Главное_Желтые карточки': 'ЖК',
  'Главное_Красные карточки': 'КК',
  'Главное_Нанесенные удары': 'Всего ударов',
  'Главное_Атаки': 'Атаки',
  'Главное_Опасные атаки': 'Опасные атаки',
}

function getStatLabel(key: string): string {
  return STAT_LABELS[key] || key
}

// Фильтруем только релевантные статистические показатели
function getRelevantStats(averages: Record<string, number>): Record<string, number> {
  const relevantKeys = [
    'Главное_Удары в створ',
    'Главное_Владение мячом',
    'Главное_Угловые',
    'Главное_Желтые карточки',
    'Главное_Удары',
    'Главное_Опасные атаки',
  ]
  const result: Record<string, number> = {}
  for (const key of relevantKeys) {
    if (averages[key] !== undefined) {
      result[key] = averages[key]
    }
  }
  return result
}

function hasMatchStats(matches: any[] | undefined): boolean {
  if (!matches || matches.length === 0) return false
  return matches.some((m: any) => m.stats && Object.keys(m.stats).length > 0)
}
</script>

<template>
  <div class="d-flex flex-column ga-4">
    <div class="d-flex align-center justify-space-between">
      <div class="d-flex align-center ga-3">
        <v-btn variant="text" prepend-icon="mdi-arrow-left" to="/matches">К списку</v-btn>
        <div>
          <div class="text-h5 font-weight-bold">{{ matchId }}</div>
          <div v-if="m" class="text-body-2 text-medium-emphasis">
            {{ m.home_team || '—' }} — {{ m.away_team || '—' }}
          </div>
        </div>
      </div>
      <v-btn variant="outlined" :loading="pending" @click="refresh()">Обновить</v-btn>
    </div>

    <v-alert v-if="error" type="error" density="compact">{{ error.message || error }}</v-alert>

    <v-card v-if="m">
      <v-card-title>Карточка матча</v-card-title>
      <v-divider />
      <v-card-text>
        <v-row dense>
          <v-col cols="12" md="3"><strong>Дата:</strong> {{ m.match_date }}</v-col>
          <v-col cols="12" md="3">
            <strong>Лига:</strong>
            {{ [m.country_name, m.league_name].filter(Boolean).join(': ') || '—' }}
          </v-col>
          <v-col cols="12" md="3"><strong>Статус:</strong> {{ m.match_status }}</v-col>
          <v-col cols="12" md="3"><strong>Счёт:</strong> {{ m.score_home }} : {{ m.score_away }}</v-col>
          <v-col cols="12" md="3"><strong>Минута:</strong> {{ m.minute }}</v-col>
          <v-col cols="12" md="3"><strong>Прогноз:</strong> {{ m.prediction || '—' }}</v-col>
          <v-col cols="12" md="3"><strong>Профит:</strong> {{ m.profit }}</v-col>
          <v-col cols="12" md="3"><strong>Спорт:</strong> {{ sportLabel(m.sport as number) }}</v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <v-card v-if="snap">
      <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-2">
        <span>Данные на момент анализа</span>
        <span class="text-caption text-medium-emphasis">{{ snap.fetched_at || '' }}</span>
      </v-card-title>
      <v-divider />
      <v-card-text>
        <v-row dense>
          <v-col cols="12" md="3"><strong>Стадион:</strong> {{ snap.venue || '—' }}</v-col>
          <v-col cols="12" md="3"><strong>Город:</strong> {{ snap.town || '—' }}</v-col>
          <v-col cols="12" md="3"><strong>Судья:</strong> {{ refereeLabel }}</v-col>
          <v-col cols="12" md="3">
            <strong>Вместимость:</strong> {{ fmtCount(snap.capacity) }}
          </v-col>
          <v-col cols="12" md="3">
            <strong>Зрителей:</strong> {{ fmtCount(snap.attendance) }}
          </v-col>
          <v-col cols="12" md="3">
            <strong>Расстояние:</strong>
            {{ snap.distance != null ? `${snap.distance} км` : '—' }}
          </v-col>
        </v-row>

        <!-- ELO Rating -->
        <div v-if="eloDelta" class="mt-4">
          <div class="text-subtitle-2 mb-2">ELO Рейтинг</div>
          <v-row dense>
            <v-col cols="12" md="4">
              <v-card variant="tonal">
                <v-card-text class="pa-3">
                  <div class="d-flex align-center justify-space-between">
                    <span class="text-body-2 font-weight-medium">{{ eloDelta.home_team }}</span>
                    <v-chip size="x-small" :color="eloTier(eloDelta.elo_before.home).color" variant="tonal">
                      {{ eloTier(eloDelta.elo_before.home).label }}
                    </v-chip>
                  </div>
                  <div class="d-flex align-center ga-2 mt-1">
                    <span class="text-h6">{{ Math.round(eloDelta.elo_before.home) }}</span>
                    <v-icon size="small" :color="eloDelta.delta.home >= 0 ? 'success' : 'error'">
                      {{ eloDelta.delta.home >= 0 ? 'mdi-arrow-up-thin' : 'mdi-arrow-down-thin' }}
                    </v-icon>
                    <span class="text-body-2" :class="eloDelta.delta.home >= 0 ? 'text-success' : 'text-error'">
                      {{ eloDelta.delta.home >= 0 ? '+' : '' }}{{ Math.round(eloDelta.delta.home) }}
                    </span>
                  </div>
                  <div class="text-caption text-medium-emphasis">→ {{ Math.round(eloDelta.elo_after.home) }}</div>
                </v-card-text>
              </v-card>
            </v-col>
            <v-col cols="12" md="4">
              <v-card variant="tonal">
                <v-card-text class="pa-3">
                  <div class="d-flex align-center justify-space-between">
                    <span class="text-body-2 font-weight-medium">{{ eloDelta.away_team }}</span>
                    <v-chip size="x-small" :color="eloTier(eloDelta.elo_before.away).color" variant="tonal">
                      {{ eloTier(eloDelta.elo_before.away).label }}
                    </v-chip>
                  </div>
                  <div class="d-flex align-center ga-2 mt-1">
                    <span class="text-h6">{{ Math.round(eloDelta.elo_before.away) }}</span>
                    <v-icon size="small" :color="eloDelta.delta.away >= 0 ? 'success' : 'error'">
                      {{ eloDelta.delta.away >= 0 ? 'mdi-arrow-up-thin' : 'mdi-arrow-down-thin' }}
                    </v-icon>
                    <span class="text-body-2" :class="eloDelta.delta.away >= 0 ? 'text-success' : 'text-error'">
                      {{ eloDelta.delta.away >= 0 ? '+' : '' }}{{ Math.round(eloDelta.delta.away) }}
                    </span>
                  </div>
                  <div class="text-caption text-medium-emphasis">→ {{ Math.round(eloDelta.elo_after.away) }}</div>
                </v-card-text>
              </v-card>
            </v-col>
            <v-col cols="12" md="4">
              <v-card variant="tonal">
                <v-card-text class="pa-3 text-center">
                  <div class="text-caption text-medium-emphasis">Счёт</div>
                  <div class="text-h5 font-weight-bold">{{ eloDelta.score_home ?? '—' }} : {{ eloDelta.score_away ?? '—' }}</div>
                  <div class="text-caption text-medium-emphasis mt-1">ELO-дельта: {{ eloDelta.delta.home >= 0 ? '+' : '' }}{{ Math.round(eloDelta.delta.home) }} / {{ eloDelta.delta.away >= 0 ? '+' : '' }}{{ Math.round(eloDelta.delta.away) }}</div>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </div>
        <div v-else-if="!eloPending && m" class="mt-4">
          <div class="text-subtitle-2 mb-2">ELO Рейтинг</div>
          <div class="text-caption text-medium-emphasis">Нет данных ELO (матч ещё не обработан)</div>
        </div>

        <!-- Glicko-2 Rating -->
        <div v-if="glicko2Data && (glicko2Data.home || glicko2Data.away)" class="mt-4">
          <div class="d-flex align-center justify-space-between mb-2">
            <div class="text-subtitle-2">Glicko-2 Рейтинг</div>
            <v-chip v-if="glicko2Data.home" size="x-small" variant="tonal" color="info">
              {{ glicko2Data.home.matches_played }} матчей
            </v-chip>
          </div>
          <v-row dense>
            <v-col cols="12" md="4">
              <v-card variant="tonal">
                <v-card-text class="pa-3">
                  <div class="d-flex align-center justify-space-between">
                    <span class="text-body-2 font-weight-medium">{{ glicko2Data.home_team }}</span>
                  </div>
                  <div class="d-flex align-center ga-2 mt-1">
                    <span class="text-h6">{{ glicko2Data.home ? glicko2Data.home.rating.toFixed(1) : '—' }}</span>
                    <span class="text-caption text-medium-emphasis">
                      RD {{ glicko2Data.home ? glicko2Data.home.rd.toFixed(1) : '—' }}
                    </span>
                  </div>
                  <div class="text-caption text-medium-emphasis">
                    {{ glicko2Data.home?.wins || 0 }}В / {{ glicko2Data.home?.draws || 0 }}Н / {{ glicko2Data.home?.losses || 0 }}П
                  </div>
                </v-card-text>
              </v-card>
            </v-col>
            <v-col cols="12" md="4">
              <v-card variant="tonal">
                <v-card-text class="pa-3">
                  <div class="d-flex align-center justify-space-between">
                    <span class="text-body-2 font-weight-medium">{{ glicko2Data.away_team }}</span>
                  </div>
                  <div class="d-flex align-center ga-2 mt-1">
                    <span class="text-h6">{{ glicko2Data.away ? glicko2Data.away.rating.toFixed(1) : '—' }}</span>
                    <span class="text-caption text-medium-emphasis">
                      RD {{ glicko2Data.away ? glicko2Data.away.rd.toFixed(1) : '—' }}
                    </span>
                  </div>
                  <div class="text-caption text-medium-emphasis">
                    {{ glicko2Data.away?.wins || 0 }}В / {{ glicko2Data.away?.draws || 0 }}Н / {{ glicko2Data.away?.losses || 0 }}П
                  </div>
                </v-card-text>
              </v-card>
            </v-col>
            <v-col cols="12" md="4">
              <v-card variant="tonal">
                <v-card-text class="pa-3 text-center">
                  <div class="text-caption text-medium-emphasis">Счёт</div>
                  <div class="text-h5 font-weight-bold">{{ glicko2Data.score_home ?? '—' }} : {{ glicko2Data.score_away ?? '—' }}</div>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </div>
        <div v-else-if="!glicko2Pending && m" class="mt-4">
          <div class="text-subtitle-2 mb-2">Glicko-2 Рейтинг</div>
          <div class="text-caption text-medium-emphasis">Нет данных Glicko-2 (матч ещё не обработан)</div>
        </div>

        <!-- OpenSkill Rating -->
        <div v-if="openskillData && (openskillData.home || openskillData.away)" class="mt-4">
          <div class="d-flex align-center justify-space-between mb-2">
            <div class="text-subtitle-2">OpenSkill Рейтинг</div>
            <v-chip v-if="openskillData.home" size="x-small" variant="tonal" color="secondary">
              {{ openskillData.home.matches_played }} матчей
            </v-chip>
          </div>
          <v-row dense>
            <v-col cols="12" md="4">
              <v-card variant="tonal">
                <v-card-text class="pa-3">
                  <div class="text-body-2 font-weight-medium">{{ openskillData.home_team }}</div>
                  <div class="d-flex align-center ga-2 mt-1">
                    <span class="text-h6">{{ openskillData.home ? openskillData.home.rating.toFixed(1) : '—' }}</span>
                    <span class="text-caption text-medium-emphasis">μ {{ openskillData.home ? openskillData.home.mu.toFixed(1) : '—' }}</span>
                  </div>
                  <div class="text-caption text-medium-emphasis">
                    {{ openskillData.home?.wins || 0 }}В / {{ openskillData.home?.draws || 0 }}Н / {{ openskillData.home?.losses || 0 }}П
                  </div>
                </v-card-text>
              </v-card>
            </v-col>
            <v-col cols="12" md="4">
              <v-card variant="tonal">
                <v-card-text class="pa-3">
                  <div class="text-body-2 font-weight-medium">{{ openskillData.away_team }}</div>
                  <div class="d-flex align-center ga-2 mt-1">
                    <span class="text-h6">{{ openskillData.away ? openskillData.away.rating.toFixed(1) : '—' }}</span>
                    <span class="text-caption text-medium-emphasis">μ {{ openskillData.away ? openskillData.away.mu.toFixed(1) : '—' }}</span>
                  </div>
                  <div class="text-caption text-medium-emphasis">
                    {{ openskillData.away?.wins || 0 }}В / {{ openskillData.away?.draws || 0 }}Н / {{ openskillData.away?.losses || 0 }}П
                  </div>
                </v-card-text>
              </v-card>
            </v-col>
            <v-col cols="12" md="4">
              <v-card variant="tonal">
                <v-card-text class="pa-3 text-center">
                  <div class="text-caption text-medium-emphasis">Счёт</div>
                  <div class="text-h5 font-weight-bold">{{ openskillData.score_home ?? '—' }} : {{ openskillData.score_away ?? '—' }}</div>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </div>
        <div v-else-if="!openskillPending && m" class="mt-4">
          <div class="text-subtitle-2 mb-2">OpenSkill Рейтинг</div>
          <div class="text-caption text-medium-emphasis">Нет данных OpenSkill (матч ещё не обработан)</div>
        </div>

        <div v-if="weatherCards.length" class="text-subtitle-2 mt-4 mb-2">Погода</div>
        <v-row v-if="weatherCards.length" dense>
          <v-col v-for="card in weatherCards" :key="card.key" cols="12" md="4">
            <v-card variant="tonal">
              <v-card-title class="text-subtitle-2">{{ card.title }}</v-card-title>
              <v-card-text>
                <div class="text-h6 mb-1">
                  {{ fmtWeatherNumber(card.item.temperature_c, '°C') }}
                  · {{ weatherText(card.item.weather_code) }}
                </div>
                <div>Ощущается: {{ fmtWeatherNumber(card.item.apparent_temperature_c, '°C') }}</div>
                <div>
                  Ветер: {{ fmtWeatherNumber(card.item.wind_ms, 'м/с') }},
                  порывы {{ fmtWeatherNumber(card.item.gust_ms, 'м/с') }}
                </div>
                <div>
                  Осадки: {{ fmtWeatherNumber(card.item.precipitation_mm, 'мм') }}
                  ({{ fmtCount(card.item.precipitation_probability) }}%)
                </div>
                <div>
                  Влажность: {{ fmtCount(card.item.humidity_pct) }}%,
                  облачность {{ fmtCount(card.item.cloud_pct) }}%
                </div>
                <div class="text-caption text-medium-emphasis mt-1">
                  На {{ card.item.valid_at || card.item.weather_at || '—' }} · получено {{ card.item.fetched_at || '—' }}
                </div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <template v-if="hasSnapshotData">
          <v-row dense class="mt-2">
            <v-col cols="12" md="6">
              <div class="d-flex align-center justify-space-between ga-2 mb-1">
                <div class="text-subtitle-2">Таблица</div>
                <v-btn-toggle
                  v-model="standingsSide"
                  density="compact"
                  variant="outlined"
                  mandatory
                >
                  <v-btn v-for="s in sideItems" :key="s.value" :value="s.value" size="small">
                    {{ s.title }}
                  </v-btn>
                </v-btn-toggle>
              </div>
              <v-data-table
                :headers="snapTableHeaders"
                :items="standingsRows"
                :items-per-page="-1"
                density="compact"
                hide-default-footer
              />
              <div v-if="!standingsRows.length" class="text-medium-emphasis">Нет данных</div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="d-flex align-center justify-space-between ga-2 mb-1">
                <div class="text-subtitle-2">Форма</div>
                <v-btn-toggle v-model="formSide" density="compact" variant="outlined" mandatory>
                  <v-btn v-for="s in sideItems" :key="s.value" :value="s.value" size="small">
                    {{ s.title }}
                  </v-btn>
                </v-btn-toggle>
              </div>
              <v-data-table
                :headers="snapTableHeaders"
                :items="formRows"
                :items-per-page="-1"
                density="compact"
                hide-default-footer
              />
              <div v-if="!formRows.length" class="text-medium-emphasis">Нет данных</div>
            </v-col>
          </v-row>

          <v-row dense class="mt-2">
            <v-col cols="12" md="6">
              <div class="text-subtitle-2 mb-1">Личные встречи</div>
              <v-data-table
                :headers="historyHeaders"
                :items="h2hRows"
                :items-per-page="-1"
                density="compact"
                hide-default-footer
              >
                <template #item.teams="{ item }">
                  {{ item.home_name }} — {{ item.away_name }}
                </template>
                <template #item.score="{ item }">{{ historyScore(item) }}</template>
              </v-data-table>
              <div v-if="!h2hRows.length" class="text-medium-emphasis">Нет данных</div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="d-flex align-center justify-space-between ga-2 mb-1 flex-wrap">
                <div class="text-subtitle-2">Матчи команды</div>
                <div class="d-flex align-center ga-2">
                  <v-btn-toggle
                    v-model="matchesTeam"
                    density="compact"
                    variant="outlined"
                    mandatory
                  >
                    <v-btn value="home" size="small">{{ m?.home_team || 'Дома' }}</v-btn>
                    <v-btn value="away" size="small">{{ m?.away_team || 'Гости' }}</v-btn>
                  </v-btn-toggle>
                  <v-btn-toggle
                    v-model="matchesSide"
                    density="compact"
                    variant="outlined"
                    mandatory
                  >
                    <v-btn v-for="s in sideItems" :key="s.value" :value="s.value" size="small">
                      {{ s.title }}
                    </v-btn>
                  </v-btn-toggle>
                </div>
              </div>
              <v-data-table
                :headers="historyHeaders"
                :items="teamMatchRows"
                :items-per-page="-1"
                density="compact"
                hide-default-footer
              >
                <template #item.teams="{ item }">
                  {{ item.home_name }} — {{ item.away_name }}
                </template>
                <template #item.score="{ item }">{{ historyScore(item) }}</template>
              </v-data-table>
              <div v-if="!teamMatchRows.length" class="text-medium-emphasis">Нет данных</div>
            </v-col>
          </v-row>
        </template>
      </v-card-text>
    </v-card>

    <v-card v-if="ws">
      <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-2">
        <span>WhoScored</span>
        <a
          v-if="ws.ws_url"
          :href="String(ws.ws_url)"
          target="_blank"
          rel="noopener noreferrer"
          class="text-body-2"
        >preview</a>
      </v-card-title>
      <v-divider />
      <v-card-text>
        <v-row dense class="mb-4">
          <v-col cols="12" md="4">
            <strong>Прогноз счёта:</strong>
            {{ ws.score_home ?? '—' }} : {{ ws.score_away ?? '—' }}
          </v-col>
          <v-col cols="12" md="4">
            <strong>Схема дома:</strong>
            {{ ws.formation_home || ws.lineups?.home?.formation || '—' }}
          </v-col>
          <v-col cols="12" md="4">
            <strong>Схема гостей:</strong>
            {{ ws.formation_away || ws.lineups?.away?.formation || '—' }}
          </v-col>
        </v-row>

        <div class="text-subtitle-2 mb-2">Составы</div>
        <v-row dense>
          <v-col cols="12" md="6">
            <div class="text-body-2 font-weight-medium mb-1">
              {{ ws.home_name || m?.home_team || 'Дома' }}
            </div>
            <v-table density="compact">
              <thead>
                <tr>
                  <th>Игрок</th>
                  <th>Поз.</th>
                  <th>Рейтинг</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in lineupPlayers('home')" :key="`h-${p.player_id}-${p.name}`">
                  <td>{{ p.name || p.full_name }}</td>
                  <td>{{ p.position || '—' }}</td>
                  <td>{{ fmtRating(p.rating) }}</td>
                </tr>
                <tr v-if="!lineupPlayers('home').length">
                  <td colspan="3" class="text-medium-emphasis">Нет состава</td>
                </tr>
              </tbody>
            </v-table>
          </v-col>
          <v-col cols="12" md="6">
            <div class="text-body-2 font-weight-medium mb-1">
              {{ ws.away_name || m?.away_team || 'Гости' }}
            </div>
            <v-table density="compact">
              <thead>
                <tr>
                  <th>Игрок</th>
                  <th>Поз.</th>
                  <th>Рейтинг</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in lineupPlayers('away')" :key="`a-${p.player_id}-${p.name}`">
                  <td>{{ p.name || p.full_name }}</td>
                  <td>{{ p.position || '—' }}</td>
                  <td>{{ fmtRating(p.rating) }}</td>
                </tr>
                <tr v-if="!lineupPlayers('away').length">
                  <td colspan="3" class="text-medium-emphasis">Нет состава</td>
                </tr>
              </tbody>
            </v-table>
          </v-col>
        </v-row>

        <div class="text-subtitle-2 mt-4 mb-2">Пропуски</div>
        <v-row dense>
          <v-col cols="12" md="6">
            <v-table density="compact">
              <thead>
                <tr>
                  <th>Игрок</th>
                  <th>Причина</th>
                  <th>Статус</th>
                  <th>Рейтинг</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in missingRows('home')" :key="`mh-${p.player_id}`">
                  <td>{{ p.name }}</td>
                  <td>{{ p.reason || '—' }}</td>
                  <td>{{ p.status || '—' }}</td>
                  <td>{{ fmtRating(p.rating) }}</td>
                </tr>
                <tr v-if="!missingRows('home').length">
                  <td colspan="4" class="text-medium-emphasis">Нет данных</td>
                </tr>
              </tbody>
            </v-table>
          </v-col>
          <v-col cols="12" md="6">
            <v-table density="compact">
              <thead>
                <tr>
                  <th>Игрок</th>
                  <th>Причина</th>
                  <th>Статус</th>
                  <th>Рейтинг</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in missingRows('away')" :key="`ma-${p.player_id}`">
                  <td>{{ p.name }}</td>
                  <td>{{ p.reason || '—' }}</td>
                  <td>{{ p.status || '—' }}</td>
                  <td>{{ fmtRating(p.rating) }}</td>
                </tr>
                <tr v-if="!missingRows('away').length">
                  <td colspan="4" class="text-medium-emphasis">Нет данных</td>
                </tr>
              </tbody>
            </v-table>
          </v-col>
        </v-row>

        <div class="text-subtitle-2 mt-4 mb-2">Team news</div>
        <v-row dense>
          <v-col cols="12" md="6">
            <ul class="pl-4">
              <li v-for="(item, i) in newsItems('home')" :key="`nh-${i}`">{{ item }}</li>
            </ul>
            <div v-if="!newsItems('home').length" class="text-medium-emphasis">Нет новостей</div>
          </v-col>
          <v-col cols="12" md="6">
            <ul class="pl-4">
              <li v-for="(item, i) in newsItems('away')" :key="`na-${i}`">{{ item }}</li>
            </ul>
            <div v-if="!newsItems('away').length" class="text-medium-emphasis">Нет новостей</div>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <v-card v-if="matchStats">
      <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-2">
        <span>Статистика матча</span>
        <v-chip size="small" color="info" variant="tonal">
          {{ matchStats.fetched_at || '' }}
        </v-chip>
      </v-card-title>
      <v-divider />
      <v-card-text>
        <v-table density="compact">
          <thead>
            <tr>
              <th>Показатель</th>
              <th class="text-center">{{ m?.home_team || 'Дома' }}</th>
              <th class="text-center">{{ m?.away_team || 'Гости' }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="(stat, key) in matchStats" :key="key">
              <tr v-if="key !== 'fetched_at'">
                <td>{{ key }}</td>
                <td class="text-center font-weight-medium">{{ stat.home }}</td>
                <td class="text-center font-weight-medium">{{ stat.away }}</td>
              </tr>
            </template>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>

    <v-card v-else>
      <v-card-title>Статистика матча</v-card-title>
      <v-divider />
      <v-card-text class="text-medium-emphasis">Нет данных</v-card-text>
    </v-card>

    <!-- Форма команд (последние 5 матчей) -->
    <v-row dense>
      <v-col cols="12" md="6">
        <v-card v-if="homeForm">
          <v-card-title class="d-flex align-center justify-space-between">
            <span>Форма {{ m?.home_team || 'Хозяева' }}</span>
            <v-chip size="small" color="success" variant="tonal">
              {{ homeForm.results?.wins || 0 }}W / {{ homeForm.results?.draws || 0 }}D / {{ homeForm.results?.losses || 0 }}L
            </v-chip>
          </v-card-title>
          <v-divider />
          <v-card-text>
            <v-row dense class="mb-3">
              <v-col cols="4">
                <div class="text-caption text-medium-emphasis">Голы забито</div>
                <div class="text-h6">{{ homeForm.goals?.scored?.toFixed(1) || '—' }}</div>
              </v-col>
              <v-col cols="4">
                <div class="text-caption text-medium-emphasis">Голы пропущено</div>
                <div class="text-h6">{{ homeForm.goals?.conceded?.toFixed(1) || '—' }}</div>
              </v-col>
              <v-col cols="4">
                <div class="text-caption text-medium-emphasis">Винрейт</div>
                <div class="text-h6">{{ ((homeForm.results?.win_rate || 0) * 100).toFixed(0) }}%</div>
              </v-col>
            </v-row>

            <!-- Статистические показатели -->
            <div v-if="homeForm.averages && Object.keys(homeForm.averages).length > 0" class="mb-3">
              <div class="text-subtitle-2 mb-2">Средняя статистика</div>
              <v-row dense>
                <v-col cols="4" v-for="(stat, key) in getRelevantStats(homeForm.averages)" :key="key">
                  <div class="text-caption text-medium-emphasis">{{ getStatLabel(key) }}</div>
                  <div class="text-h6">{{ stat.toFixed(1) }}</div>
                </v-col>
              </v-row>
            </div>
            <div class="text-subtitle-2 mb-2">Последние матчи</div>
            <v-table density="compact">
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Турнир</th>
                  <th>Соперник</th>
                  <th>Счёт</th>
                  <th v-if="hasMatchStats(homeForm?.matches)">Статистика</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(match, i) in (homeForm.matches || []).slice(0, 5)" :key="i">
                  <td class="text-caption">{{ match.date }}</td>
                  <td class="text-caption">{{ match.tournament }}</td>
                  <td>{{ match.opponent }} ({{ match.venue }})</td>
                  <td class="text-center font-weight-medium">{{ match.score }}</td>
                  <td v-if="match.stats && Object.keys(match.stats).length > 0" class="text-caption">
                    <div v-for="(val, key) in getRelevantStats(match.stats)" :key="key">
                      {{ getStatLabel(key) }}: {{ val.toFixed(0) }}
                    </div>
                  </td>
                </tr>
              </tbody>
            </v-table>
            <div v-if="!homeForm.matches?.length" class="text-medium-emphasis text-caption">Нет данных</div>
          </v-card-text>
        </v-card>
        <v-card v-else>
          <v-card-title>Форма {{ m?.home_team || 'Хозяева' }}</v-card-title>
          <v-divider />
          <v-card-text class="text-medium-emphasis">Нет данных</v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card v-if="awayForm">
          <v-card-title class="d-flex align-center justify-space-between">
            <span>Форма {{ m?.away_team || 'Гости' }}</span>
            <v-chip size="small" color="success" variant="tonal">
              {{ awayForm.results?.wins || 0 }}W / {{ awayForm.results?.draws || 0 }}D / {{ awayForm.results?.losses || 0 }}L
            </v-chip>
          </v-card-title>
          <v-divider />
          <v-card-text>
            <v-row dense class="mb-3">
              <v-col cols="4">
                <div class="text-caption text-medium-emphasis">Голы забито</div>
                <div class="text-h6">{{ awayForm.goals?.scored?.toFixed(1) || '—' }}</div>
              </v-col>
              <v-col cols="4">
                <div class="text-caption text-medium-emphasis">Голы пропущено</div>
                <div class="text-h6">{{ awayForm.goals?.conceded?.toFixed(1) || '—' }}</div>
              </v-col>
              <v-col cols="4">
                <div class="text-caption text-medium-emphasis">Винрейт</div>
                <div class="text-h6">{{ ((awayForm.results?.win_rate || 0) * 100).toFixed(0) }}%</div>
              </v-col>
            </v-row>

            <!-- Статистические показатели -->
            <div v-if="awayForm.averages && Object.keys(awayForm.averages).length > 0" class="mb-3">
              <div class="text-subtitle-2 mb-2">Средняя статистика</div>
              <v-row dense>
                <v-col cols="4" v-for="(stat, key) in getRelevantStats(awayForm.averages)" :key="key">
                  <div class="text-caption text-medium-emphasis">{{ getStatLabel(key) }}</div>
                  <div class="text-h6">{{ stat.toFixed(1) }}</div>
                </v-col>
              </v-row>
            </div>
            <div class="text-subtitle-2 mb-2">Последние матчи</div>
            <v-table density="compact">
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Турнир</th>
                  <th>Соперник</th>
                  <th>Счёт</th>
                  <th v-if="hasMatchStats(awayForm?.matches)">Статистика</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(match, i) in (awayForm.matches || []).slice(0, 5)" :key="i">
                  <td class="text-caption">{{ match.date }}</td>
                  <td class="text-caption">{{ match.tournament }}</td>
                  <td>{{ match.opponent }} ({{ match.venue }})</td>
                  <td class="text-center font-weight-medium">{{ match.score }}</td>
                  <td v-if="match.stats && Object.keys(match.stats).length > 0" class="text-caption">
                    <div v-for="(val, key) in getRelevantStats(match.stats)" :key="key">
                      {{ getStatLabel(key) }}: {{ val.toFixed(0) }}
                    </div>
                  </td>
                </tr>
              </tbody>
            </v-table>
            <div v-if="!awayForm.matches?.length" class="text-medium-emphasis text-caption">Нет данных</div>
          </v-card-text>
        </v-card>
        <v-card v-else>
          <v-card-title>Форма {{ m?.away_team || 'Гости' }}</v-card-title>
          <v-divider />
          <v-card-text class="text-medium-emphasis">Нет данных</v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-card>
      <v-card-title>Прогнозы стратегий</v-card-title>
      <v-divider />
      <v-data-table
        :headers="predHeaders"
        :items="data?.predictions || []"
        :loading="pending"
        :items-per-page="-1"
        item-value="id"
        hide-default-footer
      >
        <template #item.edge="{ item }">
          <span :class="edgeClass(item.edge)">{{ fmtEdge(item.edge) }}</span>
        </template>
      </v-data-table>
    </v-card>

    <v-card>
      <v-card-title>Вероятности исходов (10 стратегий)</v-card-title>
      <v-divider />
      <v-data-table
        :headers="outcomeHeaders"
        :items="data?.outcomes || []"
        :loading="pending"
        item-value="id"
        hide-default-footer
      />
    </v-card>

    <v-row dense>
      <v-col cols="12" md="7">
        <v-card>
          <v-card-title>Коэффициенты</v-card-title>
          <v-divider />
          <v-data-table
            :headers="oddsHeaders"
            :items="data?.odds || []"
            :loading="pending"
            :items-per-page="-1"
            item-value="id"
            hide-default-footer
          />
        </v-card>
      </v-col>
      <v-col cols="12" md="5">
        <v-card>
          <v-card-title>Вероятности голов</v-card-title>
          <v-divider />
          <v-data-table
            :headers="[
              { title: 'Голы', key: 'goals' },
              { title: 'Дома %', key: 'home' },
              { title: 'Гости %', key: 'away' },
            ]"
            :items="goalRows"
            :items-per-page="-1"
            item-value="goals"
            hide-default-footer
          />
          <v-card-text v-if="!data?.goals" class="text-medium-emphasis">Нет данных</v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>
