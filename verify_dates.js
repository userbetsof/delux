const { DatabaseSync } = require('node:sqlite');
const db = new DatabaseSync('matches.db');

console.log('=== Date format check ===');

// Check all dates are valid YYYY.MM.DD HH:MM format
const all = db.prepare("SELECT id, match_date FROM matches WHERE match_date IS NOT NULL AND match_date != ''").all();
let valid = 0, invalid = 0;
const invalidSamples = [];

for (const row of all) {
  if (/^\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}$/.test(row.match_date)) {
    valid++;
  } else {
    invalid++;
    if (invalidSamples.length < 10) invalidSamples.push(row.match_date);
  }
}

console.log(`Valid: ${valid}`);
console.log(`Invalid: ${invalid}`);
if (invalidSamples.length > 0) {
  console.log('Invalid samples:', invalidSamples);
}

const empty = db.prepare("SELECT COUNT(*) as c FROM matches WHERE match_date IS NULL OR match_date = ''").get();
console.log(`Empty: ${empty.c}`);

console.log('\n=== Sample dates ===');
db.prepare("SELECT match_date FROM matches ORDER BY id LIMIT 5").all().forEach(r => console.log(r.match_date));
console.log('...');
db.prepare("SELECT match_date FROM matches ORDER BY id DESC LIMIT 5").all().forEach(r => console.log(r.match_date));

db.close();
console.log('\nDone.');
