# TODO: Implement Updated Odds Table Insert from Excel "Коэффициенты" Sheet

## Approved Plan Breakdown (Logical Steps)

### Step 1: ✅ Fix odds table schema in db.py
- Updated CREATE TABLE odds to per-market structure.
- Temporarily disabled old INSERT to avoid column mismatch.
- Add `odds_value DECIMAL(10,2)` column.
- Repurpose: keep `market_name` (header e.g. 'OVER 2.5'), `line_value DECIMAL(5,2)` (parsed 2.5), `odds_value`.
- Drop/replace fixed 1X2 columns or make generic.
- Handle `outcome`/`side` if needed (implicit from name).

### Step 2: ✅ Create `read_full_odds_sheet(excel_path)` function
### Step 4: ✅ Integrate into main flow
- read_excel_file now reads archive + calls read_full_odds_sheet.
- data['odds_data'] available in insert_match_data.
- Added full parser for odds sheet: row1 headers, row3 values.
- Parses market_name, outcome, side, line_value via regex.
- Returns dict with home_id, away_id, list of markets.
- Integrated as read_excel_file calls it (stub).
- Load SHEET_ODDS.
- Read row 1: headers list.
- Read row 3: values list.
- Parse each header-value pair → dict {'market_name': header, 'line_value': parsed or NULL, 'odds_value': float(val)}.
- Extract HOME_ID, AWAY_ID from cols 1,2 row3.
- Return odds_data dict/list.

### Step 3: [PENDING] Update `insert_match_data(item, excel_path)`
- After match insert: DELETE existing odds for match_id.
- Get odds_data = read_full_odds_sheet(excel_path).
- For each market: INSERT OR REPLACE INTO odds (match_id, market_name, line_value, odds_value) VALUES(...).
- Parse logic: regex for OVER/UNDER (\d+\.?\d*), HANDICAP HOME/AWAY, etc.

### Step 4: [PENDING] Integrate into main flow
- Pass excel_file_path to insert_match_data.
- Update read_excel_file callers.
- Test single match first (current logic).

### Step 5: [PENDING] Verify & Test
- Run `python db.py`.
- Check `sqlite3 matches.db "SELECT * FROM odds;"`.
- Handle multiples if needed later.

## Progress Tracking
- Update this file after each step completion.
- When all ✅, delete or mark COMPLETE.

