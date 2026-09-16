<script setup lang="ts">
import type { Paginated } from '~/types/db'

const { dbQuery } = useAdminDb()
const { limit, offset, nextPage, prevPage, resetOffset, setLimit } = useTablePagination(50)

const query = computed(() => ({
  ...dbQuery.value,
  limit: limit.value,
  offset: offset.value,
}))

const { data, pending, error, refresh } = await useFetch<Paginated<Record<string, unknown>>>(
  '/api/goals',
  { query, watch: [query] },
)

const headers = [
  { title: 'ID', key: 'id' },
  { title: 'Матч', key: 'match_id' },
  ...Array.from({ length: 13 }, (_, n) => ({ title: `Д${n}`, key: `home_goals_${n}` })),
  ...Array.from({ length: 13 }, (_, n) => ({ title: `Г${n}`, key: `away_goals_${n}` })),
]

watch(limit, resetOffset)
</script>

<template>
  <div>
    <div class="d-flex align-center justify-space-between mb-4">
      <div class="text-h5 font-weight-bold">Вероятности голов</div>
      <v-btn variant="outlined" :loading="pending" @click="refresh()">Обновить</v-btn>
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
