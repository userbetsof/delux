<script setup lang="ts">
const { dbQuery } = useAdminDb()
const { data, pending, error, refresh } = await useFetch<{ items: Record<string, unknown>[] }>(
  '/api/table/leagues',
  { query: dbQuery, watch: [dbQuery] },
)
const headers = [
  { title: 'ID', key: 'id' },
  { title: 'Страна', key: 'country_name' },
  { title: 'Лига', key: 'name' },
]
</script>

<template>
  <div>
    <div class="d-flex align-center justify-space-between mb-4">
      <div class="text-h5 font-weight-bold">Лиги</div>
      <v-btn variant="outlined" :loading="pending" @click="refresh()">Обновить</v-btn>
    </div>
    <v-alert v-if="error" type="error" class="mb-3" density="compact">{{ error.message || error }}</v-alert>
    <v-card>
      <v-data-table
        :headers="headers"
        :items="data?.items || []"
        :loading="pending"
        item-value="id"
      />
    </v-card>
  </div>
</template>
