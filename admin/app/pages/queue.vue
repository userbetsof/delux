<script setup lang="ts">
import type { Paginated } from '~/types/db'
import { sportLabel } from '~/types/db'

interface QueueRow {
  match_id: string
  sport: number
  tour_name?: string
  date_match?: string
  home_name?: string
  away_name?: string
  start_home?: number
  start_draw?: number
  start_away?: number
  current_home?: number
  current_draw?: number
  current_away?: number
}

const { dbQuery } = useAdminDb()
const search = ref('')
const sport = ref<number | null>(null)
const { limit, offset, nextPage, prevPage, resetOffset, setLimit } = useTablePagination(50)

const query = computed(() => ({
  ...dbQuery.value,
  q: search.value || undefined,
  sport: sport.value ?? undefined,
  limit: limit.value,
  offset: offset.value,
}))

const { data, pending, error, refresh } = await useFetch<Paginated<QueueRow>>('/api/queue', {
  query,
  watch: [query],
})

const headers = [
  { title: 'ID', key: 'match_id' },
  { title: 'Дата', key: 'date_match' },
  { title: 'Лига', key: 'tour_name' },
  { title: 'Матч', key: 'fixture' },
  { title: '1 / X / 2', key: 'odds' },
  { title: 'Спорт', key: 'sport' },
]

const sportItems = [
  { title: 'Все', value: null },
  { title: 'Футбол', value: 1 },
  { title: 'Баскетбол', value: 3 },
  { title: 'Хоккей', value: 4 },
  { title: 'Бейсбол', value: 6 },
]

watch([search, sport, limit], resetOffset)
</script>

<template>
  <div>
    <div class="d-flex align-center justify-space-between mb-4 flex-wrap ga-2">
      <div class="text-h5 font-weight-bold">Очередь матчей</div>
      <div class="d-flex align-center ga-2 flex-wrap">
        <v-text-field
          v-model="search"
          label="Поиск"
          density="compact"
          hide-details
          clearable
          style="min-width: 220px"
        />
        <v-select
          v-model="sport"
          :items="sportItems"
          label="Спорт"
          density="compact"
          hide-details
          style="min-width: 140px"
        />
        <v-btn variant="outlined" :loading="pending" @click="refresh()">Обновить</v-btn>
      </div>
    </div>

    <v-alert v-if="error" type="error" class="mb-3" density="compact">{{ error.message || error }}</v-alert>
    <v-alert
      v-else-if="!pending && (data?.total || 0) === 0"
      type="info"
      class="mb-3"
      density="compact"
    >
      Таблица match_queue пуста или отсутствует в выбранной БД.
    </v-alert>

    <v-card>
      <v-data-table
        :headers="headers"
        :items="data?.items || []"
        :loading="pending"
        item-value="match_id"
        hide-default-footer
      >
        <template #item.match_id="{ item }">
          <NuxtLink :to="`/matches/${item.match_id}`">{{ item.match_id }}</NuxtLink>
        </template>
        <template #item.fixture="{ item }">
          {{ item.home_name || '—' }} — {{ item.away_name || '—' }}
        </template>
        <template #item.odds="{ item }">
          {{ item.current_home || item.start_home || '—' }}
          /
          {{ item.current_draw || item.start_draw || '—' }}
          /
          {{ item.current_away || item.start_away || '—' }}
        </template>
        <template #item.sport="{ item }">
          {{ sportLabel(item.sport) }}
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
