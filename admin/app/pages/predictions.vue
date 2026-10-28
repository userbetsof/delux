<script setup lang="ts">
import type { Paginated } from '~/types/db'

type Summary = {
  total: number
  settled: number
  pending: number
  wins: number
  losses: number
  pushes: number
  unknown: number
  stake_sum: number
  profit: number
  roi: number
  stake_unit: number
  by_strategy: Array<{
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
    roi: number
  }>
}

const { dbQuery } = useAdminDb()
const matchId = ref('')
const strategyIds = ref<number[]>([])
const sports = ref<number[]>([])
const settledOnly = ref(false)
const stake = ref(1)
const oddsMin = ref<number | null>(null)
const oddsMax = ref<number | null>(null)
const edgeMin = ref<number | null>(null)
const edgeMax = ref<number | null>(null)
const dateFrom = ref<string | null>(null)
const dateTo = ref<string | null>(null)
const { limit, offset, nextPage, prevPage, resetOffset, setLimit } = useTablePagination(10)

function formatDate(d: Date | null): string | null {
  if (!d) return null
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function clearDate() {
  dateFrom.value = null
  dateTo.value = null
}

const strategyItems = [
  { title: '1 NTB', value: 1 },
  { title: '2 Betalone', value: 2 },
  { title: '3 Sniper', value: 3 },
  { title: '4 BTS', value: 4 },
  { title: '5 Favorites', value: 5 },
  { title: '6 StavkaTV', value: 6 },
  { title: '7 Moneyway', value: 7 },
  { title: '8 1pr', value: 8 },
  { title: '9 WhoScored', value: 9 },
  { title: '10 XGBoost', value: 10 },
]

const sportItems = [
  { title: 'Футбол', value: 1 },
  { title: 'Баскетбол', value: 3 },
  { title: 'Хоккей', value: 4 },
  { title: 'Бейсбол', value: 6 },
]

// Пустой выбор = без фильтра (все). Передаём строкой через запятую.
function joinIds(values: number[]): string | undefined {
  return values.length ? values.join(',') : undefined
}

function numOrUndef(v: unknown): number | undefined {
  if (v == null || v === '') return undefined
  const n = Number(v)
  return Number.isFinite(n) ? n : undefined
}

function stripUndefined(obj: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(obj)) {
    if (v !== undefined) result[k] = v
  }
  return result
}

const filterNums = computed(() => ({
  odds_min: numOrUndef(oddsMin.value),
  odds_max: numOrUndef(oddsMax.value),
  edge_min: numOrUndef(edgeMin.value),
  edge_max: numOrUndef(edgeMax.value),
}))

const listQuery = computed(() =>
  stripUndefined({
    ...dbQuery.value,
    match_id: matchId.value || undefined,
    strategy_id: joinIds(strategyIds.value),
    sport: joinIds(sports.value),
    date_from: dateFrom.value || undefined,
    date_to: dateTo.value || undefined,
    ...filterNums.value,
    limit: limit.value,
    offset: offset.value,
  }),
)

const summaryQuery = computed(() =>
  stripUndefined({
    ...dbQuery.value,
    match_id: matchId.value || undefined,
    strategy_id: joinIds(strategyIds.value),
    sport: joinIds(sports.value),
    date_from: dateFrom.value || undefined,
    date_to: dateTo.value || undefined,
    settled: settledOnly.value ? '1' : undefined,
    stake: stake.value || 1,
    ...filterNums.value,
  }),
)

const { data, pending, error, refresh } = await useFetch<Paginated<Record<string, unknown>>>(
  '/api/predictions',
  { query: listQuery, watch: [listQuery] },
)

const {
  data: summary,
  pending: summaryPending,
  error: summaryError,
  refresh: refreshSummary,
} = await useFetch<Summary>('/api/predictions/summary', {
  query: summaryQuery,
  watch: [summaryQuery],
})

const headers = [
  { title: 'ID', key: 'id', width: '80px' },
  { title: 'Дата', key: 'match_date', width: '160px' },
  { title: 'Матч', key: 'match_id', width: '120px' },
  { title: 'Стратегия', key: 'strategy_name', width: '140px' },
  { title: 'Прогноз', key: 'prediction' },
  { title: 'Кф', key: 'odds', width: '80px' },
  { title: 'Edge', key: 'edge', width: '100px' },
  { title: 'Счёт', key: 'score', width: '90px' },
  { title: 'Результат', key: 'result', width: '110px' },
  { title: 'Профит', key: 'profit', width: '100px' },
]

const stratHeaders = [
  { title: 'Стратегия', key: 'strategy_name' },
  { title: 'Всего', key: 'total', width: '80px' },
  { title: 'Расчёт', key: 'settled', width: '80px' },
  { title: 'Ожид.', key: 'pending', width: '80px' },
  { title: 'W', key: 'wins', width: '60px' },
  { title: 'L', key: 'losses', width: '60px' },
  { title: 'P', key: 'pushes', width: '60px' },
  { title: 'Ставка', key: 'stake_sum', width: '100px' },
  { title: 'Профит', key: 'profit', width: '100px' },
  { title: 'ROI %', key: 'roi', width: '80px' },
]

watch(
  [matchId, strategyIds, sports, dateFrom, dateTo, limit, settledOnly, stake, oddsMin, oddsMax, edgeMin, edgeMax],
  () => {
    resetOffset()
    refreshAll()
  },
  { deep: true },
)

function fmt(n: number | null | undefined, digits = 2) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return Number(n).toFixed(digits)
}

function fmtEdge(v: unknown) {
  const n = Number(v)
  if (v == null || v === '' || Number.isNaN(n)) return '—'
  const pp = Math.abs(n) <= 1.5 ? n * 100 : n
  const sign = pp > 0 ? '+' : ''
  return `${sign}${pp.toFixed(1)} pp`
}

function profitColor(n: number | null | undefined) {
  const v = Number(n || 0)
  if (v > 0) return 'success'
  if (v < 0) return 'error'
  return undefined
}

async function refreshAll() {
  await Promise.all([refresh(), refreshSummary()])
}
</script>

<template>
  <div>
    <!-- Page Header -->
    <div class="page-header mb-5">
      <div class="page-title">Прогнозы стратегий</div>
    </div>

    <!-- Filters -->
    <div class="filter-section">
      <v-row dense>
        <v-col cols="12" sm="6" md="2">
          <v-text-field
            v-model="matchId"
            label="match_id"
            density="compact"
            hide-details
            clearable
            variant="outlined"
            class="text-black"
          />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-select
            v-model="strategyIds"
            :items="strategyItems"
            label="Стратегия"
            density="compact"
            hide-details
            variant="outlined"
            multiple
            chips
            closable-chips
            clearable
            class="text-black"
          />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-select
            v-model="sports"
            :items="sportItems"
            label="Спорт"
            density="compact"
            hide-details
            variant="outlined"
            multiple
            chips
            closable-chips
            clearable
            class="text-black"
          />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-text-field
            v-model="dateFrom"
            label="Дата от"
            type="date"
            density="compact"
            hide-details
            clearable
            variant="outlined"
            class="text-black"
          />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-text-field
            v-model="dateTo"
            label="Дата до"
            type="date"
            density="compact"
            hide-details
            clearable
            variant="outlined"
            class="text-black"
          />
        </v-col>
        <v-col cols="6" sm="4" md="2">
          <v-text-field
            v-model.number="oddsMin"
            label="Кф от"
            type="number"
            density="compact"
            hide-details
            clearable
            variant="outlined"
            min="1"
            step="0.05"
          />
        </v-col>
        <v-col cols="6" sm="4" md="2">
          <v-text-field
            v-model.number="oddsMax"
            label="Кф до"
            type="number"
            density="compact"
            hide-details
            clearable
            variant="outlined"
            min="1"
            step="0.05"
          />
        </v-col>
        <v-col cols="6" sm="4" md="2">
          <v-text-field
            v-model.number="edgeMin"
            label="Edge от, pp"
            type="number"
            density="compact"
            hide-details
            clearable
            variant="outlined"
            step="0.1"
          />
        </v-col>
        <v-col cols="6" sm="4" md="2">
          <v-text-field
            v-model.number="edgeMax"
            label="Edge до, pp"
            type="number"
            density="compact"
            hide-details
            clearable
            variant="outlined"
            step="0.1"
          />
        </v-col>
        <v-col cols="12" sm="6" md="2" class="d-flex align-end flex-wrap gap-2">
          <v-btn
            variant="outlined"
            :loading="pending || summaryPending"
            @click="refreshAll()"
            color="primary"
            full-width
          >
            <v-icon start>mdi-refresh</v-icon>
            Обновить
          </v-btn>
        </v-col>
      </v-row>
    </div>

    <!-- Error Alerts -->
    <v-alert v-if="error || summaryError" type="error" class="mb-3" density="compact" rounded="lg">
      {{ error?.message || summaryError?.message || error || summaryError }}
    </v-alert>

    <!-- Summary Cards -->
    <v-row class="mb-4" dense>
      <v-col cols="6" sm="4" md="2">
        <div class="metric-card pa-3">
          <div class="text-caption text-medium-emphasis">Прогнозов</div>
          <div class="text-h6">{{ summary?.total ?? '—' }}</div>
        </div>
      </v-col>
      <v-col cols="6" sm="4" md="2">
        <div class="metric-card pa-3">
          <div class="text-caption text-medium-emphasis">Расчёт / ожид.</div>
          <div class="text-h6">{{ summary?.settled ?? 0 }} / {{ summary?.pending ?? 0 }}</div>
        </div>
      </v-col>
      <v-col cols="6" sm="4" md="2">
        <div class="metric-card pa-3">
          <div class="text-caption text-medium-emphasis">W / L / P</div>
          <div class="text-h6 text-body-2">
            {{ summary?.wins ?? 0 }} / {{ summary?.losses ?? 0 }} / {{ summary?.pushes ?? 0 }}
          </div>
        </div>
      </v-col>
      <v-col cols="6" sm="4" md="2">
        <div class="metric-card pa-3">
          <div class="text-caption text-medium-emphasis">Оборот (stake)</div>
          <div class="text-h6">{{ fmt(summary?.stake_sum) }}</div>
        </div>
      </v-col>
      <v-col cols="6" sm="4" md="2">
        <div class="metric-card pa-3" :class="profitColor(summary?.profit)">
          <div class="text-caption">Профит</div>
          <div class="text-h6">{{ fmt(summary?.profit) }}</div>
        </div>
      </v-col>
      <v-col cols="6" sm="4" md="2">
        <div class="metric-card pa-3" :class="profitColor(summary?.roi)">
          <div class="text-caption">ROI %</div>
          <div class="text-h6">{{ fmt(summary?.roi) }}</div>
        </div>
      </v-col>
    </v-row>

    <!-- Strategy Performance -->
    <div class="content-card mb-4">
      <div class="card-header">
        Прибыль по стратегиям
        <span class="text-caption text-medium-emphasis ml-2">
          (только завершённые, stake={{ summary?.stake_unit ?? 1 }})
        </span>
      </div>
      <v-data-table
        :headers="stratHeaders"
        :items="summary?.by_strategy || []"
        :loading="summaryPending"
        item-value="strategy_id"
        hide-default-footer
        density="compact"
        class="elevation-0"
      >
        <template #item.profit="{ item }">
          <span :class="Number(item.profit) > 0 ? 'text-success' : Number(item.profit) < 0 ? 'text-error' : ''">
            {{ fmt(item.profit) }}
          </span>
        </template>
        <template #item.roi="{ item }">
          <span :class="Number(item.roi) > 0 ? 'text-success' : Number(item.roi) < 0 ? 'text-error' : ''">
            {{ fmt(item.roi) }}
          </span>
        </template>
      </v-data-table>
    </div>

    <!-- Predictions Table -->
    <div class="content-card">
      <v-data-table
        :headers="headers"
        :items="data?.items || []"
        :loading="pending"
        item-value="id"
        hide-default-footer
        density="compact"
        class="elevation-0"
      >
        <template #item.match_id="{ item }">
          <NuxtLink :to="`/matches/${item.match_id}`" class="text-primary font-weight-medium">
            {{ item.match_id }}
          </NuxtLink>
        </template>
        <template #item.score="{ item }">
          <span v-if="item.score_home != null && item.score_away != null">
            {{ item.score_home }} : {{ item.score_away }}
          </span>
          <span v-else class="text-medium-emphasis">—</span>
        </template>
        <template #item.edge="{ item }">
          <span
            :class="
              Number(item.edge) > 0 ? 'text-success' : Number(item.edge) < 0 ? 'text-error' : ''
            "
          >
            {{ fmtEdge(item.edge) }}
          </span>
        </template>
        <template #item.profit="{ item }">
          <span
            :class="
              Number(item.profit) > 0 ? 'text-success' : Number(item.profit) < 0 ? 'text-error' : ''
            "
          >
            {{ item.profit ?? '—' }}
          </span>
        </template>
        <template #item.result="{ item }">
          <v-chip
            size="small"
            :color="
              item.result === 'win' ? 'success' : item.result === 'loss' ? 'error' : 'warning'
            "
            variant="tonal"
          >
            {{ item.result || '—' }}
          </v-chip>
        </template>
      </v-data-table>
      <v-divider />
      <PaginationBar
        :offset="offset"
        :limit="limit"
        :total="data?.total || 0"
        :pending="pending"
        @prev="prevPage"
        @next="nextPage"
        @update:limit="setLimit"
      />
    </div>
  </div>
</template>

<style scoped>
.ml-2 {
  margin-left: 8px;
}

.gap-2 {
  gap: 8px;
}
</style>
