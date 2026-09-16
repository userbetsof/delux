from oletools.olevba import VBA_Parser

p = VBA_Parser(r"c:\papki\work\bets\delux\DeluX_IncoProrok_mvp.xlsm")
for _fn, _sp, vba_filename, vba_code in p.extract_macros():
    if vba_filename in ("Module1.bas", "Module2.bas"):
        out = rf"c:\papki\work\bets\delux\{vba_filename.replace('.bas', '_extracted.bas')}"
        with open(out, "w", encoding="utf-8") as f:
            f.write(vba_code)
        print("written", vba_filename, len(vba_code.splitlines()))
