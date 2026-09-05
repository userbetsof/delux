type TableSpec = {
  table: string
  orderBy: string
  join?: string
  select?: string
}

const SPECS: Record<string, TableSpec> = {
  countries: { table: 'countries', orderBy: 'name', select: 'id, name' },
  leagues: {
    table: 'leagues',
    orderBy: 'c.name, l.name',
    select: 'l.id, l.name, l.country_id, c.name AS country_name',
    join: 'leagues l LEFT JOIN countries c ON c.id = l.country_id',
  },
  teams: { table: 'teams', orderBy: 'name', select: 'id, name, name_arbworld' },
  strategies: { table: 'strategies', orderBy: 'id', select: 'id, name, description' },
  'sub-strategies': {
    table: 'sub_strategies',
    orderBy: 'id',
    select: 'id, strategy_name, description',
  },
}

export default defineEventHandler((event) => {
  const name = getRouterParam(event, 'name') || ''
  const spec = SPECS[name]
  if (!spec) {
    throw createError({ statusCode: 404, statusMessage: `Unknown table: ${name}` })
  }

  const q = getQuery(event)
  const dbName = typeof q.db === 'string' ? q.db : 'matches'
  const db = openDb(dbName)
  try {
    if (!tableExists(db, spec.table)) {
      return { items: [] }
    }
    const from = spec.join || spec.table
    const select = spec.select || '*'
    const items = rows(db, `SELECT ${select} FROM ${from} ORDER BY ${spec.orderBy}`)
    return { items }
  } finally {
    db.close()
  }
})
