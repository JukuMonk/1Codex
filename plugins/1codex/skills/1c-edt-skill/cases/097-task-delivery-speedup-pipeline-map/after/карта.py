# -*- coding: utf-8 -*-
"""Карта конфигурации для правки без раскопок (18.10.2026): по объектам подсистем — реквизиты и ТЧ, формы (дерево
элементов с путями и событиями), процедуры модулей объекта, менеджера и форм с первой строкой комментария; отдельно —
экспортные функции общих модулей. Читать раздел нужного объекта ПЕРЕД правкой (grep «### Catalog.X»), а не искать
по выгрузке: на ДиЗ-05 изучение кода стоило 3+ минуты.

  python инструменты/карта.py [подсистема …]      # по умолчанию Методолог и ПроектыИЗадачи → КАРТА.md
Перегенерируется командой «цикл» (платформа.py) после каждой загрузки; пишет файл только при изменении.
"""
import contextlib
import csv
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import платформа as пл  # noqa: E402
import схема_форм  # noqa: E402

ИТОГ = os.path.join(пл.КОРЕНЬ, 'КАРТА.md')
ПАПКИ = {'Catalog': 'Catalogs', 'DataProcessor': 'DataProcessors', 'Report': 'Reports', 'Document': 'Documents',
         'InformationRegister': 'InformationRegisters', 'Enum': 'Enums'}
ВИДЫ_CSV = {'Catalog': 'Справочники', 'Document': 'Документы', 'DataProcessor': 'Обработки', 'Report': 'Отчёты',
            'InformationRegister': 'Регистры сведений', 'Enum': 'Перечисления'}


def процедуры(путь, только_экспорт=False):
    """[(директива, вид, имя(параметры), экспорт, комментарий над объявлением)]."""
    if not os.path.exists(путь):
        return []
    строки = io.open(путь, encoding='utf-8-sig').read().splitlines()
    итог = []
    for н, с in enumerate(строки):
        м = re.match(r'\s*(Процедура|Функция)\s+(\w+)\s*\(([^)]*)\)?\s*(Экспорт)?', с)
        if not м:
            continue
        if только_экспорт and not м.group(4):
            continue
        директива, комментарий, к = '', [], н - 1
        while к >= 0 and (строки[к].strip().startswith('//') or строки[к].strip().startswith('&')):
            if строки[к].strip().startswith('&'):
                директива = строки[к].strip()
            else:
                комментарий.insert(0, строки[к].strip()[2:].strip())
            к -= 1
        параметры = re.sub(r'\s+', ' ', (м.group(3) or '').strip())
        итог.append((директива, м.group(1), '%s(%s)' % (м.group(2), параметры), bool(м.group(4)),
                     ' '.join(комментарий)[:160]))
    return итог


def строки_модуля(путь, заголовок, только_экспорт=False):
    п = процедуры(путь, только_экспорт)
    if not п:
        return []
    вывод = ['  %s:' % заголовок]
    for д, вид, имя, эксп, ком in п:
        вывод.append('    %s %s%s%s%s' % (вид, имя, ' Экспорт' if эксп else '', ' ' + д if д else '',
                                         ' — ' + ком if ком else ''))
    return вывод


def реквизиты(вид, имя):
    вид_csv = ВИДЫ_CSV.get(вид)
    if not вид_csv:
        return []
    вывод = []
    with io.open(os.path.join(пл.КОРЕНЬ, 'метаданные.csv'), encoding='utf-8-sig') as f:
        for р in csv.reader(f, delimiter=';'):
            if len(р) >= 6 and р[0] == вид_csv and р[1] == имя:
                вывод.append('    %-16s %-28s %-36s %s' % (р[2], р[3], р[4], р[5]))
    return ['  реквизиты (раздел; имя; синоним; тип):'] + вывод if вывод else []


def main(подсистемы=('Методолог', 'ПроектыИЗадачи')):
    части = ['# Карта конфигурации (генерируется: python инструменты/карта.py — не править руками)', '',
             'Подсистемы: ' + ', '.join(подсистемы) + '. Формы: тип элемента, имя, «заголовок», [путь данных], '
             'события; модули — процедуры с директивой и комментарием над объявлением.', '']
    уже = set()
    for подсистема in подсистемы:
        for вид, имя in пл.состав_подсистемы(подсистема):
            if вид not in ПАПКИ or (вид, имя) in уже:
                continue
            уже.add((вид, имя))
            части += ['', '### %s.%s' % (вид, имя)]
            части += реквизиты(вид, имя)
            папка = os.path.join(пл.ВЫГРУЗКА, ПАПКИ[вид], имя)
            части += строки_модуля(os.path.join(папка, 'Ext', 'ObjectModule.bsl'), 'модуль объекта')
            части += строки_модуля(os.path.join(папка, 'Ext', 'ManagerModule.bsl'), 'модуль менеджера')
            формы = os.path.join(папка, 'Forms')
            if os.path.isdir(формы):
                for форма in sorted(ф for ф in os.listdir(формы) if not ф.endswith('.xml')):
                    п = os.path.join(формы, форма, 'Ext', 'Form.xml')
                    if not os.path.exists(п):
                        continue
                    import xml.etree.ElementTree as ET
                    вывод = []
                    схема_форм.обойти(ET.parse(п).getroot(), 2, вывод)
                    части.append('  форма %s:' % форма)
                    части += вывод
                    части += ['  ' + с for с in строки_модуля(os.path.join(формы, форма, 'Ext', 'Form', 'Module.bsl'),
                                                              'модуль формы %s' % форма)]
    части += ['', '## Общие модули — экспортные процедуры и функции']
    общие = os.path.join(пл.ВЫГРУЗКА, 'CommonModules')
    for имя in sorted(и for и in os.listdir(общие) if not и.endswith('.xml')):
        мета = io.open(os.path.join(общие, имя + '.xml'), encoding='utf-8-sig').read()
        флаги = [ф for ф in ('Server', 'ServerCall', 'ClientManagedApplication', 'Global', 'Privileged')
                 if '<%s>true</%s>' % (ф, ф) in мета]
        части += ['', '### ОбщийМодуль.%s [%s]' % (имя, ', '.join(флаги))]
        части += строки_модуля(os.path.join(общие, имя, 'Ext', 'Module.bsl'), 'экспорт', только_экспорт=True)
    текст = '\n'.join(части) + '\n'
    старый = io.open(ИТОГ, encoding='utf-8').read() if os.path.exists(ИТОГ) else ''
    if текст != старый:
        io.open(ИТОГ, 'w', encoding='utf-8', newline='\n').write(текст)
    print('карта: %s (%d КБ, объектов %d)%s' % (ИТОГ, len(текст.encode('utf-8')) // 1024, len(уже),
                                              '' if текст != старый else ', без изменений'))


if __name__ == '__main__':
    main(tuple(sys.argv[1:]) or ('Методолог', 'ПроектыИЗадачи'))
