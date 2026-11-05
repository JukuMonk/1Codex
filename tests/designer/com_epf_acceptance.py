"""Invoke the exported method of the freshly compiled acceptance EPF."""
import gc
import os
import win32com.client
connector=win32com.client.Dispatch(os.environ.get('ONECODEX_COM_PROGID','V83.COMConnector'))
connection=connector.Connect('File="'+os.environ['ONECODEX_TEST_IB']+'";')
protection=connection.NewObject('ОписаниеЗащитыОтОпасныхДействий')
protection.ПредупреждатьОбОпасныхДействиях=False
processor=connection.ВнешниеОбработки.Создать(os.environ['ONECODEX_ARTIFACT'],False,protection)
assert processor.Самопроверка()==42
print('COM EPF PASS: exported method returned 42')
processor=protection=connection=connector=None;gc.collect()
