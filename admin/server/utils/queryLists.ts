/**
 * Разбор мультивыбора из query-параметров.
 *
 * Поддерживаются оба формата:
 *   ?strategy_id=1,3,8   (строка с запятыми)
 *   ?strategy_id=1&strategy_id=3   (повторённый параметр — массив)
 *
 * Возвращает отфильтрованный массив чисел. Пустая строка / null / отсутствие
 * значения даёт [] (то есть «без фильтра»).
 */
export function parseNumberList(value: unknown): number[] {
  if (value == null) return []
  const raw: unknown[] = Array.isArray(value) ? value : [value]
  const out: number[] = []
  for (const item of raw) {
    if (item == null) continue
    for (const part of String(item).split(',')) {
      const trimmed = part.trim()
      if (!trimmed) continue
      const n = Number(trimmed)
      if (Number.isFinite(n) && !out.includes(n)) out.push(n)
    }
  }
  return out
}

/**
 * Построить SQL-условие «колонка IN (...)» для списка чисел.
 * Возвращает null, если список пуст (фильтр не нужен).
 */
export function sqlInList(
  column: string,
  values: number[],
): { clause: string; params: unknown[] } | null {
  if (!values.length) return null
  const placeholders = values.map(() => '?').join(', ')
  return { clause: `${column} IN (${placeholders})`, params: [...values] }
}
