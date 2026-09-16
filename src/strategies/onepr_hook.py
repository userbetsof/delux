"""Хук DeluX → стратегия #8 (1pr) + опционально внешнее приложение 1pr."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ONEPR_ROOT = Path(os.environ.get("ONEPR_ROOT", r"c:\papki\work\bets\1pr")).resolve()


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name, str(default)).strip().lower()
    return v in ("1", "true", "yes", "on")


def _skip() -> bool:
    from db import should_skip_onepr

    return should_skip_onepr()


def _external_enabled() -> bool:
    """Старое приложение 1pr — только если явно включено."""
    if _skip():
        return False
    return _env_bool("ONEPR_EXTERNAL", False) or (
        _env_bool("ONEPR_HOOK", False) and not _env_bool("ONEPR_STRATEGY_ONLY", True)
    )


def sync_1pr_signal(match_id: str) -> dict | None:
    """После анализа: записать прогноз в strategy_predictions (#8)."""
    if not match_id or _skip():
        return None

    result: dict = {"ok": False, "match_id": match_id}
    try:
        from src.strategies.onepr import save_onepr_strategy_prediction

        pred = save_onepr_strategy_prediction(str(match_id))
        if pred:
            print(
                f"    1pr (#8)={pred.get('label')} @ {pred.get('odds')} "
                f"p={float(pred.get('probability') or 0)*100:.1f}% "
                f"edge={float(pred.get('difference') or 0)*100:+.1f}pp"
            )
            result = {
                "ok": True,
                "match_id": match_id,
                "prediction": pred["prediction"],
                "selected_odds": pred.get("odds"),
                "difference": pred.get("difference"),
                "saved_strategy": True,
            }
        else:
            result = {"ok": False, "reason": "no_signal", "match_id": match_id}
    except Exception as exc:
        print(f"[1pr] strategy #8 error for {match_id}: {exc}")
        result = {"ok": False, "reason": "error", "error": str(exc), "match_id": match_id}

    if _external_enabled() and _ONEPR_ROOT.is_dir():
        try:
            root = str(_ONEPR_ROOT)
            if root not in sys.path:
                sys.path.insert(0, root)
            from app.signals import emit_for_match  # type: ignore

            ext = emit_for_match(str(match_id))
            result["external"] = ext
            if ext.get("ok") and (ext.get("saved") or ext.get("updated")):
                print(
                    f"[1pr] external {ext.get('prediction')} @ {ext.get('selected_odds')} "
                    f"({match_id})"
                )
        except Exception as exc:
            print(f"[1pr] external hook error: {exc}")
            result["external_error"] = str(exc)
    elif _external_enabled() and not _ONEPR_ROOT.is_dir():
        print(f"[1pr] external skip: app not found at {_ONEPR_ROOT}")

    return result
