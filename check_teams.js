const { DatabaseSync } = require('node:sqlite');
const db = new DatabaseSync('matches.db');

console.log('=== NULL team_ids ===');
const nullHome = db.prepare("SELECT COUNT(*) as c FROM matches WHERE home_team_id IS NULL").get();
const nullAway = db.prepare("SELECT COUNT(*) as c FROM matches WHERE away_team_id IS NULL").get();
console.log('NULL home_team_id:', nullHome.c);
console.log('NULL away_team_id:', nullAway.c);

console.log('\n=== Empty team names (teams table) ===');
const emptyNames = db.prepare("SELECT COUNT(*) as c FROM teams WHERE name IS NULL OR name = ''").get();
console.log('Empty team names:', emptyNames.c);

console.log('\n=== Total teams ===');
const totalTeams = db.prepare("SELECT COUNT(*) as c FROM teams").get();
console.log('Total teams:', totalTeams.c);

console.log('\n=== Total matches ===');
const totalMatches = db.prepare("SELECT COUNT(*) as c FROM matches").get();
console.log('Total matches:', totalMatches.c);

db.close();
console.log('\nDone.');
