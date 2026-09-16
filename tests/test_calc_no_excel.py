from formula_port.workbook_loader import has_formula_cache
from unittest import TestCase
import sys


class TestNoExcelImport(TestCase):
    def test_engine_does_not_import_excel_com(self):
        for name in list(sys.modules):
            if name in ("excel_com", "calc_engine") or name.startswith("win32com"):
                sys.modules.pop(name, None)
        import formula_port.engine  # noqa: F401

        self.assertNotIn("excel_com", sys.modules)
        self.assertNotIn("calc_engine", sys.modules)

    def test_formula_cache_present(self):
        self.assertTrue(has_formula_cache())
