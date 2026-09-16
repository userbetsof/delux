Attribute VB_Name = "ЭтаКнига"
Attribute VB_Base = "0{00020819-0000-0000-C000-000000000046}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = True
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = True
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
        Call getMS(True) 'true

        
        ' Записываем дату текущего запуска
        wsStart.Range("AA2").value = currentDate
    End If
End Sub
