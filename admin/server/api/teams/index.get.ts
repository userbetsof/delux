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
    const hasVenue = cols.some((c) => c.name === 'venue_id')
    const selectParts = ['t.id', 't.name']
    selectParts.push(hasArb ? 't.name_arbworld' : 'NULL AS name_arbworld')
    selectParts.push(hasWs ? 't.name_whoscored' : 'NULL AS name_whoscored')
    if (hasVenue) {
      selectParts.push('t.venue_id')
      selectParts.push('v.venue AS venue_name')
      selectParts.push('v.town AS venue_town')
    }
    const select = selectParts.join(', ')
    const fromClause = hasVenue ? 'teams t LEFT JOIN venues v ON v.id = t.venue_id' : 'teams t'

    const where: string[] = []
    const params: unknown[] = []
    if (search) {
      const likeParts = ['t.name LIKE ?']
      params.push(`%${search}%`)
      if (hasArb) {
        likeParts.push("IFNULL(t.name_arbworld, '') LIKE ?")
        params.push(`%${search}%`)
      }
      if (hasWs) {
        likeParts.push("IFNULL(t.name_whoscored, '') LIKE ?")
        params.push(`%${search}%`)
      }
      where.push(`(${likeParts.join(' OR ')})`)
    }
    if (unmapped && hasArb) {
      where.push("(t.name_arbworld IS NULL OR TRIM(t.name_arbworld) = '')")
    }
    if (unmappedWs && hasWs) {
      where.push("(t.name_whoscored IS NULL OR TRIM(t.name_whoscored) = '')")
    }
    const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : ''

    const items = rows(
      db,
      `SELECT ${select} FROM ${fromClause} ${whereSql} ORDER BY t.name COLLATE NOCASE LIMIT ? OFFSET ?`,
      [...params, limit, offset],
    )
    const totalRow = row<{ c: number }>(
      db,
      `SELECT COUNT(*) AS c FROM teams t ${whereSql}`,
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
