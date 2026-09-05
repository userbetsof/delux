import openpyxl

wb = openpyxl.load_workbook("DeluX_IncoProrok_mvp.xlsm", read_only=True, data_only=False)

for sheet_name in ["Анализ", "Расчеты"]:
    print(f"\n=================== SHEET: {sheet_name} ===================")
    ws = wb[sheet_name]
    # Limit to 150 rows and 50 columns
    for r in range(1, min(ws.max_row + 1, 150)):
        for c in range(1, min(ws.max_column + 1, 50)):
            cell = ws.cell(row=r, column=c)
            val = cell.value
            if val is not None and str(val).startswith("="):
                print(f"{cell.coordinate}: {val}")
wb.close()
