# -*- coding: utf-8 -*-
"""make_examples — собирает examples/ из edt_lib с нейтральными именами.

Примеры не пишутся руками: они получены теми же строителями, что дали
рабочие объекты проекта-источника, и проходят check_form/check_mdo.
Пересобрать: python tools/make_examples.py   (README.md не трогает)
"""
import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edt_lib as L  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(HERE, 'examples')
CRLF = L.CRLF


def put(rel, text, xml=None):
    path = os.path.join(EX, rel.replace('/', os.sep))
    L.write_text(path, text, xml=xml)
    return path


def bsl(lines):
    """BSL из списка строк с отступами табами."""
    return CRLF.join(lines) + CRLF


def check_form(rel, module_rel=None, name=''):
    text = L.read_text(os.path.join(EX, rel))
    module = L.read_text(os.path.join(EX, module_rel)) if module_rel else None
    problems = [p for p in L.check_form(text, module) if not p.startswith('предупреждение')]
    if problems:
        sys.exit('ОШИБКА в примере %s: %s' % (rel, problems))
    if module is not None:
        problems = [p for p in L.check_bsl(module) if not p.startswith('предупреждение')]
        if problems:
            sys.exit('ОШИБКА в модуле %s: %s' % (module_rel, problems))
    print('  ok  %s' % rel)


def check_mdo(rel):
    problems = L.check_mdo(L.read_text(os.path.join(EX, rel)))
    if problems:
        sys.exit('ОШИБКА в примере %s: %s' % (rel, problems))
    print('  ok  %s' % rel)


# ------------------------------------------------------------------ метаданные
CAT = 'ПримерСправочник'
ENUM = 'ПримерПеречисление'
CONST = 'ПримерУпрощённыйРежим'
REG = 'ПримерНедоступность'
ACC = 'ПримерОстатки'
DOC = 'ПримерДокумент'
MOD = 'ПримерОбщийМодуль'
PROC = 'ПримерОбработка'
REP = 'ПримерОтчет'
REP2 = 'ПримерОтчетПоПериоду'
SUB = 'ПримерРаздел'
SUBCH = 'ПримерГруппа'
PIC = 'ПримерРаздел'
ROLE = 'ПримерРоль'
MOB = 'ПримерМобильная'
MAP = 'ПримерКарта'


def metadata():
    put('metadata/enum/%s/%s.mdo' % (ENUM, ENUM), L.enum_mdo(
        ENUM, 'Пример перечисления',
        [('Первое', 'Первое значение'), ('Второе', 'Второе значение'), ('Третье', 'Третье значение')],
        comment='Имена значений сверять с .mdo, а не сочинять (Перечисления.X.Y в коде)'))
    check_mdo('metadata/enum/%s/%s.mdo' % (ENUM, ENUM))

    put('metadata/catalog/%s/%s.mdo' % (CAT, CAT), L.catalog_mdo(
        CAT, 'Пример справочника',
        attributes=[('Тип', 'Тип', 'Перечисление.' + ENUM, 'обязательный'),
                    ('Радиус', 'Радиус, пикселей', 'Число(3,0)'),
                    ('Активен', 'Активен', 'Булево'),
                    ('Комментарий', 'Комментарий', 'Строка(0)')],
        tabular_sections=[{'name': 'Точки', 'synonym': 'Точки',
                           'attributes': [('X', 'X', 'Число(15,3)'), ('Y', 'Y', 'Число(15,3)')]}],
        comment='Минимальный справочник: реквизиты четырёх типов и табличная часть',
        forms=[('ФормаЭлемента', 'Форма элемента'), ('ФормаСписка', 'Форма списка')],
        default_forms=[('defaultObjectForm', 'ФормаЭлемента'), ('defaultListForm', 'ФормаСписка')]))
    check_mdo('metadata/catalog/%s/%s.mdo' % (CAT, CAT))

    put('metadata/constant/%s/%s.mdo' % (CONST, CONST), L.constant_mdo(
        CONST, 'Упрощённый режим', 'Булево',
        explanation='Включает упрощённый вид форм: лишнее скрывается модулем формы, XML не меняется.',
        comment='Переключатель поведения; читается Константы.X.Получить()'))
    check_mdo('metadata/constant/%s/%s.mdo' % (CONST, CONST))

    put('metadata/information-register/%s/%s.mdo' % (REG, REG), L.information_register_mdo(
        REG, 'Пример регистра сведений',
        dimensions=[('Объект', 'Объект', 'Справочник.' + CAT)],
        resources=[('НедоступенС', 'Недоступен с', 'ДатаВремя'),
                   ('НедоступенПо', 'Недоступен по', 'ДатаВремя'),
                   ('Причина', 'Причина', 'Строка(100)')],
        comment='Независимый непериодический регистр: одна актуальная запись на объект',
        forms=[('ФормаЗаписи', 'Форма записи'), ('ФормаСписка', 'Форма списка')],
        default_forms=[('defaultRecordForm', 'ФормаЗаписи'), ('defaultListForm', 'ФормаСписка')]))
    check_mdo('metadata/information-register/%s/%s.mdo' % (REG, REG))

    put('metadata/accumulation-register/%s/%s.mdo' % (ACC, ACC), L.accumulation_register_mdo(
        ACC, 'Пример остатков',
        dimensions=[('Объект', 'Объект', 'Справочник.' + CAT)],
        resources=[('Количество', 'Количество', 'Число(10,0)')],
        comment='Регистр остатков; структура снята с типового объекта (MEDIUM)'))
    check_mdo('metadata/accumulation-register/%s/%s.mdo' % (ACC, ACC))

    put('metadata/document/%s/%s.mdo' % (DOC, DOC), L.document_mdo(
        DOC, 'Пример документа',
        attributes=[('Объект', 'Объект', 'Справочник.' + CAT, 'обязательный'),
                    ('Комментарий', 'Комментарий', 'Строка(0)')],
        tabular_sections=[{'name': 'Строки', 'synonym': 'Строки',
                           'attributes': [('Объект', 'Объект', 'Справочник.' + CAT),
                                          ('Количество', 'Количество', 'Число(10,3)')]}],
        forms=[('ФормаДокумента', 'Форма документа')],
        default_forms=[('defaultObjectForm', 'ФормаДокумента')],
        register_records=['AccumulationRegister.' + ACC],
        comment='Документ с проведением по регистру остатков; структура снята с типового (MEDIUM)'))
    check_mdo('metadata/document/%s/%s.mdo' % (DOC, DOC))

    put('metadata/common-module/%s/%s.mdo' % (MOD, MOD), L.common_module_mdo(
        MOD, 'Пример общего модуля', server=True, server_call=True))
    check_mdo('metadata/common-module/%s/%s.mdo' % (MOD, MOD))
    put('metadata/common-module/%s/Module.bsl' % MOD, bsl([
        '// Серверный общий модуль с вызовом сервера: экспортные функции зовут из',
        '// клиентского кода форм. Помощники держим СВОИ (ЧислоИлиНоль) — функцию из',
        '// чужого модуля, вызванную без префикса, компилятор не проверяет (case 013).',
        '',
        '#Область ПрограммныйИнтерфейс',
        '',
        '// Активные элементы справочника. Иерархический справочник обязан отсекать',
        '// группы: у группы реквизиты возвращают NULL (case 017).',
        'Функция АктивныеЭлементы() Экспорт',
        '',
        '\tЗапрос = Новый Запрос(',
        '\t\t"ВЫБРАТЬ',
        '\t\t|\tЭлементы.Ссылка КАК Ссылка,',
        '\t\t|\tЭлементы.Наименование КАК Наименование,',
        '\t\t|\tЭлементы.Радиус КАК Радиус',
        '\t\t|ИЗ',
        '\t\t|\tСправочник.%s КАК Элементы' % CAT,
        '\t\t|ГДЕ',
        '\t\t|\tНЕ Элементы.ПометкаУдаления',
        '\t\t|\tИ Элементы.Активен',
        '\t\t|',
        '\t\t|УПОРЯДОЧИТЬ ПО',
        '\t\t|\tЭлементы.Наименование");',
        '\tВозврат Запрос.Выполнить().Выгрузить();',
        '',
        'КонецФункции',
        '',
        '// Запись независимого регистра: одна актуальная запись на объект.',
        'Процедура ОтметитьНедоступность(Объект, Минут, Причина) Экспорт',
        '',
        '\tНабор = РегистрыСведений.%s.СоздатьНаборЗаписей();' % REG,
        '\tНабор.Отбор.Объект.Установить(Объект);',
        '\tЗапись = Набор.Добавить();',
        '\tЗапись.Объект = Объект;',
        '\tЗапись.НедоступенС = ТекущаяДата();',
        '\tЗапись.НедоступенПо = ТекущаяДата() + Минут * 60;',
        '\tЗапись.Причина = Лев(Причина, 100);',
        '\tНабор.Записать();',
        '',
        'КонецПроцедуры',
        '',
        '// Чтение независимого регистра — ЗАПРОСОМ: метод Получить возвращает',
        '// структуру всегда, даже когда записи нет (case 018).',
        'Функция Недоступность(Объект) Экспорт',
        '',
        '\tЗапрос = Новый Запрос(',
        '\t\t"ВЫБРАТЬ ПЕРВЫЕ 1',
        '\t\t|\tЗаписи.НедоступенПо КАК НедоступенПо,',
        '\t\t|\tЗаписи.Причина КАК Причина',
        '\t\t|ИЗ',
        '\t\t|\tРегистрСведений.%s КАК Записи' % REG,
        '\t\t|ГДЕ',
        '\t\t|\tЗаписи.Объект = &Объект',
        '\t\t|\tИ Записи.НедоступенПо > &Сейчас");',
        '\tЗапрос.УстановитьПараметр("Объект", Объект);',
        '\tЗапрос.УстановитьПараметр("Сейчас", ТекущаяДата());',
        '\tВыборка = Запрос.Выполнить().Выбрать();',
        '\tЕсли НЕ Выборка.Следующий() Тогда',
        '\t\tВозврат Неопределено;',
        '\tКонецЕсли;',
        '\tВозврат Новый Структура("По, Причина", Выборка.НедоступенПо, Выборка.Причина);',
        '',
        'КонецФункции',
        '',
        '#КонецОбласти',
        '',
        '#Область СлужебныеПроцедурыИФункции',
        '',
        '// Число из чего угодно: NULL у реквизита группы, пустая строка, Неопределено.',
        'Функция ЧислоИлиНоль(Значение)',
        '',
        '\tЕсли Значение = Неопределено ИЛИ Значение = NULL ИЛИ Значение = "" Тогда',
        '\t\tВозврат 0;',
        '\tКонецЕсли;',
        '\tПопытка',
        '\t\tВозврат Число(Значение);',
        '\tИсключение',
        '\t\tВозврат 0;',
        '\tКонецПопытки;',
        '',
        'КонецФункции',
        '',
        '#КонецОбласти']), xml=False)

    # роль
    put('metadata/role/%s/%s.mdo' % (ROLE, ROLE), L.role_mdo(ROLE, 'Пример роли'))
    put('metadata/role/%s/Rights.rights' % ROLE, L.rights_file(
        'ИмяКонфигурации', ['ThinClient', 'MobileClient', 'OutputToPrinter', 'SaveUserData'],
        [('DataProcessor.' + PROC, ['Use', 'View']),
         ('Catalog.' + CAT, ['Read', 'View']),
         ('Document.' + DOC, ['Read', 'View', 'Edit', 'Update']),
         ('InformationRegister.' + REG, ['Read', 'Update']),
         ('Subsystem.' + SUB, ['View'])]))
    check_mdo('metadata/role/%s/%s.mdo' % (ROLE, ROLE))

    # подсистема с дочерней и картинкой
    put('metadata/subsystem/%s/%s.mdo' % (SUB, SUB), L.subsystem_mdo(
        SUB, 'Пример раздела', ['DataProcessor.' + PROC], children=[SUBCH], picture=PIC,
        explanation='Раздел командного интерфейса: обработка сверху, справочники в группе'))
    put('metadata/subsystem/%s/CommandInterface.cmi' % SUB, L.command_interface_cmi(
        important=L.commands_of(['DataProcessor.' + PROC]), subsystems=[SUBCH], parent=SUB))
    put('metadata/subsystem/%s/Subsystems/%s/%s.mdo' % (SUB, SUBCH, SUBCH), L.subsystem_mdo(
        SUBCH, 'Пример группы', ['Catalog.' + CAT, 'InformationRegister.' + REG, 'Report.' + REP,
                                'Enum.' + ENUM, 'Constant.' + CONST], parent=SUB,
        explanation='Дочерняя подсистема: связь с родителем держит parentSubsystem'))
    cmds = L.commands_of(['Catalog.' + CAT, 'InformationRegister.' + REG, 'Report.' + REP,
                          'Constant.' + CONST])
    put('metadata/subsystem/%s/Subsystems/%s/CommandInterface.cmi' % (SUB, SUBCH),
        L.command_interface_cmi(important=cmds[:1], ordinary=cmds[1:]))
    put('metadata/subsystem/CommonPictures/%s/%s.mdo' % (PIC, PIC), L.common_picture_mdo(
        PIC, 'Раздел "Пример"'))
    make_picture(os.path.join(EX, 'metadata', 'subsystem', 'CommonPictures', PIC, 'Picture.zip'))
    check_mdo('metadata/subsystem/%s/%s.mdo' % (SUB, SUB))
    check_mdo('metadata/subsystem/%s/Subsystems/%s/%s.mdo' % (SUB, SUBCH, SUBCH))


def make_picture(path):
    """Picture.zip общей картинки: 8 масштабов + Picture.png + manifest.xml.
    Без Pillow пишется только манифест и заглушки-квадраты 1x1 нельзя —
    тогда zip не создаётся, а README объясняет состав."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print('  (Pillow не найден — Picture.zip не собран, см. README)')
        return

    def draw(size):
        k = 16
        w = size * k
        im = Image.new('RGBA', (w, w), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse([w * 0.1, w * 0.1, w * 0.9, w * 0.9], fill=(58, 74, 92, 255))
        d.ellipse([w * 0.35, w * 0.35, w * 0.65, w * 0.65], fill=(232, 150, 32, 255))
        return im.resize((size, size), Image.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for fname, size, _d in L.PICTURE_SCALES:
            buf = io.BytesIO()
            draw(size).save(buf, 'PNG', optimize=True)
            z.writestr(fname, buf.getvalue())
        buf = io.BytesIO()
        draw(16).save(buf, 'PNG', optimize=True)
        z.writestr('Picture.png', buf.getvalue())
        z.writestr('manifest.xml', L.picture_manifest().encode('utf-8'))
    print('  ok  Picture.zip')


# ------------------------------------------------------------------ формы объектов
def item_form():
    ids = L.Ids()
    items = []
    items += L.usual_group(ids, 'КодНаименование', None, (
        L.field(ids, 'Код', 'Объект.Code', 4, width=11, max_width=True)
        + L.field(ids, 'Наименование', 'Объект.Description', 4)), 2)
    items += L.usual_group(ids, 'Параметры', 'Параметры', (
        L.field(ids, 'Тип', 'Объект.Тип', 4)
        + L.field(ids, 'Радиус', 'Объект.Радиус', 4, width=8, max_width=True, fmt='ЧЦ=3; ЧДЦ=0; ЧН=')
        + L.field(ids, 'Активен', 'Объект.Активен', 4, kind='CheckBoxField')), 2,
        direction='Vertical', representation='WeakSeparation')
    items += L.usual_group(ids, 'Прочее', 'Прочее', (
        L.field(ids, 'Комментарий', 'Объект.Комментарий', 4, multiline=True)), 2,
        direction='Vertical', representation='WeakSeparation')
    items += L.usual_group(ids, 'СтраницаТочки', 'Точки', L.object_tabular_table(
        ids, 'Точки', 'Объект.Точки', ['X', 'Y'], 4), 2, direction='Vertical',
        representation='WeakSeparation')
    nums = L.Ids()
    attrs = L.form_attribute(nums, 'Объект', None, 'CatalogObject.' + CAT, main=True, saved_data=True)
    text = L.form_file(items, attrs, handlers=[('OnCreateAtServer', 'ПриСозданииНаСервере')],
                       ext='form:CatalogFormExtInfo', window_mode='LockOwnerWindow')
    put('forms/simple-item-form/%s/Forms/ФормаЭлемента/Form.form' % CAT, text)
    put('forms/simple-item-form/%s/Forms/ФормаЭлемента/Module.bsl' % CAT, bsl([
        '// Модуль формы элемента. Каждая процедура — с директивой: без неё',
        '// процедура модуля формы компилируется серверной (case 011).',
        '',
        '&НаСервере',
        'Процедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)',
        '',
        '\t// Новый элемент: умолчания ставим здесь, а не в XML формы.',
        '\tЕсли Объект.Ссылка.Пустая() И НЕ Объект.Активен Тогда',
        '\t\tОбъект.Активен = Истина;',
        '\tКонецЕсли;',
        '',
        'КонецПроцедуры']), xml=False)
    check_form('forms/simple-item-form/%s/Forms/ФормаЭлемента/Form.form' % CAT,
               'forms/simple-item-form/%s/Forms/ФормаЭлемента/Module.bsl' % CAT)
    # копия внутрь примера справочника — чтобы scaffold брал объект целиком
    put('metadata/catalog/%s/Forms/ФормаЭлемента/Form.form' % CAT, text)
    put('metadata/catalog/%s/Forms/ФормаЭлемента/Module.bsl' % CAT,
        L.read_text(os.path.join(EX, 'forms/simple-item-form/%s/Forms/ФормаЭлемента/Module.bsl' % CAT)), xml=False)


def list_form():
    ids = L.Ids()
    items = L.list_form_settings_group(ids, 2)
    items += L.dynamic_list_table(ids, 'Список', [
        ('Код', 'Список.Code', 11), ('Наименование', 'Список.Description', None),
        ('Тип', 'Список.Тип', None), ('Активен', 'Список.Активен', 8)], 2)
    nums = L.Ids()
    attrs = L.form_attribute(nums, 'Список', None, 'DynamicList', main=True,
                             ext=L.dynamic_list_ext('Catalog.' + CAT, 0))
    text = L.form_file(items, attrs, ext='form:DynamicListFormExtInfo')
    put('forms/list-form/%s/Forms/ФормаСписка/Form.form' % CAT, text)
    check_form('forms/list-form/%s/Forms/ФормаСписка/Form.form' % CAT)
    put('metadata/catalog/%s/Forms/ФормаСписка/Form.form' % CAT, text)


def record_form():
    ids = L.Ids()
    items = L.usual_group(ids, 'Объект', None, L.field(ids, 'Объект', 'Запись.Объект', 4), 2,
                          direction='Vertical', representation='WeakSeparation')
    items += L.usual_group(ids, 'Окно', 'Когда недоступен', L.usual_group(
        ids, 'Период', None,
        L.field(ids, 'НедоступенС', 'Запись.НедоступенС', 6, width=16, max_width=True)
        + L.field(ids, 'НедоступенПо', 'Запись.НедоступенПо', 6, width=16, max_width=True), 4,
        direction='AlwaysHorizontal'), 2, direction='Vertical', representation='WeakSeparation')
    items += L.usual_group(ids, 'Причина', None, L.field(ids, 'Причина', 'Запись.Причина', 4), 2,
                           direction='Vertical', representation='WeakSeparation')
    nums = L.Ids()
    attrs = L.form_attribute(nums, 'Запись', None, 'InformationRegisterRecordManager.' + REG,
                             main=True, saved_data=True)
    text = L.form_file(items, attrs, ext='form:InformationRegisterManagerFormExtInfo',
                       window_mode='LockOwnerWindow')
    put('forms/record-form/%s/Forms/ФормаЗаписи/Form.form' % REG, text)
    check_form('forms/record-form/%s/Forms/ФормаЗаписи/Form.form' % REG)
    put('metadata/information-register/%s/Forms/ФормаЗаписи/Form.form' % REG, text)
    # список регистра
    ids = L.Ids()
    items = L.list_form_settings_group(ids, 2)
    items += L.dynamic_list_table(ids, 'Список', [
        ('Объект', 'Список.Объект', None), ('НедоступенС', 'Список.НедоступенС', 16),
        ('НедоступенПо', 'Список.НедоступенПо', 16), ('Причина', 'Список.Причина', None)], 2)
    nums = L.Ids()
    attrs = L.form_attribute(nums, 'Список', None, 'DynamicList', main=True,
                             ext=L.dynamic_list_ext('InformationRegister.' + REG, 0))
    text = L.form_file(items, attrs, ext='form:DynamicListFormExtInfo')
    put('metadata/information-register/%s/Forms/ФормаСписка/Form.form' % REG, text)
    check_form('metadata/information-register/%s/Forms/ФормаСписка/Form.form' % REG)


def document_form():
    ids = L.Ids()
    items = L.usual_group(ids, 'НомерДата', None, (
        L.field(ids, 'Номер', 'Объект.Number', 4, width=12, max_width=True)
        + L.field(ids, 'Дата', 'Объект.Date', 4, width=16, max_width=True)), 2)
    items += L.usual_group(ids, 'Шапка', None, (
        L.field(ids, 'Объект', 'Объект.Объект', 4)
        + L.field(ids, 'Комментарий', 'Объект.Комментарий', 4)), 2, direction='Vertical')
    items += L.object_tabular_table(ids, 'Строки', 'Объект.Строки', ['Объект', 'Количество'], 2)
    nums = L.Ids()
    attrs = L.form_attribute(nums, 'Объект', None, 'DocumentObject.' + DOC, main=True, saved_data=True)
    text = L.form_file(items, attrs, ext='form:DocumentFormExtInfo', window_mode='LockOwnerWindow')
    put('metadata/document/%s/Forms/ФормаДокумента/Form.form' % DOC, text)
    check_form('metadata/document/%s/Forms/ФормаДокумента/Form.form' % DOC)


# ------------------------------------------------------------------ обработка с таблицей
def processor():
    put('metadata/data-processor/%s/%s.mdo' % (PROC, PROC), L.data_processor_mdo(
        PROC, 'Пример обработки', [('Форма', 'Пример обработки')], default_form='Форма',
        comment='Обработка: таблица значений, настройки, три команды'))
    check_mdo('metadata/data-processor/%s/%s.mdo' % (PROC, PROC))
    ids = L.Ids()
    commands = [('Заполнить', 'Заполнить', 'Перечитать элементы по отбору'),
                ('Записать', 'Записать отмеченные', 'Записать комментарий в отмеченные элементы'),
                ('ОтметитьВсе', 'Отметить все', 'Поставить галку у всех строк')]
    items = L.command_bar(ids, 'КоманднаяПанель', sum(
        (L.bar_button(ids, name, 4, name == 'Заполнить') for name, _t, _p in commands), []), 2)
    items += L.field(ids, 'ТолькоАктивные', 'ТолькоАктивные', 2, 'CheckBoxField', 'Только активные')
    items += L.field(ids, 'Шаблон', 'Шаблон', 2, 'InputField', 'Отбор по имени (звёздочка — любые знаки)')
    items += L.value_table(ids, 'Строки', [
        ('Отметка', 'Записать', 'CheckBoxField', False),
        ('Элемент', 'Элемент', 'InputField', True),
        ('Комментарий', 'Комментарий', 'InputField', False),
        ('Состояние', 'Что нашлось', 'InputField', True)], 2, selection='MultiRow')
    nums = L.Ids()
    attrs = L.form_attribute(nums, 'Объект', None, 'DataProcessorObject.' + PROC, main=True)
    attrs += L.form_attribute(nums, 'ТолькоАктивные', 'Только активные', 'Boolean')
    attrs += L.form_attribute(nums, 'Шаблон', 'Отбор по имени', 'String')
    attrs += L.form_attribute(nums, 'Строки', 'Элементы', 'ValueTable', columns=[
        ('Отметка', 'Записать', 'Boolean'), ('Элемент', 'Элемент', 'CatalogRef.' + CAT),
        ('Комментарий', 'Комментарий', 'String'), ('Состояние', 'Что нашлось', 'String')])
    cmds = []
    for n, (name, title, tip) in enumerate(commands, 1):
        cmds += L.form_command(n, name, title, tip)
    text = L.form_file(items, attrs, cmds, handlers=[('OnCreateAtServer', 'ПриСозданииНаСервере')],
                       auto_bar_id=ids(), auto_bar_fill=False)
    put('metadata/data-processor/%s/Forms/Форма/Form.form' % PROC, text)
    module = bsl([
        '// Модуль формы обработки «Пример обработки».',
        '//',
        '// Правило: клиентская команда → серверная процедура «…НаСервере» →',
        '// серверная работа с таблицей. У каждой процедуры директива (case 011).',
        '',
        '&НаСервере',
        'Процедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)',
        '',
        '\tТолькоАктивные = Истина;',
        '\tЗаполнитьСтроки();',
        '',
        'КонецПроцедуры',
        '',
        '&НаКлиенте',
        'Процедура Заполнить(Команда)',
        '',
        '\tЗаполнитьНаСервере();',
        '',
        'КонецПроцедуры',
        '',
        '&НаСервере',
        'Процедура ЗаполнитьНаСервере()',
        '',
        '\tЗаполнитьСтроки();',
        '',
        'КонецПроцедуры',
        '',
        '&НаКлиенте',
        'Процедура ОтметитьВсе(Команда)',
        '',
        '\tОтмечено = 0;',
        '\tДля Каждого Строка Из Строки Цикл',
        '\t\tЕсли ЗначениеЗаполнено(Строка.Элемент) Тогда',
        '\t\t\tСтрока.Отметка = Истина;',
        '\t\t\tОтмечено = Отмечено + 1;',
        '\t\tКонецЕсли;',
        '\tКонецЦикла;',
        '\tПоказатьПредупреждение(, "Отмечено строк: " + Отмечено);',
        '',
        'КонецПроцедуры',
        '',
        '&НаКлиенте',
        'Процедура Записать(Команда)',
        '',
        '\tКЗаписи = 0;',
        '\tДля Каждого Строка Из Строки Цикл',
        '\t\tЕсли Строка.Отметка И ЗначениеЗаполнено(Строка.Элемент) Тогда',
        '\t\t\tКЗаписи = КЗаписи + 1;',
        '\t\tКонецЕсли;',
        '\tКонецЦикла;',
        '\tЕсли КЗаписи = 0 Тогда',
        '\t\tПоказатьПредупреждение(, "Не отмечено ни одной строки.");',
        '\t\tВозврат;',
        '\tКонецЕсли;',
        '\tИтог = ЗаписатьНаСервере();',
        '\tЗаполнитьНаСервере();',
        '\tПоказатьПредупреждение(, Итог);',
        '',
        'КонецПроцедуры',
        '',
        '&НаСервере',
        'Функция ЗаписатьНаСервере()',
        '',
        '\tЗаписано = 0;',
        '\tОшибок = 0;',
        '\tДля Каждого Строка Из Строки Цикл',
        '\t\tЕсли НЕ Строка.Отметка ИЛИ НЕ ЗначениеЗаполнено(Строка.Элемент) Тогда',
        '\t\t\tПродолжить;',
        '\t\tКонецЕсли;',
        '\t\tПопытка',
        '\t\t\tЭлементОбъект = Строка.Элемент.ПолучитьОбъект();',
        '\t\t\tЭлементОбъект.Комментарий = Строка.Комментарий;',
        '\t\t\t// Режим загрузки — свойство СТРУКТУРЫ ОбменДанными (case 014).',
        '\t\t\tЭлементОбъект.ОбменДанными.Загрузка = Истина;',
        '\t\t\tЭлементОбъект.Записать();',
        '\t\t\tЗаписано = Записано + 1;',
        '\t\tИсключение',
        '\t\t\tОшибок = Ошибок + 1;',
        '\t\t\tСообщить("Элемент «" + Строка.Элемент + "» не записан: " + ОписаниеОшибки());',
        '\t\tКонецПопытки;',
        '\tКонецЦикла;',
        '\tИтог = "Записано: " + Записано;',
        '\tЕсли Ошибок > 0 Тогда',
        '\t\tИтог = Итог + ", с ошибкой: " + Ошибок;',
        '\tКонецЕсли;',
        '\tВозврат Итог;',
        '',
        'КонецФункции',
        '',
        '// Шаблон пользователь пишет звёздочкой, языку запросов нужен процент.',
        '&НаСервереБезКонтекста',
        'Функция ШаблонВЗапрос(Шаблон)',
        '',
        '\tТекст = СокрЛП(Шаблон);',
        '\tЕсли ПустаяСтрока(Текст) Тогда',
        '\t\tВозврат "";',
        '\tКонецЕсли;',
        '\tТекст = СтрЗаменить(Текст, "*", "%");',
        '\tЕсли СтрНайти(Текст, "%") = 0 Тогда',
        '\t\tТекст = "%" + Текст + "%";',
        '\tКонецЕсли;',
        '\tВозврат Текст;',
        '',
        'КонецФункции',
        '',
        '&НаСервере',
        'Процедура ЗаполнитьСтроки()',
        '',
        '\tСтроки.Очистить();',
        '\t// Сравнение со строкой в запросе не пишем: пустая строка внутри',
        '\t// строкового литерала требует четырёх кавычек (case 015). Пустой',
        '\t// шаблон отсеиваем параметром.',
        '\tЗапрос = Новый Запрос(',
        '\t\t"ВЫБРАТЬ',
        '\t\t|\tЭлементы.Ссылка КАК Ссылка,',
        '\t\t|\tЭлементы.Наименование КАК Наименование,',
        '\t\t|\tЭлементы.Комментарий КАК Комментарий,',
        '\t\t|\tЭлементы.Активен КАК Активен',
        '\t\t|ИЗ',
        '\t\t|\tСправочник.%s КАК Элементы' % CAT,
        '\t\t|ГДЕ',
        '\t\t|\tНЕ Элементы.ПометкаУдаления',
        '\t\t|\tИ (&БезОтбора ИЛИ Элементы.Наименование ПОДОБНО &Шаблон)',
        '\t\t|',
        '\t\t|УПОРЯДОЧИТЬ ПО',
        '\t\t|\tЭлементы.Наименование");',
        '\tШаблонЗапроса = ШаблонВЗапрос(Шаблон);',
        '\tЗапрос.УстановитьПараметр("БезОтбора", ПустаяСтрока(ШаблонЗапроса));',
        '\tЗапрос.УстановитьПараметр("Шаблон", ШаблонЗапроса);',
        '\tВыборка = Запрос.Выполнить().Выбрать();',
        '\tПока Выборка.Следующий() Цикл',
        '\t\tЕсли ТолькоАктивные И НЕ Выборка.Активен Тогда',
        '\t\t\tПродолжить;',
        '\t\tКонецЕсли;',
        '\t\tСтрока = Строки.Добавить();',
        '\t\tСтрока.Элемент = Выборка.Ссылка;',
        '\t\tСтрока.Комментарий = Выборка.Комментарий;',
        '\t\tСтрока.Состояние = ?(Выборка.Активен, "активен", "выключен");',
        '\tКонецЦикла;',
        '',
        'КонецПроцедуры'])
    put('metadata/data-processor/%s/Forms/Форма/Module.bsl' % PROC, module, xml=False)
    check_form('metadata/data-processor/%s/Forms/Форма/Form.form' % PROC,
               'metadata/data-processor/%s/Forms/Форма/Module.bsl' % PROC)


# ------------------------------------------------------------------ мобильная форма
def mobile():
    put('mobile/mobile-form/%s/%s.mdo' % (MOB, MOB), L.data_processor_mdo(
        MOB, 'Пример мобильной формы',
        [('ФормаМобильная', 'Мои задачи', ('MobileDevice', 'PersonalComputer'))],
        default_form='ФормаМобильная',
        comment='Одна форма с двумя назначениями: телефон и проверка в тонком клиенте'))
    ids = L.Ids()
    now = L.decoration(ids, 'ЧтоДелать', 'Что делать', 6, bold=True)
    now += L.field(ids, 'ТекущийОбъект', 'ТекущийОбъект', 6, 'InputField', 'Объект', read_only=True)
    now += L.field(ids, 'НормативТекст', 'НормативТекст', 6, 'InputField', 'Норматив', read_only=True)
    now += L.field(ids, 'Просрочено', 'Просрочено', 6, 'CheckBoxField', 'Пора заканчивать', read_only=True)
    now += L.page_button(ids, 'Дальше', 6, True, 'главная')
    now += L.page_button(ids, 'НеПолучается', 6, False, 'осторожно')
    tasks = L.value_table(ids, 'Задачи', [
        ('Описание', 'Задача', 'InputField', True), ('Состояние', 'Что делаю', 'InputField', True)], 6,
        selection='SingleRow', on_activate_row='ЗадачиПриАктивизацииСтроки', mobile=True)
    chat = L.value_table(ids, 'Сообщения', [
        ('Когда', 'Когда', 'InputField', True), ('Текст', 'Сообщение', 'InputField', True)], 6,
        selection='SingleRow', mobile=True)
    chat += L.field(ids, 'НовоеСообщение', 'НовоеСообщение', 6, 'InputField', 'Написать',
                    multiline=True, title_location='None', input_hint='Написать диспетчеру…')
    chat += L.page_button(ids, 'Отправить', 6, False, 'главная')
    items = L.pages(ids, 'Страницы', [
        ('СтраницаСейчас', 'Сейчас', now), ('СтраницаЗадачи', 'Задачи', tasks),
        ('СтраницаЧат', 'Чат', chat)], 2, representation='TabsOnTop',
        on_change='СтраницыПриСменеСтраницы')
    nums = L.Ids()
    attrs = L.form_attribute(nums, 'Объект', None, 'DataProcessorObject.' + MOB, main=True)
    attrs += L.form_attribute(nums, 'Задачи', 'Задачи', 'ValueTable', columns=[
        ('Задача', 'Задача', 'CatalogRef.' + CAT), ('Описание', 'Задача', 'String'),
        ('Состояние', 'Что делаю', 'String'), ('Точек', 'Точек', 'Number'),
        ('Готово', 'Готово', 'Boolean')])
    attrs += L.form_attribute(nums, 'Сообщения', 'Сообщения', 'ValueTable', columns=[
        ('Дата', 'Дата', 'Date'), ('Когда', 'Когда', 'String'), ('Текст', 'Сообщение', 'String'),
        ('ОтДиспетчера', 'От диспетчера', 'Boolean')])
    for name, title, kind in (('ТекущийОбъект', 'Объект', 'CatalogRef.' + CAT),
                              ('НормативТекст', 'Норматив', 'String'),
                              ('Просрочено', 'Пора заканчивать', 'Boolean'),
                              ('НовоеСообщение', 'Новое сообщение', 'String'),
                              ('ТекущаяЗадача', 'Текущая задача', 'CatalogRef.' + CAT),
                              ('НовыхСообщений', 'Новых сообщений', 'Number')):
        attrs += L.form_attribute(nums, name, title, kind)
    cmds = []
    for n, (name, title, tip) in enumerate([
            ('Дальше', 'Дальше', 'Отметить следующий шаг'),
            ('НеПолучается', 'Не получается', 'Закрыть задачу с причиной'),
            ('Отправить', 'Отправить', 'Написать диспетчеру')], 1):
        cmds += L.form_command(n, name, title, tip)
    text = L.form_file(items, attrs, cmds, title='Мои задачи', auto_title=False,
                       handlers=[('OnCreateAtServer', 'ПриСозданииНаСервере'), ('OnOpen', 'ПриОткрытии')],
                       auto_bar_id=ids(), auto_bar_fill=False)
    put('mobile/mobile-form/%s/Forms/ФормаМобильная/Form.form' % MOB, text)
    module = bsl([
        '// Модуль мобильной формы. Логика — в общем модуле, форма раскладывает ответ.',
        '// Страницы закладками (TabsOnTop) работают и на телефоне, и на компьютере;',
        '// смахивания ПО СТРОКЕ у платформы нет — действия строки в контекстном',
        '// меню (долгое нажатие) или кнопками на странице (case 030).',
        '',
        '&НаСервере',
        'Процедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)',
        '',
        '\tЗаполнитьВсё();',
        '\tЭлементы.Страницы.ТекущаяСтраница = Элементы.СтраницаСейчас;',
        '',
        'КонецПроцедуры',
        '',
        '// Экран перечитывается сам раз в минуту: пользователь «Обновить» не жмёт.',
        '&НаКлиенте',
        'Процедура ПриОткрытии(Отказ)',
        '',
        '\tПодключитьОбработчикОжидания("ПоТаймеру", 60);',
        '',
        'КонецПроцедуры',
        '',
        '&НаКлиенте',
        'Процедура ПоТаймеру()',
        '',
        '\tЗаполнитьНаСервере();',
        '',
        'КонецПроцедуры',
        '',
        '&НаСервере',
        'Процедура ЗаполнитьНаСервере()',
        '',
        '\tЗаполнитьВсё();',
        '',
        'КонецПроцедуры',
        '',
        '&НаСервере',
        'Процедура ЗаполнитьВсё()',
        '',
        '\t// Таблица общего модуля кладётся в реквизит целиком: колонки реквизита',
        '\t// формы держим НАДМНОЖЕСТВОМ колонок таблицы модуля.',
        '\tЗначениеВРеквизитФормы(%s.АктивныеЭлементы(), "Задачи");' % MOD,
        '\tЕсли Задачи.Количество() > 0 И НЕ ЗначениеЗаполнено(ТекущаяЗадача) Тогда',
        '\t\tТекущаяЗадача = Задачи[0].Задача;',
        '\t\tЭлементы.Задачи.ТекущаяСтрока = Задачи[0].ПолучитьИдентификатор();',
        '\tКонецЕсли;',
        '\tПоказатьЭкран();',
        '',
        'КонецПроцедуры',
        '',
        '// Заголовок и пояснение — НАДПИСИ: текст им отдаётся через Заголовок,',
        '// длинное переносится, а не обрезается. Пустое на телефоне не показываем.',
        '&НаСервере',
        'Процедура ПоказатьЭкран()',
        '',
        '\t// «Объект» — свойство формы (case 010): свой реквизит назван иначе.',
        '\tТекущийОбъект = ТекущаяЗадача;',
        '\tЭлементы.ЧтоДелать.Заголовок = ?(ЗначениеЗаполнено(ТекущаяЗадача),',
        '\t\t"Выполнить: " + Строка(ТекущаяЗадача), "Задач нет");',
        '\tЭлементы.ЧтоДелать.ЦветТекста = ?(Просрочено, Новый Цвет(211, 47, 47), Новый Цвет());',
        '\tЭлементы.Дальше.Заголовок = ?(ЗначениеЗаполнено(ТекущаяЗадача), "Готово", "Дальше");',
        '\tЭлементы.НормативТекст.Видимость = НЕ ПустаяСтрока(НормативТекст);',
        '\tЭлементы.Просрочено.Видимость = Просрочено;',
        '',
        'КонецПроцедуры',
        '',
        '&НаКлиенте',
        'Процедура ЗадачиПриАктивизацииСтроки(Элемент)',
        '',
        '\tТекущиеДанные = Элементы.Задачи.ТекущиеДанные;',
        '\tЕсли ТекущиеДанные = Неопределено ИЛИ ТекущиеДанные.Задача = ТекущаяЗадача Тогда',
        '\t\tВозврат;',
        '\tКонецЕсли;',
        '\tТекущаяЗадача = ТекущиеДанные.Задача;',
        '\tЗаполнитьНаСервере();',
        '',
        'КонецПроцедуры',
        '',
        '&НаКлиенте',
        'Процедура СтраницыПриСменеСтраницы(Элемент, ТекущаяСтраница)',
        '',
        '\tЕсли ТекущаяСтраница = Элементы.СтраницаЧат И НовыхСообщений > 0 Тогда',
        '\t\tЗаполнитьНаСервере();',
        '\tКонецЕсли;',
        '',
        'КонецПроцедуры',
        '',
        '&НаКлиенте',
        'Процедура Дальше(Команда)',
        '',
        '\tЕсли НЕ ЗначениеЗаполнено(ТекущаяЗадача) Тогда',
        '\t\tПоказатьПредупреждение(, "Задач нет.");',
        '\t\tВозврат;',
        '\tКонецЕсли;',
        '\tПоказатьПредупреждение(, ШагНаСервере());',
        '',
        'КонецПроцедуры',
        '',
        '&НаСервере',
        'Функция ШагНаСервере()',
        '',
        '\t%s.ОтметитьНедоступность(ТекущаяЗадача, 30, "в работе");' % MOD,
        '\tЗаполнитьВсё();',
        '\tВозврат "Отмечено.";',
        '',
        'КонецФункции',
        '',
        '// Выбор причины — меню: ПоказатьВыборИзМеню с оповещением, не окно с таблицей.',
        '&НаКлиенте',
        'Процедура НеПолучается(Команда)',
        '',
        '\tСписок = Новый СписокЗначений;',
        '\tСписок.Добавить("нет", "Груза нет");',
        '\tСписок.Добавить("некому", "Принять некому");',
        '\tПоказатьВыборИзМеню(Новый ОписаниеОповещения("ПричинаВыбрана", ЭтотОбъект),',
        '\t\tСписок, Элементы.НеПолучается);',
        '',
        'КонецПроцедуры',
        '',
        '&НаКлиенте',
        'Процедура ПричинаВыбрана(Выбранное, ДопПараметры) Экспорт',
        '',
        '\tЕсли Выбранное = Неопределено Тогда',
        '\t\tВозврат;',
        '\tКонецЕсли;',
        '\tПоказатьОповещениеПользователя("Причина: " + Выбранное.Представление);',
        '',
        'КонецПроцедуры',
        '',
        '// Ответ — оповещением в углу, а не окном: в чате «ОК» на каждую реплику невыносимо.',
        '&НаКлиенте',
        'Процедура Отправить(Команда)',
        '',
        '\tЕсли ПустаяСтрока(НовоеСообщение) Тогда',
        '\t\tПоказатьОповещениеПользователя("Напишите сообщение");',
        '\t\tВозврат;',
        '\tКонецЕсли;',
        '\tНовоеСообщение = "";',
        '\tПоказатьОповещениеПользователя("Отправлено");',
        '',
        'КонецПроцедуры'])
    put('mobile/mobile-form/%s/Forms/ФормаМобильная/Module.bsl' % MOB, module, xml=False)
    check_form('mobile/mobile-form/%s/Forms/ФормаМобильная/Form.form' % MOB,
               'mobile/mobile-form/%s/Forms/ФормаМобильная/Module.bsl' % MOB)


# ------------------------------------------------------------------ поле HTML и мост
def html_form():
    put('forms/html-field-form/%s/%s.mdo' % (MAP, MAP), L.data_processor_mdo(
        MAP, 'Пример поля HTML', [('Форма', 'Пример поля HTML')], default_form='Форма',
        templates=[('СтраницаHTML', 'Страница, HTML', 'TextDocument')],
        comment='Поле HTML с макетом и обменом через скрытые поля'))
    ids = L.Ids()
    items = L.html_field(ids, 'ПолеСтраницы', 'HTMLСтраницы', 2, on_complete='ПолеСтраницыДокументСформирован')
    nums = L.Ids()
    attrs = L.form_attribute(nums, 'Объект', None, 'DataProcessorObject.' + MAP, main=True)
    attrs += L.form_attribute(nums, 'HTMLСтраницы', 'HTML страницы', 'String')
    text = L.form_file(items, attrs, handlers=[('OnCreateAtServer', 'ПриСозданииНаСервере'),
                                               ('OnOpen', 'ПриОткрытии'), ('OnClose', 'ПриЗакрытии')],
                       auto_bar_fill=False)
    put('forms/html-field-form/%s/Forms/Форма/Form.form' % MAP, text)
    put('forms/html-field-form/%s/Forms/Форма/Module.bsl' % MAP, bsl([
        '// Поле HTML и обмен с 1С БЕЗ вызова JS: 1С пишет в скрытые поля страницы,',
        '// страница читает их по таймеру; обратно — страница пишет очередь команд в',
        '// поле bridge_out, 1С опрашивает его обработчиком ожидания и подтверждает',
        '// номер в out_ack. Снято с рабочего АРМ (reference/html-field-data-processor).',
        '',
        '&НаКлиенте',
        'Перем ДокументГотов;',
        '',
        '&НаКлиенте',
        'Перем СчётчикВхода;',
        '',
        '&НаКлиенте',
        'Перем ПоследняяКомандаОбработана;',
        '',
        '&НаСервере',
        'Процедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)',
        '',
        '\t// Макет берётся у объекта обработки, а не у формы.',
        '\tОбъектОбработки = РеквизитФормыВЗначение("Объект");',
        '\tМакет = ОбъектОбработки.ПолучитьМакет("СтраницаHTML");',
        '\tHTMLСтраницы = Макет.ПолучитьТекст();',
        '\t// Текстовый макет хранится построчно: длинные строки сборка режет по 900',
        '\t// символов с маркером Символ(1) в конце куска, здесь склеиваем (case 023).',
        '\tHTMLСтраницы = СтрЗаменить(HTMLСтраницы, Символ(1) + Символы.ВК + Символы.ПС, "");',
        '\tHTMLСтраницы = СтрЗаменить(HTMLСтраницы, Символ(1) + Символы.ПС, "");',
        '\tHTMLСтраницы = СтрЗаменить(HTMLСтраницы, Символ(1), "");',
        '\tЕсли СтрНайти(Прав(HTMLСтраницы, 40), "</html>") = 0 Тогда',
        '\t\tСообщить("Макет пришёл неполным — текст обрывается не на </html>.");',
        '\tКонецЕсли;',
        '',
        'КонецПроцедуры',
        '',
        '&НаКлиенте',
        'Процедура ПриОткрытии(Отказ)',
        '',
        '\tДокументГотов = Ложь;',
        '\tСчётчикВхода = 0;',
        '\tПоследняяКомандаОбработана = 0;',
        '',
        'КонецПроцедуры',
        '',
        '&НаКлиенте',
        'Процедура ПриЗакрытии(ЗавершениеРаботы)',
        '',
        '\tОтключитьОбработчикОжидания("ОпросМоста");',
        '',
        'КонецПроцедуры',
        '',
        '// Раньше этого момента обращаться к Документу нельзя.',
        '&НаКлиенте',
        'Процедура ПолеСтраницыДокументСформирован(Элемент)',
        '',
        '\tДокументГотов = Истина;',
        '\t// Повторяющийся обработчик: минимальный интервал — 1 секунда.',
        '\tПодключитьОбработчикОжидания("ОпросМоста", 1);',
        '',
        'КонецПроцедуры',
        '',
        '// 1С → страница: текст в поле in_<тип>, метка «длина\\u0001номер» в in_<тип>_sig.',
        '&НаКлиенте',
        'Процедура ОтправитьВСтраницу(ВидСообщения, Текст)',
        '',
        '\tПопытка',
        '\t\tДок = Элементы.ПолеСтраницы.Документ;',
        '\tИсключение',
        '\t\tДок = Неопределено;',
        '\tКонецПопытки;',
        '\tЕсли Док = Неопределено Тогда',
        '\t\tВозврат;',
        '\tКонецЕсли;',
        '\tПолеДанных = Док.getElementById("in_" + ВидСообщения);',
        '\tПолеСигнала = Док.getElementById("in_" + ВидСообщения + "_sig");',
        '\tЕсли ПолеДанных = Неопределено ИЛИ ПолеСигнала = Неопределено Тогда',
        '\t\tСообщить("Поле обмена in_" + ВидСообщения + " не найдено в документе.");',
        '\t\tВозврат;',
        '\tКонецЕсли;',
        '\tСчётчикВхода = СчётчикВхода + 1;',
        '\tПолеДанных.value = Текст;',
        '\tПолеСигнала.value = Формат(СтрДлина(Текст), "ЧГ=0") + Символ(1) + Формат(СчётчикВхода, "ЧГ=0");',
        '',
        'КонецПроцедуры',
        '',
        '// Страница → 1С: очередь команд JSON в поле bridge_out; подтверждение номером в out_ack.',
        '&НаКлиенте',
        'Процедура ОпросМоста()',
        '',
        '\tЕсли НЕ ДокументГотов Тогда',
        '\t\tВозврат;',
        '\tКонецЕсли;',
        '\tПопытка',
        '\t\tПолеВыхода = Элементы.ПолеСтраницы.Документ.getElementById("bridge_out");',
        '\tИсключение',
        '\t\tВозврат;',
        '\tКонецПопытки;',
        '\tЕсли ПолеВыхода = Неопределено ИЛИ ПустаяСтрока(ПолеВыхода.value) Тогда',
        '\t\tВозврат;',
        '\tКонецЕсли;',
        '\t// «Команды» — свойство управляемой формы, в него писать нельзя (case 010).',
        '\tСписокКоманд = ИзJSON(ПолеВыхода.value);',
        '\tПоследнийНомер = ПоследняяКомандаОбработана;',
        '\tДля Каждого Команда Из СписокКоманд Цикл',
        '\t\tНомер = Команда["n"];',
        '\t\tЕсли ТипЗнч(Номер) = Тип("Число") И Номер <= ПоследняяКомандаОбработана Тогда',
        '\t\t\tПродолжить;',
        '\t\tКонецЕсли;',
        '\t\tПопытка',
        '\t\t\tОбработатьКоманду(Команда["k"], Команда["d"]);',
        '\t\tИсключение',
        '\t\t\tСообщить("Ошибка обработки команды " + Команда["k"] + ": " + ОписаниеОшибки());',
        '\t\tКонецПопытки;',
        '\t\tЕсли ТипЗнч(Номер) = Тип("Число") Тогда',
        '\t\t\tПоследнийНомер = Номер;',
        '\t\tКонецЕсли;',
        '\tКонецЦикла;',
        '\tПоследняяКомандаОбработана = ПоследнийНомер;',
        '\tПолеПодтв = Элементы.ПолеСтраницы.Документ.getElementById("out_ack");',
        '\tЕсли ПолеПодтв <> Неопределено Тогда',
        '\t\tПолеПодтв.value = Формат(ПоследняяКомандаОбработана, "ЧГ=0");',
        '\tКонецЕсли;',
        '',
        'КонецПроцедуры',
        '',
        '&НаКлиенте',
        'Процедура ОбработатьКоманду(Имя, Данные)',
        '',
        '\tЕсли Имя = "appReady" Тогда',
        '\t\t// Страница поднялась целиком — только теперь отправляем данные.',
        '\t\tОтправитьВСтраницу("package", ПакетНаСервере());',
        '\tИначеЕсли Имя = "select" Тогда',
        '\t\tПоказатьОповещениеПользователя("Выбрано: " + Строка(Данные["ид"]));',
        '\tКонецЕсли;',
        '',
        'КонецПроцедуры',
        '',
        '&НаСервереБезКонтекста',
        'Функция ПакетНаСервере()',
        '',
        '\tВозврат ВJSON(Новый Структура("версия", 1));',
        '',
        'КонецФункции',
        '',
        '&НаКлиентеНаСервереБезКонтекста',
        'Функция ВJSON(Значение)',
        '',
        '\tЗапись = Новый ЗаписьJSON;',
        '\tЗапись.УстановитьСтроку();',
        '\tЗаписатьJSON(Запись, Значение);',
        '\tВозврат Запись.Закрыть();',
        '',
        'КонецФункции',
        '',
        '&НаКлиентеНаСервереБезКонтекста',
        'Функция ИзJSON(Текст)',
        '',
        '\tЧтение = Новый ЧтениеJSON;',
        '\tЧтение.УстановитьСтроку(Текст);',
        '\tВозврат ПрочитатьJSON(Чтение, Ложь);',
        '',
        'КонецФункции']), xml=False)
    # минимальный макет: поля обмена + мост
    html = [
        '<!DOCTYPE html>',
        '<html><head><meta charset="utf-8"><title>Пример</title>',
        '<style>html,body{height:100%;margin:0} #app{padding:12px;font-family:sans-serif}</style>',
        '</head>',
        '<body>',
        '<div id="app">Страница из макета. Команды уходят в 1С по кнопке.',
        ' <button onclick="Bridge.send(\'select\',{ид:\'demo\'})">Выбрать</button></div>',
        '<!-- поля обмена: 1С читает и пишет их value; вызовов JS из 1С в этой связке нет -->',
        '<input type="hidden" id="in_package"><input type="hidden" id="in_package_sig">',
        '<input type="hidden" id="bridge_out"><input type="hidden" id="out_ack">',
        '<script>',
        '(function(){',
        '  var очередь = [], номер = 0, принято = {};',
        '  function читать(имя){ var п = document.getElementById("in_"+имя), с = document.getElementById("in_"+имя+"_sig");',
        '    if(!п||!с||!с.value) return; var м = с.value.split("\\u0001"); var длина = +м[0], seq = +м[1];',
        '    if(принято[имя]===seq) return; if(п.value.length<длина) return; принято[imя]=seq; got(имя, п.value); }',
        '  function got(имя, текст){ document.getElementById("app").textContent = имя + ": " + текст.length + " символов"; }',
        '  function send(имя, данные){ очередь.push({n:++номер,k:имя,d:данные}); document.getElementById("bridge_out").value = JSON.stringify(очередь); }',
        '  setInterval(function(){ читать("package"); var ack = +document.getElementById("out_ack").value || 0;',
        '    if(ack){ очередь = очередь.filter(function(к){return к.n>ack;}); document.getElementById("bridge_out").value = очередь.length?JSON.stringify(очередь):""; } }, 40);',
        '  window.Bridge = {send:send};',
        '  send("appReady", {});',
        '})();',
        '</script>',
        '</body></html>']
    # опечатка-ловушка в JS исключена: имя переменной одинаково кириллицей
    html = [l.replace('принято[imя]', 'принято[имя]') for l in html]
    put('forms/html-field-form/%s/Templates/СтраницаHTML/Template.txt' % MAP, CRLF.join(html) + CRLF, xml=False)
    check_form('forms/html-field-form/%s/Forms/Форма/Form.form' % MAP,
               'forms/html-field-form/%s/Forms/Форма/Module.bsl' % MAP)


# ------------------------------------------------------------------ отчёты
def reports():
    put('metadata/report/%s/%s.mdo' % (REP, REP), L.report_mdo(REP, 'Пример отчёта'))
    query = '\n'.join([
        'ВЫБРАТЬ РАЗРЕШЕННЫЕ',
        '\tЭлементы.Ссылка КАК Элемент,',
        '\tЭлементы.Тип КАК Тип,',
        '\tВЫБОР',
        '\t\tКОГДА Элементы.Активен',
        '\t\t\tТОГДА "активен"',
        '\t\tИНАЧЕ "выключен"',
        '\tКОНЕЦ КАК Состояние,',
        '\t1 КАК Элементов',
        'ИЗ',
        '\tСправочник.%s КАК Элементы' % CAT,
        'ГДЕ',
        '\tНЕ Элементы.ПометкаУдаления',
        '',
        'УПОРЯДОЧИТЬ ПО',
        '\tЭлементы.Наименование'])
    put('metadata/report/%s/Templates/ОсновнаяСхемаКомпоновкиДанных/Template.dcs' % REP, L.dcs_schema(
        REP, 'Элементы по состоянию',
        [('Элемент', 'Элемент'), ('Тип', 'Тип'), ('Состояние', 'Состояние'), ('Элементов', 'Элементов')],
        query, ['Элемент', 'Тип', 'Состояние'],
        filters=[('Тип', 'Перечисление.%s.ПустаяСсылка' % ENUM), ('Состояние', '')],
        total='Элементов', groups=['Состояние']))
    check_mdo('metadata/report/%s/%s.mdo' % (REP, REP))
    print('  ok  Template.dcs (%s)' % REP)

    put('reports/report-with-parameters-and-grouping/%s/%s.mdo' % (REP2, REP2),
        L.report_mdo(REP2, 'Пример отчёта по периоду'))
    query2 = '\n'.join([
        'ВЫБРАТЬ РАЗРЕШЕННЫЕ',
        '\tДокументы.Ссылка КАК Документ,',
        '\tДокументы.Дата КАК Дата,',
        '\tНАЧАЛОПЕРИОДА(Документы.Дата, ДЕНЬ) КАК День,',
        '\tДокументы.Объект КАК Объект,',
        '\tДокументы.Комментарий КАК Комментарий,',
        '\t1 КАК Документов',
        'ИЗ',
        '\tДокумент.%s КАК Документы' % DOC,
        'ГДЕ',
        '\tНЕ Документы.ПометкаУдаления',
        '\tИ Документы.Дата МЕЖДУ &НачалоПериода И &КонецПериода',
        '',
        'УПОРЯДОЧИТЬ ПО',
        '\tДокументы.Дата'])
    put('reports/report-with-parameters-and-grouping/%s/Templates/ОсновнаяСхемаКомпоновкиДанных/Template.dcs' % REP2,
        L.dcs_schema(REP2, 'Документы за период',
                     [('Документ', 'Документ'), ('Дата', 'Дата'), ('День', 'День'), ('Объект', 'Объект'),
                      ('Комментарий', 'Комментарий'), ('Документов', 'Документов')],
                     query2, ['Документ', 'Дата', 'Объект', 'Комментарий'],
                     filters=[('Объект', 'Справочник.%s.ПустаяСсылка' % CAT)],
                     total='Документов', groups=['День', 'Объект'],
                     parameters=[('НачалоПериода', 'Начало периода', 'BeginningOfThisDay'),
                                 ('КонецПериода', 'Конец периода', 'BeginningOfNextDay')]))
    check_mdo('reports/report-with-parameters-and-grouping/%s/%s.mdo' % (REP2, REP2))
    print('  ok  Template.dcs (%s)' % REP2)


def main():
    print('Сборка примеров в %s' % EX)
    metadata()
    item_form()
    list_form()
    record_form()
    document_form()
    processor()
    mobile()
    html_form()
    reports()
    print('Готово.')


if __name__ == '__main__':
    main()
