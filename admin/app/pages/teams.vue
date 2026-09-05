<script setup lang="ts">
import type { Paginated } from '~/types/db'

type TeamRow = {
  id: number
  name: string
  name_arbworld?: string | null
}

const { db, dbQuery } = useAdminDb()
const search = ref('')
const unmappedOnly = ref(false)
const { limit, offset, nextPage, prevPage, resetOffset, setLimit } = useTablePagination(50)

const drafts = ref<Record<number, string>>({})
const savingId = ref<number | null>(null)
const saveError = ref('')
const saveOk = ref('')

const query = computed(() => ({
  ...dbQuery.value,
  q: search.value || undefined,
  unmapped: unmappedOnly.value ? '1' : undefined,
  limit: limit.value,
  offset: offset.value,
}))

const { data, pending, error, refresh } = await useFetch<
  Paginated<TeamRow> & { has_arbworld?: boolean }
>('/api/teams', {
  query,
  watch: [query],
})

watch(
  () => data.value?.items,
  (items) => {
    const next: Record<number, string> = { ...drafts.value }
    for (const t of items || []) {
      if (!(t.id in next)) {
        next[t.id] = t.name_arbworld || ''
      }
    }
    drafts.value = next
  },
  { immediate: true },
)

watch([search, unmappedOnly, limit], resetOffset)

const headers = [
  { title: 'ID', key: 'id', width: '80px' },
  { title: 'Flashscore', key: 'name' },
  { title: 'Arbworld', key: 'name_arbworld' },
  { title: '', key: 'actions', sortable: false, width: '120px' },
]

function dirty(item: TeamRow) {
  const cur = (drafts.value[item.id] ?? '').trim()
  const orig = (item.name_arbworld || '').trim()
  return cur !== orig
}

async function saveTeam(item: TeamRow) {
  saveError.value = ''
  saveOk.value = ''
  savingId.value = item.id
  try {
    const name_arbworld = (drafts.value[item.id] ?? '').trim() || null
    await $fetch(`/api/teams/${item.id}`, {
      method: 'PATCH',
      query: { db: db.value },
      body: { name_arbworld },
    })
    saveOk.value = `Сохранено: ${item.name}`
    await refresh()
    drafts.value[item.id] = name_arbworld || ''
  } catch (e: unknown) {
    const err = e as { data?: { statusMessage?: string }; message?: string }
    saveError.value = err?.data?.statusMessage || err?.message || String(e)
  } finally {
    savingId.value = null
  }
}

function copyFs(item: TeamRow) {
  drafts.value[item.id] = item.name
}
</script>

<template>
  <div>
    <div class="d-flex align-center justify-space-between mb-4 flex-wrap ga-2">
      <div>
        <div class="text-h5 font-weight-bold">Команды</div>
        <div class="text-caption text-medium-emphasis">
          name = Flashscore; name_arbworld — имя в Arbworld (для Moneyway)
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
              v-model="drafts[item.id]"
              density="compact"
              hide-details
              variant="outlined"
              placeholder="имя в Arbworld"
              style="min-width: 220px"
              :class="{ 'bg-amber-lighten-5': dirty(item) }"
            />
            <v-btn
              icon="mdi-content-copy"
              size="x-small"
              variant="text"
              title="Скопировать Flashscore"
              @click="copyFs(item)"
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
