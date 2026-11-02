"""Проверка сводки о сбоях: имитируем ошибку в цикле анализа сезона."""

import sys
import traceback

sys.stdout.reconfigure(encoding="utf-8")


class FakeError(RuntimeError):
    pass


def inner():
    raise FakeError("нет данных о стадионе\nвторая строка текста")


def outer():
    inner()


# --- то же, что в analyze_match.run_analyze_season ---
failures = []
todo = [{"match_id": "ABC123"}, {"match_id": "DEF456"}]

for idx, tm in enumerate(todo, 1):
    try:
        if idx == 1:
            outer()
        print(f"[+] Сохранено: {tm['match_id']}")
    except Exception as exc:
        mid = tm["match_id"]
        tb = traceback.extract_tb(exc.__traceback__)
        where = ""
        if tb:
            last = tb[-1]
            where = f"{last.filename.split(chr(92))[-1]}:{last.lineno} {last.name}"
        reason = f"{type(exc).__name__}: {exc}"
        print(f"[-] Ошибка {mid}: {reason}")
        print(f"    место: {where}")
        failures.append(
            {
                "index": idx,
                "match_id": mid,
                "league": "ТЕСТ",
                "teams": "Хозяин - Гость",
                "reason": reason,
                "where": where,
            }
        )

print()
print("=" * 62)
print(f"  НЕ УДАЛОСЬ ПРОАНАЛИЗИРОВАТЬ: {len(failures)}")
print("=" * 62)
for f in failures:
    print(f"\n  {f['match_id']}  [{f['index']}/{len(todo)}]")
    print(f"    матч:  {f['teams']}")
    print(f"    лига:  {f['league']}")
    print(f"    причина: {f['reason']}")
    if f["where"]:
        print(f"    место:   {f['where']}")
print()
print(f"  ID для повтора: {','.join(f['match_id'] for f in failures)}")
