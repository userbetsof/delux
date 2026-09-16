export default defineEventHandler((event) => {
  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const search = typeof q.q === 'string' ? q.q.trim() : ''
  const unmapped = String(q.unmapped || '') === '1' || String(q.unmapped || '').toLowerCase() === 'true'
  const unmappedWs =
    String(q.unmapped_ws || '') === '1' || String(q.unmapped_ws || '').toLowerCase() === 'true'
  const limit = Math.min(Math.max(Number(q.limit) || 100, 1), 500)
  const offset = Math.max(Number(q.offset) || 0, 0)

  const db = openDb(dbName)
  try {
    if (!tableExists(db, 'teams')) {
      return { items: [], total: 0, limit, offset }
    }

    // колонки могли появиться позже — проверяем
    const cols = rows<{ name: string }>(db, `PRAGMA table_info(teams)`)
    const hasArb = cols.some((c) => c.name === 'name_arbworld')
    const hasWs = cols.some((c) => c.name === 'name_whoscored')
    const selectParts = ['id', 'name']
    selectParts.push(hasArb ? 'name_arbworld' : 'NULL AS name_arbworld')
    selectParts.push(hasWs ? 'name_whoscored' : 'NULL AS name_whoscored')
    const select = selectParts.join(', ')

    const where: string[] = []
    const params: unknown[] = []
    if (search) {
      const likeParts = ['name LIKE ?']
      params.push(`%${search}%`)
      if (hasArb) {
        likeParts.push("IFNULL(name_arbworld, '') LIKE ?")
        params.push(`%${search}%`)
      }
      if (hasWs) {
        likeParts.push("IFNULL(name_whoscored, '') LIKE ?")
        params.push(`%${search}%`)
      }
      where.push(`(${likeParts.join(' OR ')})`)
    }
    if (unmapped && hasArb) {
      where.push("(name_arbworld IS NULL OR TRIM(name_arbworld) = '')")
    }
    if (unmappedWs && hasWs) {
      where.push("(name_whoscored IS NULL OR TRIM(name_whoscored) = '')")
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
    return {
      items,
      total: Number(totalRow?.c || 0),
      limit,
      offset,
      has_arbworld: hasArb,
      has_whoscored: hasWs,
    }
  } finally {
    db.close()
  }
})
