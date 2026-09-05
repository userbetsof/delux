Attribute VB_Name = "Module2"
Sub clearParsed()
    Sheets("Очные").Columns("A:F").Clear
    Sheets("ОчныеДГ").Columns("A:F").Clear

    Sheets("Дома").Columns("A:I").Clear
    Sheets("Дома").Range("A1").value = "Чемпионат"
    Sheets("Дома").Range("B1").value = "Дата/Время"
    Sheets("Дома").Range("C1").value = "Дома"
    Sheets("Дома").Range("D1").value = "Гости"
    Sheets("Дома").Range("E1").value = "К1 в 1Т"
    Sheets("Дома").Range("F1").value = "К2 в 1Т"
    Sheets("Дома").Range("G1").value = "К1 во 2Т"
    Sheets("Дома").Range("H1").value = "К2 во 2Т"
    Sheets("Дома").Range("I1").value = "Где играли"
    
    Sheets("ДомаДома").Columns("A:I").Clear
    Sheets("ДомаДома").Range("A1").value = "Чемпионат"
    Sheets("ДомаДома").Range("B1").value = "Дата/Время"
    Sheets("ДомаДома").Range("C1").value = "Дома"
    Sheets("ДомаДома").Range("D1").value = "Гости"
    Sheets("ДомаДома").Range("E1").value = "К1 в 1Т"
    Sheets("ДомаДома").Range("F1").value = "К2 в 1Т"
    Sheets("ДомаДома").Range("G1").value = "К1 во 2Т"
    Sheets("ДомаДома").Range("H1").value = "К2 во 2Т"
    Sheets("ДомаДома").Range("I1").value = "Где играли"
    
    Sheets("ДомаГости").Columns("A:I").Clear
    Sheets("ДомаГости").Range("A1").value = "Чемпионат"
    Sheets("ДомаГости").Range("B1").value = "Дата/Время"
    Sheets("ДомаГости").Range("C1").value = "Дома"
    Sheets("ДомаГости").Range("D1").value = "Гости"
    Sheets("ДомаГости").Range("E1").value = "К1 в 1Т"
    Sheets("ДомаГости").Range("F1").value = "К2 в 1Т"
    Sheets("ДомаГости").Range("G1").value = "К1 во 2Т"
    Sheets("ДомаГости").Range("H1").value = "К2 во 2Т"
    Sheets("ДомаГости").Range("I1").value = "Где играли"
    
    Sheets("Гости").Columns("A:I").Clear
    Sheets("Гости").Range("A1").value = "Чемпионат"
    Sheets("Гости").Range("B1").value = "Дата/Время"
    Sheets("Гости").Range("C1").value = "Дома"
    Sheets("Гости").Range("D1").value = "Гости"
    Sheets("Гости").Range("E1").value = "К1 в 1Т"
    Sheets("Гости").Range("F1").value = "К2 в 1Т"
    Sheets("Гости").Range("G1").value = "К1 во 2Т"
    Sheets("Гости").Range("H1").value = "К2 во 2Т"
    Sheets("Гости").Range("I1").value = "Где играли"
    
    Sheets("ГостиДома").Columns("A:I").Clear
    Sheets("ГостиДома").Range("A1").value = "Чемпионат"
    Sheets("ГостиДома").Range("B1").value = "Дата/Время"
    Sheets("ГостиДома").Range("C1").value = "Дома"
    Sheets("ГостиДома").Range("D1").value = "Гости"
    Sheets("ГостиДома").Range("E1").value = "К1 в 1Т"
    Sheets("ГостиДома").Range("F1").value = "К2 в 1Т"
    Sheets("ГостиДома").Range("G1").value = "К1 во 2Т"
    Sheets("ГостиДома").Range("H1").value = "К2 во 2Т"
    Sheets("ГостиДома").Range("I1").value = "Где играли"
    
    Sheets("ГостиГости").Columns("A:I").Clear
    Sheets("ГостиГости").Range("A1").value = "Чемпионат"
    Sheets("ГостиГости").Range("B1").value = "Дата/Время"
    Sheets("ГостиГости").Range("C1").value = "Дома"
    Sheets("ГостиГости").Range("D1").value = "Гости"
    Sheets("ГостиГости").Range("E1").value = "К1 в 1Т"
    Sheets("ГостиГости").Range("F1").value = "К2 в 1Т"
    Sheets("ГостиГости").Range("G1").value = "К1 во 2Т"
    Sheets("ГостиГости").Range("H1").value = "К2 во 2Т"
    Sheets("ГостиГости").Range("I1").value = "Где играли"
    
    Sheets("Таблица").Columns("A:AC").Clear
    Sheets("Таблица").Range("A1").value = "Место"
    Sheets("Таблица").Range("B1").value = "Команда"
    Sheets("Таблица").Range("C1").value = "Игр"
    Sheets("Таблица").Range("D1").value = "Выиграно"
    Sheets("Таблица").Range("E1").value = "Ничьих"
    Sheets("Таблица").Range("F1").value = "Проиграно"
    Sheets("Таблица").Range("G1").value = "Забито"
    Sheets("Таблица").Range("H1").value = "Пропущено"
    Sheets("Таблица").Range("I1").value = "Очков"
    Sheets("Таблица").Range("K1").value = "Место"
    Sheets("Таблица").Range("L1").value = "Команда"
    Sheets("Таблица").Range("M1").value = "Игр"
    Sheets("Таблица").Range("N1").value = "Выиграно"
    Sheets("Таблица").Range("O1").value = "Ничьих"
    Sheets("Таблица").Range("P1").value = "Проиграно"
    Sheets("Таблица").Range("Q1").value = "Забито"
    Sheets("Таблица").Range("R1").value = "Пропущено"
    Sheets("Таблица").Range("S1").value = "Очков"
    Sheets("Таблица").Range("U1").value = "Место"
    Sheets("Таблица").Range("V1").value = "Команда"
    Sheets("Таблица").Range("W1").value = "Игр"
    Sheets("Таблица").Range("X1").value = "Выиграно"
    Sheets("Таблица").Range("Y1").value = "Ничьих"
    Sheets("Таблица").Range("Z1").value = "Проиграно"
    Sheets("Таблица").Range("AA1").value = "Забито"
    Sheets("Таблица").Range("AB1").value = "Пропущено"
    Sheets("Таблица").Range("AC1").value = "Очков"
    
    Sheets("Форма").Columns("A:AC").Clear
    Sheets("Форма").Range("A1").value = "Место"
    Sheets("Форма").Range("B1").value = "Команда"
    Sheets("Форма").Range("C1").value = "Игр"
    Sheets("Форма").Range("D1").value = "Выиграно"
    Sheets("Форма").Range("E1").value = "Ничьих"
    Sheets("Форма").Range("F1").value = "Проиграно"
    Sheets("Форма").Range("G1").value = "Забито"
    Sheets("Форма").Range("H1").value = "Пропущено"
    Sheets("Форма").Range("I1").value = "Очков"
    Sheets("Форма").Range("K1").value = "Место"
    Sheets("Форма").Range("L1").value = "Команда"
    Sheets("Форма").Range("M1").value = "Игр"
    Sheets("Форма").Range("N1").value = "Выиграно"
    Sheets("Форма").Range("O1").value = "Ничьих"
    Sheets("Форма").Range("P1").value = "Проиграно"
    Sheets("Форма").Range("Q1").value = "Забито"
    Sheets("Форма").Range("R1").value = "Пропущено"
    Sheets("Форма").Range("S1").value = "Очков"
    Sheets("Форма").Range("U1").value = "Место"
    Sheets("Форма").Range("V1").value = "Команда"
    Sheets("Форма").Range("W1").value = "Игр"
    Sheets("Форма").Range("X1").value = "Выиграно"
    Sheets("Форма").Range("Y1").value = "Ничьих"
    Sheets("Форма").Range("Z1").value = "Проиграно"
    Sheets("Форма").Range("AA1").value = "Забито"
    Sheets("Форма").Range("AB1").value = "Пропущено"
    Sheets("Форма").Range("AC1").value = "Очков"
    
    Sheets("Коэффициенты").Columns("A:C").Clear
    Sheets("Коэффициенты").Range("A1").value = "Идентификатор"
    Sheets("Коэффициенты").Range("B1").value = "Стартовый"
    Sheets("Коэффициенты").Range("C1").value = "Текущий"
    
    Sheets("Список").Select
End Sub

Sub clearMain()
    Sheets("Список").Columns("A:Q").ClearContents
    Sheets("Список").Range("A1").value = "Чемпионат"
    Sheets("Список").Range("B1").value = "Дата/Время"
    Sheets("Список").Range("C1").value = "Дома"
    Sheets("Список").Range("D1").value = "Гости"
    Sheets("Список").Range("E1").value = "Match_ID"
    Sheets("Список").Range("F1").value = "Country_ID"
    Sheets("Список").Range("G1").value = "home_ID"
    Sheets("Список").Range("H1").value = "away_ID"
    Sheets("Список").Range("I1").value = "Загрузить"
    Sheets("Список").Range("J1").value = "К1"
    Sheets("Список").Range("K1").value = "К2"
    Sheets("Список").Range("L1").value = "П1 текущий"
    Sheets("Список").Range("M1").value = "Х текущий"
    Sheets("Список").Range("N1").value = "П2 текущий"
    Sheets("Список").Range("O1").value = "П1 старт"
    Sheets("Список").Range("P1").value = "Х старт"
    Sheets("Список").Range("Q1").value = "П2 старт"
    Sheets("Список").Range("R1").value = "П1 прогруз"
    Sheets("Список").Range("S1").value = "Х прогруз"
    Sheets("Список").Range("T1").value = "П2 прогруз"
    Sheets("Список").Range("U1").value = "Sport_ID"
    Sheets("Список").Range("A:U").Autofilter
    Sheets("Список").Select
End Sub

Sub clearAll()
    clearParsed
    clearMain
    Sheets("Старт").Select

End Sub

Sub DelDups_OneList()
Dim iListCount As Integer
Dim iCtr As Integer
Application.ScreenUpdating = False
iListCount = Sheets("Список").Range("E1:E1000").Rows.Count
Sheets("Список").Range("E1").Select
Do Until ActiveCell = ""
   For iCtr = 1 To iListCount
      If ActiveCell.Row <> Sheets("Список").Cells(iCtr, 5).Row Then
         If ActiveCell.value = Sheets("Список").Cells(iCtr, 5).value Then
            Sheets("Список").Cells(iCtr, 5).EntireRow.ClearContents
            
            iCtr = iCtr + 1
         End If
      End If
   Next iCtr
   ActiveCell.Offset(1, 0).Select
Loop
Sheets("Список").Range("A:K").Sort Key1:=Sheets("Список").Columns("B"), header:=xlYes, Order1:=xlAscending
Application.ScreenUpdating = True
End Sub


Sub refreshAll() 'обновить
    Dim sFolder As String, sFiles As String, li As Long
    sFolder = ActiveWorkbook.path
    sFolder = sFolder & IIf(Right(sFolder, 1) = Application.PathSeparator, "", Application.PathSeparator)

    sFiles = Dir(sFolder & "*.xlsx")
    Do While sFiles <> ""
        li = li + 1
        sFiles = Dir
    Loop
    Call Show_PrBar_Or_No(li, "Обновление таблиц...")
    sFiles = Dir(sFolder & "*.xlsx")
    Do While sFiles <> ""
        If bShowBar Then Call MyProgresBar
        Workbooks.Open Filename:=sFolder & sFiles, UpdateLinks:=True
        ActiveWorkbook.Close False
        sFiles = Dir
    Loop
    If bShowBar Then Unload frmStatusBar
End Sub
