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
    { 
      key: 'matches', 
      title: 'Всего матчей', 
      to: '/matches', 
      icon: 'mdi-soccer',
      color: '#E87739',
      bgColor: 'rgba(232, 119, 57, 0.1)',
    },
    { 
      key: 'match_queue', 
      title: 'В очереди', 
      to: '/queue', 
      icon: 'mdi-clock-outline',
      color: '#4A90E2',
      bgColor: 'rgba(74, 144, 226, 0.1)',
    },
    { 
      key: 'strategy_predictions', 
      title: 'Прогнозов', 
      to: '/predictions', 
      icon: 'mdi-crystal-ball',
      color: '#2ECC71',
      bgColor: 'rgba(46, 204, 113, 0.1)',
    },
    { 
      key: 'outcome_probabilities', 
      title: 'Стратегий %', 
      to: '/outcomes', 
      icon: 'mdi-chart-pie',
      color: '#9B59B6',
      bgColor: 'rgba(155, 89, 182, 0.1)',
    },
    { 
      key: 'odds', 
      title: 'Коэффициентов', 
      to: '/odds', 
      icon: 'mdi-trending-up',
      color: '#F39C12',
      bgColor: 'rgba(243, 156, 18, 0.1)',
    },
    { 
      key: 'teams', 
      title: 'Команд', 
      to: '/teams', 
      icon: 'mdi-account-group',
      color: '#3498DB',
      bgColor: 'rgba(52, 152, 219, 0.1)',
    },
    { 
      key: 'leagues', 
      title: 'Лиг', 
      to: '/leagues', 
      icon: 'mdi-trophy',
      color: '#E67E22',
      bgColor: 'rgba(230, 126, 34, 0.1)',
    },
    { 
      key: 'goal_probabilities', 
      title: 'Голы %', 
      to: '/goals', 
      icon: 'mdi-futbol',
      color: '#1ABC9C',
      bgColor: 'rgba(26, 188, 156, 0.1)',
    },
  ].map((item) => ({ ...item, value: c[item.key] ?? 0 }))
})

const recentHeaders = [
  { title: 'ID', key: 'match_id', width: '140px' },
  { title: 'Дата', key: 'match_date', width: '160px' },
  { title: 'Матч', key: 'fixture' },
  { title: 'Прогноз', key: 'prediction', width: '120px' },
  { title: 'Статус', key: 'match_status', width: '120px' },
  { title: 'Спорт', key: 'sport', width: '100px' },
]

function formatMatchDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  return `${year}.${month}.${day} ${hours}:${minutes}`
}
</script>

<template>
  <div>
    <!-- Page Header -->
    <div class="page-header d-flex align-center justify-space-between flex-wrap gap-3">
      <div>
        <div class="page-title">Обзор</div>
        <div class="page-subtitle">
          {{ data?.label || '—' }} · {{ data?.path }}
        </div>
      </div>
      <v-btn
        variant="outlined"
        prepend-icon="mdi-refresh"
        :loading="pending"
        @click="refresh()"
        color="primary"
      >
        Обновить
      </v-btn>
    </div>

    <!-- Error Alert -->
    <v-alert v-if="error" type="error" class="mb-4" density="compact" rounded="lg">
      {{ error.message || error }}
    </v-alert>

    <!-- Metric Cards -->
    <v-row dense>
      <v-col v-for="card in cards" :key="card.key" cols="12" sm="6" md="4" lg="3">
        <NuxtLink :to="card.to" style="text-decoration: none; color: inherit;">
          <div class="metric-card h-100">
            <div class="d-flex align-center justify-space-between">
              <div class="metric-icon" :style="{ backgroundColor: card.bgColor, color: card.color }">
                <v-icon :icon="card.icon" />
              </div>
              <v-icon color="text-secondary" size="small">mdi-chevron-right</v-icon>
            </div>
            <div class="metric-value">{{ card.value }}</div>
            <div class="metric-title">{{ card.title }}</div>
          </div>
        </NuxtLink>
      </v-col>
    </v-row>

    <!-- Recent Matches -->
    <div class="content-card mt-4">
      <div class="card-header d-flex align-center justify-space-between">
        <span>Последние матчи</span>
        <v-btn
          variant="text"
          size="small"
          to="/matches"
          color="primary"
        >
          Все матчи
          <v-icon end>mdi-arrow-right</v-icon>
        </v-btn>
      </div>
      <v-data-table
        :headers="recentHeaders"
        :items="data?.recent || []"
        :loading="pending"
        item-value="match_id"
        hide-default-footer
        density="compact"
        class="elevation-0"
      >
        <template #item.match_id="{ item }">
          <NuxtLink :to="`/matches/${item.match_id}`" class="text-primary font-weight-medium">
            {{ item.match_id }}
          </NuxtLink>
        </template>
        <template #item.match_date="{ item }">
          {{ formatMatchDate(item.match_date) }}
        </template>
        <template #item.fixture="{ item }">
          <div class="font-weight-medium">{{ item.home_team || '—' }}</div>
          <div class="text-caption text-medium-emphasis">
            {{ item.away_team || '—' }}
          </div>
        </template>
        <template #item.sport="{ item }">
          <v-chip size="small" variant="outlined" color="text-secondary">
            {{ sportLabel(item.sport) }}
          </v-chip>
        </template>
        <template #item.match_status="{ item }">
          <v-chip
            size="small"
            :color="item.match_status === 'finished' ? 'success' : 'warning'"
            variant="tonal"
          >
            {{ item.match_status || '—' }}
          </v-chip>
        </template>
      </v-data-table>
    </div>
  </div>
</template>

<style scoped>
.gap-3 {
  gap: 12px;
}
</style>
