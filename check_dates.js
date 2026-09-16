const { DatabaseSync } = require('node:sqlite');
const db = new DatabaseSync('matches.db');

// Show distinct broken patterns
console.log('=== Broken date patterns ===');
const broken = db.prepare(`
  SELECT match_date, COUNT(*) as cnt 
  FROM matches 
  WHERE match_date NOT LIKE '____.__.____ __:__' 
    AND match_date != ''
    AND match_date IS NOT NULL
  GROUP BY match_date 
  ORDER BY cnt DESC 
  LIMIT 30
`).all();
broken.forEach(r => console.log(`${r.match_date} (${r.cnt})`));

// Show some correct dates
console.log('\n=== Correct date samples ===');
const correct = db.prepare("SELECT match_date FROM matches WHERE match_date LIKE '____.__.____ __:__' LIMIT 10").all();
correct.forEach(r => console.log(r.match_date));

db.close();
