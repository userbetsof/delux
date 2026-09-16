Attribute VB_Name = "Module5"
Sub ТоАрхив()
'если ошибка - выход
If IsError(Worksheets("Анализ").Range("S13").value) Then Exit Sub

'ошибки нет, но есть дубль - выход
Dim valueToCheck As Variant
Dim archiveSheet As Worksheet
Dim calculationsSheet As Worksheet
Dim cell As Range
    
Set calculationsSheet = ThisWorkbook.Worksheets("Расчеты")
Set archiveSheet = ThisWorkbook.Worksheets("achive")
Set subStrategiesSheet = ThisWorkbook.Worksheets("sub_strategies")

valueToCheck = calculationsSheet.Range("A1").value

For Each cell In archiveSheet.Range("A:A")
    If Not IsEmpty(cell.value) Then
        If cell.value = valueToCheck Then
            'MsgBox "Значение уже существует в архиве. Макрос остановлен."
            Exit Sub
        End If
    End If
Next cell
    
'перенос
Dim q1 As Long
q1 = archiveSheet.Range("c" & Cells.Rows.Count).End(xlUp).Row + 1
    
    archiveSheet.Range("A" & q1) = Worksheets("Расчеты").Range("A1")  'matchID
    archiveSheet.Range("B" & q1) = Worksheets("Старт").Range("R2")  'Спорт
    archiveSheet.Range("C" & q1) = Worksheets("Анализ").Range("K2") 'Дата
    archiveSheet.Range("D" & q1) = Worksheets("Анализ").Range("E2") 'Лига
    archiveSheet.Range("E" & q1) = Worksheets("Анализ").Range("E3")  'Дома
    archiveSheet.Range("F" & q1) = Worksheets("Анализ").Range("K3")  'Гости
    
    'archiveSheet.Range("G" & q1) = Worksheets("Анализ").Range("K3")  'Статус матча
    'archiveSheet.Range("H" & q1) = Worksheets("Анализ").Range("K3")  'Тайм
    'archiveSheet.Range("I" & q1) = Worksheets("Анализ").Range("K3")  'Минута
    'archiveSheet.Range("J" & q1) = Worksheets("Анализ").Range("K3")  'Счет
    
    archiveSheet.Range("K" & q1) = Worksheets("Анализ").Range("S13")  'Прогноз NTB
    'archiveSheet.Range("L" & q1) = 1  'КФ NTB
    'archiveSheet.Range("M" & q1) = 1  'Статус NTB
    'archiveSheet.Range("N" & q1) = 1  'Прибыль NTB

    archiveSheet.Range("O" & q1) = Worksheets("Анализ").Range("O10")  'Прогноз Betalone
    'archiveSheet.Range("P" & q1) = 1  'КФ Betalone
    'archiveSheet.Range("Q" & q1) = 1  'Статус Betalone
    'archiveSheet.Range("R" & q1) = 1  'Прибыль Betalone
    
    Call GetCoefficientValuePython(q1)
    archiveSheet.Range("S" & q1) = Worksheets("Анализ").Range("X24")  'Прогноз Sniper
    'archiveSheet.Range("T" & q1) = 1  'КФ Sniper
    'archiveSheet.Range("U" & q1) = 1  'Статус Sniper
    'archiveSheet.Range("V" & q1) = 1  'Прибыль Sniper
    
    Dim comboResult As Variant 'Прогноз Mortal
    comboResult = FindMatchingCombination()
    If Not IsEmpty(comboResult(0)) Then
        archiveSheet.Range("W" & q1) = comboResult(0)  ' Номер комбинации
    Else
        archiveSheet.Range("W" & q1) = ""  ' Если комбинация не найдена
    End If
    'archiveSheet.Range("X" & q1) = 1  'КФ Mortal
    'archiveSheet.Range("Y" & q1) = 1  'Статус Mortal
    'archiveSheet.Range("Z" & q1) = 1  'Прибыль Mortal
    
    subStrategiesSheet.Range("A" & q1) = Worksheets("Анализ").Range("H12")  'Основной прогноз 1
    subStrategiesSheet.Range("B" & q1) = Worksheets("Анализ").Range("J12")  'Основной прогноз Х
    subStrategiesSheet.Range("C" & q1) = Worksheets("Анализ").Range("K12")  'Основной прогноз 2
   
    subStrategiesSheet.Range("D" & q1) = Worksheets("Анализ").Range("H8")  'Прогноз 1 - 1
    subStrategiesSheet.Range("E" & q1) = Worksheets("Анализ").Range("J8")  'Прогноз 1 - Х
    subStrategiesSheet.Range("F" & q1) = Worksheets("Анализ").Range("K8")  'Прогноз 1 - 2
   
    subStrategiesSheet.Range("G" & q1) = Worksheets("Анализ").Range("H10")  'Прогноз 2 - 1
    subStrategiesSheet.Range("H" & q1) = Worksheets("Анализ").Range("J10")  'Прогноз 2 - Х
    subStrategiesSheet.Range("I" & q1) = Worksheets("Анализ").Range("K10")  'Прогноз 2 - 2
   
    subStrategiesSheet.Range("J" & q1) = Worksheets("Анализ").Range("H14")  'Прогноз 3 - 1
    subStrategiesSheet.Range("K" & q1) = Worksheets("Анализ").Range("J14")  'Прогноз 3 - Х
    subStrategiesSheet.Range("L" & q1) = Worksheets("Анализ").Range("K14")  'Прогноз 3 - 2
   
    subStrategiesSheet.Range("M" & q1) = Worksheets("Анализ").Range("H16")  'Прогноз ВАЛУЙ - 1
    subStrategiesSheet.Range("N" & q1) = Worksheets("Анализ").Range("J16")  'Прогноз ВАЛУЙ - Х
    subStrategiesSheet.Range("O" & q1) = Worksheets("Анализ").Range("K16")  'Прогноз ВАЛУЙ - 2
   
    subStrategiesSheet.Range("P" & q1) = Worksheets("Анализ").Range("H18")  'GD-xGD - 1
    subStrategiesSheet.Range("Q" & q1) = Worksheets("Анализ").Range("J18")  'xGD
    subStrategiesSheet.Range("R" & q1) = Worksheets("Анализ").Range("K18")  'Index1
    
    subStrategiesSheet.Range("S" & q1) = Worksheets("Анализ").Range("H20")  'xG90
    subStrategiesSheet.Range("T" & q1) = Worksheets("Анализ").Range("J20")  'PPM
    subStrategiesSheet.Range("U" & q1) = Worksheets("Анализ").Range("K20")  'GD-xGD - 2
    
    subStrategiesSheet.Range("V" & q1) = Worksheets("Анализ").Range("H22")  'xGD
    subStrategiesSheet.Range("W" & q1) = Worksheets("Анализ").Range("J22")  'Index1
    subStrategiesSheet.Range("X" & q1) = Worksheets("Анализ").Range("K22")  'xG90
    
    subStrategiesSheet.Range("Y" & q1) = Worksheets("Анализ").Range("H24")  'PPM
    subStrategiesSheet.Range("Z" & q1) = Worksheets("Анализ").Range("J24")  ' Тотал
    subStrategiesSheet.Range("AA" & q1) = Worksheets("Анализ").Range("K24") ' ИТ1
    
    subStrategiesSheet.Range("AB" & q1) = Worksheets("Анализ").Range("H26") ' ИТ2
    subStrategiesSheet.Range("AC" & q1) = Worksheets("Анализ").Range("J26")  'ТБ1,5
    subStrategiesSheet.Range("AD" & q1) = Worksheets("Анализ").Range("K26")  'ТБ2,5
    
    'archiveSheet.Range("AK" & q1) = Worksheets("Анализ").Range("O10")  'ОЗ ДА
    'archiveSheet.Range("AL" & q1) = Worksheets("Анализ").Range("Q10")  'ОЗ НЕТ
    'archiveSheet.Range("AM" & q1) = Worksheets("Анализ").Range("S10")  'ОЗ ДА 100%
    
    'archiveSheet.Range("AN" & q1) = Worksheets("Анализ").Range("B11")  'кфП1
    'archiveSheet.Range("AO" & q1) = Worksheets("Анализ").Range("C11")  'кфХ
    'archiveSheet.Range("AP" & q1) = Worksheets("Анализ").Range("D11")  'кфП2

    'archiveSheet.Range("AQ" & q1).value = GetTotalUnder("2.5", 1, "CURRENT")  ' ТМ2.5
    'archiveSheet.Range("AR" & q1).value = GetTotalOver("2.5", 1, "CURRENT")   ' ТБ2.5
    'archiveSheet.Range("AS" & q1) = Worksheets("Коэффициенты").Range("F2")  'кфОЗДа
    'archiveSheet.Range("AT" & q1) = Worksheets("Коэффициенты").Range("G2")  'кфОЗНет

    'archiveSheet.Range("BG" & q1) = Worksheets("Коэффициенты").Range("H2") '1x
    'archiveSheet.Range("BH" & q1) = Worksheets("Коэффициенты").Range("I2") '12
    'archiveSheet.Range("BI" & q1) = Worksheets("Коэффициенты").Range("J2") '2x
    
    
    If Not IsEmpty(comboResult(0)) Then
        result = FindClosestUnder2Over
        If Not IsEmpty(result(0)) Then
            ' Iieo?aai cia?aiea oioaea ec caaieiaea noieaoa
            If Not IsEmpty(result(0)) Then
                totalValue = CStr(result(1))
                totalValue = Trim(Replace(Replace(totalValue, "OVER", ""), "1st Half", ""))
            Else
                totalValue = ""
            End If
            
            archiveSheet.Range("W" & q1) = "ТБ " & totalValue ' cia?aiea oioaea
            archiveSheet.Range("X" & q1) = result(0)  ' eiyooeoeaio
        End If
    End If
    Call TransferKfData

    ThisWorkbook.Save
    
    Dim command As String
    Dim wsh As Object
    
    Set wsh = CreateObject("WScript.Shell")
    pythonCheck = wsh.Exec("cmd /c where python").StdOut.ReadAll
    scriptPath = "C:\papki\work\bets\delux\db.py"
    command = "py" & " " & scriptPath & ""
    waitForReturn = True
    windowStyle = 1       ' 1 - Обычное окно (0 - скрытое)
    ' Запускаем и ждем
    result = wsh.Run(command, windowStyle, waitForReturn)
    ' result = 0 если успешно
    If result <> 0 Then MsgBox "Скрипт завершился с кодом ошибки: " & result
    
    'scriptPath = "C:\papki\work\Bets\delux\tg\db.py"
    'result = Shell(scriptPath, vbNormalFocus)
    ' Запускаем скрипт
    'ThisWorkbook.Sheets("Архив").Activate
       'Range("A" & q1 + 1).Activate

End Sub

Sub GetCoefficientValuePython(ByVal targetRow As Long)
    Dim wsh As Object
    Dim command As String
    Dim resultCode As Long
    Dim scriptPath As String
    Dim workbookPath As String
    
    scriptPath = "C:\papki\work\bets\delux\odds_coeff.py"
    workbookPath = ThisWorkbook.FullName
    
    Set wsh = CreateObject("WScript.Shell")
    command = "py """ & scriptPath & """ --workbook """ & workbookPath & """ --row " & targetRow
    resultCode = wsh.Run(command, 0, True)
    
    If resultCode <> 0 Then MsgBox "Ошибка расчета коэффициентов в Python: " & resultCode
End Sub

Function FindMaxMarketOdds(wsOdds As Worksheet, marketName As String, Optional valueType As String = "CURRENT", Optional bookmakerIndex As Integer = 0) As Variant
    Dim lastCol As Long
    Dim lastRow As Long
    Dim startCol As Long
    Dim r As Long
    Dim cellMarket As String
    Dim valCol As Long
    Dim v As Variant
    Dim best As Variant
    Dim exactMatch As Boolean
    
    lastCol = wsOdds.Cells(ODDS_SUBHEADER_ROW, wsOdds.Columns.Count).End(xlToLeft).Column
    lastRow = GetOddsDataLastRow(wsOdds)
    If lastRow < ODDS_DATA_START_ROW Then
        FindMaxMarketOdds = 0
        Exit Function
    End If
    
    If valueType = "OPEN" Then
        valCol = 1
    Else
        valCol = 2
    End If
    
    best = Empty
    exactMatch = (InStr(1, marketName, "*", vbTextCompare) = 0)
    
    For startCol = ODDS_FIRST_BK_COL To lastCol Step ODDS_BK_COLS
        If bookmakerIndex > 0 Then
            If startCol <> GetBookmakerStartCol(bookmakerIndex) Then GoTo NextBkBlock
        End If
        
        For r = ODDS_DATA_START_ROW To lastRow
            cellMarket = Trim$(CStr(wsOdds.Cells(r, startCol).value))
            If cellMarket = "" Then Exit For
            
            If exactMatch Then
                If StrComp(cellMarket, marketName, vbTextCompare) <> 0 Then GoTo NextRow
            Else
                If InStr(1, cellMarket, marketName, vbTextCompare) = 0 Then GoTo NextRow
            End If
            
            v = wsOdds.Cells(r, startCol + valCol).value
            If IsNumeric(v) Then
                If Not IsNumeric(best) Or CDbl(v) > CDbl(best) Then best = CDbl(v)
            End If
NextRow:
        Next r
NextBkBlock:
    Next startCol
    
    If Not IsNumeric(best) Then
        FindMaxMarketOdds = 0
    Else
        FindMaxMarketOdds = best
    End If
End Function
Function FindClosestUnder2Over() As Variant
    Dim ws As Worksheet
    Dim lastCol As Long
    Dim startCol As Long
    Dim r As Long
    Dim lastRow As Long
    Dim cellValue As Double
    Dim bestMarket As String
    Dim minDiff As Double
    Dim currentDiff As Double
    Dim cellHeader As String
    Dim totalValue As String
    Dim totalNumber As Double
    Dim isHalfTotal As Boolean
    
    Set ws = ThisWorkbook.Sheets("Коэффициенты")
    lastCol = ws.Cells(ODDS_SUBHEADER_ROW, ws.Columns.Count).End(xlToLeft).Column
    lastRow = GetOddsDataLastRow(ws)
    
    bestMarket = ""
    minDiff = 1000
    
    For startCol = ODDS_FIRST_BK_COL To lastCol Step ODDS_BK_COLS
        For r = ODDS_DATA_START_ROW To lastRow
            cellHeader = Trim$(CStr(ws.Cells(r, startCol).value))
            If cellHeader = "" Then Exit For
            
            If InStr(1, cellHeader, "OVER") > 0 Then
                If InStr(1, cellHeader, "1st Half") = 0 And _
                   InStr(1, cellHeader, "2nd Half") = 0 And _
                   InStr(1, cellHeader, " Half") = 0 And _
                   InStr(1, cellHeader, "1st") = 0 And _
                   InStr(1, cellHeader, "2nd") = 0 And _
                   InStr(1, cellHeader, "Half") = 0 And _
                   InStr(1, cellHeader, "тайм") = 0 And _
                   InStr(1, cellHeader, "Half Time") = 0 Then
                    
                    totalValue = ExtractTotalValue(cellHeader)
                    If totalValue <> "" Then
                        totalValue = Replace(totalValue, ".", ",")
                        totalNumber = CDbl(totalValue)
                        isHalfTotal = (totalNumber * 2) = Int(totalNumber * 2)
                        
                        If isHalfTotal Then
                            If IsNumeric(ws.Cells(r, startCol + 2).value) Then
                                cellValue = ws.Cells(r, startCol + 2).value
                                If cellValue < 2# Then
                                    currentDiff = 2# - cellValue
                                    If bestMarket = "" Or currentDiff < minDiff Then
                                        minDiff = currentDiff
                                        bestMarket = cellHeader
                                    End If
                                End If
                            End If
                        End If
                    End If
                End If
            End If
        Next r
    Next startCol
    
    If bestMarket <> "" Then
        FindClosestUnder2Over = Array(FindMaxMarketOdds(ws, bestMarket, "CURRENT", 0), bestMarket)
    Else
        FindClosestUnder2Over = Array(Empty, Empty)
    End If
End Function

' Вспомогательная функция для извлечения числового значения тотала из заголовка
Private Function ExtractTotalValue(header As String) As String
    Dim regex As Object
    Dim matches As Object
    Dim match As Object
    
    ' Создаем объект регулярного выражения
    Set regex = CreateObject("VBScript.RegExp")
    
    With regex
        .Global = True
        .IgnoreCase = True
        ' Ищем числа с десятичной точкой (например, 0.5, 1.0, 2.5)
        .pattern = "\d+\.?\d*"
        
        If .Test(header) Then
            Set matches = .Execute(header)
            If matches.Count > 0 Then
                ExtractTotalValue = matches(0).value
                Exit Function
            End If
        End If
    End With
    
    ExtractTotalValue = ""
End Function
Sub Range_to_Picture()
    Dim sName As String, nName As String, dName As String, wsTmpSh As Worksheet
    nName = Range("AT1").value
    dName = Range("K2").value
    Application.ScreenUpdating = False
    Application.DisplayAlerts = False
    Range("A1:an36").Select
    With selection
        .CopyPicture
        Set wsTmpSh = ThisWorkbook.Sheets.Add
        sName = ActiveWorkbook.FullName & "_" & Format(dName, "dd/mm/yy hh mm") & "_" & nName
        With wsTmpSh.ChartObjects.Add(0, 0, .Width, .Height).Chart
            .ChartArea.Border.LineStyle = 0
            .Parent.Select
            .Paste
            .Export Filename:=sName & ".jpg", FilterName:="JPG"
            .Parent.Delete
        End With
    End With
    wsTmpSh.Delete
    MsgBox "скрин ОК!"
    Application.ScreenUpdating = True
    Application.DisplayAlerts = True
    Range("A1").Select
End Sub
Sub getScoreHT(home_ht, away_ht, home_st, away_st)
    home_ht = CStr(Val(home_ht) - Val(home_st))
    away_ht = CStr(Val(away_ht) - Val(away_st))
End Sub

' Функция для поиска коэффициента по типу ставки, рынку и букмекеру
Function FindOddsValue(wsOdds As Worksheet, marketType As String, selection As String, _
                      Optional bookmakerIndex As Integer = 1, Optional valueType As String = "CURRENT") As Variant
    Dim bkIndex As Integer
    
    If bookmakerIndex < 1 Then bkIndex = 0 Else bkIndex = bookmakerIndex
    FindOddsValue = FindMaxMarketOdds(wsOdds, selection, valueType, bkIndex)
End Function

' Вспомогательная функция для определения блока букмекера
Function IsCorrectBookmakerBlock(col As Long, bookmakerIndex As Integer) As Boolean
    IsCorrectBookmakerBlock = Module3.IsCorrectBookmakerBlock(col, bookmakerIndex)
End Function

' Специализированные функции для конкретных ставок
Function GetTotalUnder(value As String, Optional bookmakerIndex As Integer = 1, Optional valueType As String = "CURRENT") As Variant
    Dim wsOdds As Worksheet
    Set wsOdds = ThisWorkbook.Sheets("Коэффициенты")
    
    ' Ищем UNDER с указанным значением (например "UNDER 2.5")
    GetTotalUnder = FindOddsValue(wsOdds, "TOTAL", "UNDER " & value, bookmakerIndex, valueType)
    
    ' Если не нашли, пробуем найти без пробела
    If GetTotalUnder = "" Then
        GetTotalUnder = FindOddsValue(wsOdds, "TOTAL", "UNDER" & value, bookmakerIndex, valueType)
    End If
End Function

Function GetTotalOver(value As String, Optional bookmakerIndex As Integer = 1, _
                     Optional valueType As String = "CURRENT", Optional period As String = "FULL_TIME") As Variant
    Dim wsOdds As Worksheet
    Dim prefix As String
    Dim bkIndex As Integer
    
    Set wsOdds = ThisWorkbook.Sheets("Коэффициенты")
    If period = "FIRST_PERIOD" Or period = "1st Half " Then
        prefix = "1st Half "
    Else
        prefix = ""
    End If
    
    If bookmakerIndex < 1 Then bkIndex = 0 Else bkIndex = bookmakerIndex
    GetTotalOver = FindMaxMarketOdds(wsOdds, prefix & "OVER " & value, valueType, bkIndex)
    If GetTotalOver = 0 Then
        GetTotalOver = FindMaxMarketOdds(wsOdds, "OVER " & value, valueType, bkIndex)
    End If
End Function

Function GetMatchOdds(selection As String, Optional bookmakerIndex As Integer = 1, Optional valueType As String = "CURRENT") As Variant
    Dim wsOdds As Worksheet
    Set wsOdds = ThisWorkbook.Sheets("Коэффициенты")
    
    ' selection: "1", "X", "2"
    GetMatchOdds = FindOddsValue(wsOdds, "1X2", "1X2_" & selection, bookmakerIndex, valueType)
End Function

Function GetBTTS(selection As String, Optional bookmakerIndex As Integer = 1, Optional valueType As String = "CURRENT") As Variant
    Dim wsOdds As Worksheet
    Set wsOdds = ThisWorkbook.Sheets("Коэффициенты")
    
    ' selection: "YES" или "NO"
    If UCase(selection) = "YES" Then
        GetBTTS = FindOddsValue(wsOdds, "BTTS", "BTTS_YES", bookmakerIndex, valueType)
    ElseIf UCase(selection) = "NO" Then
        GetBTTS = FindOddsValue(wsOdds, "BTTS", "BTTS_NO", bookmakerIndex, valueType)
    Else
        GetBTTS = ""
    End If
End Function

Function GetDoubleChance(selection As String, Optional bookmakerIndex As Integer = 1, Optional valueType As String = "CURRENT") As Variant
    Dim wsOdds As Worksheet
    Set wsOdds = ThisWorkbook.Sheets("Коэффициенты")
    
    ' selection: "1X", "12", "X2"
    GetDoubleChance = FindOddsValue(wsOdds, "DC", "DC_" & selection, bookmakerIndex, valueType)
End Function

' Универсальная функция для прямого доступа по имени колонки
Function GetOddsByColumnName(columnName As String, Optional bookmakerIndex As Integer = 1, Optional valueType As String = "CURRENT") As Variant
    Dim wsOdds As Worksheet
    Set wsOdds = ThisWorkbook.Sheets("Коэффициенты")
    
    GetOddsByColumnName = FindOddsValue(wsOdds, "", columnName, bookmakerIndex, valueType)
End Function

' Функция для получения текущих коэффициентов с привязкой к ID матча
Function GetOddsForMatch(matchId As String, betType As String, Optional bookmakerId As Integer = 417) As Variant
    ' Эта функция может быть расширена для проверки соответствия matchId
    ' с данными на листе "Коэффициенты" (колонки A и B)
    
    Dim wsOdds As Worksheet
    Set wsOdds = ThisWorkbook.Sheets("Коэффициенты")
    
    ' Проверяем, что ID матча совпадает с текущим
    If wsOdds.Range("A2").value = matchId Or wsOdds.Range("B2").value = matchId Then
        ' Определяем индекс букмекера по его ID
        Dim bkIndex As Integer
        bkIndex = GetBookmakerIndex(bookmakerId)
        
        ' Получаем нужный коэффициент
        Select Case UCase(betType)
            Case "TM2.5", "UNDER 2.5", "ТМ2.5"
                GetOddsForMatch = GetTotalUnder("2.5", bkIndex)
            Case "TB2.5", "OVER 2.5", "ТБ2.5"
                GetOddsForMatch = GetTotalOver("2.5", bkIndex)
            Case "1", "HOME"
                GetOddsForMatch = GetMatchOdds("1", bkIndex)
            Case "X", "DRAW"
                GetOddsForMatch = GetMatchOdds("X", bkIndex)
            Case "2", "AWAY"
                GetOddsForMatch = GetMatchOdds("2", bkIndex)
            Case "BTTS_YES", "ОБЕ ЗАБЬЮТ"
                GetOddsForMatch = GetBTTS("YES", bkIndex)
            Case "BTTS_NO", "ОБЕ НЕ ЗАБЬЮТ"
                GetOddsForMatch = GetBTTS("NO", bkIndex)
            Case "1X"
                GetOddsForMatch = GetDoubleChance("1X", bkIndex)
            Case "12"
                GetOddsForMatch = GetDoubleChance("12", bkIndex)
            Case "X2"
                GetOddsForMatch = GetDoubleChance("X2", bkIndex)
            Case Else
                GetOddsForMatch = GetOddsByColumnName(betType, bkIndex)
        End Select
    Else
        GetOddsForMatch = "ID_NOT_MATCH"
    End If
End Function

' Функция для определения индекса букмекера по его ID
Function GetBookmakerIndex(bookmakerId As Integer) As Integer
    ' Здесь должен быть словарь соответствия ID букмекера и индекса в таблице
    ' По умолчанию возвращаем 1
    
    Dim bkIds As Variant
    bkIds = Array(417, 418, 419, 420) ' Должен совпадать с массивом из vorkaOdds
    
    Dim i As Integer
    GetBookmakerIndex = 1 ' Значение по умолчанию
    
    For i = LBound(bkIds) To UBound(bkIds)
        If bkIds(i) = bookmakerId Then
            GetBookmakerIndex = i + 1 ' Индексация с 1
            Exit Function
        End If
    Next i
End Function


' Быстрый прямой поиск (если структура таблицы фиксирована)
Function FindOddsDirect(wsOdds As Worksheet, searchText As String, bookmakerIndex As Integer) As Variant
    FindOddsDirect = FindMaxMarketOdds(wsOdds, searchText, "CURRENT", bookmakerIndex)
End Function

Function GetHandicap(team As String, value As String, Optional bookmakerIndex As Integer = 1) As Variant
    Dim wsOdds As Worksheet
    Dim searchText As String
    Dim bkIndex As Integer
    
    Set wsOdds = ThisWorkbook.Sheets("Коэффициенты")
    If UCase(team) = "HOME" Then
        searchText = "HANDICAP HOME " & value
    Else
        searchText = "HANDICAP AWAY " & value
    End If
    
    If bookmakerIndex < 1 Then bkIndex = 0 Else bkIndex = bookmakerIndex
    GetHandicap = FindMaxMarketOdds(wsOdds, searchText, "CURRENT", bkIndex)
End Function

' Функция для получения индивидуального тотала
Function GetIndividualTotal(team As String, value As String, Optional bookmakerIndex As Integer = 1, _
                           Optional period As String = "FULL_TIME") As Variant
    Dim wsOdds As Worksheet
    Dim searchText As String
    Dim bkIndex As Integer
    
    Set wsOdds = ThisWorkbook.Sheets("Коэффициенты")
    If UCase(team) = "HOME" Then
        searchText = "ИТБ1 (" & value & ")"
    Else
        searchText = "ИТБ2 (" & value & ")"
    End If
    
    If bookmakerIndex < 1 Then bkIndex = 0 Else bkIndex = bookmakerIndex
    GetIndividualTotal = FindMaxMarketOdds(wsOdds, searchText, "CURRENT", bkIndex)
End Function

Function FindMatchingCombination() As Variant
    Dim wsOdds As Worksheet
    Dim wsAnalysis As Worksheet
    Dim lastCol As Integer
    Dim col As Integer
    Dim result As Variant
    Dim combinations As Collection
    Dim i As Integer
    
    Set wsOdds = ThisWorkbook.Sheets("Коэффициенты")
    Set wsAnalysis = ThisWorkbook.Sheets("Анализ")
    
    ' Получаем текущие коэффициенты
    Dim kfP1 As Double, kfX As Double, kfP2 As Double
    Dim kfTB2_5 As Double, kfTM2_5 As Double
    Dim kfF1 As Double, kfF2 As Double
    Dim kfITB1 As Double, kfITB2 As Double
    Dim kfOZ As Double
    Dim kfTB1_5_1H As Double  ' ТБ 1.5 первого тайма
    
    ' Загружаем коэффициенты (используем первый букмекер - индекс 1)
    On Error Resume Next
    kfP1 = wsAnalysis.Range("B11").value
    kfX = wsAnalysis.Range("C11").value
    kfP2 = wsAnalysis.Range("D11").value
    kfTB2_5 = GetTotalOver("2.5", 1)
    kfTM2_5 = GetTotalUnder("2.5", 1)
    kfOZ = GetBTTS("YES", 1)
    kfTB1_5_1H = GetTotalOver("1.5", 1, "CURRENT", "FIRST_PERIOD")  ' Тотал первого тайма
    On Error GoTo 0
    
    ' Создаем коллекцию комбинаций
    Set combinations = New Collection
    
    ' Добавляем комбинации с их условиями
    ' Комбинация 1: П1 ? 1.20 + ТБ 2.5 ? 1.45 = ТБ 4.5
    combinations.Add Array(1, "П1", 1.2, "TB2.5", 1.45, "=", "ТБ 4.5")
    
    ' Комбинация 2: ТБ 2.5 ? 1.45 + ИТБ1 (2.5) ? 1.60 + ОЗ ? 1.55 = ТБ 3.5
    combinations.Add Array(2, "TB2.5", 1.45, "ITB1", 1.6, "OZ", 1.55, "=", "ТБ 3.5")
    
    ' Комбинация 3: Ф2 (-1.5) ? 1.50 + ИТБ2 (2.5) ? 1.55 + ТБ 2.5 ? 1.50 = ТБ 4.5 или ИТБ2 3.5
    combinations.Add Array(3, "F2", 1.5, "ITB2", 1.55, "TB2.5", 1.5, "=", "ТБ 4.5 или ИТБ2 3.5")
    
    ' Комбинация 4: ОЗ ? 1.45 + ТБ 2.5 ? 1.55 + ТБ 1-го тайма 1.5 ? 1.85 = ТБ 3.5
    combinations.Add Array(4, "OZ", 1.45, "TB2.5", 1.55, "TB1.5_1H", 1.85, "=", "ТБ 3.5")
    
    ' Проверяем каждую комбинацию
    For i = 1 To combinations.Count
        Dim combo As Variant
        combo = combinations(i)
        
        Select Case combo(0) ' Номер комбинации
            Case 1
                ' П1 ? 1.20 + ТБ 2.5 ? 1.45
                If (kfP1 <= 1.2 And kfP1 > 0) And (kfTB2_5 <= 1.45 And kfTB2_5 > 0) Then
                    FindMatchingCombination = Array(combo(0), combo(6)) ' Номер комбинации и результат
                    Exit Function
                End If
                
            Case 2
                ' ТБ 2.5 ? 1.45 + ИТБ1 (2.5) ? 1.60 + ОЗ ? 1.55
                Dim kfITB1_2_5 As Double
                kfITB1_2_5 = GetIndividualTotal("HOME", "2.5", 1)
                
                If (kfTB2_5 <= 1.45 And kfTB2_5 > 0) And _
                   (kfITB1_2_5 <= 1.6 And kfITB1_2_5 > 0) And _
                   (kfOZ <= 1.55 And kfOZ > 0) Then
                    FindMatchingCombination = Array(combo(0), combo(8))
                    Exit Function
                End If
                
            Case 3
                ' Ф2 (-1.5) ? 1.50 + ИТБ2 (2.5) ? 1.55 + ТБ 2.5 ? 1.50
                Dim kfF2_1_5 As Double
                Dim kfITB2_2_5 As Double
                
                kfF2_1_5 = GetHandicap("AWAY", "-1.5", 1)
                kfITB2_2_5 = GetIndividualTotal("AWAY", "2.5", 1)
                
                If (kfF2_1_5 <= 1.5 And kfF2_1_5 > 0) And _
                   (kfITB2_2_5 <= 1.55 And kfITB2_2_5 > 0) And _
                   (kfTB2_5 <= 1.5 And kfTB2_5 > 0) Then
                    FindMatchingCombination = Array(combo(0), combo(8))
                    Exit Function
                End If
                
            Case 4
                ' ОЗ ? 1.45 + ТБ 2.5 ? 1.55 + ТБ 1-го тайма 1.5 ? 1.85
                If (kfOZ <= 1.45 And kfOZ > 0) And _
                   (kfTB2_5 <= 1.55 And kfTB2_5 > 0) And _
                   (kfTB1_5_1H <= 1.85 And kfTB1_5_1H > 0) Then
                    FindMatchingCombination = Array(combo(0), combo(7))
                    Exit Function
                End If
        End Select
    Next i
    
    ' Если ни одна комбинация не подошла
    FindMatchingCombination = Array(Empty, Empty)
End Function

Sub TransferKfData()
    Dim wsOld As Worksheet
    Dim wsNew As Worksheet
    Dim lastColOld As Long
    Dim lastColNew As Long
    Dim lastRowOld As Long
    Dim lastRowNew As Long
    Dim startCol As Long
    Dim r As Long
    Dim destRow As Long
    Dim marketName As String
    Dim openVal As Variant
    Dim curVal As Variant
    Dim marketKey As Variant
    Dim maxOpen As Variant
    Dim maxCur As Variant
    Dim targetCol As Long
    Dim newCol As Long
    
    Dim marketDict As Object
    Set marketDict = CreateObject("Scripting.Dictionary")
    
    Set wsOld = ThisWorkbook.Sheets("Коэффициенты")
    Set wsNew = ThisWorkbook.Sheets("kf")
    
    lastRowOld = GetOddsDataLastRow(wsOld)
    lastColOld = wsOld.Cells(ODDS_SUBHEADER_ROW, wsOld.Columns.Count).End(xlToLeft).Column
    lastRowNew = wsNew.Cells(wsNew.Rows.Count, 1).End(xlUp).Row
    
    If lastRowNew = 1 And IsEmpty(wsNew.Cells(1, 1)) Then lastRowNew = 0
    
    For startCol = ODDS_FIRST_BK_COL To lastColOld Step ODDS_BK_COLS
        For r = ODDS_DATA_START_ROW To lastRowOld
            marketName = Trim$(CStr(wsOld.Cells(r, startCol).value))
            If marketName = "" Then Exit For
            
            openVal = wsOld.Cells(r, startCol + 1).value
            curVal = wsOld.Cells(r, startCol + 2).value
            
            If Not IsNumeric(openVal) And Not IsNumeric(curVal) Then GoTo NextMarketRow
            
            If marketDict.Exists(marketName) Then
                maxOpen = marketDict(marketName)(0)
                maxCur = marketDict(marketName)(1)
            Else
                maxOpen = Empty
                maxCur = Empty
            End If
            
            If IsNumeric(openVal) Then
                If Not IsNumeric(maxOpen) Or CDbl(openVal) > CDbl(maxOpen) Then maxOpen = CDbl(openVal)
            End If
            If IsNumeric(curVal) Then
                If Not IsNumeric(maxCur) Or CDbl(curVal) > CDbl(maxCur) Then maxCur = CDbl(curVal)
            End If
            
            marketDict(marketName) = Array(maxOpen, maxCur)
NextMarketRow:
        Next r
    Next startCol
    
    If marketDict.Count = 0 Then Exit Sub
    
    If Trim$(CStr(wsNew.Cells(1, 1).value)) = "" Then wsNew.Cells(1, 1).value = "MATCH_ID"
    If Trim$(CStr(wsNew.Cells(1, 2).value)) = "" Then wsNew.Cells(1, 2).value = "HOME_ID"
    If Trim$(CStr(wsNew.Cells(1, 3).value)) = "" Then wsNew.Cells(1, 3).value = "AWAY_ID"
    
    For Each marketKey In marketDict.Keys
        marketName = CStr(marketKey)
        newCol = 0
        For targetCol = 1 To wsNew.Cells(1, wsNew.Columns.Count).End(xlToLeft).Column
            If Trim$(CStr(wsNew.Cells(1, targetCol).value)) = marketName Then
                newCol = targetCol
                Exit For
            End If
        Next targetCol
        If newCol = 0 Then
            newCol = wsNew.Cells(1, wsNew.Columns.Count).End(xlToLeft).Column + 1
            wsNew.Cells(1, newCol).value = marketName
        End If
    Next marketKey
    
    lastColNew = wsNew.Cells(1, wsNew.Columns.Count).End(xlToLeft).Column
    destRow = lastRowNew + 1
    If destRow < 2 Then destRow = 2
    
    wsNew.Cells(destRow, 1).value = Worksheets("Расчеты").Range("A1").value
    wsNew.Cells(destRow, 2).value = wsOld.Range("A2").value
    wsNew.Cells(destRow, 3).value = wsOld.Range("B2").value
    
    For Each marketKey In marketDict.Keys
        marketName = CStr(marketKey)
        maxCur = marketDict(marketKey)(1)
        For targetCol = 1 To lastColNew
            If Trim$(CStr(wsNew.Cells(1, targetCol).value)) = marketName Then
                If IsNumeric(maxCur) Then wsNew.Cells(destRow, targetCol).value = maxCur
                Exit For
            End If
        Next targetCol
    Next marketKey
    
    wsNew.Rows(1).Font.Bold = True
End Sub
