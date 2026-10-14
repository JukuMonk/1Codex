# -*- coding: utf-8 -*-
"""Уровень 5 (knowledge/testing.md набора): все формы, затронутые доработками, — ПолучитьФорму в клиенте.

Тестовая вставка — отдельным временным расширением «НПЦАП_Тест» (конфигурацию и НПЦАП_Доработки не трогает):
  * заимствованный ОбщегоНазначенияКлиентПереопределяемый: &После("ПослеНачалаРаботыСистемы") — обход форм
    по параметру /C ПроверкаФорм, итог в ХранилищеОбщихНастроек, клиент завершается сам;
  * свой серверный модуль тст_ПроверкаСервер: список форм и запись итога.
Список форм — все формы объектов расширения НПЦАП_Доработки (свои и заимствованные) + общие формы.

  python tools/test_forms.py [ext_base|base]       # собрать, загрузить, прогнать, удалить тестовое расширение
"""
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ext as be  # noqa: E402
import com  # noqa: E402
import v8  # noqa: E402

dl, t = be.dl, be.t
NAME = 'НПЦАП_Тест'
OUT = os.path.join(be.ROOT, 'src', 'test_ext', NAME)
RU = {'Catalogs': 'Справочник', 'Documents': 'Документ', 'DataProcessors': 'Обработка', 'Reports': 'Отчет',
      'InformationRegisters': 'РегистрСведений', 'AccumulationRegisters': 'РегистрНакопления',
      'ChartsOfCharacteristicTypes': 'ПланВидовХарактеристик', 'ExchangePlans': 'ПланОбмена'}
OVR = 'ОбщегоНазначенияКлиентПереопределяемый'


def form_names():
    names = []
    for d in sorted(os.listdir(be.OUT)):
        base = os.path.join(be.OUT, d)
        if d == 'CommonForms':
            names += ['ОбщаяФорма.' + f[:-4] for f in sorted(os.listdir(base)) if f.endswith('.xml')]
            continue
        if d not in RU or not os.path.isdir(base):
            continue
        for obj in sorted(os.listdir(base)):
            fdir = os.path.join(base, obj, 'Forms')
            if os.path.isdir(fdir):
                names += ['%s.%s.Форма.%s' % (RU[d], obj, f[:-4]) for f in sorted(os.listdir(fdir)) if f.endswith('.xml')]
    return names


def build():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    w = lambda rel, txt: dl.write(os.path.join(OUT, rel), txt)
    # заимствованный переопределяемый модуль БСП
    ve = be.root_elem(os.path.join(be.VENDOR, 'CommonModules', OVR + '.xml'))
    p = [t(1) + '<CommonModule uuid="%s">' % dl.uid(NAME, OVR), be.internal_info(ve, NAME + OVR, ('Module',))]
    p += be.adopted_props('CommonModule', ve, 2)
    p.append(t(1) + '</CommonModule>')
    w(os.path.join('CommonModules', OVR + '.xml'), be.md_header() + '\n'.join(p) + '\n</MetaDataObject>')
    w(os.path.join('CommonModules', OVR, 'Ext', 'Module.bsl'), '''&После("ПослеНачалаРаботыСистемы")
Процедура тст_ПослеНачалаРаботыСистемы()

	Если СтрНайти(ПараметрЗапуска, "ПроверкаФорм") = 0 Тогда
		Возврат;
	КонецЕсли;
	ОшибкиФорм = Новый Массив;
	ИменаФорм = тст_ПроверкаСервер.ИменаФорм();
	Для Каждого ИмяФормы Из ИменаФорм Цикл
		Попытка
			ПолучитьФорму(ИмяФормы, , , Новый УникальныйИдентификатор);
		Исключение
			ОшибкиФорм.Добавить(ИмяФормы + ": " + ПодробноеПредставлениеОшибки(ИнформацияОбОшибке()));
		КонецПопытки;
	КонецЦикла;
	тст_ПроверкаСервер.ЗаписатьИтог("ФОРМЫ: проверено " + ИменаФорм.Количество() + ", ошибок " + ОшибкиФорм.Количество()
		+ Символы.ПС + СтрСоединить(ОшибкиФорм, Символы.ПС + "----" + Символы.ПС));
	ЗавершитьРаботуСистемы(Ложь);

КонецПроцедуры
''')
    # свой серверный модуль
    xml = dl.common_module_xml('тст_ПроверкаСервер', 'Проверка форм (тест)', kind='server_call')
    xml = xml.replace(dl.uid('CommonModule.тст_ПроверкаСервер'), dl.uid(NAME, 'тст_ПроверкаСервер'))
    w(os.path.join('CommonModules', 'тст_ПроверкаСервер.xml'), xml)
    names = form_names()
    body = ['Функция ИменаФорм() Экспорт', '\tИмена = Новый Массив;']
    body += ['\tИмена.Добавить("%s");' % n for n in names]
    body += ['\tВозврат Имена;', 'КонецФункции', '',
             'Процедура ЗаписатьИтог(Текст) Экспорт',
             '\tХранилищеОбщихНастроек.Сохранить("ТестФормы", "Итог", Текст);', 'КонецПроцедуры', '']
    w(os.path.join('CommonModules', 'тст_ПроверкаСервер', 'Ext', 'Module.bsl'), '\n'.join(body))
    # язык и корень
    ve = be.root_elem(os.path.join(be.VENDOR, 'Languages', 'Русский.xml'))
    p = [t(1) + '<Language uuid="%s">' % dl.uid(NAME, 'Language'), t(2) + '<InternalInfo/>']
    p += be.adopted_props('Language', ve, 2) + [t(1) + '</Language>']
    w(os.path.join('Languages', 'Русский.xml'), be.md_header() + '\n'.join(p) + '\n</MetaDataObject>')
    cfg = be.rd(os.path.join(be.OUT, 'Configuration.xml'))
    head = cfg[:cfg.index('<ChildObjects>')]
    head = head.replace('<Name>%s</Name>' % be.EXT_NAME, '<Name>%s</Name>' % NAME).replace('<NamePrefix>дс_</NamePrefix>', '<NamePrefix>тст_</NamePrefix>')
    # ClassId постоянные; новые — только uuid корня и ObjectId
    head = __import__('re').sub(r'(<xr:ObjectId>|Configuration uuid=")([0-9a-f-]{36})',
                                lambda m: m.group(1) + dl.uid(NAME, m.group(2)), head)
    w('Configuration.xml', head + dl.configuration_child_objects(
        {'Language': ['Русский'], 'CommonModule': [OVR, 'тст_ПроверкаСервер']}).lstrip('\t') + '\n\t</Configuration>\n</MetaDataObject>')
    return names


def stop_clients(ib):
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match '1cv8' -and $_.CommandLine -like '*%s*' } "
          "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" % ib)
    subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True)


def main(base='ext_base'):
    ib = os.path.join(be.ROOT, base)
    names = build()
    print('форм к проверке:', len(names))
    if v8.run('DESIGNER', '/LoadConfigFromFiles "%s" -Extension "%s"' % (OUT, NAME), 'test_load.log', ib=ib) or \
       v8.run('DESIGNER', '/UpdateDBCfg -Extension "%s"' % NAME, 'test_update.log', ib=ib):
        return 1
    cn = com.connect(base)
    for e in cn.РасширенияКонфигурации.Получить():
        if e.Имя == NAME:
            защита = cn.NewObject('ОписаниеЗащитыОтОпасныхДействий')
            защита.ПредупреждатьОбОпасныхДействиях = False
            e.ЗащитаОтОпасныхДействий = защита
            e.БезопасныйРежим = False
            e.Записать()
    cn.ХранилищеОбщихНастроек.Удалить('ТестФормы', 'Итог', '')
    cmd = '"%s" ENTERPRISE /F"%s" /DisableStartupDialogs /DisableStartupMessages /C "ПроверкаФорм"' % (v8.V8.replace('1cv8.exe', '1cv8c.exe'), ib)
    subprocess.Popen(cmd)
    итог, t0 = None, time.time()
    while time.time() - t0 < 900:
        time.sleep(5)
        try:
            итог = com.connect(base).ХранилищеОбщихНастроек.Загрузить('ТестФормы', 'Итог')
        except Exception:
            итог = None
        if итог:
            break
    time.sleep(3)
    stop_clients(ib)
    # тестовое расширение — удалить
    v8.run('DESIGNER', '/DeleteCfg -Extension "%s"' % NAME, 'test_delete.log', ib=ib)
    if not итог:
        print('итога нет: клиент не дошёл до проверки (диалог при запуске?)')
        return 1
    with open(os.path.join(be.ROOT, 'logs', 'forms_%s.txt' % base), 'w', encoding='utf-8') as f:
        f.write(итог)
    print(итог[:6000])
    return 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))
