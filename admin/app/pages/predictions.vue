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
const strategyId = ref<number | null>(null)
const sport = ref<number | null>(null)
const settledOnly = ref(false)
const stake = ref(1)
const { limit, offset, nextPage, prevPage, resetOffset, setLimit } = useTablePagination(50)

const strategyItems = [
  { title: 'Все', value: null },
  { title: '1 NTB', value: 1 },
  { title: '2 Betalone', value: 2 },
  { title: '3 Sniper', value: 3 },
  { title: '4 BTS', value: 4 },
  { title: '5 Favorites', value: 5 },
  { title: '6 StavkaTV', value: 6 },
  { title: '7 Moneyway', value: 7 },
  { title: '8 1pr', value: 8 },
]

const sportItems = [
  { title: 'Все', value: null },
  { title: 'Футбол', value: 1 },
  { title: 'Баскетбол', value: 3 },
  { title: 'Хоккей', value: 4 },
  { title: 'Бейсбол', value: 6 },
]

const listQuery = computed(() => ({
  ...dbQuery.value,
  match_id: matchId.value || undefined,
  strategy_id: strategyId.value ?? undefined,
  sport: sport.value ?? undefined,
  limit: limit.value,
  offset: offset.value,
}))

const summaryQuery = computed(() => ({
  ...dbQuery.value,
  match_id: matchId.value || undefined,
  strategy_id: strategyId.value ?? undefined,
  sport: sport.value ?? undefined,
  settled: settledOnly.value ? '1' : undefined,
  stake: stake.value || 1,
}))

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
  { title: 'ID', key: 'id' },
  { title: 'Дата', key: 'match_date' },
  { title: 'Матч', key: 'match_id' },
  { title: 'Стратегия', key: 'strategy_name' },
  { title: 'Прогноз', key: 'prediction' },
  { title: 'Кф', key: 'odds' },
  { title: 'Счёт', key: 'score' },
  { title: 'Результат', key: 'result' },
  { title: 'Профит', key: 'profit' },
]

const stratHeaders = [
  { title: 'Стратегия', key: 'strategy_name' },
  { title: 'Всего', key: 'total' },
  { title: 'Расчёт', key: 'settled' },
  { title: 'W', key: 'wins' },
  { title: 'L', key: 'losses' },
  { title: 'P', key: 'pushes' },
  { title: 'Ставка', key: 'stake_sum' },
  { title: 'Профит', key: 'profit' },
  { title: 'ROI %', key: 'roi' },
]

watch([matchId, strategyId, sport, limit, settledOnly, stake], resetOffset)

function fmt(n: number | null | undefined, digits = 2) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return Number(n).toFixed(digits)
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
    <div class="d-flex align-center justify-space-between mb-4 flex-wrap ga-2">
      <div class="text-h5 font-weight-bold">Прогнозы стратегий</div>
      <div class="d-flex align-center ga-2 flex-wrap">
        <v-text-field
          v-model="matchId"
          label="match_id"
          density="compact"
          hide-details
          clearable
          style="min-width: 140px"
        />
        <v-select
          v-model="strategyId"
          :items="strategyItems"
          label="Стратегия"
          density="compact"
          hide-details
          style="min-width: 150px"
        />
        <v-select
          v-model="sport"
          :items="sportItems"
          label="Спорт"
          density="compact"
          hide-details
          style="min-width: 130px"
        />
        <v-text-field
          v-model.number="stake"
          label="Stake"
          type="number"
          density="compact"
          hide-details
          style="max-width: 90px"
          min="0.1"
          step="0.1"
        />
        <v-switch
          v-model="settledOnly"
          label="Только расчёт"
          density="compact"
          hide-details
          color="primary"
        />
        <v-btn variant="outlined" :loading="pending || summaryPending" @click="refreshAll">
          Обновить
        </v-btn>
      </div>
    </div>

    <v-alert v-if="error || summaryError" type="error" class="mb-3" density="compact">
      {{ error?.message || summaryError?.message || error || summaryError }}
    </v-alert>

    <v-row class="mb-4" dense>
      <v-col cols="6" sm="4" md="2">
        <v-card variant="tonal" class="pa-3">
          <div class="text-caption text-medium-emphasis">Прогнозов</div>
          <div class="text-h6">{{ summary?.total ?? '—' }}</div>
        </v-card>
      </v-col>
      <v-col cols="6" sm="4" md="2">
        <v-card variant="tonal" class="pa-3">
          <div class="text-caption text-medium-emphasis">Расчёт / ожид.</div>
          <div class="text-h6">{{ summary?.settled ?? 0 }} / {{ summary?.pending ?? 0 }}</div>
        </v-card>
      </v-col>
      <v-col cols="6" sm="4" md="2">
        <v-card variant="tonal" class="pa-3">
          <div class="text-caption text-medium-emphasis">W / L / P</div>
          <div class="text-h6">
            {{ summary?.wins ?? 0 }} / {{ summary?.losses ?? 0 }} / {{ summary?.pushes ?? 0 }}
          </div>
        </v-card>
      </v-col>
      <v-col cols="6" sm="4" md="2">
        <v-card variant="tonal" class="pa-3">
          <div class="text-caption text-medium-emphasis">Оборот (stake)</div>
          <div class="text-h6">{{ fmt(summary?.stake_sum) }}</div>
        </v-card>
      </v-col>
      <v-col cols="6" sm="4" md="2">
        <v-card variant="tonal" class="pa-3" :color="profitColor(summary?.profit)">
          <div class="text-caption">Профит</div>
          <div class="text-h6">{{ fmt(summary?.profit) }}</div>
        </v-card>
      </v-col>
      <v-col cols="6" sm="4" md="2">
        <v-card variant="tonal" class="pa-3" :color="profitColor(summary?.roi)">
          <div class="text-caption">ROI %</div>
          <div class="text-h6">{{ fmt(summary?.roi) }}</div>
        </v-card>
      </v-col>
    </v-row>

    <v-card class="mb-4">
      <div class="pa-3 text-subtitle-1 font-weight-medium">
        Прибыль по стратегиям
        <span class="text-caption text-medium-emphasis ml-2">
          (пересчёт при смене фильтров, stake={{ summary?.stake_unit ?? 1 }})
        </span>
      </div>
      <v-data-table
        :headers="stratHeaders"
        :items="summary?.by_strategy || []"
        :loading="summaryPending"
        item-value="strategy_id"
        hide-default-footer
        density="compact"
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
    </v-card>

    <v-card>
      <v-data-table
        :headers="headers"
        :items="data?.items || []"
        :loading="pending"
        item-value="id"
        hide-default-footer
      >
        <template #item.match_id="{ item }">
          <NuxtLink :to="`/matches/${item.match_id}`">{{ item.match_id }}</NuxtLink>
        </template>
        <template #item.score="{ item }">
          <span v-if="item.score_home != null && item.score_away != null">
            {{ item.score_home }} : {{ item.score_away }}
          </span>
          <span v-else class="text-medium-emphasis">—</span>
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
    </v-card>
  </div>
</template>
