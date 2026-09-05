Attribute VB_Name = "Module1"
Dim fs_rows_length As Long

Sub getMS(Optional ByVal auto As Boolean = False)
    Dim wsh As Object
    Dim command As String
    Dim resultCode As Long
    Dim scriptPath As String
    Dim workbookPath As String
    Dim analyzed As Long
    
    On Error Resume Next
    Application.ScreenUpdating = False
    Application.Calculation = xlManual
    Application.EnableEvents = False
    Application.StatusBar = False
    clearParsed
    clearMain
    
    scriptPath = "C:\papki\work\bets\delux\matches_list.py"
    workbookPath = ThisWorkbook.FullName
    
    Set wsh = CreateObject("WScript.Shell")
    command = "py """ & scriptPath & """ --workbook """ & workbookPath & """ --excel"
    If auto = True Then command = command & " --auto"
    resultCode = wsh.Run(command, 0, True)
    
    Application.ScreenUpdating = True
    Application.Calculation = xlAutomatic
    Application.EnableEvents = True
    Application.StatusBar = True
    Application.Visible = True
    
    If resultCode <> 0 Then
        MsgBox "Ошибка Python-загрузки списка матчей: " & resultCode
        Exit Sub
    End If
    
    If auto = True Then
        analyzed = autoAnalisis()
        If analyzed > 0 Then
            ' Дата последнего УСПЕШНОГО автоанализа - только после реальных getGame
            On Error Resume Next
            Sheets("Старт").Range("AA2").value = Date
            ActiveWorkbook.Save
            On Error GoTo 0
            Application.Quit
        Else
            MsgBox "Автоанализ: в "Списке" нет видимых матчей (или все ID пустые)." & vbCrLf & _
                   "Дата AA2 не обновлена - при следующем открытии запуск повторится." & vbCrLf & _
                   "Excel не закрыт."
        End If
    End If
End Sub

Function autoAnalisis() As Long
    Dim wsList As Worksheet
    Dim filteredRange As Range
    Dim cell As Range
    Dim matchId As String
    Dim gameCount As Long
    Dim currentGame As Long
    Dim doneCount As Long
    
    doneCount = 0
    Set wsList = Sheets("Список")

    ' Снять автофильтр, если он скрыл все строки (иначе SpecialCells = Nothing)
    On Error Resume Next
    If wsList.FilterMode Or wsList.AutoFilterMode Then
        ' оставляем фильтр, но если видимых нет - снимем
    End If
    On Error GoTo 0

    On Error Resume Next
    Set filteredRange = wsList.Range("E2:E" & wsList.Cells(wsList.Rows.Count, "E").End(xlUp).Row).SpecialCells(xlCellTypeVisible)
    On Error GoTo 0
    
    If filteredRange Is Nothing Then
        ' Попробуем без фильтра: показать все строки с ID
        On Error Resume Next
        If wsList.AutoFilterMode Then wsList.AutoFilterMode = False
        On Error GoTo 0
        On Error Resume Next
        Set filteredRange = wsList.Range("E2:E" & wsList.Cells(wsList.Rows.Count, "E").End(xlUp).Row).SpecialCells(xlCellTypeVisible)
        On Error GoTo 0
    End If
    
    If Not filteredRange Is Nothing Then
        gameCount = filteredRange.Cells.Count
        Call Show_PrBar_Or_No(gameCount, "Автоанализ матчей...")
        currentGame = 0
        
        For Each cell In filteredRange
            wsList.Select
            currentGame = currentGame + 1
            matchId = Trim(CStr(cell.value & ""))
            If matchId <> "" And matchId <> "None" Then
                wsList.Cells(cell.Row, "I").Select
                Call getGame(matchId)
                doneCount = doneCount + 1
            End If
        Next cell
    End If
    autoAnalisis = doneCount
End Function
Sub getGame(id As String)
    ' Полный цикл в Python: данные ? листы ? формулы Excel ? архив ? БД
    Dim wsh As Object
    Dim command As String
    Dim resultCode As Long
    Dim workbookPath As String
    
    On Error Resume Next
    Application.ScreenUpdating = False
    Application.Calculation = xlManual
    Application.EnableEvents = False
    Application.StatusBar = False
    On Error GoTo 0
    
    Sheets("Список").Range("Y1").value = id
    workbookPath = ThisWorkbook.FullName
    
    Set wsh = CreateObject("WScript.Shell")
    command = "py ""C:\papki\work\bets\delux\get_game.py"" --workbook """ & workbookPath & """ --match-id """ & id & """"
    resultCode = wsh.Run(command, 0, True)
    
    Application.Visible = True
    Application.ScreenUpdating = True
    Application.Calculation = xlAutomatic
    Application.EnableEvents = True
    Application.StatusBar = True
    
    On Error Resume Next
    Sheets("Анализ").Select
    On Error GoTo 0
    
    If resultCode <> 0 Then
        MsgBox "Ошибка Python get_game: " & resultCode
    End If
End Sub
Function getTable(id, sourcer, table_name)
    Dim table(200) As Variant
    Dim game(25) As Variant
   
    Select Case table_name:
        Case "table_overall": table_index = 1: my_temper = "0"
        Case "table_home": table_index = 2: my_temper = "0"
        Case "table_away": table_index = 3: my_temper = "0"
        Case "form_overall": table_index = 5: my_temper = "0"
        Case "form_home": table_index = 8: my_temper = "0"
        Case "form_away": table_index = 9: my_temper = "0"
        Case "over_under_overall": table_index = 6: my_temper = "2.5"
        Case "over_under_home": table_index = 17: my_temper = "2.5"
        Case "over_under_away": table_index = 18: my_temper = "2.5"
    End Select
   
    t = 0
    sport = Sheets("Старт").Range("r2").value
    Set objHttp = CreateObject("MSXML2.XMLHTTP")
    objHttp.Open "GET", "https://" & sourcer & "x/feed/df_to_" & sport & "_" & id & "_" & table_index, False
    objHttp.setRequestHeader "X-Fsign", "SW9D1eZo"
    objHttp.send
    fs_input = objHttp.responseText
    fs_rows = Split(fs_input, "¬~")
    fs_rows_len = UBound(fs_rows) - LBound(fs_rows)
    For i = 0 To fs_rows_len - 1
        fs_row = Split(fs_rows(i), "¬")
        fs_row_len = UBound(fs_row) - LBound(fs_row)
        fs_index = Split(fs_row(0), ChrW(&HF7))
        If IsArray(fs_index) Then
            fs_index_name = fs_index(0)
            fs_index_value = fs_index(1)
        End If
        If fs_index_name = "TR" And temper = True Then
            Erase game
            For j = 0 To fs_row_len
                fs_row_parts = Split(fs_row(j), ChrW(&HF7))
                Select Case fs_row_parts(0):
                    Case "TR": game(0) = fs_row_parts(1)
                    Case "TN": game(3) = fs_row_parts(1)
                    Case "TM":
                        f = fs_row_parts(1)
                        game(6) = f
                    Case "TWR", "OUO": game(9) = fs_row_parts(1)
                    Case "TDR", "OUU": game(12) = fs_row_parts(1)
                    Case "TLR": If IsEmpty(game(15)) Then game(15) = fs_row_parts(1)
                    Case "TG":
                        gols = Split(fs_row_parts(1), ":")
                        If IsEmpty(game(15)) Then game(15) = gols(0)
                        game(16) = gols(1)
                        game(18) = gols(0)
                        game(19) = gols(1)
                    Case "TP": game(25) = fs_row_parts(1)
                End Select
                   
            Next j
            If table_index = 5 And f < 5 Then GoTo next_item
            If t > 200 Then GoTo return_table
            table(t) = game
            t = t + 1
        ElseIf fs_index_name = "ETI" Then
            temper = False
            If fs_index_value = my_temper Then temper = True
        End If
next_item:
    Next i
return_table:
    getTable = table
End Function
Sub FilterChampionships()

    Dim wsStart As Worksheet
    Dim wsList As Worksheet
    Dim sportType As Long
    Dim leagueColumn As Long
    Dim lastRow As Long
    Dim i As Long
    Dim leagues() As String
    Dim leagueCount As Long
    Dim cellValue As String

    On Error Resume Next
    Set wsStart = Sheets("Старт")
    Set wsList = Sheets("Список")
    On Error GoTo 0

    If wsStart Is Nothing Or wsList Is Nothing Then Exit Sub

    sportType = Val(wsStart.Range("R2").value)

    If sportType <= 0 Then Exit Sub

    ' AB=28 для спорта 1
    leagueColumn = 27 + sportType

    lastRow = wsStart.Cells(wsStart.Rows.Count, leagueColumn).End(xlUp).Row

    If lastRow < 2 Then Exit Sub

    If wsList.AutoFilterMode Then wsList.AutoFilterMode = False

    leagueCount = 0

    For i = 2 To lastRow

        cellValue = Trim(wsStart.Cells(i, leagueColumn).value)

        If cellValue <> "" Then
            leagueCount = leagueCount + 1
            ReDim Preserve leagues(1 To leagueCount)
            leagues(leagueCount) = cellValue
        End If

    Next i

    With wsList

        .Range("A:Q").Autofilter Field:=1, Criteria1:="<>"

        If leagueCount > 0 Then
            .Range("A:Q").Autofilter _
                Field:=1, _
                Criteria1:=leagues, _
                Operator:=xlFilterValues
        End If

    End With

End Sub


