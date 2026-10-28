"""График: зависимость вероятности исхода 1x2 от формы (form10_diff) — model-free калибровка."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"C:\papki\work\bets\delux\research")
RESULTS = ROOT / "form10_results.json"
OUT_PNG = ROOT / "form10_calibration.png"


def main() -> int:
    payload = json.loads(RESULTS.read_text(encoding="utf-8"))
    reports = [r for r in payload["reports"] if "outcome_by_form_bucket" in r]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
    titles = {
        (6, "strict"): "Бейсбол — обе команды ≥10 матчей",
        (6, "graceful"): "Бейсбол — любая история ≥1",
        (1, "graceful"): "Футбол — любая история ≥1",
    }
    order = [(6, "strict"), (6, "graceful"), (1, "graceful")]

    for ax, (sport, variant) in zip(axes, order):
        rep = next(r for r in reports if r["sport"] == sport and r["variant"] == variant)
        rows = rep["outcome_by_form_bucket"]
        # строка вида "(-inf, -1.5]" -> метка центра/диапазона
        labels, centers, home, draw, away, counts = [], [], [], [], [], []
        for row in rows:
            label = row["form10_diff"]
            home.append(row["home_win"] * 100)
            draw.append(row["draw"] * 100)
            away.append(row["away_win"] * 100)
            counts.append(row["n"])
            # извлечь среднюю точку интервала
            lo = -3.0 if "-inf" in label else float(label.strip("()[]").split(",")[0])
            hi = 3.0 if "inf" in label else float(label.strip("()[]").split(",")[1])
            centers.append((lo + hi) / 2)
            labels.append(f"{lo:+.1f}..{hi:+.1f}")
        centers = np.array(centers)
        home = np.array(home)
        draw = np.array(draw)
        away = np.array(away)
        counts = np.array(counts)

        ax.plot(centers, home, "-o", color="#1f77b4", label="Победа хозяев (1)")
        ax.plot(centers, away, "-s", color="#d62728", label="Победа гостей (2)")
        ax.plot(centers, draw, "-^", color="#7f7f7f", label="Ничья (0)")
        ax.axvline(0, color="black", linestyle=":", alpha=0.5)
        ax.axhline(50, color="gray", linestyle="--", alpha=0.3)
        ax.set_title(titles[(sport, variant)])
        ax.set_xlabel("form10_diff = ppg(хозяева) − ppg(гости)")
        ax.set_xticks(centers)
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        # подписи числа наблюдений
        for x, c in zip(centers, counts):
            ax.text(x, 96, f"n={c}", ha="center", fontsize=7, color="0.4")
        ax.set_ylim(0, 105)
        ax.grid(alpha=0.3)

    axes[0].set_ylabel("Доля исходов, %")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Зависимость исхода 1x2 от единственного признака — формы за последние 10 матчей",
                 fontsize=13, y=1.02)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=130, bbox_inches="tight")
    print(f"сохранено: {OUT_PNG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
