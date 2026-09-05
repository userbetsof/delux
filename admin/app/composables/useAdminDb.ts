import type { DbName } from '~/types/db'

const STORAGE_KEY = 'delux-admin-db'

export function useAdminDb() {
  const db = useState<DbName>('admin-db', () => 'matches')

  if (import.meta.client && db.value === 'matches') {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) db.value = saved
  }

  watch(db, (value) => {
    if (import.meta.client) localStorage.setItem(STORAGE_KEY, value)
  })

  const dbQuery = computed(() => ({ db: db.value }))

  return { db, dbQuery }
}
