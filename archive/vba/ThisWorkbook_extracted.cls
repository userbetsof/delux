Attribute VB_Name = "ЭтаКнига"
Private Sub Workbook_Open()
    Dim wsStart As Worksheet
    Dim lastRunDate As Date
    Dim currentDate As Date
    
    Set wsStart = ThisWorkbook.Sheets("Старт")
    
    ' Получаем текущую дату
    currentDate = Date
    
    ' Получаем дату последнего запуска из колонки AA
    If IsDate(wsStart.Range("AA2").value) Then
        lastRunDate = CDate(wsStart.Range("AA2").value)
    Else
        ' Если дата невалидная, устанавливаем вчерашнюю дату чтобы запуск произошел
        lastRunDate = currentDate - 1
    End If
    
    ' Проверяем, был ли уже запуск сегодня
    If lastRunDate < currentDate Then
        ' Если запуска сегодня не было, выполняем код
        wsStart.Select
        wsStart.Range("V2").value = 7
        Call getResults
        wsStart.Range("V2").value = 8
        
        ' AA2 ставит getMS только после реального анализа
        Call getMS(True) 'true
    End If
End Sub
