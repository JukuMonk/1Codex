# Что не сработало

```bat
:: 8.3.27 и .dt из базы 8.5.1
"C:\Program Files\1cv8\8.3.27.2342\bin\1cv8.exe" DESIGNER /F"C:\Базы\Копия" /RestoreIB "C:\Downloads\База.dt"
:: → «необходима версия платформы не ниже 8.5.1»
```

```python
# COM к копии: у полной роли снято право «Внешнее соединение»
import win32com.client
connector = win32com.client.Dispatch("V85.COMConnector")
connector.Connect('File="C:\\Базы\\Копия";Usr="…";Pwd="…"')
# → «Внешнее соединение не разрешено»
```

```bat
:: Внешняя обработка: сеанс ждёт ответа на «Предупреждение безопасности» (Да/Нет)
"C:\Program Files\1cv8\8.5.1.1529\bin\1cv8c.exe" ENTERPRISE /F"C:\Базы\Копия" /N"…" /P"…" ^
  /DisableStartupDialogs /DisableStartupMessages /Execute "C:\Работа\ВыгрузкаДляНоды.epf"
```

```python
# designer_lib по умолчанию — формат 8.3.27
files = {"DataProcessors/X.xml": dl.data_processor_xml("X", "…", forms=["Форма"])}  # version="2.20"
# остальная выгрузка 8.5.1 — version="2.21"
```
