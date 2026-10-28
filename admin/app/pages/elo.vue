<script setup lang="ts">
import type { Paginated } from '~/types/db'
import { sportLabel, eloTier } from '~/types/db'

interface EloItem {
  team_id: number
  team_name: string
  sport: number
  rating: number
  matches_played: number
  wins: number
  losses: number
  draws: number
  last_updated: string
}

interface EloSummaryData {
  total_teams: number
  avg_rating: number
  median_rating: number
  min_rating: number
  max_rating: number
  total_matches: number
  by_tier: Record<string, number>
}

const sport = ref<number | null>(null)
const search = ref('')
const { limit, offset, nextPage, prevPage, resetOffset, setLimit } = useTablePagination(10)

const sportItems = [
  { title: 'Все', value: null },
  { title: 'Футбол', value: 1 },
  { title: 'Баскетбол', value: 3 },
  { title: 'Хоккей', value: 4 },
  { title: 'Бейсбол', value: 6 },
]

const query = computed(() => ({
  sport: sport.value ?? undefined,
  q: search.value || undefined,
  limit: limit.value,
  offset: offset.value,
}))

const summaryQuery = computed(() => ({
  sport: sport.value ?? undefined,
}))

const { data, pending, error, refresh } = await useFetch<Paginated<EloItem>>(
  '/api/elo/ratings',
  { query, watch: [query] },
)

const {
  data: summary,
  pending: summaryPending,
  error: summaryError,
  refresh: refreshSummary,
} = await useFetch<EloSummaryData>('/api/elo/summary', {
  query: summaryQuery,
  watch: [summaryQuery],
})

const { pending: recalcPending, execute: recalculate } = useAsyncData(
  'elo-recalculate',
  async () => {
    await $fetch('/api/elo/recalculate', {
      method: 'POST',
      body: { sport: sport.value },
    })
    await refresh()
    await refreshSummary()
  },
)

watch([sport, search, limit], () => {
  resetOffset()
  refreshAll()
})

async function refreshAll() {
  await Promise.all([refresh(), refreshSummary()])
}

function fmt(n: number | string | null | undefined, digits = 1) {
  if (n == null || n === '') return '—'
  return Number(n).toFixed(digits)
}
</script>

<template>
  <div>
    <!-- Page Header -->
    <div class="page-header mb-5">
      <div class="page-title">ELO Рейтинг команд</div>
    </div>

    <!-- Filters -->
    <div class="filter-section">
      <v-row dense>
        <v-col cols="12" sm="6" md="3">
          <v-select
            v-model="sport"
            :items="sportItems"
            label="Вид спорта"
            density="compact"
            hide-details
            variant="outlined"
            class="text-black"
          />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field
            v-model="search"
            label="Поиск команды"
            density="compact"
            hide-details
            clearable
            variant="outlined"
            class="text-black"
          />
        </v-col>
        <v-col cols="6" sm="4" md="3">
          <v-btn
            variant="outlined"
            :loading="recalcPending"
            @click="recalculate()"
            color="primary"
            full-width
          >
            <v-icon start>mdi-update</v-icon>
            Пересчитать
          </v-btn>
        </v-col>
        <v-col cols="6" sm="4" md="3" class="d-flex align-end">
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
      {{ error?.message || summaryError?.message }}
    </v-alert>

    <!-- Summary Cards -->
    <v-row class="mb-4" dense>
      <v-col cols="6" sm="4" md="2">
        <div class="metric-card pa-3">
          <div class="text-caption text-medium-emphasis">Команд</div>
          <div class="text-h6">{{ summary?.total_teams ?? '—' }}</div>
        </div>
      </v-col>
      <v-col cols="6" sm="4" md="2">
        <div class="metric-card pa-3">
          <div class="text-caption text-medium-emphasis">Ср. рейтинг</div>
          <div class="text-h6">{{ fmt(summary?.avg_rating) }}</div>
        </div>
      </v-col>
      <v-col cols="6" sm="4" md="2">
        <div class="metric-card pa-3">
          <div class="text-caption text-medium-emphasis">Медиана</div>
          <div class="text-h6">{{ fmt(summary?.median_rating) }}</div>
        </div>
      </v-col>
      <v-col cols="6" sm="4" md="2">
        <div class="metric-card pa-3">
          <div class="text-caption text-medium-emphasis">Матчей</div>
          <div class="text-h6">{{ summary?.total_matches ?? '—' }}</div>
        </div>
      </v-col>
      <v-col cols="6" sm="4" md="2">
        <div class="metric-card pa-3">
          <div class="text-caption">Мин</div>
          <div class="text-h6">{{ fmt(summary?.min_rating) }}</div>
        </div>
      </v-col>
      <v-col cols="6" sm="4" md="2">
        <div class="metric-card pa-3">
          <div class="text-caption">Макс</div>
          <div class="text-h6">{{ fmt(summary?.max_rating) }}</div>
        </div>
      </v-col>
    </v-row>

    <!-- Tier Breakdown -->
    <div class="content-card mb-4" v-if="summary">
      <div class="card-header">Распределение по тирам</div>
      <v-row dense class="mt-2">
        <v-col cols="6" sm="3" md="3" v-for="tier in ['champion', 'strong', 'average', 'weak']" :key="tier">
          <div class="tier-bar-container">
            <div class="tier-label">
              <v-chip size="x-small" :color="eloTier(0).color" variant="tonal" class="mr-1">
                {{ tier === 'champion' ? '🏆' : tier === 'strong' ? '💪' : tier === 'average' ? '📊' : '📉' }}
              </v-chip>
              {{ tier === 'champion' ? 'Champion' : tier === 'strong' ? 'Strong' : tier === 'average' ? 'Average' : 'Weak' }}
            </div>
            <v-progress-linear
              :model-value="tier === 'champion' ? summary.by_tier.champion : tier === 'strong' ? summary.by_tier.strong : tier === 'average' ? summary.by_tier.average : summary.by_tier.weak"
              :max="summary.total_teams || 1"
              :color="tier === 'champion' ? 'success' : tier === 'strong' ? 'primary' : tier === 'average' ? '' : 'error'"
              height="8"
              rounded
            >
              <template #default="{ value }">
                <span class="text-caption">{{ Math.round(value) }}</span>
              </template>
            </v-progress-linear>
          </div>
        </v-col>
      </v-row>
    </div>

    <!-- ELO Table -->
    <div class="content-card">
      <v-data-table
        :headers="[
          { title: 'Команда', key: 'team_name', width: '200px' },
          { title: 'Спорт', key: 'sport', width: '100px' },
          { title: 'Рейтинг', key: 'rating', width: '100px' },
          { title: 'Матчи', key: 'matches_played', width: '80px' },
          { title: 'W', key: 'wins', width: '60px' },
          { title: 'D', key: 'draws', width: '60px' },
          { title: 'L', key: 'losses', width: '60px' },
          { title: 'Тир', key: 'tier', width: '120px' },
          { title: 'Обновлён', key: 'last_updated', width: '160px' },
        ]"
        :items="data?.items || []"
        :loading="pending"
        item-value="team_id"
        hide-default-footer
        density="compact"
        class="elevation-0"
      >
        <template #item.sport="{ item }">
          {{ sportLabel(item.sport) }}
        </template>
        <template #item.rating="{ item }">
          <span class="font-weight-medium">{{ fmt(item.rating, 0) }}</span>
        </template>
        <template #item.tier="{ item }">
          <v-chip size="small" :color="eloTier(item.rating).color" variant="tonal">
            {{ eloTier(item.rating).label }}
          </v-chip>
        </template>
        <template #item.last_updated="{ item }">
          <span class="text-caption">{{ item.last_updated }}</span>
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
.tier-bar-container {
  padding: 8px 0;
}
.tier-label {
  font-size: 12px;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
