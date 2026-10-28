import { execSync } from 'node:child_process'
import { resolve } from 'node:path'

export default defineEventHandler(async (event) => {
  const body = await readBody(event).catch(() => ({}))
  const sport = body?.sport != null && body?.sport !== '' ? Number(body.sport) : null

  const scriptDir = resolve(process.cwd(), '..')

  const args: string[] = ['ratings.py', 'openskill-recalc']
  if (sport != null) {
    args.push('--sport', String(sport))
  }

  try {
    const result = execSync(`python ${args.join(' ')}`, {
      cwd: scriptDir,
      encoding: 'utf-8',
      timeout: 300000,
    })

    const lines = result.trim().split('\n')
    let teams = 0
    let matches = 0
    let durationMs = 0
    for (const line of lines) {
      const mT = line.match(/(\d+)\s+teams/)
      const mM = line.match(/(\d+)\s+matches/)
      const mD = line.match(/(\d+(?:\.\d+)?)ms/)
      if (mT) teams = Number(mT[1])
      if (mM) matches = Number(mM[1])
      if (mD) durationMs = Number(mD[1])
    }

    return { ok: true, sport, teams_processed: teams, matches_processed: matches, duration_ms: durationMs }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err)
    throw createError({
      statusCode: 500,
      statusMessage: `OpenSkill recalculation failed: ${message}`,
    })
  }
})
