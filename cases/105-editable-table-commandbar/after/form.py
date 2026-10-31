# CORRECT: пользователь должен иметь возможность добавлять и удалять строки.
form.table('Подвкладки', 'Объект.Подвкладки', [form.input('Вкладка')],
           change_rowset=True, autofill=True)
