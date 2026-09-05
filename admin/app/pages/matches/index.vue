<script setup lang="ts">
import type { MatchRow, Paginated } from '~/types/db'
import { sportLabel } from '~/types/db'

const { dbQuery } = useAdminDb()
const search = ref('')
const status = ref('')
const sport = ref<number | null>(null)
const { limit, offset, nextPage, prevPage, resetOffset, setLimit } = useTablePagination(50)

const query = computed(() => ({
  ...dbQuery.value,
  q: search.value || undefined,
  status: status.value || undefined,
  sport: sport.value ?? undefined,
  limit: limit.value,
  offset: offset.value,
}))

const { data, pending, error, refresh } = await useFetch<Paginated<MatchRow>>('/api/matches', {
  query,
  watch: [query],
})

const headers = [
  { title: 'ID', key: 'match_id' },
  { title: 'Дата', key: 'match_date' },
  { title: 'Матч', key: 'fixture' },
  { title: 'Счёт', key: 'score' },
  { title: 'Прогноз', key: 'prediction' },
  { title: 'Статус', key: 'match_status' },
  { title: 'Профит', key: 'profit' },
  { title: 'Спорт', key: 'sport' },
]

const sportItems = [
  { title: 'Все', value: null },
  { title: 'Футбол', value: 1 },
  { title: 'Баскетбол', value: 3 },
  { title: 'Хоккей', value: 4 },
  { title: 'Бейсбол', value: 6 },
]

watch([search, status, sport, limit], resetOffset)
</script>

<template>
  <div>
    <div class="d-flex align-center justify-space-between mb-4 flex-wrap ga-2">
      <div class="text-h5 font-weight-bold">Матчи</div>
      <div class="d-flex align-center ga-2 flex-wrap">
        <v-text-field
          v-model="search"
          label="Поиск"
          prepend-inner-icon="mdi-magnify"
          density="compact"
          hide-details
          clearable
          style="min-width: 220px"
        />
        <v-text-field
          v-model="status"
          label="Статус"
          density="compact"
          hide-details
          clearable
          style="min-width: 160px"
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
          <div>{{ item.home_team || '—' }} — {{ item.away_team || '—' }}</div>
          <div class="text-caption text-medium-emphasis">
            {{ [item.country_name, item.league_name].filter(Boolean).join(': ') || '—' }}
          </div>
        </template>
        <template #item.score="{ item }">
          {{ item.score_home ?? 0 }} : {{ item.score_away ?? 0 }}
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
