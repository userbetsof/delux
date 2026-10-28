"""Check ExcelCalcEngine.write_payload and M26-M32."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

# Check ExcelCalcEngine
from calc_engine import ExcelCalcEngine
import inspect

# Get source of write_payload
src = inspect.getsource(ExcelCalcEngine.write_payload)
print("=== ExcelCalcEngine.write_payload ===")
print(src[:3000])
