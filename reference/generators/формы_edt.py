# -*- coding: utf-8 -*-
"""Вывод реквизитов и табличных частей на управляемые формы проекта 1C:EDT.

Три приёма, все три сняты с натуры из форм этой же конфигурации:
  • поле в корень формы или в существующую группу;
  • колонка в СУЩЕСТВУЮЩУЮ таблицу формы;
  • новая вкладка с таблицей в группе страниц.

Точки вставки ищутся по содержимому, а не по номерам строк: у группы это первая
строка её собственных свойств, у таблицы — её autoCommandBar сразу после колонок.

Файлы сохраняются как есть: UTF-8 без BOM, CRLF, отступы пробелами.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

ПРОЕКТ = r'C:\Users\user\AppData\Local\1C\1cedtstart\projects\MVM\УАТ_МВМ'
ПРОБА = '--проба' in sys.argv

ЗАДАНИЯ = [
    {
        'форма': r'src\Catalogs\уатВидыУпаковки_уэ\Forms\ФормаЭлемента\Form.form',
        'что': 'Виды упаковки',
        # ТЗ-08 п.11: весогабаритные характеристики вида упаковки
        'поля_в_корень': ['Длина', 'Ширина', 'Высота', 'МаксСнаряженныйВес',
                          'МаксНагрузкаСверху', 'МожноКантовать'],
    },
    {
        'форма': r'src\Catalogs\уатМаршруты\Forms\ФормаЭлемента\Form.form',
        'что': 'Маршруты',
        # ТЗ-08 п.8.4: шапка маршрута
        'поля_в_группу': ('Шапка', 2, [
            'ОсобенностьМаршрута', 'НаправлениеПеревозки', 'ОграниченийНет',
            'ОграничениеПоВесу', 'ОграничениеПоВысоте', 'ОграничениеПоШирине',
            'ЦветРамкиНаКарте']),
        # скорость в типовую таблицу «Пункты следования» (ТЧ Этапы)
        'колонки_в_таблицу': [('ПунктыСледования', 'Этапы', ['Скорость'])],
        # новая вкладка «Допустимые ТС на операции»
        'вкладки_в_группу': ('Страницы', 2, [
            ('ДопустимыеТСНаОперации', 'Допустимые ТС на операции',
             ['Операция', 'ТипТС', 'МаксСнаряженнаяМасса',
              'МаксСнаряженнаяВысота', 'МаксСнаряженнаяШирина'])]),
    },
]


class Ид:
    def __init__(self, старт):
        self.n = старт

    def взять(self):
        self.n += 1
        return self.n - 1


def подсказка(имя, ид, о):
    return [f'{о}<extendedTooltip>',
            f'{о}  <name>{имя}РасширеннаяПодсказка</name>',
            f'{о}  <id>{ид}</id>',
            f'{о}  <type>Label</type>',
            f'{о}  <autoMaxWidth>true</autoMaxWidth>',
            f'{о}  <autoMaxHeight>true</autoMaxHeight>',
            f'{о}  <extInfo xsi:type="form:LabelDecorationExtInfo">',
            f'{о}    <horizontalAlign>Left</horizontalAlign>',
            f'{о}  </extInfo>',
            f'{о}</extendedTooltip>']


def меню(имя, ид, о):
    return [f'{о}<contextMenu>',
            f'{о}  <name>{имя}КонтекстноеМеню</name>',
            f'{о}  <id>{ид}</id>',
            f'{о}  <autoFill>true</autoFill>',
            f'{о}</contextMenu>']


def поле(ид, имя, путь, отступ, метка=False, только_чтение=False):
    о, в = ' ' * отступ, ' ' * (отступ + 2)
    свой, мню, подск = ид.взять(), ид.взять(), ид.взять()
    строки = [f'{о}<items xsi:type="form:FormField">',
              f'{в}<name>{имя}</name>',
              f'{в}<id>{свой}</id>',
              f'{в}<visible>true</visible>',
              f'{в}<enabled>true</enabled>',
              f'{в}<userVisible>',
              f'{в}  <common>true</common>',
              f'{в}</userVisible>',
              f'{в}<dataPath xsi:type="form:DataPath">',
              f'{в}  <segments>{путь}</segments>',
              f'{в}</dataPath>']
    строки += подсказка(имя, подск, в)
    строки += меню(имя, мню, в)
    строки.append(f'{в}<type>{"LabelField" if метка else "InputField"}</type>')
    if только_чтение:
        # порядок узлов как в типовой форме: readOnly сразу после type
        строки.append(f'{в}<readOnly>true</readOnly>')
    строки += [f'{в}<editMode>EnterOnInput</editMode>',
               f'{в}<showInHeader>true</showInHeader>',
               f'{в}<headerHorizontalAlign>Left</headerHorizontalAlign>',
               f'{в}<showInFooter>true</showInFooter>']
    if метка:
        строки += [f'{в}<extInfo xsi:type="form:LabelFieldExtInfo">',
                   f'{в}  <autoMaxWidth>true</autoMaxWidth>',
                   f'{в}  <autoMaxHeight>true</autoMaxHeight>',
                   f'{в}</extInfo>']
    else:
        строки += [f'{в}<extInfo xsi:type="form:InputFieldExtInfo">',
                   f'{в}  <autoMaxWidth>true</autoMaxWidth>',
                   f'{в}  <autoMaxHeight>true</autoMaxHeight>',
                   f'{в}  <wrap>true</wrap>',
                   f'{в}  <chooseType>true</chooseType>',
                   f'{в}  <typeDomainEnabled>true</typeDomainEnabled>',
                   f'{в}  <textEdit>true</textEdit>',
                   f'{в}</extInfo>']
    строки.append(f'{о}</items>')
    return строки


def дополнение(ид, тег, имя_табл, суффикс, тип, о):
    в = ' ' * (len(о) + 2)
    имя = f'{имя_табл}{суффикс}'
    свой, мню, подск = ид.взять(), ид.взять(), ид.взять()
    строки = [f'{о}<{тег}>', f'{в}<name>{имя}</name>', f'{в}<id>{свой}</id>']
    строки += подсказка(имя, подск, в)
    строки += меню(имя, мню, в)
    строки += [f'{в}<source>{имя_табл}</source>',
               f'{в}<extInfo xsi:type="form:{тип}ExtInfo">',
               f'{в}  <autoMaxWidth>true</autoMaxWidth>',
               f'{в}</extInfo>', f'{о}</{тег}>']
    return строки


def вкладка(ид, имя, заголовок, колонки, отступ_страницы):
    о4 = ' ' * отступ_страницы
    о6 = ' ' * (отступ_страницы + 2)
    о8 = ' ' * (отступ_страницы + 4)
    ид_гр, ид_табл = ид.взять(), ид.взять()
    строки = [f'{о4}<items xsi:type="form:FormGroup">',
              f'{о6}<name>Группа{имя}</name>',
              f'{о6}<id>{ид_гр}</id>',
              f'{о6}<items xsi:type="form:Table">',
              f'{о8}<name>{имя}</name>',
              f'{о8}<id>{ид_табл}</id>',
              f'{о8}<visible>true</visible>',
              f'{о8}<enabled>true</enabled>',
              f'{о8}<userVisible>',
              f'{о8}  <common>true</common>',
              f'{о8}</userVisible>',
              f'{о8}<dataPath xsi:type="form:DataPath">',
              f'{о8}  <segments>Объект.{имя}</segments>',
              f'{о8}</dataPath>',
              f'{о8}<titleLocation>None</titleLocation>']
    строки += поле(ид, f'{имя}НомерСтроки', f'Объект.{имя}.LineNumber',
                   отступ_страницы + 4, метка=True)
    for к in колонки:
        строки += поле(ид, f'{имя}{к}', f'Объект.{имя}.{к}', отступ_страницы + 4)
    строки += [f'{о8}<autoCommandBar>',
               f'{о8}  <name>{имя}КоманднаяПанель</name>',
               f'{о8}  <id>{ид.взять()}</id>',
               f'{о8}  <horizontalAlign>Left</horizontalAlign>',
               f'{о8}  <autoFill>true</autoFill>',
               f'{о8}</autoCommandBar>']
    строки += дополнение(ид, 'searchStringAddition', имя, 'СтрокаПоиска',
                         'SearchStringAddition', о8)
    строки += дополнение(ид, 'viewStatusAddition', имя, 'СостояниеПросмотра',
                         'ViewStatusAddition', о8)
    строки += дополнение(ид, 'searchControlAddition', имя, 'УправлениеПоиском',
                         'SearchControlAddition', о8)
    строки += подсказка(имя, ид.взять(), о8)
    строки += меню(имя, ид.взять(), о8)
    строки += [f'{о8}<changeRowSet>true</changeRowSet>',
               f'{о8}<changeRowOrder>true</changeRowOrder>',
               f'{о8}<autoMaxWidth>true</autoMaxWidth>',
               f'{о8}<autoMaxHeight>true</autoMaxHeight>',
               f'{о8}<autoMaxRowsCount>true</autoMaxRowsCount>',
               f'{о8}<selectionMode>MultiRow</selectionMode>',
               f'{о8}<header>true</header>',
               f'{о8}<headerHeight>1</headerHeight>',
               f'{о8}<footerHeight>1</footerHeight>',
               f'{о8}<horizontalScrollBar>AutoUse</horizontalScrollBar>',
               f'{о8}<verticalScrollBar>AutoUse</verticalScrollBar>',
               f'{о8}<autoInsertNewRow>true</autoInsertNewRow>',
               f'{о8}<searchOnInput>Auto</searchOnInput>',
               f'{о8}<initialListView>Auto</initialListView>',
               f'{о8}<horizontalStretch>true</horizontalStretch>',
               f'{о8}<verticalStretch>true</verticalStretch>',
               f'{о8}<enableStartDrag>true</enableStartDrag>',
               f'{о8}<enableDrag>true</enableDrag>',
               f'{о8}<rowFilter xsi:type="core:UndefinedValue"/>',
               f'{о6}</items>',
               f'{о6}<visible>true</visible>',
               f'{о6}<enabled>true</enabled>',
               f'{о6}<userVisible>',
               f'{о6}  <common>true</common>',
               f'{о6}</userVisible>',
               f'{о6}<title>',
               f'{о6}  <key>ru</key>',
               f'{о6}  <value>{заголовок}</value>',
               f'{о6}</title>']
    строки += подсказка(f'Группа{имя}', ид.взять(), о6)
    строки += [f'{о6}<type>Page</type>',
               f'{о6}<extInfo xsi:type="form:PageGroupExtInfo">',
               f'{о6}  <group>Vertical</group>',
               f'{о6}  <showTitle>true</showTitle>',
               f'{о6}  <titleDataPath xsi:type="form:DataPath">',
               f'{о6}    <segments>Объект.{имя}.RowsCount</segments>',
               f'{о6}  </titleDataPath>',
               f'{о6}</extInfo>',
               f'{о4}</items>']
    return строки


# ------------------------------------------------------------- точки вставки
def конец_группы(строки, имя, отступ):
    """Первая строка собственных свойств группы = конец её содержимого."""
    метка_имени = ' ' * (отступ + 2) + f'<name>{имя}</name>'
    метка_свойств = ' ' * (отступ + 2) + '<visible>true</visible>'
    места = [i for i, с in enumerate(строки) if с == метка_имени]
    if len(места) != 1:
        sys.exit(f'ОШИБКА: группа «{имя}» найдена {len(места)} раз(а)')
    for i in range(места[0], len(строки)):
        if строки[i] == метка_свойств:
            return i
    sys.exit(f'ОШИБКА: не найден конец содержимого группы «{имя}»')


def конец_корня(строки):
    for i, с in enumerate(строки):
        м = re.match(r'^  <(\w+)', с)
        if м and м.group(1) != 'items':
            return i
    sys.exit('ОШИБКА: не найден конец корневых элементов формы')


def конец_колонок(строки, имя_таблицы):
    """autoCommandBar таблицы стоит сразу после её колонок."""
    for i, с in enumerate(строки):
        м = re.match(r'^(\s*)<items xsi:type="form:Table">$', с)
        if not м:
            continue
        отступ = len(м.group(1))
        if строки[i + 1].strip() != f'<name>{имя_таблицы}</name>':
            continue
        метка = ' ' * (отступ + 2) + '<autoCommandBar>'
        for j in range(i, len(строки)):
            if строки[j] == метка:
                return j, отступ + 2
    sys.exit(f'ОШИБКА: не найдена таблица «{имя_таблицы}»')


def обработать(з):
    путь = os.path.join(ПРОЕКТ, з['форма'])
    сырьё = open(путь, 'rb').read()
    if сырьё.startswith(b'\xef\xbb\xbf'):
        sys.exit('ОШИБКА: у файла BOM, а быть его не должно')
    текст = сырьё.decode('utf-8')
    строки = текст.split('\r\n')
    ид = Ид(max(int(ч) for ч in re.findall(r'<id>(\d+)</id>', текст)) + 1)
    первый = ид.n
    сделано = []

    # Идемпотентность: элемент с такой привязкой данных уже на форме —
    # пропускаем. Без этого повторный прогон дублировал поля (ловили на
    # форме маршрутов: «ОграниченийНет» оказался на форме дважды).
    def уже(привязка):
        return f'<segments>{привязка}</segments>' in текст

    # вставки собираем как (позиция, строки) и применяем снизу вверх
    вставки = []

    if 'колонки_в_таблицу' in з:
        for имя_табл, имя_тч, колонки in з['колонки_в_таблицу']:
            новые = [к for к in колонки if not уже(f'Объект.{имя_тч}.{к}')]
            if not новые:
                continue
            поз, отступ = конец_колонок(строки, имя_табл)
            блок = []
            for к in новые:
                блок += поле(ид, f'{имя_тч}{к}', f'Объект.{имя_тч}.{к}', отступ)
                сделано.append(f'колонка {имя_табл}.{к}')
            вставки.append((поз, блок))

    if 'вкладки_в_группу' in з:
        имя_гр, отступ_гр, вкладки = з['вкладки_в_группу']
        новые_вк = [в for в in вкладки if not уже(f'Объект.{в[0]}')]
        if новые_вк:
            поз = конец_группы(строки, имя_гр, отступ_гр)
            блок = []
            for имя, заголовок, колонки in новые_вк:
                блок += вкладка(ид, имя, заголовок, колонки, отступ_гр + 2)
                сделано.append(f'вкладка {имя} ({len(колонки)} колонок)')
            вставки.append((поз, блок))

    if 'поля_в_группу' in з:
        имя_гр, отступ_гр, поля = з['поля_в_группу']
        новые_п = [имя for имя in поля if not уже(f'Объект.{имя}')]
        if новые_п:
            поз = конец_группы(строки, имя_гр, отступ_гр)
            блок = []
            for имя in новые_п:
                блок += поле(ид, имя, f'Объект.{имя}', отступ_гр + 2)
                сделано.append(f'поле {имя}')
            вставки.append((поз, блок))

    if 'поля_в_корень' in з:
        новые_к = [имя for имя in з['поля_в_корень'] if not уже(f'Объект.{имя}')]
        if новые_к:
            поз = конец_корня(строки)
            блок = []
            for имя in новые_к:
                блок += поле(ид, имя, f'Объект.{имя}', 2)
                сделано.append(f'поле {имя}')
            вставки.append((поз, блок))

    for поз, блок in sorted(вставки, key=lambda п: -п[0]):
        строки[поз:поз] = блок

    новый = '\r\n'.join(строки)
    try:
        корень = ET.fromstring(новый.encode('utf-8'))
    except ET.ParseError as e:
        sys.exit(f'ОШИБКА: XML сломан: {e}')

    к = lambda э: э.tag.split('}')[-1]
    визуальные = []
    for ветка in корень:
        if к(ветка) in ('items', 'autoCommandBar'):
            for узел in ветка.iter():
                for д in узел:
                    if к(д) == 'id' and (д.text or '').strip().isdigit():
                        визуальные.append(int(д.text))
    повторы = sorted({ч for ч in визуальные if визуальные.count(ч) > 1})
    if повторы:
        sys.exit(f'ОШИБКА: повторяющиеся id элементов формы: {повторы}')

    if not ПРОБА:
        open(путь, 'wb').write(новый.encode('utf-8'))
    return сделано, первый, ид.n - 1, len(новый.split('\r\n')) - len(текст.split('\r\n'))


def main():
    print('Формы%s\n' % ('   (ПРОБА)' if ПРОБА else ''))
    for з in ЗАДАНИЯ:
        сделано, с_ид, по_ид, строк = обработать(з)
        print('  %s' % з['что'])
        for что in сделано:
            print('      + %s' % что)
        print('      id %d..%d, строк добавлено %d' % (с_ид, по_ид, строк))


if __name__ == '__main__':
    main()
