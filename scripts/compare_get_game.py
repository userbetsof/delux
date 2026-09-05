"""Сверка Python get_game vs baseline архива / ячеек Анализа для match_id."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from excel_com import connect_excel, open_workbook, restore_excel_ui, snapshot_excel_ui  # noqa: E402
from get_game import get_game  # noqa: E402
from sheets_config import SHEET_ANALYSIS, SHEET_HOME_HOME, SHEET_TABLE  # noqa: E402


def _s(v):
    if v is None:
        return ""
    return str(v).strip()


def _f(v):
    try:
        if v is None or v == "":
            return None
        if isinstance(v, str) and (v.startswith("#") or v.upper() == "RISK"):
            return None
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def snapshot(wb, match_id: str) -> dict:
    ws = wb.Worksheets(SHEET_ANALYSIS)
    ws_t = wb.Worksheets(SHEET_TABLE)
    ws_hh = wb.Worksheets(SHEET_HOME_HOME)

    def unique_teams(start_col: int) -> int:
        teams = set()
        for r in range(2, 200):
            name = _s(ws_t.Cells(r, start_col + 1).Value)
            if not name:
                break
            teams.add(name)
        return len(teams)

    def hist_rows() -> int:
        n = 0
        for r in range(2, 200):
            if _s(ws_hh.Cells(r, 1).Value):
                n += 1
            else:
                break
        return n

    archive = {}
    try:
        ws_a = wb.Worksheets("achive")
        last = ws_a.Cells(ws_a.Rows.Count, "A").End(-4162).Row
        for r in range(2, last + 1):
            if _s(ws_a.Range(f"A{r}").Value) == match_id:
                archive = {
                    "row": r,
                    "K": _s(ws_a.Range(f"K{r}").Value),
                    "O": _s(ws_a.Range(f"O{r}").Value),
                    "S": _s(ws_a.Range(f"S{r}").Value),
                    "L": _s(ws_a.Range(f"L{r}").Value),
                    "T": _s(ws_a.Range(f"T{r}").Value),
                }
                break
    except Exception:
        pass

    return {
        "match_id": match_id,
        "S13": _s(ws.Range("S13").Value),
        "O10": _s(ws.Range("O10").Value),
        "X24": _s(ws.Range("X24").Value),
        "E2": _s(ws.Range("E2").Value),
        "K2": _s(ws.Range("K2").Value),
        "E3": _s(ws.Range("E3").Value),
        "K3": _s(ws.Range("K3").Value),
        "H8": _f(ws.Range("H8").Value),
        "J8": _f(ws.Range("J8").Value),
        "K8": _f(ws.Range("K8").Value),
        "table_overall_unique": unique_teams(1),
        "table_home_unique": unique_teams(11),
        "table_away_unique": unique_teams(21),
        "home_home_rows": hist_rows(),
        "archive": archive,
    }


def compare(a: dict, b: dict, tol: float = 1e-6) -> list[str]:
    diffs = []
    for key in ("S13", "O10", "X24", "E3", "K3"):
        if _s(a.get(key)) != _s(b.get(key)):
            diffs.append(f"{key}: {a.get(key)!r} -> {b.get(key)!r}")
    for key in ("H8", "J8", "K8"):
        fa, fb = a.get(key), b.get(key)
        if fa is None and fb is None:
            continue
        if fa is None or fb is None or abs(float(fa) - float(fb)) > tol:
            diffs.append(f"{key}: {fa} -> {fb}")
    for key in ("table_overall_unique", "table_home_unique", "table_away_unique"):
        if a.get(key) != b.get(key):
            diffs.append(f"{key}: {a.get(key)} -> {b.get(key)}")
    return diffs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", default=str(ROOT / "DeluX_IncoProrok_mvp0.xlsm"))
    parser.add_argument("--match-id", default="YPpBCfeo")
    parser.add_argument("--baseline", default=str(ROOT / "scripts" / "_baseline_YPpBCfeo.json"))
    parser.add_argument("--save-baseline-only", action="store_true")
    args = parser.parse_args()

    xl = connect_excel()
    ui = snapshot_excel_ui(xl)
    try:
        if ui.get("Visible", True):
            xl.Visible = True
        wb = open_workbook(xl, args.workbook)
        before = snapshot(wb, args.match_id)
    finally:
        restore_excel_ui(xl, {**ui, "Visible": True})

    baseline_path = Path(args.baseline)
    if args.save_baseline_only:
        # Prefer archive tip if Анализ currently another match
        base = before
        if before.get("archive"):
            base = dict(before)
            base["S13"] = before["archive"].get("K") or before["S13"]
            base["O10"] = before["archive"].get("O") or before["O10"]
            base["X24"] = before["archive"].get("S") or before["X24"]
        baseline_path.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[+] baseline saved: {baseline_path}")
        print(json.dumps(base, ensure_ascii=False, indent=2))
        return 0

    if baseline_path.is_file():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    else:
        baseline = before
        if before.get("archive"):
            baseline = dict(before)
            baseline["S13"] = before["archive"].get("K") or before["S13"]
            baseline["O10"] = before["archive"].get("O") or before["O10"]
            baseline["X24"] = before["archive"].get("S") or before["X24"]
        baseline_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[*] baseline created from archive/current: {baseline_path}")

    print("[*] running get_game...")
    results = get_game(args.workbook, args.match_id, do_archive=True, do_db=True)

    xl = connect_excel()
    ui = snapshot_excel_ui(xl)
    try:
        xl.Visible = True
        wb = open_workbook(xl, args.workbook)
        after = snapshot(wb, args.match_id)
    finally:
        restore_excel_ui(xl, {**ui, "Visible": True})

    print("[*] after:", json.dumps({k: after[k] for k in ("S13", "O10", "X24", "table_home_unique", "table_away_unique", "home_home_rows")}, ensure_ascii=False))
    print("[*] results:", results.get("prediction_ntb"), results.get("prediction_sniper"))

    diffs = []
    for key in ("S13", "O10", "X24"):
        exp = _s(baseline.get(key))
        got = _s(after.get(key))
        if exp and got and exp != got:
            diffs.append(f"pred {key}: expected {exp!r} got {got!r}")
        elif exp and not got:
            diffs.append(f"pred {key}: expected {exp!r} got empty")

    for key, minimum in (("table_home_unique", 28), ("table_away_unique", 28), ("table_overall_unique", 28)):
        got = after.get(key) or 0
        if got < minimum:
            diffs.append(f"{key}: {got} < {minimum}")

    if after.get("home_home_rows", 0) < 1:
        diffs.append("home_home_rows empty (ДомаДома)")

    if diffs:
        print("[-] DIFFS:")
        for d in diffs:
            print(" ", d)
        return 1
    print("[+] OK: predictions match baseline / tables >= 28 unique / history present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
