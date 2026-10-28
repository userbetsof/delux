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
const dateMenu = ref(false)
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

const query = computed(() => ({
  ...dbQuery.value,
  q: search.value || undefined,
  sport: sport.value ?? undefined,
  date_from: dateFrom.value || undefined,
  date_to: dateTo.value || undefined,
  limit: limit.value,
  offset: offset.value,
}))

const { data, pending, error, refresh } = await useFetch<Paginated<QueueRow>>('/api/queue', {
  query,
  watch: [query],
})

const headers = [
  { title: 'ID', key: 'match_id', width: '140px' },
  { title: 'Дата', key: 'date_match', width: '160px' },
  { title: 'Лига', key: 'tour_name', width: '150px' },
  { title: 'Матч', key: 'fixture' },
  { title: '1 / X / 2', key: 'odds', width: '160px' },
  { title: 'Спорт', key: 'sport', width: '100px' },
]

const sportItems = [
  { title: 'Все', value: null },
  { title: 'Футбол', value: 1 },
  { title: 'Баскетбол', value: 3 },
  { title: 'Хоккей', value: 4 },
  { title: 'Бейсбол', value: 6 },
]

watch([search, sport, dateFrom, dateTo, limit], resetOffset)
</script>

<template>
  <div>
    <!-- Page Header -->
    <div class="page-header mb-5">
      <div class="page-title">Очередь матчей</div>
    </div>

    <!-- Filters -->
    <div class="filter-section">
      <v-row dense>
        <v-col cols="12" sm="6" md="3">
          <v-text-field
            v-model="search"
            label="Поиск"
            prepend-inner-icon="mdi-magnify"
            density="compact"
            hide-details
            clearable
            variant="outlined"
          />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-select
            v-model="sport"
            :items="sportItems"
            label="Спорт"
            density="compact"
            hide-details
            variant="outlined"
          />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-menu v-model="dateMenu" transition="slide-y-transition">
            <template #activator="{ props }">
              <v-text-field
                v-bind="props"
                :label="dateLabel || 'Дата'"
                prepend-inner-icon="mdi-calendar-range"
                density="compact"
                hide-details
                clearable
                variant="outlined"
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
        </v-col>
        <v-col cols="12" sm="6" md="2" class="d-flex align-end">
          <v-btn
            variant="outlined"
            :loading="pending"
            @click="refresh()"
            color="primary"
            full-width
          >
            <v-icon start>mdi-refresh</v-icon>
            Обновить
          </v-btn>
        </v-col>
      </v-row>
    </div>

    <!-- Alerts -->
    <v-alert v-if="error" type="error" class="mb-3" density="compact" rounded="lg">
      {{ error.message || error }}
    </v-alert>
    <v-alert
      v-else-if="!pending && (data?.total || 0) === 0"
      type="info"
      class="mb-3"
      density="compact"
      rounded="lg"
    >
      Таблица match_queue пуста или отсутствует в выбранной БД.
    </v-alert>

    <!-- Table -->
    <div class="content-card">
      <v-data-table
        :headers="headers"
        :items="data?.items || []"
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
        <template #item.fixture="{ item }">
          <div class="font-weight-medium">
            {{ item.home_name || '—' }} — {{ item.away_name || '—' }}
          </div>
          <div v-if="item.tour_name" class="text-caption text-medium-emphasis">
            {{ item.tour_name }}
          </div>
        </template>
        <template #item.odds="{ item }">
          <div class="d-flex gap-2">
            <v-chip size="small" variant="tonal" color="success">
              {{ item.current_home || item.start_home || '—' }}
            </v-chip>
            <v-chip size="small" variant="tonal" color="warning">
              {{ item.current_draw || item.start_draw || '—' }}
            </v-chip>
            <v-chip size="small" variant="tonal" color="error">
              {{ item.current_away || item.start_away || '—' }}
            </v-chip>
          </div>
        </template>
        <template #item.sport="{ item }">
          <v-chip size="small" variant="outlined" color="text-secondary">
            {{ sportLabel(item.sport) }}
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
.gap-2 {
  gap: 6px;
}
</style>
