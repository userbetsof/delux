<script setup lang="ts">
import type { Paginated } from '~/types/db'

type TeamRow = {
  id: number
  name: string
  name_arbworld?: string | null
  name_whoscored?: string | null
}

const { db, dbQuery } = useAdminDb()
const search = ref('')
const unmappedOnly = ref(false)
const unmappedWsOnly = ref(false)
const { limit, offset, nextPage, prevPage, resetOffset, setLimit } = useTablePagination(50)

const draftsArb = ref<Record<number, string>>({})
const draftsWs = ref<Record<number, string>>({})
const savingId = ref<number | null>(null)
const saveError = ref('')
const saveOk = ref('')

const query = computed(() => ({
  ...dbQuery.value,
  q: search.value || undefined,
  unmapped: unmappedOnly.value ? '1' : undefined,
  unmapped_ws: unmappedWsOnly.value ? '1' : undefined,
  limit: limit.value,
  offset: offset.value,
}))

const { data, pending, error, refresh } = await useFetch<
  Paginated<TeamRow> & { has_arbworld?: boolean; has_whoscored?: boolean }
>('/api/teams', {
  query,
  watch: [query],
})

watch(
  () => data.value?.items,
  (items) => {
    const nextArb: Record<number, string> = { ...draftsArb.value }
    const nextWs: Record<number, string> = { ...draftsWs.value }
    for (const t of items || []) {
      if (!(t.id in nextArb)) nextArb[t.id] = t.name_arbworld || ''
      if (!(t.id in nextWs)) nextWs[t.id] = t.name_whoscored || ''
    }
    draftsArb.value = nextArb
    draftsWs.value = nextWs
  },
  { immediate: true },
)

watch([search, unmappedOnly, unmappedWsOnly, limit], resetOffset)

const headers = [
  { title: 'ID', key: 'id', width: '80px' },
  { title: 'Flashscore', key: 'name' },
  { title: 'Arbworld', key: 'name_arbworld' },
  { title: 'WhoScored', key: 'name_whoscored' },
  { title: '', key: 'actions', sortable: false, width: '120px' },
]

function dirtyArb(item: TeamRow) {
  return (draftsArb.value[item.id] ?? '').trim() !== (item.name_arbworld || '').trim()
}

function dirtyWs(item: TeamRow) {
  return (draftsWs.value[item.id] ?? '').trim() !== (item.name_whoscored || '').trim()
}

function dirty(item: TeamRow) {
  return dirtyArb(item) || dirtyWs(item)
}

async function saveTeam(item: TeamRow) {
  saveError.value = ''
  saveOk.value = ''
  savingId.value = item.id
  try {
    const name_arbworld = (draftsArb.value[item.id] ?? '').trim() || null
    const name_whoscored = (draftsWs.value[item.id] ?? '').trim() || null
    await $fetch(`/api/teams/${item.id}`, {
      method: 'PATCH',
      query: { db: db.value },
      body: { name_arbworld, name_whoscored },
    })
    saveOk.value = `Сохранено: ${item.name}`
    await refresh()
    draftsArb.value[item.id] = name_arbworld || ''
    draftsWs.value[item.id] = name_whoscored || ''
  } catch (e: unknown) {
    const err = e as { data?: { statusMessage?: string }; message?: string }
    saveError.value = err?.data?.statusMessage || err?.message || String(e)
  } finally {
    savingId.value = null
  }
}

function copyFsArb(item: TeamRow) {
  draftsArb.value[item.id] = item.name
}

function copyFsWs(item: TeamRow) {
  draftsWs.value[item.id] = item.name
}
</script>

<template>
  <div>
    <div class="d-flex align-center justify-space-between mb-4 flex-wrap ga-2">
      <div>
        <div class="text-h5 font-weight-bold">Команды</div>
        <div class="text-caption text-medium-emphasis">
          Flashscore → Arbworld (Moneyway) и WhoScored (стратегия #9)
        </div>
      </div>
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
        <v-switch
          v-model="unmappedOnly"
          label="Без Arbworld"
          density="compact"
          hide-details
          color="primary"
        />
        <v-switch
          v-model="unmappedWsOnly"
          label="Без WhoScored"
          density="compact"
          hide-details
          color="primary"
        />
        <v-btn variant="outlined" :loading="pending" @click="refresh()">Обновить</v-btn>
      </div>
    </div>

    <v-alert v-if="error" type="error" class="mb-3" density="compact">
      {{ error.message || error }}
    </v-alert>
    <v-alert v-if="saveError" type="error" class="mb-3" density="compact" closable>
      {{ saveError }}
    </v-alert>
    <v-alert v-if="saveOk" type="success" class="mb-3" density="compact" closable>
      {{ saveOk }}
    </v-alert>

    <v-card>
      <v-data-table
        :headers="headers"
        :items="data?.items || []"
        :loading="pending"
        item-value="id"
        hide-default-footer
        density="compact"
      >
        <template #item.name="{ item }">
          <div class="font-weight-medium">{{ item.name }}</div>
        </template>
        <template #item.name_arbworld="{ item }">
          <div class="d-flex align-center ga-1">
            <v-text-field
              v-model="draftsArb[item.id]"
              density="compact"
              hide-details
              variant="outlined"
              placeholder="имя в Arbworld"
              style="min-width: 200px"
              :class="{ 'bg-amber-lighten-5': dirtyArb(item) }"
            />
            <v-btn
              icon="mdi-content-copy"
              size="x-small"
              variant="text"
              title="Скопировать Flashscore"
              @click="copyFsArb(item)"
            />
          </div>
        </template>
        <template #item.name_whoscored="{ item }">
          <div class="d-flex align-center ga-1">
            <v-text-field
              v-model="draftsWs[item.id]"
              density="compact"
              hide-details
              variant="outlined"
              placeholder="имя в WhoScored"
              style="min-width: 200px"
              :class="{ 'bg-amber-lighten-5': dirtyWs(item) }"
            />
            <v-btn
              icon="mdi-content-copy"
              size="x-small"
              variant="text"
              title="Скопировать Flashscore"
              @click="copyFsWs(item)"
            />
          </div>
        </template>
        <template #item.actions="{ item }">
          <v-btn
            size="small"
            color="primary"
            variant="tonal"
            :disabled="!dirty(item)"
            :loading="savingId === item.id"
            @click="saveTeam(item)"
          >
            Сохранить
          </v-btn>
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
