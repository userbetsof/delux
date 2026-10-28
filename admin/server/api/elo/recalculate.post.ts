import { openDbWrite } from '../../utils/db'
import { execSync } from 'node:child_process'
import { resolve } from 'node:path'

export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  const dbName = typeof body.db === 'string' ? body.db : 'matches'
  const sport = body.sport != null ? Number(body.sport) : null

  const dbPath = resolveDbPath(dbName)
  const scriptDir = resolve(process.cwd(), '..')
  const scriptPath = resolve(scriptDir, 'settle_elo.py')

  const args: string[] = ['settle_elo.py']
  if (sport != null) {
    args.push('--sport', String(sport))
  }

  try {
    const result = execSync(`python ${args.join(' ')}`, {
      cwd: scriptDir,
      encoding: 'utf-8',
      timeout: 300000, // 5 min max
    })

    // Parse output for stats
    const lines = result.trim().split('\n')
    let matchesProcessed = 0
    let teamsProcessed = 0
    let durationMs = 0

    for (const line of lines) {
      const mMatches = line.match(/(\d+)\s+matches/)
      const mTeams = line.match(/(\d+)\s+teams/)
      const mDuration = line.match(/(\d+(?:\.\d+)?)ms/)
      if (mMatches) matchesProcessed = Number(mMatches[1])
      if (mTeams) teamsProcessed = Number(mTeams[1])
      if (mDuration) durationMs = Number(mDuration[1])
    }

    return {
      ok: true,
      sport,
      teams_processed: teamsProcessed,
      matches_processed: matchesProcessed,
      duration_ms: durationMs,
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err)
    throw createError({
      statusCode: 500,
      statusMessage: `ELO recalculation failed: ${message}`,
    })
  }
})

function resolveDbPath(db?: string): string {
  const key = (db || 'matches').trim().toLowerCase()
  const aliases: Record<string, string> = {
    matches: 'C:/papki/work/bets/delux/matches.db',
  }
  return aliases[key] || aliases.matches
}
