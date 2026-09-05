<script setup lang="ts">
import type { Paginated } from '~/types/db'

const { dbQuery } = useAdminDb()
const matchId = ref('')
const signal = ref<string | null>(null)
const found = ref<string | null>(null)
const { limit, offset, nextPage, prevPage, resetOffset, setLimit } = useTablePagination(50)

const signalItems = [
  { title: 'Все', value: null },
  { title: 'С сигналом', value: '1' },
  { title: 'Без сигнала', value: '0' },
]
const foundItems = [
  { title: 'Все', value: null },
  { title: 'Найден в Arbworld', value: '1' },
  { title: 'Не найден', value: '0' },
]

const query = computed(() => ({
  ...dbQuery.value,
  match_id: matchId.value || undefined,
  signal: signal.value || undefined,
  found: found.value || undefined,
  limit: limit.value,
  offset: offset.value,
}))

const { data, pending, error, refresh } = await useFetch<Paginated<Record<string, unknown>>>(
  '/api/moneyway',
  { query, watch: [query] },
)

const headers = [
  { title: 'Матч', key: 'match_id' },
  { title: 'Дата', key: 'match_date' },
  { title: 'Команды', key: 'teams' },
  { title: 'Found', key: 'found' },
  { title: 'Кф 1/X/2', key: 'coefs' },
  { title: 'Vol 1/X/2', key: 'vols' },
  { title: 'Сигнал', key: 'signal' },
  { title: 'Лига AW', key: 'league' },
  { title: 'Fetched', key: 'fetched_at' },
]

watch([matchId, signal, found, limit], resetOffset)
</script>

<template>
  <div>
    <div class="d-flex align-center justify-space-between mb-4 flex-wrap ga-2">
      <div>
        <div class="text-h5 font-weight-bold">Moneyway</div>
        <div class="text-caption text-medium-emphasis">
          Снимки Arbworld по каждому проанализированному футбольному матчу
        </div>
      </div>
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
          v-model="found"
          :items="foundItems"
          label="Found"
          density="compact"
          hide-details
          style="min-width: 160px"
        />
        <v-select
          v-model="signal"
          :items="signalItems"
          label="Сигнал"
          density="compact"
          hide-details
          style="min-width: 150px"
        />
        <v-btn variant="outlined" :loading="pending" @click="refresh()">Обновить</v-btn>
      </div>
    </div>

    <v-alert v-if="error" type="error" class="mb-3" density="compact">
      {{ error.message || error }}
    </v-alert>

    <v-card>
      <v-data-table
        :headers="headers"
        :items="data?.items || []"
        :loading="pending"
        item-value="match_id"
        hide-default-footer
        density="compact"
      >
        <template #item.match_id="{ item }">
          <NuxtLink :to="`/matches/${item.match_id}`">{{ item.match_id }}</NuxtLink>
        </template>
        <template #item.teams="{ item }">
          <div>{{ item.home_name || item.home_team || '—' }} — {{ item.away_name || item.away_team || '—' }}</div>
          <div v-if="item.score_home != null" class="text-caption text-medium-emphasis">
            {{ item.score_home }} : {{ item.score_away }} · {{ item.match_status || '' }}
          </div>
        </template>
        <template #item.found="{ item }">
          <v-chip size="x-small" :color="item.found ? 'success' : 'default'" variant="tonal">
            {{ item.found ? 'yes' : 'no' }}
          </v-chip>
        </template>
        <template #item.coefs="{ item }">
          <span v-if="item.found">{{ item.coef_1 }} / {{ item.coef_x }} / {{ item.coef_2 }}</span>
          <span v-else class="text-medium-emphasis">—</span>
        </template>
        <template #item.vols="{ item }">
          <span v-if="item.found">{{ item.volume_1 }} / {{ item.volume_x }} / {{ item.volume_2 }}</span>
          <span v-else class="text-medium-emphasis">—</span>
        </template>
        <template #item.signal="{ item }">
          <template v-if="item.has_signal">
            <v-chip size="small" color="primary" variant="tonal">
              {{ item.signal_side }} @ {{ item.signal_odds }}
            </v-chip>
          </template>
          <span v-else class="text-medium-emphasis">—</span>
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
