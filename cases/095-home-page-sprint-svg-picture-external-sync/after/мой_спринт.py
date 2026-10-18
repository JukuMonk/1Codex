# -*- coding: utf-8 -*-
"""«Мой спринт» — начальная страница исполнителя (18.10.2026): задачи текущего спринта тремя колонками (не начаты /
в работе / завершены), неделя по дням и прогресс картинкой (SVG), работа вне плана; «Записать часы» и «Завершить»
прямо со страницы.

Запись — как ручной ввод (форма элемента «Учет времени»): элемент справочника УчетВремени без ДатаЗагрузкиБ24.
Обмен с Битрикс24 односторонний (Б24 → 1С) и ищет свои записи по коду = ID в Б24 (до ~200 тыс.), у записей 1С код
от 979 млн — не пересекаются. «Завершить» = запись времени с флажком «Завершено» по задаче и стадии из плана спринта:
так форма спринта («Пересчитать») и отчёты уже считают «стадия завершена». Закрытие задачи — в Б24 (кнопка «Открыть
в Битрикс24»): дату закрытия обмен перезаписывает из Б24.

  python инструменты/мой_спринт.py      # идемпотентно: XML обработки, права, подсистема, начальная страница
ВЫПОЛНЕН 18.10.2026 и выгрузка принята как исходник (Конфигуратор 8.5.1 переписал формы и права, У-13): повторный
запуск вернёт формат генератора — после него снова «принять». Дальше правки форм — в конфигурация\ напрямую.
Модули форм — руками в конфигурация\\DataProcessors\\МойСпринт\\…\\Module.bsl (генератор их не трогает).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xml_правка as x  # noqa: E402
sys.path.insert(0, r'C:\1c-edt-skill\tools')
import designer_lib as dl  # noqa: E402

dl.VERSION = '2.21'
ИМЯ = 'МойСпринт'
ВЫГРУЗКА = x.путь()
ЗАДАЧИ_КОЛОНКИ = [
    ('Задача', 'cfg:CatalogRef.Задачи', 'Задача'), ('Проект', 'cfg:CatalogRef.Проекты', 'Проект'),
    ('Стадия', 'cfg:CatalogRef.Стадии', 'Стадия'), ('Исполнитель', 'cfg:CatalogRef.ПользователиБитрикс', 'Исполнитель'),
    ('Часы', 'string:40', 'Часы'), ('Отметка', 'string:60', 'Отметка'), ('Срок', 'date', 'Срок'),
    ('ЧасыПлан', 'number:10.2', 'План, ч'), ('ЧасыФакт', 'number:10.2', 'Факт, ч'),
    ('Просрочена', 'boolean', 'Просрочена'), ('СверхПлана', 'boolean', 'Сверх плана'), ('Закрыта', 'boolean', 'Закрыта')]
КОЛОНКИ = (('НеНачаты', 'Не начаты'), ('ВРаботе', 'В работе'), ('Завершены', 'Завершены'))


def картинка_xml(имя, путь, ids, отступ, ширина, высота):
    """Поле картинки по образцу выгрузки (КонсольСистемыКомпоновкиДанных); размер картинки — кодом."""
    о = отступ
    return ('%s<PictureField name="%s" id="%d">\n%s\t<DataPath>%s</DataPath>\n%s\t<TitleLocation>None</TitleLocation>\n'
            '%s\t<Width>%d</Width>\n%s\t<Height>%d</Height>\n%s\t<HorizontalStretch>true</HorizontalStretch>\n'
            '%s\t<ContextMenu name="%sКонтекстноеМеню" id="%d"/>\n'
            '%s\t<ExtendedTooltip name="%sРасширеннаяПодсказка" id="%d"/>\n%s</PictureField>\n'
            % (о, имя, ids(), о, путь, о, о, ширина, о, высота, о, о, имя, ids(), о, имя, ids(), о))


def заменить_место(текст, место, xml):
    """Надпись-заглушку (f.label) заменить готовым элементом с тем же отступом."""
    а, б = dl.xml_block(текст, '<LabelDecoration name="%s"' % место, 'LabelDecoration')
    нач = текст.rfind('\n', 0, а) + 1
    return текст[:нач] + xml + текст[б + 1:]


def гиперссылка(текст, имя, обработчик):
    """Надпись → гиперссылка с событием «Нажатие» (порядок тегов — КонсольЗапросов: Hyperlink перед ContextMenu)."""
    а, б = dl.xml_block(текст, '<LabelDecoration name="%s"' % имя, 'LabelDecoration')
    эл = текст[а:б]
    о = dl.line_indent(текст, а)
    эл = эл.replace('\n%s\t<ContextMenu ' % о, '\n%s\t<Hyperlink>true</Hyperlink>\n%s\t<ContextMenu ' % (о, о), 1)
    эл = эл.replace('\n%s</LabelDecoration>' % о, '\n%s\t<Events>\n%s\t\t<Event name="Click">%s</Event>\n%s\t</Events>\n'
                    '%s</LabelDecoration>' % (о, о, обработчик, о, о), 1)
    return текст[:а] + эл + текст[б:]


def форма_страницы():
    f = dl.Form('Мой спринт')
    f.attr('Объект', 'cfg:DataProcessorObject.' + ИМЯ, main=True)
    f.attr('Спринт', 'cfg:CatalogRef.Спринт', 'Спринт')
    f.attr('Исполнитель', 'cfg:CatalogRef.ПользователиБитрикс', 'Исполнитель')
    f.attr('ВсяКоманда', 'boolean', 'Вся команда')
    f.attr('КартинкаСпринта', 'string', 'Картинка спринта')
    for имя, заголовок in КОЛОНКИ:
        f.attr(имя, 'ValueTable', заголовок, columns=ЗАДАЧИ_КОЛОНКИ)
    f.attr('ВнеПлана', 'ValueTable', 'Вне плана спринта', columns=[
        ('Задача', 'cfg:CatalogRef.Задачи', 'Задача'), ('Исполнитель', 'cfg:CatalogRef.ПользователиБитрикс', 'Исполнитель'),
        ('Часов', 'number:10.2', 'Часов')])
    f.command('ЗаписатьЧасы', 'Записать часы', tooltip='Записать часы по выбранной задаче: сколько и что сделано '
              '(как в «Учете времени»)', picture='StdPicture.CreateListItem', representation='TextPicture')
    f.command('Завершить', 'Завершить', tooltip='Отметить, что ваша стадия задачи завершена (запись времени с флажком '
              '«Завершено»; форма спринта и отчёты это видят). Саму задачу закрывают в Битрикс24')
    f.command('ОткрытьЗадачу', 'Открыть задачу', tooltip='Карточка задачи')
    f.command('ОткрытьВБ24', 'Открыть в Битрикс24', tooltip='Задача в Битрикс24 (там её закрывают)')
    f.command('Обновить', 'Обновить', picture='StdPicture.Refresh')
    f.command('ПредыдущийСпринт', 'Предыдущий спринт', picture='StdPicture.MoveLeft', representation='Picture')
    f.command('СледующийСпринт', 'Следующий спринт', picture='StdPicture.MoveRight', representation='Picture')
    f.cmdbar = ['ЗаписатьЧасы', 'Завершить', 'ОткрытьЗадачу', 'ОткрытьВБ24', 'Обновить']
    f.autofill_cmdbar = False

    def колонка(имя, заголовок):
        return f.group('Группа' + имя, [
            f.label('Заголовок' + имя, заголовок, font_bold=True),
            f.table(имя, имя, [
                f.input('Задача', read_only=True, width=30, auto_max_width=False),
                f.input('Исполнитель', read_only=True, width=14),
                f.input('Часы', read_only=True, width=9),
                f.input('Отметка', read_only=True, width=12)],
                read_only=True, height_rows=8,
                events={'Selection': имя + 'Выбор', 'OnActivateRow': имя + 'ПриАктивизацииСтроки'})])

    f.items = [
        f.group('Шапка', [
            f.label('Заголовок', 'Мой спринт', font_bold=True, wide=True),
            f.button('ПредыдущийСпринт'), f.button('СледующийСпринт'),
            f.check('ВсяКоманда', events={'OnChange': 'ВсяКомандаПриИзменении'})], 'horizontal'),
        f.label('Итог', '', wide=True),
        f.label('МестоКартинки', ''),
        f.group('Колонки', [колонка(и, з) for и, з in КОЛОНКИ], 'horizontal'),
        f.label('СсылкаВнеПлана', '', wide=True),
        f.table('ВнеПлана', 'ВнеПлана', [
            f.input('Задача', read_only=True, width=40, auto_max_width=False),
            f.input('Исполнитель', read_only=True, width=14), f.input('Часов', read_only=True, width=8)],
            read_only=True, height_rows=4, events={'Selection': 'ВнеПланаВыбор'}),
    ]
    т = f.xml(events={'OnCreateAtServer': 'ПриСозданииНаСервере', 'NotificationProcessing': 'ОбработкаОповещения',
                      'OnOpen': 'ПриОткрытии'},
              extra_props=['\t<AutoTitle>false</AutoTitle>'])
    ids = dl.FormIds(т)
    а = т.index('<LabelDecoration name="МестоКартинки"')
    т = заменить_место(т, 'МестоКартинки', картинка_xml('КартинкаСпринта', 'КартинкаСпринта', ids,
                                                        dl.line_indent(т, а), 120, 6))
    return гиперссылка(т, 'СсылкаВнеПлана', 'СсылкаВнеПланаНажатие')


def форма_записи():
    f = dl.Form('Записать часы')
    f.attr('Объект', 'cfg:DataProcessorObject.' + ИМЯ, main=True)
    f.attr('Задача', 'cfg:CatalogRef.Задачи', 'Задача')
    f.attr('Стадия', 'cfg:CatalogRef.Стадии', 'Стадия')
    f.attr('Исполнитель', 'cfg:CatalogRef.ПользователиБитрикс', 'Исполнитель')
    f.attr('Дата', 'date', 'Дата')
    f.attr('Часов', 'number:5.2+', 'Часов')
    f.attr('Комментарий', 'string', 'Что сделано')
    f.attr('СтадияЗавершена', 'boolean', 'Моя стадия завершена')
    f.command('Записать', 'Записать', tooltip='Записать часы в «Учет времени»')
    f.param('Задача', 'cfg:CatalogRef.Задачи')
    f.param('Стадия', 'cfg:CatalogRef.Стадии')
    f.param('Исполнитель', 'cfg:CatalogRef.ПользователиБитрикс')
    f.param('Завершить', 'boolean')
    f.cmdbar = ['Записать']
    f.items = [
        f.input('Задача', read_only=True, width=50, auto_max_width=False),
        f.group('Строка', [f.input('Стадия', read_only=True, width=26), f.input('Исполнитель', read_only=True, width=22)],
                'horizontal'),
        f.group('Ввод', [f.input('Дата', width=10), f.input('Часов', width=6)], 'horizontal'),
        f.input('Комментарий', multiline=True, height=3, width=50, auto_max_width=False),
        f.check('СтадияЗавершена', help='Флажок «Завершено» записи времени: стадия задачи из плана спринта выполнена. '
                'Можно записать и 0 часов — только отметку.'),
    ]
    т = f.xml(events={'OnCreateAtServer': 'ПриСозданииНаСервере'},
              extra_props=['\t<AutoTitle>false</AutoTitle>', '\t<WindowOpeningMode>LockOwnerWindow</WindowOpeningMode>'])
    return т.replace('<CommandName>Form.Command.Записать</CommandName>',
                     '<DefaultButton>true</DefaultButton>\n\t\t\t\t<CommandName>Form.Command.Записать</CommandName>', 1)


def метаданные():
    x.записать(x.путь('DataProcessors', ИМЯ + '.xml'), dl.data_processor_xml(
        ИМЯ, 'Мой спринт', forms=['Форма', 'ЗаписьЧасов'], default_form='Форма',
        explanation='Начальная страница исполнителя: задачи текущего спринта, часы по дням, запись часов и '
                    'завершение стадии'))
    x.записать(x.путь('DataProcessors', ИМЯ, 'Forms', 'Форма.xml'),
               dl.form_meta_xml('DataProcessor.' + ИМЯ, 'Форма', 'Мой спринт'))
    x.записать(x.путь('DataProcessors', ИМЯ, 'Forms', 'ЗаписьЧасов.xml'),
               dl.form_meta_xml('DataProcessor.' + ИМЯ, 'ЗаписьЧасов', 'Записать часы'))
    x.записать(x.путь('DataProcessors', ИМЯ, 'Forms', 'Форма', 'Ext', 'Form.xml'), форма_страницы())
    x.записать(x.путь('DataProcessors', ИМЯ, 'Forms', 'ЗаписьЧасов', 'Ext', 'Form.xml'), форма_записи())
    dl.register_in_configuration(ВЫГРУЗКА, 'DataProcessor', ИМЯ)
    for роль in ('Консультант', 'ДобавлениеВремениЗаДругогоСотрудника'):
        dl.add_rights(ВЫГРУЗКА, роль, 'DataProcessor.' + ИМЯ)
    dl.add_to_subsystem(x.путь('Subsystems', 'ПроектыИЗадачи.xml'), 'DataProcessor.' + ИМЯ)


def начальная_страница():
    """«Мой спринт» — первым во всю ширину; прежний отчёт по спринту — под ним."""
    # шаблон OneColumn — элементы в <Column>, а не LeftColumn/RightColumn (иначе «Текущее LeftColumn, ожидаемое Column»)
    x.записать(x.путь('Ext', 'HomePageWorkArea.xml'), dl.home_page_xml([
        ('DataProcessor.%s.Form.Форма' % ИМЯ, 30), ('Report.АнализВыполненияСпринтаПоДням.Form.ФормаОтчета', 10)]) + '\n')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    метаданные()
    начальная_страница()
    print('готово:', ИМЯ)
