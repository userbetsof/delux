export default defineEventHandler(async (event) => {
  const idRaw = getRouterParam(event, 'id')
  const id = Number(idRaw)
  if (!Number.isFinite(id) || id <= 0) {
    throw createError({ statusCode: 400, statusMessage: 'Invalid team id' })
  }

  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const body = await readBody<{ name_arbworld?: string | null }>(event)
  if (!body || !('name_arbworld' in body)) {
    throw createError({ statusCode: 400, statusMessage: 'name_arbworld required' })
  }

  const alias =
    body.name_arbworld == null ? null : String(body.name_arbworld).trim() || null

  const db = openDbWrite(dbName)
  try {
    if (!tableExists(db, 'teams')) {
      throw createError({ statusCode: 404, statusMessage: 'teams table missing' })
    }
    const cols = rows<{ name: string }>(db, `PRAGMA table_info(teams)`)
    if (!cols.some((c) => c.name === 'name_arbworld')) {
      db.exec('ALTER TABLE teams ADD COLUMN name_arbworld TEXT')
    }

    const existing = row<{ id: number; name: string }>(
      db,
      'SELECT id, name FROM teams WHERE id = ?',
      [id],
    )
    if (!existing) {
      throw createError({ statusCode: 404, statusMessage: 'Team not found' })
    }

    db.prepare('UPDATE teams SET name_arbworld = ? WHERE id = ?').run(alias, id)
    const updated = row<{ id: number; name: string; name_arbworld: string | null }>(
      db,
      'SELECT id, name, name_arbworld FROM teams WHERE id = ?',
      [id],
    )
    return { ok: true, item: updated }
  } finally {
    db.close()
  }
})
