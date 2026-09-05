<script setup lang="ts">
import type { Paginated } from '~/types/db'

const { dbQuery } = useAdminDb()
const matchId = ref('')
const { limit, offset, nextPage, prevPage, resetOffset, setLimit } = useTablePagination(50)

const query = computed(() => ({
  ...dbQuery.value,
  match_id: matchId.value || undefined,
  limit: limit.value,
  offset: offset.value,
}))

const { data, pending, error, refresh } = await useFetch<Paginated<Record<string, unknown>>>(
  '/api/odds',
  { query, watch: [query] },
)

const headers = [
  { title: 'ID', key: 'id' },
  { title: 'Матч', key: 'match_id' },
  { title: 'Дата', key: 'match_date' },
  { title: 'Рынок', key: 'market_name' },
  { title: 'Исход', key: 'outcome' },
  { title: 'Сторона', key: 'side' },
  { title: 'Линия', key: 'line_value' },
  { title: 'Кф', key: 'odds_value' },
]

watch([matchId, limit], resetOffset)
</script>

<template>
  <div>
    <div class="d-flex align-center justify-space-between mb-4 flex-wrap ga-2">
      <div class="text-h5 font-weight-bold">Коэффициенты</div>
      <div class="d-flex align-center ga-2">
        <v-text-field
          v-model="matchId"
          label="match_id"
          density="compact"
          hide-details
          clearable
          style="min-width: 160px"
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
        item-value="id"
        hide-default-footer
      >
        <template #item.match_id="{ item }">
          <NuxtLink :to="`/matches/${item.match_id}`">{{ item.match_id }}</NuxtLink>
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
