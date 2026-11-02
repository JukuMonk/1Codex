"""Real COM checks, called only with the isolated test base environment."""
import gc
import os
import sys
import win32com.client

sys.stdout.reconfigure(encoding='utf-8')
path=os.environ['ONECODEX_TEST_IB']
connector=win32com.client.Dispatch(os.environ.get('ONECODEX_COM_PROGID','V83.COMConnector'))
connection=connector.Connect('File="'+path+'";')
assert connection.тстСервис.Проверка()=='1Codex OK'
catalog=connection.Справочники.тстТовары
item=catalog.СоздатьЭлемент();item.Наименование='Проверка 1Codex';item.Артикул='AUDIT-001';item.Записать()
uid=str(item.Ссылка.УникальныйИдентификатор())
item.Наименование='Проверка повторной записи';item.Записать()
assert str(item.Ссылка.УникальныйИдентификатор())==uid
assert item.Ссылка.ПолучитьОбъект().Артикул=='AUDIT-001'
query=connection.NewObject('Запрос')
query.Текст='ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК ВсегоЗаписей ИЗ Справочник.тстТовары ГДЕ Артикул = &Артикул'
query.УстановитьПараметр('Артикул','AUDIT-001')
rows=query.Выполнить().Выбрать();assert rows.Следующий();assert rows.ВсегоЗаписей>=1
print('COM PASS: module call, catalog write/read, stable UUID on repeated write, query parameter')
rows=query=item=catalog=connection=connector=None
gc.collect()
