# -*- coding: utf-8 -*-
"""Карта конфигурации (КАРТА.md) по XML-выгрузке Конфигуратора — правка без раскопок (Case 097).

По объектам выбранных подсистем: реквизиты и табличные части (имя, синоним, тип), формы — дерево элементов (тип, имя,
«заголовок», [путь данных], события), процедуры модулей объекта, менеджера и форм с директивой и комментарием над
объявлением; отдельно — экспортные процедуры общих модулей с флагами. Перед правкой объекта читать его раздел
(`grep -n "### Catalog.Имя" КАРТА.md`, затем Read с этой строки) вместо grep по выгрузке: на ДиЗ-05 проекта UP
раскопки кода стоили 3+ минуты, с картой (ДиЗ-07) — около минуты.

  python <skill>/tools/config_map.py <выгрузка> [подсистема …] [--итог КАРТА.md]
  python <skill>/tools/config_map.py конфигурация Методолог ПроектыИЗадачи --итог КАРТА.md

Без подсистем — все объекты выгрузки (для большой типовой — укажите подсистемы). Файл пишется только при изменении;
перегенерировать после каждой загрузки в базу (в конвейере «цикл» проекта — шаг «карта»).
Проект UP (своя конфигурация 8.5.1 без EDT), 18.10.2026.
"""
import io
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding='utf-8')

ПАПКИ = {'Catalog': 'Catalogs', 'Document': 'Documents', 'DataProcessor': 'DataProcessors', 'Report': 'Reports',
         'InformationRegister': 'InformationRegisters', 'AccumulationRegister': 'AccumulationRegisters',
         'ChartOfCharacteristicTypes': 'ChartsOfCharacteristicTypes', 'BusinessProcess': 'BusinessProcesses',
         'Task': 'Tasks', 'ExchangePlan': 'ExchangePlans', 'Enum': 'Enums'}
NS = {'f': 'http://v8.1c.ru/8.3/xcf/logform', 'v8': 'http://v8.1c.ru/8.1/data/core',
      'md': 'http://v8.1c.ru/8.3/MDClasses'}
ЭЛЕМЕНТЫ = {'UsualGroup': 'группа', 'Pages': 'страницы', 'Page': 'стр', 'InputField': 'поле', 'LabelField': 'надпись',
            'CheckBoxField': 'флажок', 'Table': 'ТАБЛИЦА', 'Button': 'кнопка', 'LabelDecoration': 'текст',
            'SpreadSheetDocumentField': 'таб.док', 'HTMLDocumentField': 'HTML', 'PictureDecoration': 'картинка',
            'RadioButtonField': 'переключатель', 'TextDocumentField': 'текст.док', 'ButtonGroup': 'гр.кнопок',
            'CommandBar': 'панель', 'Popup': 'подменю', 'PictureField': 'поле картинки', 'CalendarField': 'календарь'}


def читать(п):
    return io.open(п, encoding='utf-8-sig').read()


def состав_подсистемы(выгрузка, имя):
    """[(вид, имя)] подсистемы вместе с дочерними (Subsystems/<Имя>/Subsystems/*.xml)."""
    итог = []
    мета = читать(os.path.join(выгрузка, 'Subsystems', имя + '.xml'))
    каталог = os.path.join(выгрузка, 'Subsystems', имя, 'Subsystems')
    for дочерняя in re.findall(r'<Subsystem>(\w+)</Subsystem>', мета):
        п = os.path.join(каталог, дочерняя + '.xml')
        if os.path.exists(п):
            итог += re.findall(r'<xr:Item xsi:type="xr:MDObjectRef">(\w+)\.(\w+)</xr:Item>', читать(п))
    итог += [о for о in re.findall(r'<xr:Item xsi:type="xr:MDObjectRef">(\w+)\.(\w+)</xr:Item>', мета) if о not in итог]
    return итог


def все_объекты(выгрузка):
    итог = []
    for вид, папка in ПАПКИ.items():
        к = os.path.join(выгрузка, папка)
        if os.path.isdir(к):
            итог += [(вид, и[:-4]) for и in sorted(os.listdir(к)) if и.endswith('.xml')]
    return итог


def синоним(эл):
    т = эл.find('md:Properties/md:Synonym/v8:item/v8:content', NS)
    return т.text if т is not None and т.text else ''


def тип(эл):
    типы = [т.text.split(':')[-1] for т in эл.findall('md:Properties/md:Type/v8:Type', NS) if т.text]
    длина = эл.find('md:Properties/md:Type/v8:StringQualifiers/v8:Length', NS)
    if типы == ['string'] and длина is not None:
        типы = ['string(%s)' % (длина.text if длина.text != '0' else 'неогр')]
    return ', '.join(типы)


def реквизиты(путь_xml):
    """Реквизиты шапки и табличных частей из XML объекта."""
    try:
        корень = ET.parse(путь_xml).getroot()
    except (ET.ParseError, FileNotFoundError):
        return []
    объект = next(iter(корень), None)
    дети = объект.find('md:ChildObjects', NS) if объект is not None else None
    if дети is None:
        return []
    вывод = []
    for эл in дети:
        тег = эл.tag.split('}')[1]
        имя = эл.find('md:Properties/md:Name', NS)
        if имя is None:
            continue
        if тег in ('Attribute', 'Dimension', 'Resource'):
            вывод.append('    %-28s %-36s %s' % (имя.text, синоним(эл), тип(эл)))
        elif тег == 'TabularSection':
            вывод.append('    ТЧ %s «%s»:' % (имя.text, синоним(эл)))
            for р in эл.findall('md:ChildObjects/md:Attribute', NS):
                вывод.append('      %-26s %-36s %s' % (р.find('md:Properties/md:Name', NS).text, синоним(р), тип(р)))
        elif тег == 'EnumValue':
            вывод.append('    %-28s %s' % (имя.text, синоним(эл)))
    return ['  реквизиты (имя; синоним; тип):'] + вывод if вывод else []


def обойти(эл, уровень, вывод):
    дети = эл.find('f:ChildItems', NS)
    if дети is None:
        return
    for д in дети:
        тег = д.tag.split('}')[1]
        if тег not in ЭЛЕМЕНТЫ:
            continue
        части = [ЭЛЕМЕНТЫ[тег], д.get('name')]
        з = д.find('f:Title/v8:item/v8:content', NS)
        if з is not None and з.text:
            части.append('«%s»' % з.text)
        путь = д.find('f:DataPath', NS)
        if путь is not None:
            части.append('[%s]' % путь.text)
        команда = д.find('f:CommandName', NS)
        if команда is not None:
            части.append('→ ' + команда.text)
        видимость = д.find('f:Visible', NS)
        if видимость is not None and видимость.text == 'false':
            части.append('СКРЫТ')
        события = ['%s=%s' % (с.get('name'), с.text) for с in д.findall('f:Events/f:Event', NS)]
        if события:
            части.append('{%s}' % ', '.join(события))
        вывод.append('  ' * уровень + ' '.join(части))
        if тег != 'Button':
            обойти(д, уровень + 1, вывод)


def процедуры(путь, только_экспорт=False):
    if not os.path.exists(путь):
        return []
    строки = читать(путь).splitlines()
    итог = []
    for н, с in enumerate(строки):
        м = re.match(r'\s*(Процедура|Функция)\s+(\w+)\s*\(([^)]*)\)?\s*(Экспорт)?', с)
        if not м or (только_экспорт and not м.group(4)):
            continue
        директива, комментарий, к = '', [], н - 1
        while к >= 0 and строки[к].strip().startswith(('//', '&')):
            if строки[к].strip().startswith('&'):
                директива = строки[к].strip()
            else:
                комментарий.insert(0, строки[к].strip()[2:].strip())
            к -= 1
        параметры = re.sub(r'\s+', ' ', (м.group(3) or '').strip())
        итог.append('    %s %s(%s)%s%s%s' % (м.group(1), м.group(2), параметры, ' Экспорт' if м.group(4) else '',
                                           ' ' + директива if директива else '',
                                           ' — ' + ' '.join(комментарий)[:160] if комментарий else ''))
    return итог


def модуль(путь, заголовок, только_экспорт=False):
    п = процедуры(путь, только_экспорт)
    return ['  %s:' % заголовок] + п if п else []


def построить(выгрузка, подсистемы=()):
    объекты = []
    for п in подсистемы:
        объекты += [о for о in состав_подсистемы(выгрузка, п) if о not in объекты]
    if not подсистемы:
        объекты = все_объекты(выгрузка)
    части = ['# Карта конфигурации (генерируется: <skill>/tools/config_map.py — не править руками)', '',
             'Подсистемы: %s. Формы: тип элемента, имя, «заголовок», [путь данных], → команда, {события}; модули — '
             'процедуры с директивой и комментарием над объявлением.' % (', '.join(подсистемы) or 'все объекты'), '']
    число = 0
    for вид, имя in объекты:
        if вид not in ПАПКИ:
            continue
        число += 1
        папка = os.path.join(выгрузка, ПАПКИ[вид], имя)
        части += ['', '### %s.%s' % (вид, имя)]
        части += реквизиты(os.path.join(выгрузка, ПАПКИ[вид], имя + '.xml'))
        части += модуль(os.path.join(папка, 'Ext', 'ObjectModule.bsl'), 'модуль объекта')
        части += модуль(os.path.join(папка, 'Ext', 'ManagerModule.bsl'), 'модуль менеджера')
        формы = os.path.join(папка, 'Forms')
        if os.path.isdir(формы):
            for форма in sorted(ф for ф in os.listdir(формы) if not ф.endswith('.xml')):
                п = os.path.join(формы, форма, 'Ext', 'Form.xml')
                if not os.path.exists(п):
                    continue
                вывод = []
                корень = ET.parse(п).getroot()
                обойти(корень, 2, вывод)
                события = ['%s=%s' % (с.get('name'), с.text) for с in корень.findall('f:Events/f:Event', NS)]
                части.append('  форма %s%s:' % (форма, ' {%s}' % ', '.join(события) if события else ''))
                части += вывод
                части += ['  ' + с for с in модуль(os.path.join(формы, форма, 'Ext', 'Form', 'Module.bsl'),
                                                  'модуль формы %s' % форма)]
    общие = os.path.join(выгрузка, 'CommonModules')
    if os.path.isdir(общие):
        части += ['', '## Общие модули — экспортные процедуры и функции']
        for имя in sorted(и[:-4] for и in os.listdir(общие) if и.endswith('.xml')):
            мета = читать(os.path.join(общие, имя + '.xml'))
            флаги = [ф for ф in ('Server', 'ServerCall', 'ClientManagedApplication', 'Global', 'Privileged')
                     if '<%s>true</%s>' % (ф, ф) in мета]
            части += ['', '### ОбщийМодуль.%s [%s]' % (имя, ', '.join(флаги))]
            части += модуль(os.path.join(общие, имя, 'Ext', 'Module.bsl'), 'экспорт', только_экспорт=True)
    return '\n'.join(части) + '\n', число


def main():
    арг = [а for а in sys.argv[1:]]
    итог = 'КАРТА.md'
    if '--итог' in арг:
        и = арг.index('--итог')
        итог = арг[и + 1]
        del арг[и:и + 2]
    if not арг:
        sys.exit(__doc__)
    текст, число = построить(арг[0], tuple(арг[1:]))
    старый = io.open(итог, encoding='utf-8').read() if os.path.exists(итог) else ''
    if текст != старый:
        io.open(итог, 'w', encoding='utf-8', newline='\n').write(текст)
    print('карта: %s (%d КБ, объектов %d)%s' % (итог, len(текст.encode('utf-8')) // 1024, число,
                                              '' if текст != старый else ', без изменений'))


if __name__ == '__main__':
    main()
