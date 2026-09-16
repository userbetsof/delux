const { DatabaseSync } = require('node:sqlite');
const db = new DatabaseSync('matches.db');

function normalizeDate(dateStr) {
  if (!dateStr || dateStr === '') return null;
  const s = dateStr.trim();
  
  // Already correct: YYYY.MM.DD HH:MM
  if (/^\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}$/.test(s)) return s;
  
  // Old format: DD.MM.YY HH:MM or DD.MM.YY H:MM
  let m = s.match(/^(\d{2})\.(\d{2})\.(\d{2}) (\d{1,2}):(\d{2})$/);
  if (m) {
    const day = m[1], month = m[2], year = 2000 + parseInt(m[3], 10);
    const hour = String(parseInt(m[4], 10)).padStart(2, '0');
    const minute = m[5];
    return `${year}.${month}.${day} ${hour}:${minute}`;
  }
  
  // Already YYYY.MM.DD but with single-digit hour: YYYY.MM.DD H:MM
  m = s.match(/^(\d{4})\.(\d{2})\.(\d{2}) (\d{1,2}):(\d{2})$/);
  if (m) {
    const year = m[1], month = m[2], day = m[3];
    const hour = String(parseInt(m[4], 10)).padStart(2, '0');
    const minute = m[5];
    return `${year}.${month}.${day} ${hour}:${minute}`;
  }
  
  return null;
}

console.log('=== Normalizing dates ===');
const all = db.prepare("SELECT id, match_id, match_date FROM matches WHERE match_date IS NOT NULL AND match_date != ''").all();
let updated = 0, unchanged = 0;

for (const row of all) {
  const norm = normalizeDate(row.match_date);
  if (norm && norm !== row.match_date) {
    db.prepare("UPDATE matches SET match_date = ? WHERE id = ?").run(norm, row.id);
    updated++;
    console.log(`  ${row.match_id}: "${row.match_date}" -> "${norm}"`);
  } else { unchanged++; }
}

console.log(`\nUpdated: ${updated}, Unchanged: ${unchanged}`);

// Fix empty dates from queue
console.log('\n=== Fixing empty dates ===');
const empty = db.prepare("SELECT m.id, m.match_id FROM matches m WHERE m.match_date IS NULL OR m.match_date = ''").all();
for (const row of empty) {
  const q = db.prepare("SELECT date_match FROM match_queue WHERE match_id = ?").get(row.match_id);
  if (q && q.date_match) {
    const norm = normalizeDate(q.date_match);
    if (norm) {
      db.prepare("UPDATE matches SET match_date = ? WHERE id = ?").run(norm, row.id);
      console.log(`  ${row.match_id}: "${norm}"`);
    }
  }
}

// Final verify
console.log('\n=== Verification ===');
const all2 = db.prepare("SELECT match_date FROM matches WHERE match_date IS NOT NULL AND match_date != ''").all();
let valid = 0, invalid = 0;
for (const r of all2) {
  if (/^\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}$/.test(r.match_date)) valid++;
  else invalid++;
}
console.log(`Valid: ${valid}, Invalid: ${invalid}`);

const emptyAfter = db.prepare("SELECT COUNT(*) as c FROM matches WHERE match_date IS NULL OR match_date = ''").get();
console.log(`Empty: ${emptyAfter.c}`);

db.close();
console.log('\nDone.');
