# Archive — not part of the runtime pipeline

- `vba/` — extracted Excel macros (historical COM/VBA UI).
- `patches/` — one-off migration scripts (`_patch_*`, `_reimport_*`).
- `excel_dumps/` — binary workbook extracts (`159C3300`, `F66A3300`); gitignored.

Current calc path is Python (`CALC_BACKEND=python` + `formula_port/`). Excel remains optional for reports and parity checks.
