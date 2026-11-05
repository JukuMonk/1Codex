"""Shared BSL/query checks; no EDT or platform dependencies."""
import re
CRLF="\r\n"

# ============================================================ проверки: BSL
QUERY_KEYWORDS = {
    'ПО', 'И', 'ИЛИ', 'НЕ', 'ИЗ', 'ГДЕ', 'ВЫБРАТЬ', 'КАК', 'ЕСТЬ', 'В', 'МЕЖДУ', 'ПЕРВЫЕ',
    'РАЗЛИЧНЫЕ', 'УБЫВ', 'ВОЗР', 'ВЫРАЗИТЬ', 'ТОГДА', 'ИНАЧЕ', 'КОНЕЦ', 'ВЫБОР',
    'КОГДА', 'ЕСТЬNULL', 'ОБЪЕДИНИТЬ', 'ВСЕ', 'ИТОГИ', 'СГРУППИРОВАТЬ', 'УПОРЯДОЧИТЬ',
    'ИМЕЮЩИЕ', 'ЛЕВОЕ', 'ПРАВОЕ', 'ПОЛНОЕ', 'ВНУТРЕННЕЕ', 'СОЕДИНЕНИЕ', 'ПОМЕСТИТЬ',
    'УНИЧТОЖИТЬ', 'ИНДЕКСИРОВАТЬ', 'ДЛЯ', 'ИЗМЕНЕНИЯ', 'АВТОУПОРЯДОЧИВАНИЕ', 'СПЕЦСИМВОЛ',
    'ПОДОБНО', 'ИЕРАРХИИ', 'ТОЛЬКО',
}
# «Ссылка», «Дата», «Номер», «Значение» — законные имена полей (в проекте-источнике
# ресурс «Значение» и псевдоним «КАК Значение» работают в бою), их не трогаем (case 016).
# HIGH подтверждены только По/В/Из/Где/Для/Все/Как/Есть/Не/И/Или; остальные — по
# документации языка запросов (MEDIUM).

CLIENT_ONLY = ('ОткрытьФорму', 'ПоказатьВопрос', 'ПоказатьПредупреждение',
               'ПодключитьОбработчикОжидания', 'ОтключитьОбработчикОжидания', 'ОповеститьОВыборе',
               'ЗакрытьФорму', 'НачатьПомещениеФайла', 'ПоказатьВыборИзМеню',
               'ПоказатьОповещениеПользователя', 'ПоказатьВыборИзСписка')

TYPOS = {'ОбменДаннымиЗагрузка': 'ОбменДанными.Загрузка',
         'ДополнительныеСвойстваВставить': 'ДополнительныеСвойства.Вставить'}

FORM_RESERVED = ('Параметры', 'Объект', 'Элементы', 'ЭтаФорма', 'ЭтотОбъект')

# Глобальные методы платформы: функция модуля с таким именем в ТОЛСТОМ клиенте
# падает «уже определена» (case 047). Список неполный — самые ходовые имена.
GLOBAL_METHODS = {
    'Состояние', 'Сообщить', 'Формат', 'Мин', 'Макс', 'Строка', 'Число', 'Дата', 'Булево',
    'Лев', 'Прав', 'Сред', 'Найти', 'СтрДлина', 'ВРег', 'НРег', 'ТРег', 'СокрЛП', 'СокрЛ', 'СокрП',
    'Окр', 'Цел', 'ТекущаяДата', 'ПустаяСтрока', 'ЗначениеЗаполнено', 'ТипЗнч', 'Тип', 'Вопрос',
    'Предупреждение', 'СтрЗаменить', 'СтрРазделить', 'СтрСоединить', 'СтрНайти', 'Символ',
    'КодСимвола', 'Год', 'Месяц', 'День', 'Час', 'Минута', 'Секунда', 'НачалоДня', 'КонецДня',
    'НачалоМесяца', 'КонецМесяца', 'ДобавитьМесяц', 'ДеньНедели', 'ЗаписатьJSON', 'ПрочитатьJSON',
    'XMLСтрока', 'XMLЗначение', 'Base64Строка', 'Base64Значение', 'ОписаниеОшибки', 'Ожидать',
    'Сигнал', 'Оповестить', 'ОбработкаПрерыванияПользователя', 'ПолучитьСсылку', 'Шаблон',
}

# Ключевые слова BSL: так нельзя назвать процедуру, а значит и команду формы (case 057).
BSL_KEYWORDS = {
    'прервать', 'продолжить', 'возврат', 'если', 'тогда', 'иначе', 'иначеесли', 'конецесли', 'для',
    'каждого', 'из', 'по', 'пока', 'цикл', 'конеццикла', 'процедура', 'функция', 'конецпроцедуры',
    'конецфункции', 'перем', 'экспорт', 'попытка', 'исключение', 'конецпопытки', 'вызватьисключение',
    'новый', 'истина', 'ложь', 'неопределено', 'и', 'или', 'не', 'перейти', 'выполнить',
}


def _strip_strings_and_comments(text):
    out = []
    for line in text.split('\n'):
        if line.lstrip().startswith('|'):
            out.append('')
            continue
        s = re.sub(r'"[^"]*"', '""', line)
        pos = s.find('//')
        out.append(s[:pos] if pos >= 0 else s)
    return '\n'.join(out)


def _unfold_query_line(s):
    s = re.sub(r'"\s*\+.*?\+\s*"', '', s)
    s = re.sub(r'"\s*\)?;?\s*$', '', s)
    return s.replace('""', '"')


def check_bsl(text, is_form_module=True, hierarchical_catalogs=(), tabular_of=None):
    """Список претензий к модулю. Каждая — то, что 1С показывает только в
    бою, а компилятор пропускает. Номера кейсов — в скобках."""
    problems = []
    nl = CRLF if CRLF in text else '\n'
    lines = text.split(nl)
    # 1) директивы и клиентские методы в серверных процедурах (case 011, 012)
    directive, current, is_server = '', '', False
    for n, raw in enumerate(lines, 1):
        s = raw.strip()
        if s.startswith('&'):
            directive = s
            continue
        if s.startswith(('Процедура ', 'Функция ', 'Асинх Процедура ', 'Асинх Функция ')):
            current = s.split('(')[0]
            if is_form_module and directive == '':
                problems.append('строка %d: «%s» без директивы компиляции — в модуле формы '
                                'станет серверной (case 011/012)' % (n, current))
            is_server = directive.startswith('&НаСервере') or directive == ''
            directive = ''
            continue
        if s.startswith(('КонецПроцедуры', 'КонецФункции')):
            current, is_server = '', False
            continue
        if is_form_module and is_server and current and not s.startswith('//'):
            for meth in CLIENT_ONLY:
                if meth + '(' in raw:
                    problems.append('строка %d: клиентский %s() в серверной «%s» (case 011)'
                                    % (n, meth, current))
        if s.startswith('&НаКлиентеНаСервере') and 'БезКонтекста' not in s:
            problems.append('строка %d: &НаКлиентеНаСервере — серверный вызов такой процедуры '
                            'не нашёл её в бою; сделайте две процедуры (case 033, MEDIUM)' % n)
    clean = _strip_strings_and_comments(text)
    # 2) опечатки, которые платформа встречает «Поле объекта не обнаружено» (case 014, 032)
    for bad, good in TYPOS.items():
        if bad in clean:
            problems.append('«%s» — такого поля нет, нужно «%s» (case 014)' % (bad, good))
    for m in re.finditer(r'ПустаяСсылка(?![(\w])', clean):
        problems.append('строка %d: «ПустаяСсылка» без скобок — это метод: ПустаяСсылка() (case 032)'
                        % (clean.count('\n', 0, m.start()) + 1))
    # 3) занятые имена формы (case 010)
    if is_form_module:
        for m in re.finditer(r'^\s*(%s)\s*=[^=]' % '|'.join(FORM_RESERVED), clean, re.M):
            before = re.findall(r'^&(\w+)', clean[:m.start()], re.M)
            if before and 'БезКонтекста' in before[-1]:
                continue
            problems.append('строка %d: переменная «%s» — свойство формы, только для чтения (case 010)'
                            % (clean.count('\n', 0, m.start()) + 1, m.group(1)))
    # 4) тексты запросов (case 015, 016, 017)
    prev = ''
    for n, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s.startswith('|'):
            prev = ''
            continue
        if _unfold_query_line(s).count('"') % 2:
            problems.append('строка %d: одиночная кавычка в тексте запроса — «Строка, не закрывающаяся '
                            'кавычкой»; пустая строка пишется четырьмя кавычками (case 015)' % n)
        for m in re.finditer(r'\bКАК\s+([А-Яа-яЁёA-Za-z_][А-Яа-яЁёA-Za-z_0-9]*)', s):
            if m.group(1).upper() in QUERY_KEYWORDS:
                problems.append('строка %d: псевдоним «%s» — ключевое слово запроса, «Ожидается имя» '
                                '(case 016)' % (n, m.group(1)))
        body = s[1:].strip()
        if body == ';' and prev == ';':
            problems.append('строка %d: два «;» подряд — пустой запрос в пакете, «Ожидается выражение '
                            'ВЫБРАТЬ»' % n)
        if body:
            prev = body
    if hierarchical_catalogs:
        for m in re.finditer(r'Новый Запрос\((.*?)"\);', text, re.S):
            piece = m.group(1)
            for cat, alias in set(re.findall(r'Справочник\.([А-Яа-яЁёA-Za-z_0-9]+) КАК ([А-Яа-яЁёA-Za-z_0-9]+)', piece)):
                if cat in hierarchical_catalogs and ('%s.ЭтоГруппа' % alias) not in piece:
                    problems.append('строка %d: «%s» иерархический, а группы не отсеяны — у группы '
                                    'реквизиты NULL (case 017)' % (text.count('\n', 0, m.start()) + 1, cat))
    # 4b) псевдоним таблицы против табличных частей объектов запроса (case 062)
    if tabular_of is not None:
        for q in queries_in_module(text):
            for p in check_query_aliases(q, tabular_of):
                problems.append('запрос: ' + p)
    # 5) имена процедур: глобальные методы (case 047) и ключевые слова (case 057)
    for m in re.finditer(r'^\s*(?:Асинх\s+)?(?:Процедура|Функция)\s+([А-Яа-яЁёA-Za-z_][А-Яа-яЁёA-Za-z_0-9]*)', clean, re.M):
        name = m.group(1)
        n = clean.count('\n', 0, m.start()) + 1
        if name in GLOBAL_METHODS:
            problems.append('строка %d: «%s» — имя глобального метода платформы: толстый клиент '
                            'падает «уже определена» (case 047)' % (n, name))
        if name.lower() in BSL_KEYWORDS:
            problems.append('строка %d: «%s» — ключевое слово BSL, «Ожидается имя процедуры» '
                            '(case 057)' % (n, name))
    # 6) «Число + Строка»: тип результата задаёт левый операнд (case 058)
    numeric, cur = set(), ''
    ident = r'[А-Яа-яЁёA-Za-z_][А-Яа-яЁёA-Za-z_0-9]*'
    for n, raw in enumerate(lines, 1):
        s = raw.strip()
        if s.startswith(('Процедура ', 'Функция ', 'Асинх Процедура ', 'Асинх Функция ')):
            numeric, cur = set(), s.split('(')[0]
            continue
        if s.startswith('//'):
            continue
        m = re.match(r'^\s*(' + ident + r')\s*=\s*(.+?);?\s*$', raw)
        if m and (re.match(r'^-?\d+(\.\d+)?$', m.group(2))
                  or re.match(r'^(Цел|Окр|Число)\(', m.group(2))
                  or re.search(r'\.Количество\(\)\s*$', m.group(2))
                  or re.match(r'^' + re.escape(m.group(1)) + r'\s*[+\-*/]\s*\d', m.group(2))):
            numeric.add(m.group(1))
        m = re.match(r'^\s*Для\s+(' + ident + r')\s*=', raw)
        if m:
            numeric.add(m.group(1))
        for m in re.finditer(r'(?:=|\(|,|Возврат)\s*(' + ident + r'|\d+)\s*\+\s*"', raw):
            if m.group(1).isdigit() or m.group(1) in numeric:
                problems.append('строка %d: «%s + "…"» — тип задаёт левый операнд, будет '
                                '«Преобразование значения к типу Число»; оберните Строка() или '
                                'Формат(…, "ЧГ=") (case 058)' % (n, m.group(1)))
    # 7) агрегат по строке неограниченной длины (case 031) — предупреждение
    for m in re.finditer(r'\b(МАКСИМУМ|МИНИМУМ)\(([^()]*)\)', text):
        if 'ВЫРАЗИТЬ' not in m.group(2) and re.search(r'[А-Яа-я]+\.(Наименование|Название|Комментарий|Описание)', m.group(2)):
            problems.append('предупреждение: %s по строковому полю — если длина 0 (неограниченная), '
                            '«Неверные параметры»: оберните ВЫРАЗИТЬ(… КАК СТРОКА(150)) (case 031)' % m.group(1))
    # 8) НачатьПомещениеФайлов(Оповещение, Файлы, Диалог, ИдентификаторФормы) — после диалога идёт
    #    булево «Интерактивно»; компилятор молчит, в клиенте «Несоответствие типов (параметр номер '4')» (case 088)
    for n, raw in enumerate(lines, 1):
        m = re.search(r'НачатьПомещениеФайлов\(([^;]*)\)\s*;', raw)
        if not m:
            continue
        parts = [x.strip() for x in m.group(1).split(',')]
        if len(parts) == 4 and 'Диалог' in parts[2] and re.search(r'УникальныйИдентификатор|Идентификатор', parts[3]):
            problems.append('строка %d: НачатьПомещениеФайлов с диалогом — 4-й параметр «Интерактивно» (Булево), '
                            'идентификатор формы — 5-м: (Оповещение, , Диалог, Истина, УникальныйИдентификатор) '
                            '(case 088)' % n)
    return problems


# ------------------------------------------------ запросы: псевдоним и ТЧ (case 062)
QUERY_KINDS = {'Справочник': 'Catalog', 'Документ': 'Document', 'РегистрСведений': 'InformationRegister',
               'РегистрНакопления': 'AccumulationRegister', 'ПланВидовХарактеристик': 'ChartOfCharacteristicTypes'}


def tabular_sections_of_mdo(text):
    """Имена табличных частей объекта из его .mdo."""
    names = []
    # EDT пишет <producedTypes> перед <name> — без него ТЧ не находились и case 062 молчал (UP, ДиЗ-02 2026-10)
    for m in re.finditer(r'<tabularSections uuid="[^"]+">\s*(?:<producedTypes>.*?</producedTypes>\s*)?'
                         r'<name>([^<]+)</name>', text, re.S):
        names.append(m.group(1))
    return set(names)


def queries_in_module(text):
    """Тексты запросов модуля (строки «|…» подряд) как список строк."""
    queries, buf = [], []
    for line in text.split('\n'):
        s = line.strip()
        if s.startswith('|'):
            buf.append(s[1:])
            continue
        # первая строка запроса — после кавычки: Новый Запрос("ВЫБРАТЬ … (без неё терялись источники в ИЗ)
        m = re.search(r'"\s*((?:ВЫБРАТЬ|SELECT)\b.*)$', s)
        if m and not buf:
            buf.append(m.group(1))
            continue
        if buf:
            queries.append('\n'.join(buf)); buf = []
    if buf:
        queries.append('\n'.join(buf))
    return queries


def check_query_aliases(query, tabular_of):
    """Псевдоним таблицы (источника или подзапроса) совпал с именем табличной
    части объекта из того же запроса — в бою «Неоднозначное поле "X.Ссылка"»:
    платформа не отличает псевдоним от ТЧ (case 062). tabular_of(kind, name)
    возвращает множество имён ТЧ объекта или None, если объект неизвестен."""
    problems = []
    sources = {}
    for m in re.finditer(r'\b(?:ИЗ|СОЕДИНЕНИЕ)\s+([А-Яа-яЁёA-Za-z_]+)\.([А-Яа-яЁёA-Za-z_0-9]+)'
                         r'(?:\.([А-Яа-яЁёA-Za-z_0-9]+))?\s*(?:\(|\s)\s*(?:КАК\s+)?'
                         r'([А-Яа-яЁёA-Za-z_][А-Яа-яЁёA-Za-z_0-9]*)?', query, re.I):
        kind, obj, third, alias = m.groups()
        if alias:
            sources[alias] = (kind, obj, third or '')
    if not sources:
        return problems
    aliases = set(sources) | set(re.findall(
        r'\)\s*КАК\s+([А-Яа-яЁёA-Za-z_][А-Яа-яЁёA-Za-z_0-9]*)', query, re.I))
    for alias, (kind, obj, _t) in list(sources.items()):
        ts = tabular_of(QUERY_KINDS.get(kind, kind), obj)
        if not ts:
            continue
        for name in sorted(aliases & ts):
            if sources.get(name) == (kind, obj, name):
                continue          # сама таблица ТЧ под своим именем — законно
            msg = ('псевдоним таблицы «%s» совпадает с именем табличной части %s.%s — '
                   '«Неоднозначное поле "%s.Ссылка"»; переименуйте псевдоним (case 062)'
                   % (name, kind, obj, name))
            if msg not in problems:
                problems.append(msg)
    return problems


def check_form_attributes_in_no_context(module_text, attr_names):
    """Реквизит формы в процедуре &НаСервереБезКонтекста — «Переменная не
    определена» в бою: формы там нет (case 060). Параметры и локальные
    присваивания процедуры реквизитом не считаются; текст запросов и
    комментарии пропускаются."""
    problems = []
    directive, proc, params, locals_, body = '', '', set(), set(), []
    lines = module_text.split(CRLF if CRLF in module_text else '\n')

    def flush():
        if 'БезКонтекста' not in directive or not proc:
            return
        for n, s in body:
            st = s.strip()
            if st.startswith(('//', '|', '"')):
                continue
            code = re.sub(r'"[^"]*"', '""', st.split('//')[0])
            for a in attr_names:
                if a in params or a in locals_:
                    continue
                if re.search(r'(?<![\wА-Яа-яЁё.])%s(?![\wА-Яа-яЁё(])' % re.escape(a), code):
                    problems.append('строка %d: реквизит формы «%s» в процедуре без контекста «%s» — '
                                    '«Переменная не определена»; передайте параметром (case 060)'
                                    % (n, a, proc))
                    break

    for n, raw in enumerate(lines, 1):
        s = raw.strip()
        if s.startswith('&'):
            flush()
            directive, proc, params, locals_, body = s, '', set(), set(), []
            continue
        m = re.match(r'^(?:Асинх\s+)?(?:Процедура|Функция)\s+(\w+)\s*\(([^)]*)\)', s)
        if m:
            proc = m.group(1)
            params = {p.strip().split('=')[0].strip().replace('Знач ', '').strip()
                      for p in m.group(2).split(',') if p.strip()}
            continue
        if s.startswith(('КонецПроцедуры', 'КонецФункции')):
            flush()
            directive, proc, params, locals_, body = '', '', set(), set(), []
            continue
        if proc:
            mm = re.match(r'^([А-Яа-яЁёA-Za-z_][\wА-Яа-яЁё]*)\s*=[^=]', s)
            if mm:
                locals_.add(mm.group(1))
            mm = re.match(r'^Для\s+(?:Каждого\s+)?([А-Яа-яЁёA-Za-z_][\wА-Яа-яЁё]*)', s)
            if mm:
                locals_.add(mm.group(1))
            body.append((n, raw))
    flush()
    return problems


