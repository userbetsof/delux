Attribute VB_Name = "Module3"

Public Const ODDS_BK_COLS As Long = 3
Public Const ODDS_BK_TITLE_ROW As Long = 1
Public Const ODDS_SUBHEADER_ROW As Long = 2
Public Const ODDS_DATA_START_ROW As Long = 3
Public Const ODDS_STATIC_MARKET_COUNT As Long = 8
Public Const ODDS_FIRST_BK_COL As Long = 3

Public Function GetOddsDataLastRow(wsOdds As Worksheet) As Long
    Dim lastCol As Long
    Dim startCol As Long
    Dim r As Long
    Dim maxRow As Long
    
    maxRow = ODDS_DATA_START_ROW
    lastCol = wsOdds.Cells(ODDS_SUBHEADER_ROW, wsOdds.Columns.Count).End(xlToLeft).Column
    If lastCol < ODDS_FIRST_BK_COL Then
        GetOddsDataLastRow = maxRow
        Exit Function
    End If
    
    For startCol = ODDS_FIRST_BK_COL To lastCol Step ODDS_BK_COLS
        r = wsOdds.Cells(wsOdds.Rows.Count, startCol).End(xlUp).Row
        If r > maxRow Then maxRow = r
    Next startCol
    
    GetOddsDataLastRow = maxRow
End Function

Sub getOdds(id As String)
    Dim wsList As Worksheet
    Dim wsAnalysis As Worksheet
    Dim foundRow As Range
    Dim searchRange As Range
    
    Set wsList = ThisWorkbook.Sheets("Список")
    Set wsAnalysis = ThisWorkbook.Sheets("Анализ")
    
    Set searchRange = wsList.Range("E:E")
    Set foundRow = searchRange.Find(What:=id, LookIn:=xlValues, LookAt:=xlWhole)
    
    If Not foundRow Is Nothing Then
        wsAnalysis.Range("B15").value = wsList.Cells(foundRow.Row, "O").value
        wsAnalysis.Range("C15").value = wsList.Cells(foundRow.Row, "P").value
        wsAnalysis.Range("D15").value = wsList.Cells(foundRow.Row, "Q").value
    End If
    
    Call vorkaOdds(id)
End Sub

Sub vorkaOdds(id As String)
    Dim wsh As Object
    Dim command As String
    Dim resultCode As Long
    Dim scriptPath As String
    Dim workbookPath As String

    scriptPath = "C:\papki\work\bets\delux\odds_fetch.py"
    workbookPath = ThisWorkbook.FullName

    Set wsh = CreateObject("WScript.Shell")
    command = "py """ & scriptPath & """ --workbook """ & workbookPath & """ --event-id """ & id & """"
    resultCode = wsh.Run(command, 0, True)
    If resultCode <> 0 Then
        MsgBox "Ошибка получения коэффициентов из интернета через Python: " & resultCode
        Exit Sub
    End If

    Call TransferKfData
End Sub

Function GetBookmakerStartCol(bookmakerIndex As Integer) As Long
    GetBookmakerStartCol = ODDS_FIRST_BK_COL + (bookmakerIndex - 1) * ODDS_BK_COLS
End Function

Function IsCorrectBookmakerBlock(col As Long, bookmakerIndex As Integer) As Boolean
    Dim startCol As Long
    startCol = GetBookmakerStartCol(bookmakerIndex)
    IsCorrectBookmakerBlock = (col >= startCol And col <= startCol + ODDS_BK_COLS - 1)
End Function

