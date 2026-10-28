import { existsSync } from 'node:fs'
import { resolve, basename } from 'node:path'
import { DatabaseSync } from 'node:sqlite'

const ROOT = resolve(process.cwd(), '..')

const DB_ALIASES: Record<string, string> = {
  matches: 'C:/papki/work/bets/delux/matches.db',
  parity_excel: resolve(ROOT, 'data', 'parity_excel.db'),
  parity_python: resolve(ROOT, 'data', 'parity_python.db'),
}

export type DbAlias = keyof typeof DB_ALIASES

export function resolveDbPath(db?: string | null): string {
  const key = (db || 'matches').trim().toLowerCase()
  if (key in DB_ALIASES) return DB_ALIASES[key as DbAlias]
  const custom = resolve(ROOT, key)
  if (existsSync(custom)) return custom
  return DB_ALIASES.matches
}

export function openDb(db?: string | null): DatabaseSync {
  const path = resolveDbPath(db)
  if (!existsSync(path)) {
    throw createError({
      statusCode: 404,
      statusMessage: `DB not found: ${path}`,
    })
  }
  // readOnly требует, чтобы файл уже существовал
  return new DatabaseSync(path, { readOnly: true })
}

/** Запись только в разрешённые БД (маппинг команд и т.п.). */
export function openDbWrite(db?: string | null): DatabaseSync {
  const key = (db || 'matches').trim().toLowerCase()
  if (key !== 'matches') {
    throw createError({
      statusCode: 403,
      statusMessage: 'Write allowed only for matches.db',
    })
  }
  const path = resolveDbPath(key)
  if (!existsSync(path)) {
    throw createError({
      statusCode: 404,
      statusMessage: `DB not found: ${path}`,
    })
  }
  return new DatabaseSync(path, { readOnly: false })
}

export function rows<T extends Record<string, unknown> = Record<string, unknown>>(
  db: DatabaseSync,
  sql: string,
  params: unknown[] = [],
): T[] {
  return db.prepare(sql).all(...params) as T[]
}

export function row<T extends Record<string, unknown> = Record<string, unknown>>(
  db: DatabaseSync,
  sql: string,
  params: unknown[] = [],
): T | null {
  const result = db.prepare(sql).get(...params) as T | undefined
  return result ?? null
}

export function tableExists(db: DatabaseSync, name: string): boolean {
  const r = row<{ c: number }>(
    db,
    `SELECT COUNT(*) AS c FROM sqlite_master WHERE type = 'table' AND name = ?`,
    [name],
  )
  return Boolean(r && Number(r.c) > 0)
}

export function dbLabel(path: string): string {
  return basename(path)
}

export { DB_ALIASES, ROOT }
