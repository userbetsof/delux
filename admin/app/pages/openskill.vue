<script setup lang="ts">
import type { Paginated } from '~/types/db'
import { sportLabel } from '~/types/db'

interface OpenSkillItem {
  team_id: number
  team_name: string
  sport: number
  mu: number
  sigma: number
  rating: number
  matches_played: number
  wins: number
  draws: number
  losses: number
  last_updated: string
}

interface OpenSkillSummary {
  total_teams: number
  avg_mu: number
  avg_sigma: number
  total_matches: number
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

const { data, pending, error, refresh } = await useFetch<Paginated<OpenSkillItem>>(
  '/api/openskill/ratings',
  { query, watch: [query] },
)

const { data: summary, refresh: refreshSummary } = await useFetch<OpenSkillSummary>(
  '/api/openskill/summary',
  { query: computed(() => ({ sport: sport.value ?? undefined })), watch: [sport] },
)

const { pending: recalcPending, execute: recalculate } = useAsyncData(
  'openskill-recalculate',
  async () => {
    await $fetch('/api/openskill/recalculate', {
      method: 'POST',
      body: { sport: sport.value },
    })
    await refresh()
    await refreshSummary()
  },
)

watch([sport, search, limit], () => resetOffset())

function fmt(n: number | string | null | undefined, digits = 1) {
  if (n == null || n === '') return '—'
  return Number(n).toFixed(digits)
}
</script>

<template>
  <div>
    <div class="page-header mb-5">
      <div class="page-title">OpenSkill Рейтинг команд</div>
      <div class="text-caption text-medium-emphasis">μ (skill) и σ (неопределённость); рейтинг = μ − 3σ</div>
    </div>

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
          <v-btn variant="outlined" :loading="recalcPending" @click="recalculate()" color="primary" full-width>
            <v-icon start>mdi-update</v-icon>
            Пересчитать
          </v-btn>
        </v-col>
        <v-col cols="6" sm="4" md="3" class="d-flex align-end">
          <v-btn variant="outlined" :loading="pending" @click="refresh()" color="primary" full-width>
            <v-icon start>mdi-refresh</v-icon>
            Обновить
          </v-btn>
        </v-col>
      </v-row>
    </div>

    <v-alert v-if="error" type="error" class="mb-3" density="compact" rounded="lg">
      {{ error.message || error }}
    </v-alert>

    <v-row class="mb-4" dense>
      <v-col cols="6" sm="4" md="3">
        <div class="metric-card pa-3">
          <div class="text-caption text-medium-emphasis">Команд</div>
          <div class="text-h6">{{ summary?.total_teams ?? '—' }}</div>
        </div>
      </v-col>
      <v-col cols="6" sm="4" md="3">
        <div class="metric-card pa-3">
          <div class="text-caption text-medium-emphasis">Ср. μ</div>
          <div class="text-h6">{{ summary?.avg_mu ?? '—' }}</div>
        </div>
      </v-col>
      <v-col cols="6" sm="4" md="3">
        <div class="metric-card pa-3">
          <div class="text-caption text-medium-emphasis">Ср. σ</div>
          <div class="text-h6">{{ summary?.avg_sigma ?? '—' }}</div>
        </div>
      </v-col>
      <v-col cols="6" sm="4" md="3">
        <div class="metric-card pa-3">
          <div class="text-caption text-medium-emphasis">Матчей</div>
          <div class="text-h6">{{ summary?.total_matches ?? '—' }}</div>
        </div>
      </v-col>
    </v-row>

    <div class="content-card">
      <v-data-table
        :headers="[
          { title: 'Команда', key: 'team_name', width: '200px' },
          { title: 'Спорт', key: 'sport', width: '100px' },
          { title: 'Рейтинг', key: 'rating', width: '100px' },
          { title: 'μ', key: 'mu', width: '80px' },
          { title: 'σ', key: 'sigma', width: '80px' },
          { title: 'Матчи', key: 'matches_played', width: '80px' },
          { title: 'W', key: 'wins', width: '60px' },
          { title: 'D', key: 'draws', width: '60px' },
          { title: 'L', key: 'losses', width: '60px' },
          { title: 'Обновлён', key: 'last_updated', width: '160px' },
        ]"
        :items="data?.items || []"
        :loading="pending"
        item-value="team_id"
        hide-default-footer
        density="compact"
        class="elevation-0"
      >
        <template #item.sport="{ item }">{{ sportLabel(item.sport) }}</template>
        <template #item.rating="{ item }">
          <span class="font-weight-medium">{{ fmt(item.rating, 1) }}</span>
        </template>
        <template #item.mu="{ item }">{{ fmt(item.mu, 2) }}</template>
        <template #item.sigma="{ item }">{{ fmt(item.sigma, 2) }}</template>
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
