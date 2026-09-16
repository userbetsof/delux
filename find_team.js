const { DatabaseSync } = require('node:sqlite');
const db = new DatabaseSync('matches.db');

console.log('=== Matches with team 172 ===');
const matches = db.prepare("SELECT match_id, home_team_id, away_team_id FROM matches WHERE home_team_id = 172 OR away_team_id = 172 LIMIT 20").all();
matches.forEach(m => console.log(m));

console.log('\n=== Check match_queue for these matches ===');
matches.forEach(m => {
  const q = db.prepare("SELECT home_name, away_name FROM match_queue WHERE match_id = ?").get(m.match_id);
  if (q) console.log(m.match_id, 'home:', q.home_name, 'away:', q.away_name);
});

db.close();
console.log('\nDone.');
