# -*- coding: utf-8 -*-
"""ДиЗ-05 к ТЗ-01 (18.10.2026), XML-часть: идемпотентно, по образцам выгрузки 8.5.1.

п.1–2  Сценарии работы: «Тип сценария» (перечисление ТипыСценариев), «Адрес объекта» под объектом — для
       программной разработки (видимость — в модуле формы).
п.3    Справочник «Адреса объектов»: код, группы, наименование 150, примечание 2000.
п.4    вид и текст пункта по типу сценария и правилу заполнения — модули (МетодологТЗ, форма сценария).
п.5    наименование версии до проверки заполнения — модули (ObjectModule, форма версии).
п.6–7  Версии структуры: «Это маппинг», вкладка «Маппинг»: передающие / принимающие объекты с версиями,
       ТЧ соответствий, «Загрузить все реквизиты принимающего (их) объекта».

  python инструменты/диз05.py
Модули .bsl — руками (генератор их не трогает). После загрузки Конфигуратор 8.5.1 переписывает формат —
«принять выгрузку» (У-13); повторный запуск генератора после этого ничего не добавит (всё по наличию имени).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xml_правка as x  # noqa: E402
sys.path.insert(0, r'C:\1c-edt-skill\tools')
import designer_lib as dl  # noqa: E402

dl.VERSION = '2.21'
В = x.путь()
ПРАВА = ('Read', 'Insert', 'Update', 'Delete', 'View', 'InteractiveInsert', 'Edit', 'InteractiveSetDeletionMark',
         'InteractiveClearDeletionMark', 'InteractiveDeleteMarked', 'InputByString')


# ------------------------------------------------------------------ метаданные
def зарегистрировать(вид, имя):
    dl.register_in_configuration(В, вид, имя)


def добавить_реквизиты(объект, поля):
    """Реквизиты шапки справочника — после последнего реквизита шапки (до первой ТЧ / формы)."""
    п = x.путь('Catalogs', объект + '.xml')
    т = dl.read_lf(п)
    дети = т.index('<ChildObjects>')
    for поле in поля:
        if re.search(r'<Attribute uuid="[^"]+">\s*<Properties>\s*<Name>%s</Name>' % поле[0], т[дети:]):
            continue
        блок = dl.md_field('Catalog.' + объект, 'Attribute', поле, 3, dl._tail_object(dl._field_parts(поле)[3], 'ForItem'))
        # конец последнего реквизита шапки = начало первой ТЧ / формы / конец ChildObjects
        конец = len(т)
        for тег in ('\n\t\t\t<TabularSection uuid', '\n\t\t\t<Form>', '\n\t\t</ChildObjects>'):
            к = т.find(тег, дети)
            if к > 0:
                конец = min(конец, к)
        т = т[:конец] + '\n' + блок + т[конец:]
    x.записать(п, т)


def добавить_тч(объект, тч):
    п = x.путь('Catalogs', объект + '.xml')
    т = dl.read_lf(п)
    if 'CatalogTabularSection.%s.%s"' % (объект, тч[0]) in т:
        return
    дети = т.index('<ChildObjects>')
    конец = len(т)
    for тег in ('\n\t\t\t<Form>', '\n\t\t\t<Template>', '\n\t\t\t<Command ', '\n\t\t</ChildObjects>'):
        к = т.find(тег, дети)
        if к > 0:
            конец = min(конец, к)
    т = т[:конец] + '\n' + dl.md_object_tabular_section('Catalog', объект, тч, 3) + т[конец:]
    x.записать(п, т)


def метаданные():
    # новые объекты — только если файла нет: после «принять выгрузку» формат Конфигуратора не перезаписывать
    if not os.path.exists(x.путь('Enums', 'ТипыСценариев.xml')):
        x.записать(x.путь('Enums', 'ТипыСценариев.xml'), dl.enum_xml('ТипыСценариев', 'Типы сценариев', [
        ('ПрограммнаяРазработка', 'Программная разработка'), ('ПользовательскаяИстория', 'Пользовательская история')],
        explanation='Тип сценария работы (ДиЗ-05 к ТЗ-01): от него — вид и текст пунктов ТЗ, адрес объекта'))
    зарегистрировать('Enum', 'ТипыСценариев')

    if not os.path.exists(x.путь('Catalogs', 'АдресаОбъектов.xml')):
        x.записать(x.путь('Catalogs', 'АдресаОбъектов.xml'), dl.catalog_xml(
        'АдресаОбъектов', 'Адреса объектов', attributes=[('Примечание', 'string', 'Примечание', {'multiline': True})],  # 2000 > 1024: неогр. (case 024)
        hierarchical=True, description_length=150, code_length=9,
        explanation='Где объект в интерфейсе («Раздел / Подраздел / Объект») — для сценариев программной разработки '
                    '(ДиЗ-05 к ТЗ-01, п.3)'))
    зарегистрировать('Catalog', 'АдресаОбъектов')
    dl.add_rights(В, 'Методолог', 'Catalog.АдресаОбъектов', ПРАВА)
    dl.add_to_subsystem(x.путь('Subsystems', 'Методолог', 'Subsystems', 'БиблиотекаОбъектов.xml'), 'Catalog.АдресаОбъектов')

    добавить_реквизиты('СценарииРаботы', [
        ('ТипСценария', 'cfg:EnumRef.ТипыСценариев', 'Тип сценария'),
        ('АдресОбъекта', 'cfg:CatalogRef.АдресаОбъектов', 'Адрес объекта')])
    добавить_реквизиты('ВерсииСтруктурыОбъектов', [('ЭтоМаппинг', 'boolean', 'Это маппинг')])
    for тч in (
            ('ПередающиеОбъекты', [('Объект', 'cfg:CatalogRef.ОбъектыКонфигурации', 'Передающий объект'),
                                   ('Версия', 'cfg:CatalogRef.ВерсииСтруктурыОбъектов', 'Версия объекта')],
             'Передающие объекты (маппинг)'),
            ('ПринимающиеОбъекты', [('Объект', 'cfg:CatalogRef.ОбъектыКонфигурации', 'Принимающий объект'),
                                    ('Версия', 'cfg:CatalogRef.ВерсииСтруктурыОбъектов', 'Версия объекта')],
             'Принимающие объекты (маппинг)'),
            ('Маппинг', [('ПередающаяВерсия', 'cfg:CatalogRef.ВерсииСтруктурыОбъектов', 'Передающий: версия структуры объекта'),
                         ('ПередающийРеквизит', 'cfg:CatalogRef.РеквизитыОбъектов', 'Передающий реквизит'),
                         ('ПередающийТип', 'string:150', 'Передающий тип реквизита'),
                         ('ПринимающаяВерсия', 'cfg:CatalogRef.ВерсииСтруктурыОбъектов', 'Принимающий: версия структуры объекта'),
                         ('ПринимающийРеквизит', 'cfg:CatalogRef.РеквизитыОбъектов', 'Принимающий реквизит'),
                         ('ПринимающийТип', 'string:150', 'Принимающий тип реквизита'),
                         ('Значения', 'string:1000', 'Значения'),
                         ('Примечание', 'string:1000', 'Примечание')],
             'Маппинг')):
        добавить_тч('ВерсииСтруктурыОбъектов', тч)


# ------------------------------------------------------------------ формы
def вставить_после(т, имя, тег, xml):
    """Элемент xml — сразу после элемента имя (того же уровня)."""
    а, б = dl.xml_block(т, '<%s name="%s"' % (тег, имя), тег)
    return т[:б] + '\n' + xml.rstrip('\n') + т[б:]


def поле(имя, путь, ids, отступ, заголовок=None, ширина=None, события=(), флажок=False):
    if флажок:
        о = отступ
        с = ''.join('%s\t\t<Event name="%s">%s</Event>\n' % (о, е, о2) for е, о2 in события)
        return ('%s<CheckBoxField name="%s" id="%d">\n%s\t<DataPath>%s</DataPath>\n' % (о, имя, ids(), о, путь)
                + (dl.ml_xml('Title', заголовок, о + '\t') if заголовок else '')
                + '%s\t<TitleLocation>Right</TitleLocation>\n%s\t<EditMode>EnterOnInput</EditMode>\n'
                  '%s\t<CheckBoxType>Auto</CheckBoxType>\n' % (о, о, о)
                + '%s\t<ContextMenu name="%sКонтекстноеМеню" id="%d"/>\n' % (о, имя, ids())
                + '%s\t<ExtendedTooltip name="%sРасширеннаяПодсказка" id="%d"/>\n' % (о, имя, ids())
                + ('%s\t<Events>\n%s%s\t</Events>\n' % (о, с, о) if события else '') + '%s</CheckBoxField>\n' % о)
    return dl.form_field_xml('InputField', имя, путь, ids, отступ, заголовок, ширина, events=события)


def таблица_тч(имя, путь, колонки, ids, отступ, высота=None, панель=(), события=()):
    """Таблица ТЧ объекта по образцу ПроцессыBPMN формы версии (выгрузка 8.5.1).
    колонки: [(поле, заголовок, ширина, [(событие, обработчик)])]."""
    о = отступ
    p = ['%s<Table name="%s" id="%d">\n' % (о, имя, ids()), '%s\t<Representation>List</Representation>\n' % о,
         '%s\t<AutoMaxWidth>false</AutoMaxWidth>\n' % о]
    if высота:
        p.append('%s\t<HeightInTableRows>%d</HeightInTableRows>\n' % (о, высота))
    p += ['%s\t<RowSelectionMode>Cell</RowSelectionMode>\n%s\t<AutoInsertNewRow>true</AutoInsertNewRow>\n' % (о, о),
          '%s\t<EnableStartDrag>true</EnableStartDrag>\n%s\t<EnableDrag>true</EnableDrag>\n' % (о, о),
          '%s\t<FileDragMode>AsFile</FileDragMode>\n%s\t<DataPath>%s</DataPath>\n' % (о, о, путь),
          '%s\t<AutoMaxCardHeight>false</AutoMaxCardHeight>\n%s\t<RowFilter xsi:nil="true"/>\n' % (о, о),
          '%s\t<ContextMenu name="%sКонтекстноеМеню" id="%d"/>\n' % (о, имя, ids())]
    if панель:
        p.append('%s\t<AutoCommandBar name="%sКоманднаяПанель" id="%d">\n%s\t\t<ChildItems>\n' % (о, имя, ids(), о))
        for к in панель:
            p.append('%s\t\t\t<Button name="%s%s" id="%d">\n%s\t\t\t\t<Type>CommandBarButton</Type>\n'
                     '%s\t\t\t\t<CommandName>Form.Command.%s</CommandName>\n'
                     '%s\t\t\t\t<ExtendedTooltip name="%s%sРасширеннаяПодсказка" id="%d"/>\n%s\t\t\t</Button>\n'
                     % (о, имя, к, ids(), о, о, к, о, имя, к, ids(), о))
        p.append('%s\t\t</ChildItems>\n%s\t</AutoCommandBar>\n' % (о, о))
    else:
        p.append('%s\t<AutoCommandBar name="%sКоманднаяПанель" id="%d"/>\n' % (о, имя, ids()))
    p.append('%s\t<ExtendedTooltip name="%sРасширеннаяПодсказка" id="%d"/>\n' % (о, имя, ids()))
    for доп, вид, тег in (('СтрокаПоиска', 'SearchStringRepresentation', 'SearchStringAddition'),
                          ('СостояниеПросмотра', 'ViewStatusRepresentation', 'ViewStatusAddition'),
                          ('УправлениеПоиском', 'SearchControl', 'SearchControlAddition')):
        p.append('%s\t<%s name="%s%s" id="%d">\n%s\t\t<AdditionSource>\n%s\t\t\t<Item>%s</Item>\n%s\t\t\t<Type>%s</Type>\n'
                 '%s\t\t</AdditionSource>\n%s\t\t<ContextMenu name="%s%sКонтекстноеМеню" id="%d"/>\n'
                 '%s\t\t<ExtendedTooltip name="%s%sРасширеннаяПодсказка" id="%d"/>\n%s\t</%s>\n'
                 % (о, тег, имя, доп, ids(), о, о, имя, о, вид, о, о, имя, доп, ids(), о, имя, доп, ids(), о, тег))
    if события:
        p.append('%s\t<Events>\n' % о + ''.join('%s\t\t<Event name="%s">%s</Event>\n' % (о, е, обр) for е, обр in события)
                 + '%s\t</Events>\n' % о)
    p.append('%s\t<ChildItems>\n' % о)
    p.append('%s\t\t<LabelField name="%sНомерСтроки" id="%d">\n%s\t\t\t<DataPath>%s.LineNumber</DataPath>\n'
             '%s\t\t\t<ContextMenu name="%sНомерСтрокиКонтекстноеМеню" id="%d"/>\n'
             '%s\t\t\t<ExtendedTooltip name="%sНомерСтрокиРасширеннаяПодсказка" id="%d"/>\n%s\t\t</LabelField>\n'
             % (о, имя, ids(), о, путь, о, имя, ids(), о, имя, ids(), о))
    for к in колонки:
        п_, заг, шир = к[:3]
        соб = к[3] if len(к) > 3 else ()
        p.append(dl.form_field_xml('InputField', имя + п_, '%s.%s' % (путь, п_), ids, о + '\t\t', заг, шир, events=соб))
    p.append('%s\t</ChildItems>\n%s</Table>\n' % (о, о))
    return ''.join(p)


def форма_сценария():
    п = x.путь('Catalogs', 'СценарииРаботы', 'Forms', 'ФормаЭлемента', 'Ext', 'Form.xml')
    т = dl.form_add_event(dl.read_lf(п), 'OnCreateAtServer', 'ПриСозданииНаСервере')
    if 'name="ТипСценария"' in т:
        x.записать(п, т)
        return
    ids = dl.FormIds(т)
    а = т.index('<UsualGroup name="Шапка"')
    о = dl.line_indent(т, а)
    т = вставить_после(т, 'Шапка', 'UsualGroup', поле('ТипСценария', 'Объект.ТипСценария', ids, о, 'Тип сценария', 24,
                                                    [('OnChange', 'ТипСценарияПриИзменении')]))
    т = вставить_после(т, 'ОбъектВерсия', 'UsualGroup', поле('АдресОбъекта', 'Объект.АдресОбъекта', ids, о,
                                                           'Адрес объекта', 74))
    x.записать(п, т)


def форма_версии():
    п = x.путь('Catalogs', 'ВерсииСтруктурыОбъектов', 'Forms', 'ФормаЭлемента', 'Ext', 'Form.xml')
    т = dl.read_lf(п)
    if 'name="ЭтоМаппинг"' in т:
        return
    ids = dl.FormIds(т)
    # п.6: флажок в шапке
    а, б = dl.xml_block(т, '<UsualGroup name="Шапка"', 'UsualGroup')
    к = т.rfind('</ChildItems>', а, б)
    к = т.rfind('\n', 0, к) + 1
    о = dl.line_indent(т, т.index('<InputField name="ВерсияКонфигурации"'))
    т = т[:к] + поле('ЭтоМаппинг', 'Объект.ЭтоМаппинг', ids, о, 'Это маппинг', события=[('OnChange', 'ЭтоМаппингПриИзменении')],
                    флажок=True) + т[к:]
    # п.5: наименование — сразу при изменении полей шаблона
    for имя in ('Владелец', 'Номер', 'Проект', 'Система', 'ВерсияКонфигурации'):
        т = dl.form_item_event(т, имя, 'InputField', 'OnChange', 'ПолеНаименованияПриИзменении')
    # п.7: вкладка «Маппинг» — после «Реквизиты»
    ос = dl.line_indent(т, т.index('<Page name="СтраницаРеквизиты"'))
    вн = ос + '\t\t'
    содержимое = (
        '%s<LabelDecoration name="МаппингПояснение" id="%d">\n%s\t<AutoMaxWidth>false</AutoMaxWidth>\n' % (вн, ids(), вн)
        + dl.ml_xml('Title', 'Объект версии — виртуальный «МАППИНГ …» из справочника объектов. Обычно один передающий и '
                    'один принимающий объект; бывает несколько с одной стороны. Реквизиты в строках выбираются только из '
                    'версии своей стороны, тип подставляется сам.', вн + '\t').replace('<Title>', '<Title formatted="false">', 1)
        + '%s\t<ContextMenu name="МаппингПояснениеКонтекстноеМеню" id="%d"/>\n' % (вн, ids())
        + '%s\t<ExtendedTooltip name="МаппингПояснениеРасширеннаяПодсказка" id="%d"/>\n%s</LabelDecoration>\n' % (вн, ids(), вн)
        + '%s<UsualGroup name="МаппингОбъекты" id="%d">\n%s\t<Group>AlwaysHorizontal</Group>\n' % (вн, ids(), вн)
        + '%s\t<Representation>None</Representation>\n%s\t<ShowTitle>false</ShowTitle>\n' % (вн, вн)
        + '%s\t<ExtendedTooltip name="МаппингОбъектыРасширеннаяПодсказка" id="%d"/>\n%s\t<ChildItems>\n' % (вн, ids(), вн)
        + таблица_тч('ПередающиеОбъекты', 'Объект.ПередающиеОбъекты', [
            ('Объект', 'Передающий объект', 30, [('OnChange', 'СтороныОбъектПриИзменении')]),
            ('Версия', 'Версия объекта', 30, [('StartChoice', 'СтороныВерсияНачалоВыбора')])], ids, вн + '\t\t', высота=3)
        + таблица_тч('ПринимающиеОбъекты', 'Объект.ПринимающиеОбъекты', [
            ('Объект', 'Принимающий объект', 30, [('OnChange', 'СтороныОбъектПриИзменении')]),
            ('Версия', 'Версия объекта', 30, [('StartChoice', 'СтороныВерсияНачалоВыбора')])], ids, вн + '\t\t', высота=3)
        + '%s\t</ChildItems>\n%s</UsualGroup>\n' % (вн, вн)
        + таблица_тч('Маппинг', 'Объект.Маппинг', [
            ('ПередающаяВерсия', 'Передающий: версия структуры объекта', 26, [('StartChoice', 'МаппингВерсияНачалоВыбора')]),
            ('ПередающийРеквизит', 'Передающий реквизит', 22, [('StartChoice', 'МаппингРеквизитНачалоВыбора')]),
            ('ПередающийТип', 'Передающий тип', 12),
            ('ПринимающаяВерсия', 'Принимающий: версия структуры объекта', 26, [('StartChoice', 'МаппингВерсияНачалоВыбора')]),
            ('ПринимающийРеквизит', 'Принимающий реквизит', 22, [('StartChoice', 'МаппингРеквизитНачалоВыбора')]),
            ('ПринимающийТип', 'Принимающий тип', 12),
            ('Значения', 'Значения', 20), ('Примечание', 'Примечание', 24)],
            ids, вн, панель=('ЗагрузитьРеквизитыПринимающих',)))
    стр = dl.form_page_xml('СтраницаМаппинг', 'Маппинг', содержимое, ids, ос)
    т = dl.form_add_page(т, 'Страницы', стр, after='СтраницаРеквизиты')
    т = dl.form_add_commands(т, [('ЗагрузитьРеквизитыПринимающих', 'Загрузить все реквизиты принимающего (их) объекта',
                                  'Строки маппинга — по всем реквизитам версий принимающих объектов; при одном '
                                  'передающем объекте его версия подставляется во все строки')])
    x.записать(п, т)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    метаданные()
    форма_сценария()
    форма_версии()
    print('ДиЗ-05: XML готов')
