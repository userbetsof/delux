export default defineEventHandler((event) => {
  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const search = typeof q.q === 'string' ? q.q.trim() : ''
  const unmapped = String(q.unmapped || '') === '1' || String(q.unmapped || '').toLowerCase() === 'true'
  const limit = Math.min(Math.max(Number(q.limit) || 100, 1), 500)
  const offset = Math.max(Number(q.offset) || 0, 0)

  const db = openDb(dbName)
  try {
    if (!tableExists(db, 'teams')) {
      return { items: [], total: 0, limit, offset }
    }

    // колонка могла появиться позже — проверяем
    const cols = rows<{ name: string }>(db, `PRAGMA table_info(teams)`)
    const hasArb = cols.some((c) => c.name === 'name_arbworld')
    const select = hasArb ? 'id, name, name_arbworld' : 'id, name, NULL AS name_arbworld'

    const where: string[] = []
    const params: unknown[] = []
    if (search) {
      if (hasArb) {
        where.push('(name LIKE ? OR IFNULL(name_arbworld, \'\') LIKE ?)')
        params.push(`%${search}%`, `%${search}%`)
      } else {
        where.push('name LIKE ?')
        params.push(`%${search}%`)
      }
    }
    if (unmapped && hasArb) {
      where.push("(name_arbworld IS NULL OR TRIM(name_arbworld) = '')")
    }
    const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : ''

    const items = rows(
      db,
      `SELECT ${select} FROM teams ${whereSql} ORDER BY name COLLATE NOCASE LIMIT ? OFFSET ?`,
      [...params, limit, offset],
    )
    const totalRow = row<{ c: number }>(
      db,
      `SELECT COUNT(*) AS c FROM teams ${whereSql}`,
      params,
    )
    return { items, total: Number(totalRow?.c || 0), limit, offset, has_arbworld: hasArb }
  } finally {
    db.close()
  }
})
