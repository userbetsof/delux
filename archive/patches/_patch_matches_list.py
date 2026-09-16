from pathlib import Path

p = Path(r"c:\papki\work\bets\delux\matches_list.py")
t = p.read_text(encoding="utf-8")
old = """    for idx, sport_id in enumerate(sports):
        matches = _fetch_sport_matches(
            sport_id,
            ms.sourcer,
            ms.suffix,
            cfg.timezone,
            cfg.dayzone,
            cfg.time_offset,
        )
        sport_leagues = cfg.leagues_for_sport(sport_id)
        if sport_leagues:
            filtered = [m for m in matches if _league_allowed(m.get("league_name") or "", sport_leagues)]
        else:
            filtered = matches
        if idx == 0:
            last_row = ws_list.Cells(ws_list.Rows.Count, "A").End(-4162).Row
            if last_row >= 2:
                ws_list.Rows(f"2:{last_row}").Delete()
            row = 2
        else:
            row = ws_list.Cells(ws_list.Rows.Count, "A").End(-4162).Row + 1
            if row < 2:
                row = 2

        if not filtered:
            continue
"""
new = """    for idx, sport_id in enumerate(sports):
        try:
            matches = _fetch_sport_matches(
                sport_id,
                ms.sourcer,
                ms.suffix,
                cfg.timezone,
                cfg.dayzone,
                cfg.time_offset,
            )
        except Exception as exc:
            print(f"[-] sport={sport_id}: feed unavailable ({exc})")
            matches = []
        sport_leagues = cfg.leagues_for_sport(sport_id)
        if sport_leagues:
            filtered = [m for m in matches if _league_allowed(m.get("league_name") or "", sport_leagues)]
        else:
            filtered = matches
        if idx == 0:
            last_row = ws_list.Cells(ws_list.Rows.Count, "A").End(-4162).Row
            if last_row >= 2:
                ws_list.Rows(f"2:{last_row}").Delete()
            row = 2
        else:
            row = ws_list.Cells(ws_list.Rows.Count, "A").End(-4162).Row + 1
            if row < 2:
                row = 2

        if not filtered:
            print(f"[!] sport={sport_id}: 0 matches after league filter (raw={len(matches)})")
            continue
"""
if old not in t:
    raise SystemExit("pattern not found")
p.write_text(t.replace(old, new, 1), encoding="utf-8")
print("ok")
