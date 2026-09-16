Attribute VB_Name = "Module4"
Sub getResults()
    Dim wsh As Object
    Dim command As String
    Dim resultCode As Long
    Dim scriptPath As String
    Dim workbookPath As String

    scriptPath = "C:\papki\work\bets\delux\matches_check.py"
    workbookPath = ThisWorkbook.FullName

    Set wsh = CreateObject("WScript.Shell")
    command = "py """ & scriptPath & """ --workbook """ & workbookPath & """"
    resultCode = wsh.Run(command, 0, True)
    If resultCode <> 0 Then MsgBox "Ошибка Python-проверки матчей: " & resultCode
End Sub

Sub ProcessSportData(sport As Variant, sourcer As String, suffix As String, timezone As Integer, dayzone As Integer, wsArchive As Worksheet)
    On Error Resume Next
    
    Dim http As Object
    Dim fs_input As String
    Dim fs_rows As Variant
    Dim fs_rows_length As Integer
    Dim i As Long, j As Long
    Dim fs_row As Variant
    Dim fs_row_length As Integer
    Dim fs_index As Variant
    Dim fs_index_name As String
    Dim fs_index_value As String
    Dim sport_id As String
    Dim tour_name As String
    Dim country_id As String
    Dim match_id As String
    Dim first_home As String
    Dim first_away As String
    Dim second_home As String
    Dim second_away As String
    Dim fcell As Range
    Dim rowindx As Long
    
    Set http = CreateObject("MSXML2.XMLHTTP")
    http.Open "GET", "https://" & sourcer & "x/feed/f_" & sport & "_" & dayzone & "_" & timezone & suffix, False
    http.setRequestHeader "X-Fsign", "SW9D1eZo"
    http.send
    
    ' Проверяем, успешно ли получен ответ
    If http.status = 200 Then
        fs_input = http.responseText
        fs_rows = Split(fs_input, "~")
        fs_rows_length = UBound(fs_rows) - LBound(fs_rows)
        
        For i = 0 To fs_rows_length - 4
            fs_row = Split(fs_rows(i), "¬")
            fs_row_length = UBound(fs_row) - LBound(fs_row)
            fs_index = Split(fs_row(0), ChrW(&HF7))
            
            If IsArray(fs_index) Then
                fs_index_name = fs_index(0)
                fs_index_value = fs_index(1)
            End If
            
            If fs_index_name = "SA" Then
                sport_id = fs_index_value
            ElseIf fs_index_name = "ZA" Then
                For j = 0 To fs_row_length - 1
                    fs_row_parts = Split(fs_row(j), ChrW(&HF7))
                    If fs_row_parts(0) = "ZA" Then tour_name = fs_row_parts(1)
                    If fs_row_parts(0) = "ZB" Then country_id = fs_row_parts(1)
                Next j
            ElseIf fs_index_name = "AA" Then
                first_home = "": first_away = "": second_home = "": second_away = ""
                Dim match_status As String
                Dim match_period As String
                Dim match_minute As String
                Dim match_score As String
                Dim match_time As String
                
                For j = 0 To fs_row_length - 1
                    fs_row_parts = Split(fs_row(j), ChrW(&HF7))
                    If fs_row_parts(0) = "AA" Then match_id = fs_row_parts(1)
                    If fs_row_parts(0) = "AT" Then first_home = fs_row_parts(1)
                    If fs_row_parts(0) = "AU" Then first_away = fs_row_parts(1)
                    If fs_row_parts(0) = "BC" Then second_home = fs_row_parts(1)
                    If fs_row_parts(0) = "BD" Then second_away = fs_row_parts(1)
                    If fs_row_parts(0) = "AC" Then match_status = fs_row_parts(1)  ' Код статуса матча
                    If fs_row_parts(0) = "BX" Then match_time = fs_row_parts(1)    ' Время/минута матча
                Next j
                
                ' Получаем счет матча
                Call getScoreHT(first_home, first_away, second_home, second_away)
                
                ' Формируем счет в формате "X : Y"
                match_score = (Val(first_home) + Val(second_home)) & " : " & (Val(first_away) + Val(second_away))
                
                ' Преобразуем статус матча из кода в текст
                Dim status_text As String
                status_text = GetMatchStatusText(match_status)
                
                ' Определяем тайм и минуту
                Dim period_text As String
                Dim minute_text As String
                Call ParseMatchTime(match_time, period_text, minute_text)
                
                ' Ищем матч в архиве
                Set fcell = wsArchive.Columns("A:A").Find(match_id)
                If Not fcell Is Nothing Then
                    rowindx = fcell.Row
                    
                    ' Записываем общий счет
                    wsArchive.Range("J" & rowindx).value = match_score
                    
                    ' Записываем статус матча (колонка "Статус матча")
                    wsArchive.Range("G" & rowindx).value = status_text  ' Предполагаем, что статус в колонке BA
                    
                    ' Записываем тайм (колонка "Тайм")
                    wsArchive.Range("H" & rowindx).value = period_text   ' Предполагаем, что тайм в колонке BB
                    
                    ' Записываем минуту (колонка "Минута")
                    wsArchive.Range("I" & rowindx).value = minute_text   ' Предполагаем, что минута в колонке BC
                    
                    ' Записываем счет (колонка "Счет")
                    'wsArchive.Range("BD" & rowindx).value = match_score    ' Предполагаем, что счет в колонке BD
                    
                    ' Определяем статус прогноза и рассчитываем прибыль
                    Dim forecast As String
                    Dim forecastAK As String
                    Dim forecastBK As String
                    Dim total_home_int As Integer
                    Dim total_away_int As Integer
                    
                    forecast = wsArchive.Range("K" & rowindx).value
                    forecastAK = wsArchive.Range("O" & rowindx).value
                    forecastBK = wsArchive.Range("S" & rowindx).value
                    
                    total_home_int = Val(first_home) + Val(second_home)
                    total_away_int = Val(first_away) + Val(second_away)
                    
                    ' Определяем исход матча
                    Dim result As String
                    If total_home_int > total_away_int Then
                        result = "П1"
                    ElseIf total_home_int < total_away_int Then
                        result = "П2"
                    Else
                        result = "X"
                    End If
                    
                    ' Обработка основного прогноза (AJ)
                    Call CalculateForecastResult(forecast, result, total_home_int, total_away_int, _
                                                wsArchive, rowindx, "D", "E", "F", _
                                                "I", "J", "K", "M", "N", "L")
                    
                    ' Обработка прогноза для AK (AK)
                    Call CalculateForecastResult(forecastAK, result, total_home_int, total_away_int, _
                                                wsArchive, rowindx, "D", "E", "F", _
                                                "I", "J", "K", "Q", "R", "P")
                    
                    ' Обработка прогноза для BK (BK)
                    Call CalculateForecastResult(forecastBK, result, total_home_int, total_away_int, _
                                                wsArchive, rowindx, "D", "E", "F", _
                                                "I", "J", "K", "U", "V", "T")
                End If
            End If
        Next i
    End If
End Sub

' Функция для преобразования кода статуса в текстовое описание
Function GetMatchStatusText(statusCode As String) As String
    Dim statuses As Object
    Set statuses = CreateObject("Scripting.Dictionary")
    
    ' Словарь статусов из JavaScript кода
    statuses.Add "1", "Не начался"
    statuses.Add "45", "Будет доигран позже"
    statuses.Add "42", "Ждем..."
    statuses.Add "2", "Live"
    statuses.Add "14", "1-й период"
    statuses.Add "15", "2-й период"
    statuses.Add "16", "3-й период"
    statuses.Add "6", "Овертайм"
    statuses.Add "7", "Буллиты"
    statuses.Add "46", "Перерыв"
    statuses.Add "3", "Завершен"
    statuses.Add "10", "После овертайма"
    statuses.Add "11", "После буллитов"
    statuses.Add "9", "Неявка"
    statuses.Add "43", "Задержка"
    statuses.Add "36", "Прерван"
    statuses.Add "4", "Перенесен"
    statuses.Add "5", "Отменен"
    statuses.Add "37", "Прерван"
    statuses.Add "54", "Тех. поражение"
    
    If statuses.Exists(statusCode) Then
        GetMatchStatusText = statuses(statusCode)
    Else
        GetMatchStatusText = "Неизвестный статус (" & statusCode & ")"
    End If
End Function

' Процедура для парсинга времени матча (тайм и минута)
Sub ParseMatchTime(timeString As String, ByRef period As String, ByRef minute As String)
    Dim timeValue As Integer
    
    ' Очищаем значения
    period = ""
    minute = ""
    
    If timeString = "" Or IsNull(timeString) Then
        Exit Sub
    End If
    
    ' Проверяем, является ли время числом
    If IsNumeric(timeString) Then
        timeValue = CInt(timeString)
        
        ' Определяем тайм на основе времени
        If timeValue < 0 Then
            period = "До матча"
            minute = ""
        ElseIf timeValue >= 0 And timeValue <= 45 Then
            period = "1-й тайм"
            minute = timeValue & "'"
        ElseIf timeValue > 45 And timeValue <= 90 Then
            period = "2-й тайм"
            minute = (timeValue - 45) & "'"
        ElseIf timeValue > 90 And timeValue <= 105 Then
            period = "Овертайм"
            minute = (timeValue - 90) & "'"
        ElseIf timeValue > 105 Then
            period = "Пенальти"
            minute = ""
        End If
    Else
        ' Если время в формате "45+2" или подобном
        If InStr(timeString, "+") > 0 Then
            Dim parts As Variant
            parts = Split(timeString, "+")
            If UBound(parts) >= 1 Then
                If IsNumeric(parts(0)) Then
                    minute = timeString & "'"
                    If CInt(parts(0)) <= 45 Then
                        period = "1-й тайм"
                    Else
                        period = "2-й тайм"
                    End If
                End If
            End If
        Else
            minute = timeString
        End If
    End If
End Sub

' Универсальная функция для расчета результата прогноза
Sub CalculateForecastResult(forecast As String, result As String, total_home As Integer, total_away As Integer, _
                           wsArchive As Worksheet, rowindx As Long, _
                           colP1 As String, colX As String, colP2 As String, _
                           col1X As String, col12 As String, colX2 As String, _
                           colStatus As String, colProfit As String, _
                           colCoeffSource As String)
    
    Dim status As String
    Dim profit As Double
    Dim coeffValue As Double
    Dim wsKf As Worksheet
    Set wsKf = ThisWorkbook.Sheets("kf")
    
    status = ""
    profit = 0
    
    ' Очищаем прогноз от лишних пробелов и приводим к верхнему регистру для сравнения
    Dim cleanForecast As String
    cleanForecast = UCase(Trim(forecast))
    
    ' Проверяем на пустой прогноз или прочерк
    If cleanForecast = "" Or cleanForecast = "-" Then
        wsArchive.Range(colStatus & rowindx).value = "Нет прогноза"
        wsArchive.Range(colProfit & rowindx).value = 0
        Exit Sub
    End If
    
    ' Обработка различных типов прогнозов
    Select Case cleanForecast
        Case "П1"
            coeffValue = GetCoeffValue(wsArchive, rowindx, colP1, colCoeffSource)
            If result = "П1" Then
                status = "Выигрыш"
                profit = coeffValue - 1
            Else
                status = "Проигрыш"
                profit = -1
            End If
            
        Case "П2"
            coeffValue = GetCoeffValue(wsArchive, rowindx, colP2, colCoeffSource)
            If result = "П2" Then
                status = "Выигрыш"
                profit = coeffValue - 1
            Else
                status = "Проигрыш"
                profit = -1
            End If
            
        Case "Х", "X"
            coeffValue = GetCoeffValue(wsArchive, rowindx, colX, colCoeffSource)
            If result = "X" Then
                status = "Выигрыш"
                profit = coeffValue - 1
            Else
                status = "Проигрыш"
                profit = -1
            End If
            
        Case "1X"
            coeffValue = GetCoeffValue(wsArchive, rowindx, col1X, colCoeffSource)
            If result = "П1" Or result = "X" Then
                status = "Выигрыш"
                profit = coeffValue - 1
            Else
                status = "Проигрыш"
                profit = -1
            End If
            
        Case "X2"
            coeffValue = GetCoeffValue(wsArchive, rowindx, colX2, colCoeffSource)
            If result = "П2" Or result = "X" Then
                status = "Выигрыш"
                profit = coeffValue - 1
            Else
                status = "Проигрыш"
                profit = -1
            End If
            
        Case "12"
            coeffValue = GetCoeffValue(wsArchive, rowindx, col12, colCoeffSource)
            If result = "П1" Or result = "П2" Then
                status = "Выигрыш"
                profit = coeffValue - 1
            Else
                status = "Проигрыш"
                profit = -1
            End If
            
        Case Else
            ' Обработка фор
            If InStr(1, cleanForecast, "Ф1") > 0 Then
                Call HandleHandicap(cleanForecast, "HOME", total_home, total_away, _
                                   wsArchive, rowindx, colCoeffSource, status, profit)
            
            ElseIf InStr(1, cleanForecast, "Ф2") > 0 Then
                Call HandleHandicap(cleanForecast, "AWAY", total_home, total_away, _
                                   wsArchive, rowindx, colCoeffSource, status, profit)
            
            ' Обработка тоталов
            ElseIf InStr(1, cleanForecast, "ТБ") > 0 Then
                Call HandleTotal(cleanForecast, "OVER", total_home, total_away, _
                                wsArchive, rowindx, colCoeffSource, status, profit)
            
            ElseIf InStr(1, cleanForecast, "ТМ") > 0 Then
                Call HandleTotal(cleanForecast, "UNDER", total_home, total_away, _
                                wsArchive, rowindx, colCoeffSource, status, profit)
            
            ' Обработка ОЗ (обе забьют)
            ElseIf cleanForecast = "ОЗ" Then
                coeffValue = GetCoeffValue(wsArchive, rowindx, "AS", colCoeffSource) ' AS - ОЗ Да
                If total_home > 0 And total_away > 0 Then
                    status = "Выигрыш"
                    profit = coeffValue - 1
                Else
                    status = "Проигрыш"
                    profit = -1
                End If
            
            Else
                status = "Неизвестный прогноз"
                profit = 0
            End If
    End Select
    
    ' Записываем результаты
    wsArchive.Range(colStatus & rowindx).value = status
    wsArchive.Range(colProfit & rowindx).value = profit
    
End Sub

' Функция для получения значения коэффициента
Function GetCoeffValue(wsArchive As Worksheet, rowindx As Long, primaryCol As String, backupCol As String) As Double
    Dim value As Variant

    value = wsArchive.Range(backupCol & rowindx).value

    ' Если все еще не число, возвращаем 1 (нейтральное значение)
    If IsNumeric(value) Then
        GetCoeffValue = CDbl(value)
    Else
        GetCoeffValue = 1
    End If
End Function

' Обработка фор
Sub HandleHandicap(forecast As String, team As String, total_home As Integer, total_away As Integer, _
                  wsArchive As Worksheet, rowindx As Long, coeffCol As String, _
                  ByRef status As String, ByRef profit As Double)
    
    Dim handicapValue As Double
    Dim difference As Integer
    Dim coeff As Double
    
    ' Извлекаем значение форы (например, из "Ф1(-1.5)" или "Ф1(0)")
    Dim handicapStr As String
    Dim startPos As Integer
    Dim endPos As Integer
    
    startPos = InStr(1, forecast, "(")
    endPos = InStr(1, forecast, ")")
    
    If startPos > 0 And endPos > startPos Then
        handicapStr = Mid(forecast, startPos + 1, endPos - startPos - 1)
        handicapStr = Replace(handicapStr, ",", ".") ' Заменяем запятую на точку
        handicapValue = Val(handicapStr)
    Else
        ' Если формат нестандартный, пробуем извлечь число после Ф1/Ф2
        handicapStr = Replace(Replace(forecast, "Ф1", ""), "Ф2", "")
        handicapStr = Replace(handicapStr, ",", ".")
        handicapValue = Val(handicapStr)
    End If
    
    ' Получаем коэффициент
    coeff = GetCoeffValue(wsArchive, rowindx, coeffCol, coeffCol)
    
    ' Рассчитываем разницу с учетом форы
    If team = "HOME" Then
        difference = total_home + handicapValue - total_away
    Else ' AWAY
        difference = total_away + handicapValue - total_home
    End If
    
    ' Определяем результат
    If difference > 0 Then
        status = "Выигрыш"
        profit = coeff - 1
    ElseIf difference = 0 Then
        status = "Возврат"
        profit = 0
    Else
        status = "Проигрыш"
        profit = -1
    End If
    
End Sub

' Обработка тоталов
Sub HandleTotal(forecast As String, totalType As String, total_home As Integer, total_away As Integer, _
               wsArchive As Worksheet, rowindx As Long, coeffCol As String, _
               ByRef status As String, ByRef profit As Double)
    
    Dim totalValue As Double
    Dim matchTotal As Integer
    Dim coeff As Double
    
    ' Извлекаем значение тотала (например, из "ТБ2.5" или "ТМ3")
    Dim totalStr As String
    
    If totalType = "OVER" Then
        totalStr = Replace(forecast, "ТБ", "")
    Else
        totalStr = Replace(forecast, "ТМ", "")
    End If
    
    totalStr = Replace(totalStr, ",", ".") ' Заменяем запятую на точку
    totalValue = Val(totalStr)
    matchTotal = total_home + total_away
    
    ' Получаем коэффициент
    coeff = GetCoeffValue(wsArchive, rowindx, coeffCol, coeffCol)
    
    ' Определяем результат
    If totalType = "OVER" Then
        If matchTotal > totalValue Then
            status = "Выигрыш"
            profit = coeff - 1
        ElseIf matchTotal = totalValue Then
            status = "Возврат"
            profit = 0
        Else
            status = "Проигрыш"
            profit = -1
        End If
    Else ' UNDER
        If matchTotal < totalValue Then
            status = "Выигрыш"
            profit = coeff - 1
        ElseIf matchTotal = totalValue Then
            status = "Возврат"
            profit = 0
        Else
            status = "Проигрыш"
            profit = -1
        End If
    End If
    
End Sub

Sub ClearArchive()
    src = ThisWorkbook.Sheets("Архив").Range("A" & Cells.Rows.Count).End(xlUp).Row + 1
    Dim lRetVal As Long
    lRetVal = MsgBox("Вы уверены?", vbYesNo + vbQuestion, "Вы собираетесь удалить Архив...")
    If lRetVal = vbNo Then
        Exit Sub
        End If
    ThisWorkbook.Sheets("Архив").Range("A2:CF" & src).ClearContents

End Sub

Sub ToListing()
    ThisWorkbook.Sheets("Список").Activate
    ActiveCell.Offset(1, 0).Activate
End Sub
Sub ToArchive()
    ThisWorkbook.Sheets("Архив").Activate
    ActiveCell.Offset(1, 0).Activate
End Sub
Sub ToAnalyse()
    ThisWorkbook.Sheets("Анализ").Activate
    ActiveCell.Offset(1, 0).Activate
End Sub
Sub Autofilter()
    Range("A1").Select
    selection.Autofilter
End Sub

