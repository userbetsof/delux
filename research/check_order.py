import sys

sys.stdout.reconfigure(encoding="utf-8")

src = open(r"C:\papki\work\bets\delux\match_analysis.py", encoding="utf-8").read()

i = src.find("[cache] таблица на момент")
j = src.find("save_payload_snapshot(match.match_id, hist_payload)")
print("cache-блок:", i)
print("save_payload_snapshot:", j)
print("порядок верный:", 0 < i < j)

seg = src[i:j]
print("длина сегмента:", len(seg))
print("table_overall в сегменте:", "hist_payload.table_overall" in seg)
