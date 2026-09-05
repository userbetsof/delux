"""Счётчик COM-вызовов для паритетных тестов (pure_eval без Excel)."""

from __future__ import annotations

_com_calls = 0


def reset_com_calls() -> None:
    global _com_calls
    _com_calls = 0


def note_com_call() -> None:
    global _com_calls
    _com_calls += 1


def com_call_count() -> int:
    return _com_calls
