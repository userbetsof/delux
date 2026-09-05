import os
import time
from typing import Any, Callable, Dict, Optional, TypeVar

# msoAutomationSecurityLow
AUTOMATION_SECURITY_LOW = 1
# xlCalculationManual
XL_CALC_MANUAL = -4135

T = TypeVar("T")

# Excel busy / RPC rejected (0x800AC472, 0x80010001, 0x8001010A)
_COM_BUSY_HRESULTS = frozenset({-2146777998, -2147418111, -2147417846})


def _win32com():
    """Lazy import: Docker/Linux pipeline не требует pywin32."""
    try:
        import win32com.client as win32com_client
    except ImportError as exc:
        raise RuntimeError(
            "pywin32/win32com недоступен. Excel COM работает только на Windows; "
            "для Docker используйте pipeline без --excel (db_only) и CALC_BACKEND=python."
        ) from exc
    return win32com_client


def _com_hresult(exc: BaseException) -> int | None:
    hresult = getattr(exc, "hresult", None)
    if hresult is not None:
        try:
            return int(hresult)
        except (TypeError, ValueError):
            pass
    args = getattr(exc, "args", None)
    if args:
        try:
            return int(args[0])
        except (TypeError, ValueError, IndexError):
            pass
    return None


def com_retry(fn: Callable[[], T], *, attempts: int = 25, delay: float = 0.2) -> T:
    """Повтор COM-вызова при занятом Excel (busy / call rejected)."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last = exc
            hr = _com_hresult(exc)
            if hr is not None and hr not in _COM_BUSY_HRESULTS:
                raise
            time.sleep(delay * (1 + i // 5))
    assert last is not None
    raise last


def _norm_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.expanduser(path)))


def snapshot_excel_ui(xl) -> Dict[str, Any]:
    """Сохранить Visible/ScreenUpdating/… до правок из Python."""
    state: Dict[str, Any] = {}
    for key in ("Visible", "ScreenUpdating", "EnableEvents", "DisplayAlerts"):
        try:
            state[key] = bool(getattr(xl, key))
        except Exception:
            pass
    return state


def restore_excel_ui(xl, state: Optional[Dict[str, Any]]) -> None:
    """Вернуть UI Excel после COM-скрипта (иначе окно остаётся скрытым)."""
    if not xl or not state:
        return
    for key, val in state.items():
        try:
            setattr(xl, key, val)
        except Exception:
            pass
    # Если до скрипта окно было видно — гарантированно показать снова.
    if state.get("Visible"):
        try:
            xl.Visible = True
        except Exception:
            pass


def connect_excel(*, fresh: bool = False):
    win32com_client = _win32com()
    if not fresh:
        for _ in range(8):
            try:
                xl = win32com_client.GetObject(Class="Excel.Application")
                _ = xl.Version
                # Не трогаем Visible/ScreenUpdating/EnableEvents у уже открытого Excel:
                # Python-скрипты из VBA иначе «прячут» окно и не возвращают его.
                xl.AutomationSecurity = AUTOMATION_SECURITY_LOW
                return xl
            except Exception:
                time.sleep(0.4)
    xl = win32com_client.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    xl.ScreenUpdating = False
    xl.EnableEvents = False
    xl.AutomationSecurity = AUTOMATION_SECURITY_LOW
    return xl


def resolve_workbook_path(workbook_path: str) -> str:
    path = _norm_path(workbook_path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Workbook not found: {path}")
    return path


def _find_open_workbook(xl, target: str):
    for i in range(1, xl.Workbooks.Count + 1):
        wb = xl.Workbooks.Item(i)
        if _norm_path(str(wb.FullName)) == target:
            return wb
    return None


def _open_workbook_once(xl, workbook_path: str, target: str):
    wb = _find_open_workbook(xl, target)
    if wb is not None:
        return wb

    xl.Workbooks.Open(
        Filename=workbook_path,
        UpdateLinks=0,
        ReadOnly=False,
        Notify=False,
        AddToMru=False,
    )
    time.sleep(1.5)
    wb = _find_open_workbook(xl, target)
    if wb is not None:
        return wb

    open_names = [
        str(xl.Workbooks.Item(i).FullName)
        for i in range(1, xl.Workbooks.Count + 1)
    ]
    raise RuntimeError(
        f"Excel opened other workbooks, but not target. Open: {open_names or '[]'}"
    )


def open_workbook(xl, workbook_path: str):
    workbook_path = resolve_workbook_path(workbook_path)
    xl.DisplayAlerts = False
    xl.EnableEvents = False
    target = _norm_path(workbook_path)
    last_err: Exception | None = None

    for attempt in range(8):
        try:
            return _open_workbook_once(xl, workbook_path, target)
        except Exception as exc:
            last_err = exc
            time.sleep(0.5 + attempt * 0.25)

    hint = (
        " Закройте все окна Excel и повторите. "
        "Если файл открыт вручную — сохраните и закройте его."
    )
    detail = f" ({last_err})" if last_err else ""
    raise RuntimeError(f"Cannot open workbook: {workbook_path}{detail}.{hint}")
