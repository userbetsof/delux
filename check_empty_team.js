const { DatabaseSync } = require('node:sqlite');
const db = new DatabaseSync('matches.db');

console.log('=== Teams with empty name ===');
const empty = db.prepare("SELECT id, name, name_arbworld, name_whoscored FROM teams WHERE name IS NULL OR name = ''").all();
empty.forEach(r => console.log(r));

console.log('\n=== Matches referencing this team ===');
if (empty.length > 0) {
  const teamId = empty[0].id;
  const matches = db.prepare("SELECT match_id, home_team_id, away_team_id FROM matches WHERE home_team_id = ? OR away_team_id = ?").all(teamId, teamId);
  matches.forEach(r => console.log(r));
}

db.close();
console.log('\nDone.');
