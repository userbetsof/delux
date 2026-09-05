import type { Paginated } from '~/types/db'

export function useTablePagination(defaultLimit = 50) {
  const limit = ref(defaultLimit)
  const offset = ref(0)

  function nextPage() {
    offset.value += limit.value
  }

  function prevPage() {
    offset.value = Math.max(0, offset.value - limit.value)
  }

  function resetOffset() {
    offset.value = 0
  }

  function setLimit(value: number) {
    const n = Math.min(Math.max(Number(value) || defaultLimit, 1), 500)
    limit.value = n
    offset.value = 0
  }

  function pageLabel(data: Paginated<unknown> | null | undefined) {
    const total = data?.total || 0
    if (!total) return '0 из 0'
    const from = offset.value + 1
    const to = Math.min(offset.value + limit.value, total)
    return `${from}–${to} из ${total}`
  }

  return {
    limit,
    offset,
    nextPage,
    prevPage,
    resetOffset,
    setLimit,
    pageLabel,
  }
}
