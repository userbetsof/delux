<script setup lang="ts">
import type { MatchRow, Paginated } from '~/types/db'
import { sportLabel } from '~/types/db'

const { dbQuery } = useAdminDb()
const search = ref('')
const status = ref('')
const sport = ref<number | null>(null)
const dateMenu = ref(false)
const dateFrom = ref<string | null>(null)
const dateTo = ref<string | null>(null)
const { limit, offset, nextPage, prevPage, resetOffset, setLimit } = useTablePagination(50)

function formatDate(d: Date | null): string | null {
  if (!d) return null
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function parseDate(val: string | number): Date | null {
  if (!val) return null
  return new Date(val)
}

const dateRange = computed<Date[]>({
  get: () => {
    if (dateFrom.value && dateTo.value) {
      return [new Date(dateFrom.value), new Date(dateTo.value)]
    }
    return []
  },
  set: (val: Date[]) => {
    if (val.length >= 2) {
      dateFrom.value = formatDate(val[0])
      dateTo.value = formatDate(val[1])
    }
  },
})

const dateLabel = computed(() => {
  const parts: string[] = []
  if (dateFrom.value) parts.push(dateFrom.value)
  if (dateTo.value) parts.push(dateTo.value)
  return parts.length ? parts.join(' — ') : ''
})

function clearDate() {
  dateFrom.value = null
  dateTo.value = null
  dateMenu.value = false
}

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

const query = computed(() => ({
  ...dbQuery.value,
  q: search.value || undefined,
  status: status.value || undefined,
  sport: sport.value ?? undefined,
  date_from: dateFrom.value || undefined,
  date_to: dateTo.value || undefined,
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

watch([search, status, sport, dateFrom, dateTo, limit], resetOffset)
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
        <v-menu v-model="dateMenu" transition="slide-y-transition">
          <template #activator="{ props }">
            <v-text-field
              v-bind="props"
              :label="dateLabel || 'Дата'"
              prepend-inner-icon="mdi-calendar-range"
              density="compact"
              hide-details
              clearable
              style="min-width: 200px"
              :value="dateLabel || undefined"
            />
          </template>
          <v-date-picker
            v-model="dateRange"
            mode="range"
            density="compact"
            color="primary"
          >
            <template #append>
              <v-btn variant="text" color="error" @click.stop="clearDate">Очистить</v-btn>
              <v-btn variant="tonal" @click="dateMenu = false">Готово</v-btn>
            </template>
          </v-date-picker>
        </v-menu>
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
        <template #item.match_date="{ item }">
          {{ formatMatchDate(item.match_date) }}
        </template>
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
