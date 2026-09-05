<script setup lang="ts">
import type { StatsResponse } from '~/types/db'
import { sportLabel } from '~/types/db'

const { dbQuery } = useAdminDb()

const { data, pending, error, refresh } = await useFetch<StatsResponse>('/api/stats', {
  query: dbQuery,
  watch: [dbQuery],
})

const cards = computed(() => {
  const c = data.value?.counts || {}
  return [
    { key: 'matches', title: 'Матчи', to: '/matches', icon: 'mdi-soccer' },
    { key: 'match_queue', title: 'Очередь', to: '/queue', icon: 'mdi-format-list-bulleted' },
    { key: 'strategy_predictions', title: 'Прогнозы', to: '/predictions', icon: 'mdi-crystal-ball' },
    { key: 'outcome_probabilities', title: 'Стратегии %', to: '/outcomes', icon: 'mdi-percent-outline' },
    { key: 'odds', title: 'Коэффициенты', to: '/odds', icon: 'mdi-cash-multiple' },
    { key: 'teams', title: 'Команды', to: '/teams', icon: 'mdi-shield-outline' },
    { key: 'leagues', title: 'Лиги', to: '/leagues', icon: 'mdi-trophy-outline' },
    { key: 'goal_probabilities', title: 'Голы %', to: '/goals', icon: 'mdi-soccer-field' },
  ].map((item) => ({ ...item, value: c[item.key] ?? 0 }))
})

const recentHeaders = [
  { title: 'ID', key: 'match_id' },
  { title: 'Дата', key: 'match_date' },
  { title: 'Матч', key: 'fixture' },
  { title: 'Прогноз', key: 'prediction' },
  { title: 'Статус', key: 'match_status' },
  { title: 'Спорт', key: 'sport' },
]
</script>

<template>
  <div>
    <div class="d-flex align-center justify-space-between mb-4">
      <div>
        <div class="text-h5 font-weight-bold">Обзор</div>
        <div class="text-body-2 text-medium-emphasis">
          {{ data?.label || '—' }} · {{ data?.path }}
        </div>
      </div>
      <v-btn variant="outlined" prepend-icon="mdi-refresh" :loading="pending" @click="refresh()">
        Обновить
      </v-btn>
    </div>

    <v-alert v-if="error" type="error" class="mb-4" density="compact">{{ error.message || error }}</v-alert>

    <v-row dense class="mb-4">
      <v-col v-for="card in cards" :key="card.key" cols="12" sm="6" md="3">
        <v-card :to="card.to" hover>
          <v-card-text class="d-flex align-center ga-3">
            <v-avatar color="primary" variant="tonal" size="44">
              <v-icon :icon="card.icon" />
            </v-avatar>
            <div>
              <div class="text-caption text-medium-emphasis">{{ card.title }}</div>
              <div class="text-h5 font-weight-bold">{{ card.value }}</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-card>
      <v-card-title>Последние матчи</v-card-title>
      <v-divider />
      <v-data-table
        :headers="recentHeaders"
        :items="data?.recent || []"
        :loading="pending"
        item-value="match_id"
        hide-default-footer
      >
        <template #item.match_id="{ item }">
          <NuxtLink :to="`/matches/${item.match_id}`">{{ item.match_id }}</NuxtLink>
        </template>
        <template #item.fixture="{ item }">
          <div class="text-body-2">{{ item.home_team || '—' }} — {{ item.away_team || '—' }}</div>
          <div class="text-caption text-medium-emphasis">
            {{ [item.country_name, item.league_name].filter(Boolean).join(': ') || '—' }}
          </div>
        </template>
        <template #item.sport="{ item }">
          {{ sportLabel(item.sport) }}
        </template>
      </v-data-table>
    </v-card>
  </div>
</template>
