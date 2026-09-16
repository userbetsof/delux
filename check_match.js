const { DatabaseSync } = require('node:sqlite');
const db = new DatabaseSync('matches.db');

console.log('=== Outcome probabilities for Q9s7530B ===');
const outs = db.prepare("SELECT * FROM outcome_probabilities WHERE match_id = ?").all('Q9s7530B');
outs.forEach(o => console.log(o));

console.log('\n=== Compare: a working match ===');
const workingMatch = db.prepare("SELECT match_id, match_status, score_home, score_away FROM matches WHERE match_status != 'Не начался' AND score_home > 0 LIMIT 1").get();
console.log('Working match:', workingMatch);

console.log('\n=== Goal probs for working match ===');
const g = db.prepare("SELECT * FROM goal_probabilities WHERE match_id = ?").get(workingMatch.match_id);
console.log(g);

console.log('\n=== Goal probs for Q9s7530B ===');
const g2 = db.prepare("SELECT * FROM goal_probabilities WHERE match_id = ?").get('Q9s7530B');
console.log(g2);

// Check how many matches have zero goal probs
console.log('\n=== Matches with all-zero goal probs ===');
const zeroGoals = db.prepare(`
  SELECT COUNT(*) as c FROM goal_probabilities 
  WHERE home_goals_1 = 0 AND home_goals_2 = 0 AND away_goals_1 = 0 AND away_goals_2 = 0
  AND home_goals_0 = 100 AND away_goals_0 = 100
`).get();
console.log('All-zero goal probs:', zeroGoals.c);

db.close();
console.log('\nDone.');
