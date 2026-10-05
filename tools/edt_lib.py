# -*- coding: utf-8 -*-
"""edt_lib — строители файлов проекта 1C:EDT и проверки к ним.

Откуда взято. Каждый шаблон снят с РАБОТАЮЩЕГО объекта проекта-источника
(см. reference/) и воспроизводит порядок тегов, который пишет сам EDT при
сохранении. Не «как обычно устроено», а «как лежит в проекте, который
обновляет базу и открывается в платформе».

Что умеет:
  * .mdo: справочник, перечисление, константа, регистр сведений, регистр
    накопления (MEDIUM), документ (MEDIUM), общий модуль, обработка, отчёт,
    подсистема, роль (+ Rights.rights), общая картинка;
  * регистрация объекта в Configuration.mdo, добавление реквизитов и ТЧ в
    существующий .mdo, добавление формы в .mdo;
  * Form.form: поля, кнопки, группы, страницы, таблицы значений (со всеми
    спутниками), динамический список, поле HTML, реквизиты формы с
    квалификаторами, команды формы, каркас формы;
  * Template.dcs: схема компоновки с одним набором-запросом, отборами,
    параметрами, группировками и детальными записями;
  * CommandInterface.cmi;
  * проверки форм, .mdo, BSL и проекта целиком (см. check_*.py).

Файлы EDT: UTF-8 БЕЗ BOM, переводы строк CRLF, отступ два пробела.
Идентификаторы в коде латиницей, чтобы библиотека работала в любой консоли;
термины 1С в строках — как в конфигурации.
"""
import io
import os
import re
import sys
import uuid
import xml.etree.ElementTree as ET

CRLF = '\r\n'
TAB = '\t'

XMLNS_MD = ('xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xmlns:core="http://g5.1c.ru/v8/dt/mcore" '
            'xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass"')
XMLNS_FORM = ('xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
              'xmlns:core="http://g5.1c.ru/v8/dt/mcore" '
              'xmlns:form="http://g5.1c.ru/v8/dt/form"')


# ============================================================ служебное
def uid():
    return str(uuid.uuid4())


def stable_uid(seed):
    """Устойчивый uuid от строки: повторная сборка не плодит НОВЫЕ объекты
    (новый объект база принимает только полным обновлением — case 020)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'edt-skill/' + seed))


def read_text(path):
    raw = io.open(path, 'rb').read()
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    return raw.decode('utf-8')


def has_bom(path):
    return io.open(path, 'rb').read(3) == b'\xef\xbb\xbf'


def write_text(path, text, xml=None):
    """Пишет файл EDT: UTF-8 без BOM, только CRLF, XML обязан разбираться."""
    if text.count('\n') != text.count(CRLF):
        raise ValueError('%s: не все переводы строк CRLF' % path)
    if xml is None:
        xml = path.endswith(('.mdo', '.form', '.dcs', '.cmi', '.rights'))
    if xml:
        ET.fromstring(text.encode('utf-8'))
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    io.open(path, 'wb').write(text.encode('utf-8'))


def join(lines):
    return CRLF.join(lines)


def esc(text):
    return (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


class Ids(object):
    """Номера элементов формы. Уникальны в пределах формы (items и
    autoCommandBar — одно пространство); реквизиты формы и КОЛОНКИ их
    таблиц — ДРУГОЕ, тоже одно на всех (case 003). Команды формы — третье."""

    def __init__(self, start=1):
        self.n = start - 1

    def __call__(self):
        self.n += 1
        return self.n


# ============================================================ .mdo: общее
def synonym(text, indent, key='ru'):
    o = ' ' * indent
    return [o + '<synonym>', o + '  <key>%s</key>' % key,
            o + '  <value>%s</value>' % esc(text), o + '</synonym>']


def type_xml(spec, indent):
    """«Строка(150)» / «Строка(0)» / «Число(15,3)» / «Булево» / «Дата» /
    «ДатаВремя» / «Справочник.X» / «Документ.X» / «Перечисление.X» /
    «ПланВидовХарактеристик.X» / «ОпределяемыйТип.X» → <type>.
    Составной тип через «|» — только ссылки, без квалификаторов.

    Строка длиннее 1024 отвергается: обновление базы падает «Ошибка SDBL:
    слишком большое значение описателя длины» (case 024); для длинного
    текста — Строка(0), неограниченная."""
    o = ' ' * indent
    if '|' in spec:
        lines = [o + '<type>']
        for part in spec.split('|'):
            lines += [l for l in type_xml(part.strip(), indent) if '<types>' in l]
        return lines + [o + '</type>']
    lines = [o + '<type>']
    m = re.match(r'^Строка\((\d+)\)$', spec)
    if m:
        n = int(m.group(1))
        if n > 1024:
            raise ValueError('Строка(%d): длиннее 1024 нельзя, ставьте Строка(0)' % n)
        lines.append(o + '  <types>String</types>')
        if n == 0:
            lines.append(o + '  <stringQualifiers/>')
        else:
            lines += [o + '  <stringQualifiers>', o + '    <length>%d</length>' % n,
                      o + '  </stringQualifiers>']
    elif re.match(r'^Число\+?\(\d+,\d+\)$', spec):
        # «Число+(15,3)» — неотрицательное (nonNegative), снято с eamСмета ФРЕГАТ EAM
        prec, scale = re.findall(r'\d+', spec)
        lines += [o + '  <types>Number</types>', o + '  <numberQualifiers>',
                  o + '    <precision>%s</precision>' % prec]
        if int(scale):
            lines.append(o + '    <scale>%s</scale>' % scale)
        if '+' in spec:
            lines.append(o + '    <nonNegative>true</nonNegative>')
        lines.append(o + '  </numberQualifiers>')
    elif spec == 'ХранилищеЗначения':
        lines.append(o + '  <types>ValueStorage</types>')
    elif spec == 'Булево':
        lines.append(o + '  <types>Boolean</types>')
    elif spec in ('Дата', 'ДатаВремя'):
        lines += [o + '  <types>Date</types>', o + '  <dateQualifiers>',
                  o + '    <dateFractions>%s</dateFractions>' % ('Date' if spec == 'Дата' else 'DateTime'),
                  o + '  </dateQualifiers>']
    else:
        prefixes = {'Справочник.': 'CatalogRef.', 'Документ.': 'DocumentRef.',
                    'Перечисление.': 'EnumRef.',
                    'ПланВидовХарактеристик.': 'ChartOfCharacteristicTypesRef.',
                    'ОпределяемыйТип.': 'DefinedType.',
                    # характеристика ПВХ (значение аналитики статьи и т.п.)
                    'Характеристика.': 'Characteristic.',
                    'БизнесПроцесс.': 'BusinessProcessRef.', 'Задача.': 'TaskRef.'}
        for ru, en in prefixes.items():
            if spec.startswith(ru):
                lines.append(o + '  <types>%s%s</types>' % (en, spec[len(ru):]))
                break
        else:
            raise ValueError('неизвестный тип «%s»' % spec)
    lines.append(o + '</type>')
    return lines


def attribute(name, syn, spec, indent, in_ts=False, required=False, tag='attributes',
              extra_before_close=(), seed=None):
    """Реквизит. У реквизита ТАБЛИЧНОЙ ЧАСТИ нет fillValue (case 025).
    Порядок: synonym → type → minValue → maxValue → [fillChecking] →
    fillValue → fullTextSearch → dataHistory — снят с живого образца."""
    o = ' ' * indent
    u = stable_uid(seed) if seed else uid()
    lines = [o + '<%s uuid="%s">' % (tag, u), o + '  <name>%s</name>' % name]
    lines += synonym(syn, indent + 2)
    lines += type_xml(spec, indent + 2)
    lines += [o + '  <minValue xsi:type="core:UndefinedValue"/>',
              o + '  <maxValue xsi:type="core:UndefinedValue"/>']
    if required:
        lines.append(o + '  <fillChecking>ShowError</fillChecking>')
    if in_ts:
        lines += [o + '  <dataHistory>Use</dataHistory>',
                  o + '  <fullTextSearch>Use</fullTextSearch>']
    else:
        lines += [o + '  <fillValue xsi:type="core:UndefinedValue"/>',
                  o + '  <fullTextSearch>Use</fullTextSearch>',
                  o + '  <dataHistory>Use</dataHistory>']
    lines += [o + '  ' + l for l in extra_before_close]
    lines.append(o + '</%s>' % tag)
    return lines


def tabular_section(name, syn, attributes, indent, seed=None):
    o = ' ' * indent
    lines = [o + '<tabularSections uuid="%s">' % (stable_uid(seed) if seed else uid())]
    # producedTypes ТЧ (objectType/rowType) — есть у каждой ТЧ живых документов
    # ФРЕГАТ EAM (eamСмета); без них EDT создаёт типы сам, но uuid «плывут»
    ps = seed or uid()
    lines += [o + '  <producedTypes>',
              o + '    <objectType typeId="%s" valueTypeId="%s"/>' % (stable_uid(ps + '/objectType'),
                                                                     stable_uid(ps + '/objectType/value')),
              o + '    <rowType typeId="%s" valueTypeId="%s"/>' % (stable_uid(ps + '/rowType'),
                                                                  stable_uid(ps + '/rowType/value')),
              o + '  </producedTypes>']
    lines.append(o + '  <name>%s</name>' % name)
    lines += synonym(syn, indent + 2)
    lines += [o + '  <standardAttributes>', o + '    <dataHistory>Use</dataHistory>',
              o + '    <name>LineNumber</name>',
              o + '    <fillValue xsi:type="core:UndefinedValue"/>',
              o + '    <fullTextSearch>Use</fullTextSearch>',
              o + '    <minValue xsi:type="core:UndefinedValue"/>',
              o + '    <maxValue xsi:type="core:UndefinedValue"/>',
              o + '  </standardAttributes>']
    for a in attributes:
        lines += attribute(a[0], a[1], a[2], indent + 2, in_ts=True,
                           seed=(seed + '/' + a[0]) if seed else None)
    lines.append(o + '</tabularSections>')
    return lines


def standard_attribute(name, indent, extra=()):
    o = ' ' * indent
    lines = [o + '<standardAttributes>', o + '  <dataHistory>Use</dataHistory>',
             o + '  <name>%s</name>' % name]
    lines += [o + '  ' + l for l in extra]
    lines += [o + '  <fillValue xsi:type="core:UndefinedValue"/>',
              o + '  <fullTextSearch>Use</fullTextSearch>',
              o + '  <minValue xsi:type="core:UndefinedValue"/>',
              o + '  <maxValue xsi:type="core:UndefinedValue"/>',
              o + '</standardAttributes>']
    return lines


def _produced(kinds, seed):
    lines = ['  <producedTypes>']
    for k in kinds:
        a = stable_uid('%s/%s' % (seed, k)) if seed else uid()
        b = stable_uid('%s/%s/value' % (seed, k)) if seed else uid()
        lines.append('    <%s typeId="%s" valueTypeId="%s"/>' % (k, a, b))
    lines.append('  </producedTypes>')
    return lines


def form_ref_block(kind, obj, form_name, syn, purposes=('PersonalComputer', 'MobileDevice'),
                   seed=None):
    lines = ['  <forms uuid="%s">' % (stable_uid(seed) if seed else uid()),
             '    <name>%s</name>' % form_name]
    lines += synonym(syn, 4)
    lines += ['    <usePurposes>%s</usePurposes>' % p for p in purposes]
    lines.append('  </forms>')
    return lines


# ============================================================ .mdo: объекты
def catalog_mdo(name, syn, attributes=(), tabular_sections=(), code_length=9,
                description_length=150, manual_code=False, hierarchical=False,
                comment=None, forms=(), default_forms=(), seed=None, owners=()):
    """Справочник. forms — [(имя, синоним)], default_forms —
    [('defaultObjectForm', 'ФормаЭлемента'), ...].
    manual_code=True: код — ключ, а не номер (autonumbering=false,
    fillChecking у Code).
    owners — имена справочников-владельцев (подчинённый справочник). Порядок
    тегов снят с живого подчинённого справочника (ItobДатчики, МВМ): owners —
    после foldersOnTop и до codeLength, codeSeries WithinOwnerSubordination —
    после codeAllowedLength (UP, 2026-10)."""
    s = seed or 'Catalog/' + name
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<mdclass:Catalog %s uuid="%s">' % (XMLNS_MD, stable_uid(s))]
    lines += _produced(['objectType', 'refType', 'selectionType', 'listType', 'managerType'], s)
    lines.append('  <name>%s</name>' % name)
    lines += synonym(syn, 2)
    if comment:
        lines.append('  <comment>%s</comment>' % esc(comment))
    lines += ['  <useStandardCommands>true</useStandardCommands>',
              '  <inputByString>Catalog.%s.StandardAttribute.Description</inputByString>' % name,
              '  <inputByString>Catalog.%s.StandardAttribute.Code</inputByString>' % name,
              '  <fullTextSearchOnInputByString>DontUse</fullTextSearchOnInputByString>']
    for std in ('PredefinedDataName', 'Predefined', 'Ref', 'DeletionMark', 'IsFolder'):
        lines += standard_attribute(std, 2)
    lines += standard_attribute('Owner', 2, ['<fillFromFillingValue>true</fillFromFillingValue>'])
    lines += standard_attribute('Parent', 2, ['<fillFromFillingValue>true</fillFromFillingValue>'])
    lines += standard_attribute('Description', 2, ['<fillChecking>ShowError</fillChecking>'])
    lines += standard_attribute('Code', 2, ['<fillChecking>ShowError</fillChecking>'] if manual_code else ())
    lines += ['  <createOnInput>Use</createOnInput>',
              '  <dataLockControlMode>Managed</dataLockControlMode>',
              '  <fullTextSearch>Use</fullTextSearch>']
    if hierarchical:
        # порядок снят с типового иерархического справочника
        lines += ['  <hierarchical>true</hierarchical>', '  <levelCount>2</levelCount>',
                  '  <foldersOnTop>true</foldersOnTop>']
    lines += ['  <owners>Catalog.%s</owners>' % o for o in owners]
    lines += ['  <codeLength>%d</codeLength>' % code_length,
              '  <descriptionLength>%d</descriptionLength>' % description_length,
              '  <codeType>String</codeType>',
              '  <codeAllowedLength>Variable</codeAllowedLength>']
    if owners:
        lines.append('  <codeSeries>WithinOwnerSubordination</codeSeries>')
    lines += ['  <checkUnique>true</checkUnique>',
              '  <autonumbering>%s</autonumbering>' % ('false' if manual_code else 'true'),
              '  <defaultPresentation>AsDescription</defaultPresentation>',
              '  <editType>InDialog</editType>',
              '  <choiceMode>BothWays</choiceMode>']
    for prop, fname in default_forms:
        lines.append('  <%s>Catalog.%s.Form.%s</%s>' % (prop, name, fname, prop))
    for a in attributes:
        lines += attribute(a[0], a[1], a[2], 2, required=(len(a) > 3 and a[3] == 'обязательный'),
                           seed=s + '/attr/' + a[0])
    for ts in tabular_sections:
        lines += tabular_section(ts['name'], ts['synonym'], ts['attributes'], 2,
                                 seed=s + '/ts/' + ts['name'])
    for fname, fsyn in forms:
        lines += form_ref_block('Catalog', name, fname, fsyn, seed=s + '/form/' + fname)
    lines += ['</mdclass:Catalog>', '']
    return join(lines)


def enum_mdo(name, syn, values, comment=None, seed=None):
    s = seed or 'Enum/' + name
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<mdclass:Enum %s uuid="%s">' % (XMLNS_MD, stable_uid(s))]
    lines += _produced(['refType', 'listType', 'managerType'], s)
    lines.append('  <name>%s</name>' % name)
    lines += synonym(syn, 2)
    if comment:
        lines.append('  <comment>%s</comment>' % esc(comment))
    lines += standard_attribute('Order', 2)
    lines += standard_attribute('Ref', 2)
    lines += ['  <quickChoice>true</quickChoice>', '  <choiceMode>BothWays</choiceMode>']
    for vname, vsyn in values:
        lines.append('  <enumValues uuid="%s">' % stable_uid(s + '/value/' + vname))
        lines.append('    <name>%s</name>' % vname)
        lines += synonym(vsyn, 4)
        lines.append('  </enumValues>')
    lines += ['</mdclass:Enum>', '']
    return join(lines)


def constant_mdo(name, syn, spec='Булево', explanation=None, comment=None, seed=None):
    """Константа. Порядок тегов снят с рабочей константы проекта: type →
    explanation → minValue → maxValue → dataLockControlMode."""
    s = seed or 'Constant/' + name
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<mdclass:Constant %s uuid="%s">' % (XMLNS_MD, stable_uid(s))]
    lines += _produced(['managerType', 'valueManagerType', 'valueKeyType'], s)
    lines.append('  <name>%s</name>' % name)
    lines += synonym(syn, 2)
    if comment:
        lines.append('  <comment>%s</comment>' % esc(comment))
    lines += type_xml(spec, 2)
    if explanation:
        lines += ['  <explanation>', '    <key>ru</key>',
                  '    <value>%s</value>' % esc(explanation), '  </explanation>']
    lines += ['  <minValue xsi:type="core:UndefinedValue"/>',
              '  <maxValue xsi:type="core:UndefinedValue"/>',
              '  <dataLockControlMode>Managed</dataLockControlMode>',
              '</mdclass:Constant>', '']
    return join(lines)


def information_register_mdo(name, syn, dimensions, resources, comment=None,
                             forms=(), default_forms=(), seed=None, periodicity=None,
                             recorder=False, attributes=()):
    """Регистр сведений. По умолчанию — независимый непериодический (тегов нет).
    periodicity: 'Second' | 'Day' | 'Month' | … — периодический (порядок тегов
    editType → informationRegisterPeriodicity → mainFilterOnPeriod снят с
    eamСтоимостьТМЦ ФРЕГАТ EAM); recorder=True — подчинение регистратору
    (writeMode RecorderSubordinate, как eamГрафикТОиР). attributes — реквизиты
    регистра (идут после ресурсов). Имена ресурсов НЕ должны быть
    ключевыми словами запроса («С», «По» — case 016)."""
    s = seed or 'InformationRegister/' + name
    for n, _, _ in list(dimensions) + list(resources) + list(attributes):
        if n.upper() in QUERY_KEYWORDS:
            raise ValueError('имя «%s» — ключевое слово языка запросов (case 016)' % n)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<mdclass:InformationRegister %s uuid="%s">' % (XMLNS_MD, stable_uid(s))]
    lines += _produced(['selectionType', 'listType', 'managerType', 'recordSetType',
                        'recordKeyType', 'recordType', 'recordManagerType'], s)
    lines.append('  <name>%s</name>' % name)
    lines += synonym(syn, 2)
    if comment:
        lines.append('  <comment>%s</comment>' % esc(comment))
    lines += ['  <useStandardCommands>true</useStandardCommands>',
              '  <editType>InDialog</editType>']
    if periodicity:
        lines.append('  <informationRegisterPeriodicity>%s</informationRegisterPeriodicity>' % periodicity)
    if recorder:
        lines.append('  <writeMode>RecorderSubordinate</writeMode>')
    if periodicity and not recorder:
        # у регистра, подчинённого регистратору, mainFilterOnPeriod недопустим (EDT: «Регистр должен
        # быть независимый и периодический»)
        lines.append('  <mainFilterOnPeriod>true</mainFilterOnPeriod>')
    # ссылки на формы у РЕГИСТРА стоят ДО dataLockControlMode (у справочника —
    # после choiceMode): порядок задан схемой, сверено с типовыми (case 039)
    for prop, fname in default_forms:
        lines.append('  <%s>InformationRegister.%s.Form.%s</%s>' % (prop, name, fname, prop))
    lines.append('  <dataLockControlMode>Managed</dataLockControlMode>')
    for dn, dsyn, dspec in dimensions:
        lines += attribute(dn, dsyn, dspec, 2, tag='dimensions',
                           extra_before_close=['<mainFilter>true</mainFilter>'],
                           seed=s + '/dim/' + dn)
    for rn, rsyn, rspec in resources:
        lines += attribute(rn, rsyn, rspec, 2, tag='resources', seed=s + '/res/' + rn)
    for an, asyn, aspec in attributes:
        lines += attribute(an, asyn, aspec, 2, tag='attributes', seed=s + '/attr/' + an)
    for fname, fsyn in forms:
        lines += form_ref_block('InformationRegister', name, fname, fsyn, seed=s + '/form/' + fname)
    lines += ['</mdclass:InformationRegister>', '']
    return join(lines)


def accumulation_register_mdo(name, syn, dimensions, resources, comment=None, seed=None,
                              turnovers=False, attributes=()):
    """Регистр накопления остатков. MEDIUM: структура снята с типового объекта
    (у нас своих регистров накопления не было). У измерений и ресурсов
    регистра НЕТ fillValue/dataHistory — только minValue/maxValue/
    fullTextSearch, у измерений плюс useInTotals; ресурсы идут ДО измерений.
    turnovers=True — оборотный регистр (registerType Turnovers);
    attributes — реквизиты регистра (после ресурсов, до измерений)."""
    s = seed or 'AccumulationRegister/' + name
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<mdclass:AccumulationRegister %s uuid="%s">' % (XMLNS_MD, stable_uid(s))]
    lines += _produced(['selectionType', 'listType', 'managerType', 'recordSetType',
                        'recordKeyType', 'recordType'], s)
    lines.append('  <name>%s</name>' % name)
    lines += synonym(syn, 2)
    if comment:
        lines.append('  <comment>%s</comment>' % esc(comment))
    lines.append('  <useStandardCommands>true</useStandardCommands>')
    for std in ('RecordType', 'Active', 'LineNumber', 'Recorder'):
        lines += standard_attribute(std, 2)
    lines += standard_attribute('Period', 2, ['<fillChecking>ShowError</fillChecking>'])
    if turnovers:
        lines.append('  <registerType>Turnovers</registerType>')
    lines += ['  <dataLockControlMode>Managed</dataLockControlMode>',
              '  <enableTotalsSplitting>true</enableTotalsSplitting>']

    def reg_attr(tag, n, sy, sp, extra):
        o = '  '
        ls = [o + '<%s uuid="%s">' % (tag, stable_uid(s + '/' + tag + '/' + n)),
              o + '  <name>%s</name>' % n]
        ls += synonym(sy, 4)
        ls += type_xml(sp, 4)
        ls += [o + '  <minValue xsi:type="core:UndefinedValue"/>',
               o + '  <maxValue xsi:type="core:UndefinedValue"/>',
               o + '  <fullTextSearch>Use</fullTextSearch>']
        ls += [o + '  ' + e for e in extra]
        ls.append(o + '</%s>' % tag)
        return ls
    for rn, rsyn, rspec in resources:
        lines += reg_attr('resources', rn, rsyn, rspec, [])
    for an, asyn, aspec in attributes:
        lines += reg_attr('attributes', an, asyn, aspec, [])
    for dn, dsyn, dspec in dimensions:
        lines += reg_attr('dimensions', dn, dsyn, dspec, ['<useInTotals>true</useInTotals>'])
    lines += ['</mdclass:AccumulationRegister>', '']
    return join(lines)


def document_mdo(name, syn, attributes=(), tabular_sections=(), number_length=11,
                 forms=(), default_forms=(), register_records=(), posting=True,
                 comment=None, seed=None, based_on=(), periodicity=None):
    """Документ. MEDIUM: порядок тегов снят с типового документа (своих
    документов в проекте-источнике не заводили — рейсы и заявки типовые).
    based_on — ['Document.X', …] (ввод на основании); periodicity —
    None (сквозной номер) | 'Year' | 'Quarter' | 'Month' | 'Day'.
    Доработка ЗАГОТОВКИ, уже лежащей в проекте: результат пропустить через
    preserve_uuids(новый, старый) — uuid объекта не меняются (case 020)."""
    s = seed or 'Document/' + name
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<mdclass:Document %s uuid="%s">' % (XMLNS_MD, stable_uid(s))]
    lines += _produced(['objectType', 'refType', 'selectionType', 'listType', 'managerType'], s)
    lines.append('  <name>%s</name>' % name)
    lines += synonym(syn, 2)
    if comment:
        lines.append('  <comment>%s</comment>' % esc(comment))
    lines += ['  <useStandardCommands>true</useStandardCommands>',
              '  <inputByString>Document.%s.StandardAttribute.Number</inputByString>' % name,
              '  <fullTextSearchOnInputByString>DontUse</fullTextSearchOnInputByString>']
    for std in ('Posted', 'Ref', 'DeletionMark'):
        lines += standard_attribute(std, 2)
    lines += standard_attribute('Date', 2, ['<fillChecking>ShowError</fillChecking>'])
    lines += standard_attribute('Number', 2)
    for b in based_on:
        lines.append('  <basedOn>%s</basedOn>' % b)
    lines += ['  <createOnInput>Use</createOnInput>',
              '  <dataLockControlMode>Managed</dataLockControlMode>',
              '  <fullTextSearch>Use</fullTextSearch>',
              '  <numberType>String</numberType>',
              '  <numberLength>%d</numberLength>' % number_length,
              '  <numberAllowedLength>Variable</numberAllowedLength>']
    if periodicity:
        lines.append('  <numberPeriodicity>%s</numberPeriodicity>' % periodicity)
    lines += ['  <checkUnique>true</checkUnique>',
              '  <autonumbering>true</autonumbering>']
    for prop, fname in default_forms:
        lines.append('  <%s>Document.%s.Form.%s</%s>' % (prop, name, fname, prop))
    if posting:
        lines += ['  <realTimePosting>Deny</realTimePosting>',
                  '  <registerRecordsWritingOnPost>WriteModified</registerRecordsWritingOnPost>']
        for r in register_records:
            lines.append('  <registerRecords>%s</registerRecords>' % r)
        lines += ['  <postInPrivilegedMode>true</postInPrivilegedMode>',
                  '  <unpostInPrivilegedMode>true</unpostInPrivilegedMode>']
    else:
        lines.append('  <posting>Deny</posting>')
    for a in attributes:
        lines += attribute(a[0], a[1], a[2], 2, required=(len(a) > 3 and a[3] == 'обязательный'),
                           seed=s + '/attr/' + a[0])
    for ts in tabular_sections:
        lines += tabular_section(ts['name'], ts['synonym'], ts['attributes'], 2,
                                 seed=s + '/ts/' + ts['name'])
    for fname, fsyn in forms:
        lines += form_ref_block('Document', name, fname, fsyn, seed=s + '/form/' + fname)
    lines += ['</mdclass:Document>', '']
    return join(lines)


def common_module_mdo(name, syn, server=True, server_call=False, client_managed=False,
                      global_=False, privileged=False, seed=None):
    """Общий модуль. Свойства исполнения — теги в порядке модели EDT:
    server, clientManagedApplication (если нужен клиент), serverCall.
    Серверный модуль БЕЗ serverCall из клиента не вызвать; с serverCall —
    можно (так работают наши серверные помощники форм)."""
    s = seed or 'CommonModule/' + name
    ns = 'xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass"'
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<mdclass:CommonModule %s uuid="%s">' % (ns, stable_uid(s)),
             '  <name>%s</name>' % name]
    lines += synonym(syn, 2)
    # Флаги по стандарту 1С (проверка EDT common-module-type), сверено с модулями БСП ФРЕГАТ EAM:
    #   серверный (…Сервер)        — server + externalConnection + clientOrdinaryApplication;
    #   вызов сервера (…ВызовСервера) — server + serverCall;
    #   клиентский (…Клиент)       — clientManagedApplication + clientOrdinaryApplication;
    #   клиент-серверный           — clientManagedApplication + server + externalConnection + clientOrdinaryApplication;
    #   глобальный клиентский      — global + clientManagedApplication + clientOrdinaryApplication.
    if global_:
        lines.append('  <global>true</global>')
    if client_managed:
        lines.append('  <clientManagedApplication>true</clientManagedApplication>')
    if server:
        lines.append('  <server>true</server>')
    if server and not server_call:
        lines.append('  <externalConnection>true</externalConnection>')
    if not server_call:
        lines.append('  <clientOrdinaryApplication>true</clientOrdinaryApplication>')
    if server_call:
        lines.append('  <serverCall>true</serverCall>')
    if privileged:
        lines.append('  <privileged>true</privileged>')
    lines += ['</mdclass:CommonModule>', '']
    return join(lines)


def data_processor_mdo(name, syn, forms, default_form=None, templates=(), comment=None, seed=None):
    """Обработка. forms — [(имя, синоним, [назначения])], templates —
    [(имя, синоним, 'TextDocument'|'BinaryData'|'DataCompositionSchema')]."""
    s = seed or 'DataProcessor/' + name
    ns = 'xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass"'
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<mdclass:DataProcessor %s uuid="%s">' % (ns, stable_uid(s))]
    lines += _produced(['objectType', 'managerType'], s)
    lines.append('  <name>%s</name>' % name)
    lines += synonym(syn, 2)
    if comment:
        lines.append('  <comment>%s</comment>' % esc(comment))
    lines.append('  <useStandardCommands>true</useStandardCommands>')
    if default_form:
        lines.append('  <defaultForm>DataProcessor.%s.Form.%s</defaultForm>' % (name, default_form))
    for f in forms:
        purposes = f[2] if len(f) > 2 else ('PersonalComputer',)
        lines += form_ref_block('DataProcessor', name, f[0], f[1], purposes, seed=s + '/form/' + f[0])
    for tname, tsyn, ttype in templates:
        lines += ['  <templates uuid="%s">' % stable_uid(s + '/template/' + tname),
                  '    <name>%s</name>' % tname]
        lines += synonym(tsyn, 4)
        lines += ['    <templateType>%s</templateType>' % ttype, '  </templates>']
    lines += ['</mdclass:DataProcessor>', '']
    return join(lines)


def report_mdo(name, syn, template='ОсновнаяСхемаКомпоновкиДанных', seed=None,
               variants_storage='SettingsStorage.ХранилищеВариантовОтчетов',
               forms_common=('CommonForm.ФормаОтчета', 'CommonForm.ФормаНастроекОтчета',
                             'CommonForm.ФормаВариантаОтчета')):
    """Отчёт на СКД: формы — общие формы БСП (в конфигурации без БСП
    убрать defaultForm/defaultSettingsForm/defaultVariantForm/variantsStorage)."""
    s = seed or 'Report/' + name
    ns = 'xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass"'
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<mdclass:Report %s uuid="%s">' % (ns, stable_uid(s))]
    lines += _produced(['objectType', 'managerType'], s)
    lines.append('  <name>%s</name>' % name)
    lines += synonym(syn, 2)
    lines.append('  <useStandardCommands>true</useStandardCommands>')
    if forms_common:
        lines.append('  <defaultForm>%s</defaultForm>' % forms_common[0])
    lines.append('  <mainDataCompositionSchema>Report.%s.Template.%s</mainDataCompositionSchema>'
                 % (name, template))
    if forms_common:
        lines += ['  <defaultSettingsForm>%s</defaultSettingsForm>' % forms_common[1],
                  '  <defaultVariantForm>%s</defaultVariantForm>' % forms_common[2]]
    if variants_storage:
        lines.append('  <variantsStorage>%s</variantsStorage>' % variants_storage)
    lines += ['  <templates uuid="%s">' % stable_uid(s + '/template/' + template),
              '    <name>%s</name>' % template]
    lines += synonym('Основная схема компоновки данных', 4)
    lines += ['    <templateType>DataCompositionSchema</templateType>', '  </templates>',
              '</mdclass:Report>', '']
    return join(lines)


def subsystem_mdo(name, syn, content, children=(), parent=None, picture=None,
                  explanation=None, in_interface=True, seed=None):
    """Подсистема. Дочерняя обязана нести <parentSubsystem> (case 019) —
    вложенность папок связью НЕ является. children — имена дочерних."""
    s = seed or 'Subsystem/' + name
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<mdclass:Subsystem %s uuid="%s">' % (XMLNS_MD, stable_uid(s)),
             '  <name>%s</name>' % name]
    lines += synonym(syn, 2)
    lines.append('  <includeInCommandInterface>%s</includeInCommandInterface>'
                 % ('true' if in_interface else 'false'))
    if explanation:
        lines += ['  <explanation>', '    <key>ru</key>',
                  '    <value>%s</value>' % esc(explanation), '  </explanation>']
    if picture:
        lines += ['  <picture xsi:type="core:PictureRef">',
                  '    <picture>CommonPicture.%s</picture>' % picture, '  </picture>']
    for c in content:
        lines.append('  <content>%s</content>' % c)
    for ch in children:
        lines.append('  <subsystems>%s</subsystems>' % ch)
    if parent:
        lines.append('  <parentSubsystem>Subsystem.%s</parentSubsystem>' % parent)
    lines += ['</mdclass:Subsystem>', '']
    return join(lines)


OPEN_COMMAND = {'Catalog': 'StandardCommand.OpenList', 'Document': 'StandardCommand.OpenList',
                'InformationRegister': 'StandardCommand.OpenList',
                'AccumulationRegister': 'StandardCommand.OpenList',
                'ChartOfCharacteristicTypes': 'StandardCommand.OpenList',
                'DataProcessor': 'StandardCommand.Open', 'Report': 'StandardCommand.Open',
                'Constant': 'StandardCommand.Open'}


def commands_of(content):
    """Команды навигации по составу подсистемы; перечисления и модули в
    панель не попадают."""
    out = []
    for obj in content:
        kind = obj.split('.', 1)[0]
        if kind in OPEN_COMMAND:
            out.append('%s.%s' % (obj, OPEN_COMMAND[kind]))
    return out


def command_interface_cmi(important=(), ordinary=(), subsystems=(), parent=None):
    """CommandInterface.cmi подсистемы. subsystems — имена дочерних; их полное
    имя — Subsystem.Родитель.Subsystem.Дочерняя."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<cmi:CommandInterface xmlns:cmi="http://g5.1c.ru/v8/dt/cmi">']
    if important or ordinary:
        lines.append('  <commandsOrder>')
        for group, cmds in (('NavigationPanelImportant', important),
                            ('NavigationPanelOrdinary', ordinary)):
            if not cmds:
                continue
            lines += ['    <orderFragments>', '      <group>%s</group>' % group]
            lines += ['      <commands>%s</commands>' % c for c in cmds]
            lines.append('    </orderFragments>')
        lines.append('  </commandsOrder>')
    if subsystems:
        lines.append('  <subsystemsOrder>')
        for ch in subsystems:
            lines.append('    <subsystems>Subsystem.%s.Subsystem.%s</subsystems>' % (parent, ch))
        lines.append('  </subsystemsOrder>')
    lines += ['</cmi:CommandInterface>', '']
    return join(lines)


def common_picture_mdo(name, syn, seed=None):
    ns = 'xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass"'
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<mdclass:CommonPicture %s uuid="%s">' % (ns, stable_uid(seed or 'CommonPicture/' + name)),
             '  <name>%s</name>' % name]
    lines += synonym(syn, 2)
    lines += ['</mdclass:CommonPicture>', '']
    return join(lines)


PICTURE_SCALES = [('85.png', 14, 'bldpi'), ('100.png', 16, 'ldpi'), ('125.png', 20, 'aldpi'),
                  ('150.png', 24, 'mdpi'), ('175.png', 28, 'amdpi'), ('200.png', 32, 'hdpi'),
                  ('300.png', 48, 'xdpi'), ('400.png', 64, 'udpi')]


def picture_manifest():
    """manifest.xml внутри Picture.zip общей картинки: восемь масштабов плюс
    Picture.png для интерфейса 8.2. Формат снят с типового раздела."""
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<Picture>']
    for fname, size, density in PICTURE_SCALES:
        lines.append('\t<PictureVariant name="%s" screenDensity="%s" glyphWidth="%d" glyphHeight="%d"/>'
                     % (fname, density, size, size))
    lines.append('\t<PictureVariant name="Picture.png" interfaceVariant="version8_2" '
                 'screenDensity="ldpi" glyphWidth="16" glyphHeight="16"/>')
    lines.append('</Picture>')
    # манифест внутри zip — единственный файл С BOM: так лежит у типовой
    return '\ufeff' + CRLF.join(lines) + CRLF


def object_tabular_table(ids, name, ts_path, columns, indent, editable=True, buttons=(),
                         handlers=(), max_width=True):
    """Таблица ТАБЛИЧНОЙ ЧАСТИ объекта (Объект.ИмяТЧ) на форме элемента /
    документа: первая колонка — номер строки (LabelField), остальные —
    поля ввода. Собрана по образцу вставки вкладки с ТЧ в типовую форму.
    columns — имена реквизитов ТЧ ИЛИ кортежи (суффикс, путь, вид, заголовок,
    только_чтение[, [(событие, обработчик)]]) — для колонок-«спутников» вида
    Объект.ТЧ.Номенклатура.Код. buttons — [(имяКнопки, команда)] в командной
    панели таблицы; handlers — [(событие, обработчик)] таблицы (стоят после
    autoCommandBar, до спутников — как в eamСмета ФРЕГАТ EAM)."""
    o = ' ' * indent
    lines = [o + '<items xsi:type="form:Table">', o + '  <name>%s</name>' % name,
             o + '  <id>%d</id>' % ids(), o + '  <visible>true</visible>',
             o + '  <enabled>true</enabled>', o + '  <userVisible>',
             o + '    <common>true</common>', o + '  </userVisible>',
             o + '  <dataPath xsi:type="form:DataPath">', o + '    <segments>%s</segments>' % ts_path,
             o + '  </dataPath>', o + '  <titleLocation>None</titleLocation>']
    lines += field(ids, name + 'НомерСтроки', ts_path + '.LineNumber', indent + 2, 'LabelField')
    for c in columns:
        if isinstance(c, dict):
            # {'name', 'width', 'title', 'ro', 'kind', 'handlers'} — колонка со своей шириной (UP, 2026-10);
            # handlers — [(событие, обработчик)] колонки: OnChange, StartChoice…
            lines += field(ids, name + c['name'], '%s.%s' % (ts_path, c['name']), indent + 2,
                           c.get('kind', 'InputField'), c.get('title'), c.get('ro', False),
                           width=c.get('width'), max_width=bool(c.get('width')), handlers=c.get('handlers', ()))
        elif isinstance(c, (tuple, list)):
            suf, path, kind, ctitle, ro = c[:5]
            ch = c[5] if len(c) > 5 else ()
            lines += field(ids, name + suf, path, indent + 2, kind, ctitle, ro, handlers=ch)
        else:
            lines += field(ids, name + c, '%s.%s' % (ts_path, c), indent + 2)
    lines += [o + '  <autoCommandBar>', o + '    <name>%sКоманднаяПанель</name>' % name,
              o + '    <id>%d</id>' % ids()]
    for bname, cmd in buttons:
        lines += bar_button(ids, bname, indent + 4, command=cmd)
    lines += [o + '    <horizontalAlign>Left</horizontalAlign>',
              o + '    <autoFill>true</autoFill>', o + '  </autoCommandBar>']
    for event, proc in handlers:
        lines += [o + '  <handlers>', o + '    <event>%s</event>' % event,
                  o + '    <name>%s</name>' % proc, o + '  </handlers>']
    lines += table_companions(ids, name, indent + 2)
    lines += tooltip(name, ids(), indent + 2)
    lines += context_menu(name, ids(), indent + 2)
    ed = 'true' if editable else 'false'
    lines += [o + '  <changeRowSet>%s</changeRowSet>' % ed, o + '  <changeRowOrder>%s</changeRowOrder>' % ed,
              ] + ([o + '  <autoMaxWidth>true</autoMaxWidth>'] if max_width else []) + [
              o + '  <autoMaxHeight>true</autoMaxHeight>',
              o + '  <autoMaxRowsCount>true</autoMaxRowsCount>',
              o + '  <selectionMode>MultiRow</selectionMode>', o + '  <header>true</header>',
              o + '  <headerHeight>1</headerHeight>', o + '  <footerHeight>1</footerHeight>',
              o + '  <horizontalScrollBar>AutoUse</horizontalScrollBar>',
              o + '  <verticalScrollBar>AutoUse</verticalScrollBar>',
              o + '  <autoInsertNewRow>%s</autoInsertNewRow>' % ed,
              o + '  <searchOnInput>Auto</searchOnInput>', o + '  <initialListView>Auto</initialListView>',
              o + '  <horizontalStretch>true</horizontalStretch>',
              o + '  <verticalStretch>true</verticalStretch>',
              o + '  <enableStartDrag>true</enableStartDrag>', o + '  <enableDrag>true</enableDrag>',
              o + '  <rowFilter xsi:type="core:UndefinedValue"/>', o + '</items>']
    return lines


def role_mdo(name, syn, seed=None):
    ns = 'xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass"'
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<mdclass:Role %s uuid="%s">' % (ns, stable_uid(seed or 'Role/' + name)),
             '  <name>%s</name>' % name]
    lines += synonym(syn, 2)
    lines += ['</mdclass:Role>', '']
    return join(lines)


def rights_file(configuration_name, startup_rights, object_rights):
    """Rights.rights: права конфигурации (ThinClient, MobileClient…) и права
    объектов [(FQN, [права])]. Отступы — ТАБЫ, как у типовых ролей."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<Rights xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
             'xmlns="http://v8.1c.ru/8.2/roles" xsi:type="Rights">',
             '\t<setForNewObjects>false</setForNewObjects>',
             '\t<setForAttributesByDefault>true</setForAttributesByDefault>',
             '\t<independentRightsOfChildObjects>false</independentRightsOfChildObjects>',
             '\t<object>', '\t\t<name>Configuration.%s</name>' % configuration_name]
    for r in startup_rights:
        lines += ['\t\t<right>', '\t\t\t<name>%s</name>' % r, '\t\t\t<value>true</value>', '\t\t</right>']
    lines.append('\t</object>')
    for obj, rs in object_rights:
        lines += ['\t<object>', '\t\t<name>%s</name>' % obj]
        for r in rs:
            lines += ['\t\t<right>', '\t\t\t<name>%s</name>' % r, '\t\t\t<value>true</value>', '\t\t</right>']
        lines.append('\t</object>')
    lines += ['</Rights>', '']
    return join(lines)


# ============================================================ Configuration.mdo
CONFIG_GROUPS = {
    'Subsystem': 'subsystems', 'CommonModule': 'commonModules', 'CommonPicture': 'commonPictures',
    'Role': 'roles', 'Constant': 'constants', 'Catalog': 'catalogs', 'Document': 'documents',
    'Enum': 'enums', 'Report': 'reports', 'DataProcessor': 'dataProcessors',
    'InformationRegister': 'informationRegisters', 'AccumulationRegister': 'accumulationRegisters',
    'ChartOfCharacteristicTypes': 'chartsOfCharacteristicTypes', 'CommonForm': 'commonForms',
    'CommonCommand': 'commonCommands', 'DefinedType': 'definedTypes',
    'ScheduledJob': 'scheduledJobs', 'EventSubscription': 'eventSubscriptions',
    'DocumentJournal': 'documentJournals', 'Style': 'styles',
}

FOLDERS = {
    'Subsystem': 'Subsystems', 'CommonModule': 'CommonModules', 'CommonPicture': 'CommonPictures',
    'Role': 'Roles', 'Constant': 'Constants', 'Catalog': 'Catalogs', 'Document': 'Documents',
    'Enum': 'Enums', 'Report': 'Reports', 'DataProcessor': 'DataProcessors',
    'InformationRegister': 'InformationRegisters', 'AccumulationRegister': 'AccumulationRegisters',
    'ChartOfCharacteristicTypes': 'ChartsOfCharacteristicTypes', 'CommonForm': 'CommonForms',
    'CommonCommand': 'CommonCommands', 'DefinedType': 'DefinedTypes',
    'ScheduledJob': 'ScheduledJobs', 'EventSubscription': 'EventSubscriptions',
    'DocumentJournal': 'DocumentJournals', 'Style': 'Styles',
}

# порядок групп в Configuration.mdo, как их пишет EDT (снят с ФРЕГАТ EAM, 2026.1)
CONFIG_ORDER = ['subsystems', 'styleItems', 'styles', 'commonPictures', 'sessionParameters', 'roles',
                'commonTemplates', 'filterCriteria', 'commonModules', 'commonAttributes',
                'exchangePlans', 'xDTOPackages', 'webServices', 'eventSubscriptions',
                'scheduledJobs', 'settingsStorages', 'functionalOptions',
                'functionalOptionsParameters', 'definedTypes', 'commonCommands', 'commandGroups',
                'constants', 'commonForms', 'catalogs', 'documents', 'documentJournals', 'enums',
                'reports', 'dataProcessors', 'informationRegisters', 'accumulationRegisters',
                'chartsOfCharacteristicTypes', 'businessProcesses', 'tasks']


def register_in_configuration(config_text, kind, name):
    """Строка <catalogs>Catalog.Имя</catalogs> в Configuration.mdo: без неё
    объект лежит на диске, а конфигурация его не видит (case 021). Встаёт
    последней в своей группе. Возвращает (текст, добавили?)."""
    tag = CONFIG_GROUPS[kind]
    line = '  <%s>%s.%s</%s>' % (tag, kind, name, tag)
    if line + CRLF in config_text:
        return config_text, False
    last = config_text.rfind('  <%s>' % tag)
    if last < 0:
        # группы ещё нет (первый регистр накопления и т.п.) — встаём после
        # последней строки ближайшей ПРЕДШЕСТВУЮЩЕЙ группы (CONFIG_ORDER)
        for prev in reversed(CONFIG_ORDER[:CONFIG_ORDER.index(tag)]):
            last = config_text.rfind('  <%s>' % prev)
            if last >= 0:
                break
        if last < 0:
            raise ValueError('в Configuration.mdo нет группы <%s> и предшествующих' % tag)
    end = config_text.index(CRLF, last) + len(CRLF)
    return config_text[:end] + line + CRLF + config_text[end:], True


def enable_mobile_purpose(config_text):
    """<usePurposes>MobileDevice</usePurposes> у корня: без него мобильная
    форма не открывается нигде (case 005)."""
    line = '  <usePurposes>MobileDevice</usePurposes>'
    if line + CRLF in config_text:
        return config_text, False
    anchor = '  <usePurposes>PersonalComputer</usePurposes>' + CRLF
    if anchor not in config_text:
        raise ValueError('в Configuration.mdo нет назначения PersonalComputer')
    pos = config_text.index(anchor) + len(anchor)
    return config_text[:pos] + line + CRLF + config_text[pos:], True


# ============================================================ правка .mdo
CLOSE_ATTR = CRLF + '  </attributes>' + CRLF
CLOSE_TS = CRLF + '  </tabularSections>' + CRLF


def add_attributes_to_mdo(text, attributes, in_ts=None, tabular_sections=()):
    """Идемпотентно добавляет реквизиты (и ТЧ) в существующий .mdo.
    Якорь привязан к переводу строки и отступу «  »: голое «</attributes>»
    совпало бы и с четырёхпробельным закрытием внутри ТЧ, и новые реквизиты
    уехали бы в чужую таблицу (ловили)."""
    added = []
    # устойчивые uuid (ФРЕГАТ EAM): объект + имя — повторная доработка после перегенерации объекта
    # другим скриптом даёт тот же uuid, база не видит «новый» реквизит (case 020)
    mo = re.search(r'<name>([^<]+)</name>', text)
    obj = mo.group(1) if mo else ''
    # проверка «уже есть» — только среди реквизитов ВЕРХНЕГО уровня (отступ 2): одноимённая колонка ТЧ
    # не должна мешать добавить реквизит шапки (ФРЕГАТ EAM: eamМерыОтветственности.Должность)
    top = set(re.findall(r'\r?\n  <attributes uuid="[^"]+">\r?\n    <name>([^<]+)</name>', text))
    top_ts = set(re.findall(r'\r?\n  <tabularSections uuid="[^"]+">\s*(?:<producedTypes>.*?</producedTypes>\s*)?<name>([^<]+)</name>',
                            text, re.S))
    new = [a for a in attributes if a[0] not in top and a[0] not in top_ts]
    if new:
        block = []
        for a in new:
            block += attribute(a[0], a[1], a[2], 2, required=(len(a) > 3 and a[3] == 'обязательный'),
                               seed='addattr/%s/%s' % (obj, a[0]))
            added.append('реквизит ' + a[0])
        text = _insert_after_last(text, CLOSE_ATTR, block, 'реквизиты')
    new_ts = [t for t in tabular_sections if t['name'] not in top_ts and t['name'] not in top]
    if new_ts:
        block = []
        for t in new_ts:
            block += tabular_section(t['name'], t['synonym'], t['attributes'], 2,
                                     seed='addts/%s/%s' % (obj, t['name']))
            added.append('ТЧ ' + t['name'])
        anchor = CLOSE_TS if CLOSE_TS in text else CLOSE_ATTR
        text = _insert_after_last(text, anchor, block, 'табличные части')
    return text, added


def _insert_after_last(text, anchor, block, what):
    pos = text.rfind(anchor)
    if pos < 0:
        # у объекта ещё нет ни реквизитов, ни ТЧ (ФРЕГАТ EAM: eamДолжности): реквизиты и ТЧ
        # встают перед первым <forms>/<commands>/<templates>, иначе — перед закрывающим тегом
        m = re.search(r'\r\n  <(forms|commands|templates) ', text) or re.search(r'\r\n</mdclass:', text)
        if not m:
            raise ValueError('не найдено место для вставки (%s)' % what)
        pos = m.start() + len(CRLF)
        return text[:pos] + join(block) + CRLF + text[pos:]
    pos += len(anchor)
    return text[:pos] + join(block) + CRLF + text[pos:]


FORM_PROP_PREDECESSORS = {
    'Catalog': ['choiceMode', 'editType', 'quickChoice', 'useStandardCommands', 'hierarchical'],
    'InformationRegister': ['editType', 'useStandardCommands',
                            'informationRegisterPeriodicity', 'writeMode'],
    'Document': ['autonumbering', 'checkUnique', 'numberLength', 'useStandardCommands'],
}
FORM_PROP_ORDER = ['defaultObjectForm', 'defaultRecordForm', 'defaultListForm', 'defaultChoiceForm']


def add_form_to_mdo(text, kind, obj, form_name, syn, prop, purposes=('PersonalComputer', 'MobileDevice')):
    """Ссылка на форму по умолчанию + блок <forms>. Место ссылки задано
    схемой: у регистра ссылки стоят ПОСЛЕ editType и ДО dataLockControlMode,
    у справочника — после choiceMode (case 039). Идемпотентно."""
    ref = '  <%s>%s.%s.Form.%s</%s>' % (prop, kind, obj, form_name, prop)
    if ref in text:
        return text, False
    lines = text.split(CRLF)
    place = None
    for i, l in enumerate(lines):
        tag = l.strip().split('>')[0].lstrip('<').split(' ')[0]
        if tag in FORM_PROP_PREDECESSORS[kind]:
            place = i + 1
        if tag in FORM_PROP_ORDER:
            if FORM_PROP_ORDER.index(tag) < FORM_PROP_ORDER.index(prop):
                place = i + 1
            else:
                break
    if place is None:
        raise ValueError('не найдено место для ссылки на форму')
    lines.insert(place, ref)
    # устойчивый uuid: генератор, пересобирающий .mdo целиком и добавляющий форму этим вызовом, иначе
    # даёт форме новый uuid при каждом запуске — база видит «новую» форму (case 020; UP, 2026-10)
    block = ['  <forms uuid="%s">' % stable_uid('addform/%s/%s/%s' % (kind, obj, form_name)),
             '    <name>%s</name>' % form_name]
    block += synonym(syn, 4)
    block += ['    <usePurposes>%s</usePurposes>' % p for p in purposes]
    block.append('  </forms>')
    end = [i for i, l in enumerate(lines) if l.startswith('</mdclass:')][0]
    lines[end:end] = block
    return CRLF.join(lines), True


# ============================================================ Form.form
def tooltip(name, ident, indent):
    o = ' ' * indent
    return [o + '<extendedTooltip>', o + '  <name>%sРасширеннаяПодсказка</name>' % name,
            o + '  <id>%d</id>' % ident, o + '  <type>Label</type>',
            o + '  <autoMaxWidth>true</autoMaxWidth>', o + '  <autoMaxHeight>true</autoMaxHeight>',
            o + '  <extInfo xsi:type="form:LabelDecorationExtInfo">',
            o + '    <horizontalAlign>Left</horizontalAlign>', o + '  </extInfo>',
            o + '</extendedTooltip>']


def context_menu(name, ident, indent, buttons=()):
    o = ' ' * indent
    lines = [o + '<contextMenu>', o + '  <name>%sКонтекстноеМеню</name>' % name,
             o + '  <id>%d</id>' % ident]
    lines += buttons
    lines += [o + '  <autoFill>true</autoFill>', o + '</contextMenu>']
    return lines


def title_xml(text, indent):
    o = ' ' * indent
    return [o + '<title>', o + '  <key>ru</key>', o + '  <value>%s</value>' % esc(text), o + '</title>']


def field(ids, name, data_path, indent, kind='InputField', title=None, read_only=False,
          width=None, max_width=False, handlers=(), fmt=None, clear_button=False,
          default_item=False, title_location=None, multiline=False, input_hint=None, height=None,
          stretch=None):
    """Поле формы. Порядок тегов — как пишет EDT: title за id, handlers за
    dataPath, значения по умолчанию не пишутся (case 027).
    kind: InputField | CheckBoxField | LabelField.
    width без max_width — поле вне колонок тянется до края формы; типовая
    у узких полей пишет width ВМЕСТЕ с autoMaxWidth=true (case 008).
    height — высота многострочного поля в строках (по умолчанию 3; UP, 2026-10).
    stretch (только InputField): True — без autoMaxWidth и с horizontalStretch (наименование, тексты
    тянутся на всю форму); False — horizontalStretch=false (узкое поле с width не расползается в
    горизонтальной группе); None — как раньше. Проверено в тонком клиенте 8.5.1 (UP, 2026-10)."""
    o = ' ' * indent
    lines = [o + '<items xsi:type="form:FormField">', o + '  <name>%s</name>' % name,
             o + '  <id>%d</id>' % ids()]
    if title:
        lines += title_xml(title, indent + 2)
    lines += [o + '  <visible>true</visible>', o + '  <enabled>true</enabled>',
              o + '  <userVisible>', o + '    <common>true</common>', o + '  </userVisible>',
              o + '  <dataPath xsi:type="form:DataPath">',
              o + '    <segments>%s</segments>' % data_path, o + '  </dataPath>']
    if default_item:
        lines.append(o + '  <defaultItem>true</defaultItem>')
    for event, proc in handlers:
        lines += [o + '  <handlers>', o + '    <event>%s</event>' % event,
                  o + '    <name>%s</name>' % proc, o + '  </handlers>']
    if title_location:
        lines.append(o + '  <titleLocation>%s</titleLocation>' % title_location)
    lines += tooltip(name, ids(), indent + 2)
    lines += context_menu(name, ids(), indent + 2)
    lines.append(o + '  <type>%s</type>' % kind)
    if read_only:
        lines.append(o + '  <readOnly>true</readOnly>')
    lines += [o + '  <editMode>%s</editMode>' % ('Enter' if kind == 'LabelField' else 'EnterOnInput'),
              o + '  <showInHeader>true</showInHeader>',
              o + '  <headerHorizontalAlign>Left</headerHorizontalAlign>',
              o + '  <showInFooter>true</showInFooter>']
    if kind == 'InputField':
        lines.append(o + '  <extInfo xsi:type="form:InputFieldExtInfo">')
        if width:
            lines.append(o + '    <width>%d</width>' % width)
            if max_width and stretch is not True:
                lines.append(o + '    <autoMaxWidth>true</autoMaxWidth>')
        elif stretch is not True:
            lines.append(o + '    <autoMaxWidth>true</autoMaxWidth>')
        if multiline:
            lines += [o + '    <height>%d</height>' % (height or 3), o + '    <autoMaxHeight>true</autoMaxHeight>',
                      o + '    <horizontalStretch>true</horizontalStretch>',
                      o + '    <verticalStretch>false</verticalStretch>',
                      o + '    <wrap>true</wrap>', o + '    <multiLine>true</multiLine>',
                      o + '    <extendedEdit>true</extendedEdit>']
        else:
            lines.append(o + '    <autoMaxHeight>true</autoMaxHeight>')
            if stretch is not None:
                lines.append(o + '    <horizontalStretch>%s</horizontalStretch>' % ('true' if stretch else 'false'))
            lines.append(o + '    <wrap>true</wrap>')
        if clear_button:
            lines.append(o + '    <clearButton>true</clearButton>')
        lines += [o + '    <chooseType>true</chooseType>',
                  o + '    <typeDomainEnabled>true</typeDomainEnabled>',
                  o + '    <textEdit>true</textEdit>']
        if fmt:
            lines += [o + '    <format>', o + '      <key>ru</key>',
                      o + '      <value>%s</value>' % esc(fmt), o + '    </format>']
        if input_hint:
            lines += [o + '    <inputHint>', o + '      <key>ru</key>',
                      o + '      <value>%s</value>' % esc(input_hint), o + '    </inputHint>']
        lines.append(o + '  </extInfo>')
    elif kind == 'LabelField':
        lines += [o + '  <extInfo xsi:type="form:LabelFieldExtInfo">']
        if width:
            lines.append(o + '    <width>%d</width>' % width)
        lines += [o + '    <autoMaxWidth>true</autoMaxWidth>',
                  o + '    <autoMaxHeight>true</autoMaxHeight>', o + '  </extInfo>']
    else:
        lines += [o + '  <extInfo xsi:type="form:CheckBoxFieldExtInfo">',
                  o + '    <autoMaxWidth>true</autoMaxWidth>',
                  o + '    <autoMaxHeight>true</autoMaxHeight>', o + '  </extInfo>']
    lines.append(o + '</items>')
    return lines


def html_field(ids, name, data_path, indent, on_complete=None, width=70, height=10):
    """Поле HTML. width и height обязательны даже при растяжении — без них
    viewport документа нулевой высоты (case 022)."""
    o = ' ' * indent
    lines = [o + '<items xsi:type="form:FormField">', o + '  <name>%s</name>' % name,
             o + '  <id>%d</id>' % ids(), o + '  <visible>true</visible>',
             o + '  <enabled>true</enabled>', o + '  <userVisible>',
             o + '    <common>true</common>', o + '  </userVisible>',
             o + '  <dataPath xsi:type="form:DataPath">',
             o + '    <segments>%s</segments>' % data_path, o + '  </dataPath>',
             o + '  <titleLocation>None</titleLocation>']
    lines += tooltip(name, ids(), indent + 2)
    lines += context_menu(name, ids(), indent + 2)
    lines += [o + '  <type>HTMLDocumentField</type>', o + '  <editMode>Enter</editMode>',
              o + '  <showInHeader>true</showInHeader>',
              o + '  <headerHorizontalAlign>Left</headerHorizontalAlign>',
              o + '  <showInFooter>true</showInFooter>',
              o + '  <extInfo xsi:type="form:HtmlFieldExtInfo">']
    if on_complete:
        lines += [o + '    <handlers>', o + '      <event>DocumentComplete</event>',
                  o + '      <name>%s</name>' % on_complete, o + '    </handlers>']
    lines += [o + '    <width>%d</width>' % width, o + '    <autoMaxWidth>true</autoMaxWidth>',
              o + '    <height>%d</height>' % height, o + '    <autoMaxHeight>true</autoMaxHeight>',
              o + '    <horizontalStretch>true</horizontalStretch>',
              o + '    <verticalStretch>true</verticalStretch>',
              o + '  </extInfo>', o + '</items>']
    return lines


def spreadsheet_field(ids, name, data_path, indent, width=100, height=25, edit=False):
    """Поле табличного документа (печатная форма в форме). Теги — как в живой форме EDT
    (КонсольЗапросов.РезультатЗапроса, UP 2026-10); реквизит формы — form_attribute(kind=
    'SpreadsheetDocument', ext=['<extInfo xsi:type="form:SpreadsheetDocumentExtInfo"/>'])."""
    o = ' ' * indent
    lines = [o + '<items xsi:type="form:FormField">', o + '  <name>%s</name>' % name,
             o + '  <id>%d</id>' % ids(), o + '  <visible>true</visible>',
             o + '  <enabled>true</enabled>', o + '  <userVisible>',
             o + '    <common>true</common>', o + '  </userVisible>',
             o + '  <dataPath xsi:type="form:DataPath">',
             o + '    <segments>%s</segments>' % data_path, o + '  </dataPath>',
             o + '  <titleLocation>None</titleLocation>']
    lines += tooltip(name, ids(), indent + 2)
    lines += context_menu(name, ids(), indent + 2)
    lines += [o + '  <type>SpreadsheetDocumentField</type>', o + '  <editMode>Enter</editMode>',
              o + '  <showInHeader>true</showInHeader>',
              o + '  <headerHorizontalAlign>Left</headerHorizontalAlign>',
              o + '  <showInFooter>true</showInFooter>',
              o + '  <extInfo xsi:type="form:SpreadSheetDocFieldExtInfo">',
              o + '    <width>%d</width>' % width, o + '    <autoMaxWidth>true</autoMaxWidth>',
              o + '    <height>%d</height>' % height, o + '    <autoMaxHeight>true</autoMaxHeight>',
              o + '    <horizontalStretch>true</horizontalStretch>',
              o + '    <verticalStretch>true</verticalStretch>',
              o + '    <pointerType>Special</pointerType>',
              o + '    <verticalScrollBar>ScrollAlways</verticalScrollBar>',
              o + '    <horizontalScrollBar>ScrollAlways</horizontalScrollBar>',
              o + '    <selectionShowMode>Always</selectionShowMode>',
              o + '    <drawingSelectionShowMode>Auto</drawingSelectionShowMode>']
    if edit:
        lines.append(o + '    <edit>true</edit>')
    lines += [o + '    <showGroups>true</showGroups>',
              o + '    <enableStartDrag>true</enableStartDrag>',
              o + '    <enableDrag>true</enableDrag>',
              o + '  </extInfo>', o + '</items>']
    return lines


def decoration(ids, name, text, indent, bold=False):
    """Надпись. Текст ей отдаёт модуль через Элементы.X.Заголовок."""
    o = ' ' * indent
    lines = [o + '<items xsi:type="form:Decoration">', o + '  <name>%s</name>' % name,
             o + '  <id>%d</id>' % ids()]
    lines += title_xml(text, indent + 2)
    lines += [o + '  <visible>true</visible>', o + '  <enabled>true</enabled>',
              o + '  <userVisible>', o + '    <common>true</common>', o + '  </userVisible>']
    lines += tooltip(name, ids(), indent + 2)
    lines += context_menu(name, ids(), indent + 2)
    lines += [o + '  <type>Label</type>', o + '  <autoMaxHeight>true</autoMaxHeight>',
              o + '  <skipOnInput>false</skipOnInput>']
    if bold:
        lines += [o + '  <font xsi:type="core:FontRef">', o + '    <font>Style.NormalTextFont</font>',
                  o + '    <height>14.0</height>', o + '    <bold>true</bold>',
                  o + '    <italic>false</italic>', o + '    <underline>false</underline>',
                  o + '    <strikeout>false</strikeout>', o + '  </font>']
    lines += [o + '  <extInfo xsi:type="form:LabelDecorationExtInfo">',
              o + '    <horizontalAlign>Left</horizontalAlign>', o + '  </extInfo>', o + '</items>']
    return lines


def bar_button(ids, name, indent, default=False, command=None):
    """Кнопка в командной панели (без <type>): так пишет EDT для панели.
    command — имя команды формы, если отличается от имени кнопки, либо полный
    путь стандартной/общей команды ('Form.StandardCommand.X', 'CommonCommand.X')."""
    o = ' ' * indent
    cmd = command or name
    if not cmd.startswith(('Form.', 'CommonCommand.')):
        cmd = 'Form.Command.' + cmd
    lines = [o + '<items xsi:type="form:Button">', o + '  <name>%s</name>' % name,
             o + '  <id>%d</id>' % ids(), o + '  <visible>true</visible>',
             o + '  <enabled>true</enabled>', o + '  <userVisible>',
             o + '    <common>true</common>', o + '  </userVisible>']
    lines += tooltip(name, ids(), indent + 2)
    lines += [o + '  <commandName>%s</commandName>' % cmd,
              o + '  <representation>Auto</representation>']
    if default:
        lines.append(o + '  <defaultButton>true</defaultButton>')
    lines += [o + '  <autoMaxWidth>true</autoMaxWidth>', o + '  <autoMaxHeight>true</autoMaxHeight>',
              o + '  <placementArea>UserCmds</placementArea>',
              o + '  <representationInContextMenu>Auto</representationInContextMenu>',
              o + '</items>']
    return lines


def _color(tag, indent, rgb):
    o = ' ' * indent
    return [o + '<%s xsi:type="core:ColorDef">' % tag, o + '  <red>%d</red>' % rgb[0],
            o + '  <green>%d</green>' % rgb[1], o + '  <blue>%d</blue>' % rgb[2], o + '</%s>' % tag]


def page_button(ids, name, indent, default=False, style='обычная'):
    """Кнопка на странице (UsualButton) во всю ширину. style: обычная |
    главная (синяя, белый жирный текст) | осторожно (красная рамка)."""
    o = ' ' * indent
    lines = [o + '<items xsi:type="form:Button">', o + '  <name>%s</name>' % name,
             o + '  <id>%d</id>' % ids(), o + '  <visible>true</visible>',
             o + '  <enabled>true</enabled>', o + '  <userVisible>',
             o + '    <common>true</common>', o + '  </userVisible>',
             o + '  <skipOnInput>false</skipOnInput>']
    lines += tooltip(name, ids(), indent + 2)
    lines += [o + '  <type>UsualButton</type>',
              o + '  <commandName>Form.Command.%s</commandName>' % name,
              o + '  <representation>Auto</representation>']
    if default:
        lines.append(o + '  <defaultButton>true</defaultButton>')
    lines += [o + '  <autoMaxWidth>true</autoMaxWidth>', o + '  <autoMaxHeight>true</autoMaxHeight>',
              o + '  <horizontalStretch>true</horizontalStretch>',
              o + '  <placementArea>UserCmds</placementArea>']
    blue, red, white = (30, 99, 214), (211, 47, 47), (255, 255, 255)
    if style == 'главная':
        lines += _color('textColor', indent + 2, white) + _color('backColor', indent + 2, blue) \
            + _color('borderColor', indent + 2, blue)
    elif style == 'осторожно':
        lines += _color('textColor', indent + 2, red) + _color('borderColor', indent + 2, red)
    if style in ('главная', 'осторожно'):
        lines += [o + '  <font xsi:type="core:FontRef">', o + '    <font>Style.NormalTextFont</font>',
                  o + '    <height>12.0</height>', o + '    <bold>true</bold>',
                  o + '    <italic>false</italic>', o + '    <underline>false</underline>',
                  o + '    <strikeout>false</strikeout>', o + '  </font>']
    lines += [o + '  <representationInContextMenu>Auto</representationInContextMenu>', o + '</items>']
    return lines


def command_bar(ids, name, buttons, indent):
    """Командная панель формы с кнопками (bar_button)."""
    o = ' ' * indent
    lines = [o + '<items xsi:type="form:FormGroup">', o + '  <name>%s</name>' % name,
             o + '  <id>%d</id>' % ids()]
    lines += buttons
    lines += [o + '  <visible>true</visible>', o + '  <enabled>true</enabled>',
              o + '  <userVisible>', o + '    <common>true</common>', o + '  </userVisible>']
    lines += tooltip(name, ids(), indent + 2)
    lines += [o + '  <type>CommandBar</type>', o + '  <extInfo xsi:type="form:CommandBarExtInfo">',
              o + '    <horizontalAlign>Left</horizontalAlign>', o + '  </extInfo>', o + '</items>']
    return lines


def usual_group(ids, name, title, content, indent, direction=None, show_title=True,
                representation=None, vertical_stretch=None, horizontal_stretch=None):
    """Обычная группа. direction: None (умолчание Horizontal — тег не
    пишется), 'Vertical', 'AlwaysHorizontal'. Четыре свойства showLeftMargin/
    united/throughAlign/currentRowUse типовая пишет у КАЖДОЙ группы; без них
    платформа получает «сквозное выравнивание: Использовать» и строка
    расползается по колонкам (case 007). Свойства растяжения идут ПОСЛЕ
    title и ДО extendedTooltip (case 009)."""
    o = ' ' * indent
    lines = [o + '<items xsi:type="form:FormGroup">', o + '  <name>%s</name>' % name,
             o + '  <id>%d</id>' % ids()]
    lines += content
    lines += [o + '  <visible>true</visible>', o + '  <enabled>true</enabled>',
              o + '  <userVisible>', o + '    <common>true</common>', o + '  </userVisible>']
    if title:
        lines += title_xml(title, indent + 2)
    if horizontal_stretch is not None:
        lines.append(o + '  <horizontalStretch>%s</horizontalStretch>' % str(horizontal_stretch).lower())
    if vertical_stretch is not None:
        lines.append(o + '  <verticalStretch>%s</verticalStretch>' % str(vertical_stretch).lower())
    lines += tooltip(name, ids(), indent + 2)
    lines += [o + '  <type>UsualGroup</type>', o + '  <extInfo xsi:type="form:UsualGroupExtInfo">']
    if direction:
        lines.append(o + '    <group>%s</group>' % direction)
    if representation:
        lines.append(o + '    <representation>%s</representation>' % representation)
    lines += [o + '    <showLeftMargin>true</showLeftMargin>', o + '    <united>true</united>']
    if title and show_title:
        lines.append(o + '    <showTitle>true</showTitle>')
    lines += [o + '    <throughAlign>Auto</throughAlign>', o + '    <currentRowUse>Auto</currentRowUse>',
              o + '  </extInfo>', o + '</items>']
    return lines


def page(ids, name, title, content, indent, title_data_path=None):
    o = ' ' * indent
    lines = [o + '<items xsi:type="form:FormGroup">', o + '  <name>%s</name>' % name,
             o + '  <id>%d</id>' % ids()]
    lines += content
    lines += [o + '  <visible>true</visible>', o + '  <enabled>true</enabled>',
              o + '  <userVisible>', o + '    <common>true</common>', o + '  </userVisible>']
    lines += title_xml(title, indent + 2)
    lines += tooltip(name, ids(), indent + 2)
    lines += [o + '  <type>Page</type>', o + '  <extInfo xsi:type="form:PageGroupExtInfo">',
              o + '    <group>Vertical</group>', o + '    <showTitle>true</showTitle>']
    if title_data_path:
        lines += [o + '    <titleDataPath xsi:type="form:DataPath">',
                  o + '      <segments>%s</segments>' % title_data_path, o + '    </titleDataPath>']
    lines += [o + '  </extInfo>', o + '</items>']
    return lines


def pages(ids, name, page_list, indent, representation='TabsOnTop', on_change=None):
    """Группа страниц. page_list — [(имя, заголовок, содержимое)].
    representation: TabsOnTop (закладки; работает и на телефоне) или Swipe
    (листание пальцем, закладок нет; на компьютере без закладок между
    страницами не перейти — case 030)."""
    o = ' ' * indent
    lines = [o + '<items xsi:type="form:FormGroup">', o + '  <name>%s</name>' % name,
             o + '  <id>%d</id>' % ids()]
    for pname, ptitle, pcontent in page_list:
        lines += page(ids, pname, ptitle, pcontent, indent + 2)
    lines += [o + '  <visible>true</visible>', o + '  <enabled>true</enabled>',
              o + '  <userVisible>', o + '    <common>true</common>', o + '  </userVisible>']
    lines += tooltip(name, ids(), indent + 2)
    lines += [o + '  <type>Pages</type>', o + '  <extInfo xsi:type="form:PagesGroupExtInfo">']
    if on_change:
        lines += [o + '    <handlers>', o + '      <event>OnCurrentPageChange</event>',
                  o + '      <name>%s</name>' % on_change, o + '    </handlers>']
    lines += [o + '    <pagesRepresentation>%s</pagesRepresentation>' % representation,
              o + '    <currentRowUse>Auto</currentRowUse>', o + '  </extInfo>', o + '</items>']
    return lines


def _companion(ids, tag, table, suffix, kind, indent):
    """Спутники таблицы: строка поиска, состояние просмотра, управление
    поиском. Без них редактор EDT таблицу не рисует (case 004)."""
    o = ' ' * indent
    name = table + suffix
    lines = [o + '<%s>' % tag, o + '  <name>%s</name>' % name, o + '  <id>%d</id>' % ids()]
    lines += tooltip(name, ids(), indent + 2)
    lines += context_menu(name, ids(), indent + 2)
    if tag != 'searchStringAddition':
        lines.append(o + '  <type>%s</type>' % kind)
    lines += [o + '  <source>%s</source>' % table, o + '  <extInfo xsi:type="form:%sExtInfo">' % kind,
              o + '    <autoMaxWidth>true</autoMaxWidth>', o + '  </extInfo>', o + '</%s>' % tag]
    return lines


def table_companions(ids, table, indent):
    lines = _companion(ids, 'searchStringAddition', table, 'СтрокаПоиска', 'SearchStringAddition', indent)
    lines += _companion(ids, 'viewStatusAddition', table, 'СостояниеПросмотра', 'ViewStatusAddition', indent)
    lines += _companion(ids, 'searchControlAddition', table, 'УправлениеПоиском', 'SearchControlAddition', indent)
    return lines


def value_table(ids, name, columns, indent, selection='MultiRow', editable=False,
                on_activate_row=None, on_selection=None, mobile=False, context_commands=(),
                hide_search=False):
    """Таблица на реквизите «ТаблицаЗначений». columns — [(имя, подпись, вид,
    только_чтение)], вид: InputField/CheckBoxField. Собрана по образцу
    того, что делает сам EDT: спутники + полный набор свойств (case 004).
    mobile=True — commandBarLocation None (телефон рисует «More actions»
    на своём языке) и без строк поиска над таблицей."""
    o = ' ' * indent
    lines = [o + '<items xsi:type="form:Table">', o + '  <name>%s</name>' % name,
             o + '  <id>%d</id>' % ids(), o + '  <visible>true</visible>',
             o + '  <enabled>true</enabled>', o + '  <userVisible>',
             o + '    <common>true</common>', o + '  </userVisible>',
             o + '  <dataPath xsi:type="form:DataPath">', o + '    <segments>%s</segments>' % name,
             o + '  </dataPath>', o + '  <titleLocation>None</titleLocation>']
    for cname, ctitle, ckind, cro in columns:
        lines += field(ids, name + cname, '%s.%s' % (name, cname), indent + 2, ckind, ctitle, cro)
    if mobile:
        lines.append(o + '  <commandBarLocation>None</commandBarLocation>')
    lines += [o + '  <autoCommandBar>', o + '    <name>%sКоманднаяПанель</name>' % name,
              o + '    <id>%d</id>' % ids(), o + '    <horizontalAlign>Left</horizontalAlign>',
              o + '    <autoFill>true</autoFill>', o + '  </autoCommandBar>']
    if on_activate_row:
        lines += [o + '  <handlers>', o + '    <event>OnActivateRow</event>',
                  o + '    <name>%s</name>' % on_activate_row, o + '  </handlers>']
    if on_selection:
        lines += [o + '  <handlers>', o + '    <event>Selection</event>',
                  o + '    <name>%s</name>' % on_selection, o + '  </handlers>']
    lines += table_companions(ids, name, indent + 2)
    lines += tooltip(name, ids(), indent + 2)
    menu_buttons = []
    for cmd in context_commands:
        menu_buttons += bar_button(ids, cmd, indent + 4)
    lines += context_menu(name, ids(), indent + 2, menu_buttons)
    ed = 'true' if editable else 'false'
    lines += [o + '  <changeRowSet>%s</changeRowSet>' % ed, o + '  <changeRowOrder>%s</changeRowOrder>' % ed,
              o + '  <autoMaxWidth>true</autoMaxWidth>', o + '  <autoMaxHeight>true</autoMaxHeight>',
              o + '  <autoMaxRowsCount>true</autoMaxRowsCount>',
              o + '  <selectionMode>%s</selectionMode>' % selection,
              o + '  <header>true</header>', o + '  <headerHeight>1</headerHeight>',
              o + '  <footerHeight>1</footerHeight>',
              o + '  <horizontalScrollBar>AutoUse</horizontalScrollBar>',
              o + '  <verticalScrollBar>AutoUse</verticalScrollBar>',
              o + '  <horizontalLines>true</horizontalLines>', o + '  <verticalLines>true</verticalLines>',
              o + '  <autoInsertNewRow>%s</autoInsertNewRow>' % ed,
              o + '  <searchOnInput>Auto</searchOnInput>', o + '  <initialListView>Auto</initialListView>',
              o + '  <horizontalStretch>true</horizontalStretch>',
              o + '  <verticalStretch>true</verticalStretch>',
              o + '  <enableStartDrag>false</enableStartDrag>', o + '  <enableDrag>false</enableDrag>']
    if mobile or hide_search:
        lines += [o + '  <searchStringLocation>None</searchStringLocation>',
                  o + '  <viewStatusLocation>None</viewStatusLocation>',
                  o + '  <searchControlLocation>None</searchControlLocation>']
    lines += [o + '  <rowFilter xsi:type="core:UndefinedValue"/>', o + '</items>']
    return lines


def dynamic_list_table(ids, name, columns, indent, hierarchical=False,
                       settings_group='СписокКомпоновщикНастроекПользовательскиеНастройки'):
    """Таблица динамического списка (форма списка). columns — [(имя, путь,
    ширина)], первая подходящая («Наименование» и т.п.) — defaultItem.
    Динамическому списку нужна группа пользовательских настроек (см.
    list_form_settings_group) — её имя в userSettingsGroup."""
    o = ' ' * indent
    lines = [o + '<items xsi:type="form:Table">', o + '  <name>%s</name>' % name,
             o + '  <id>%d</id>' % ids(), o + '  <visible>true</visible>',
             o + '  <enabled>true</enabled>', o + '  <userVisible>',
             o + '    <common>true</common>', o + '  </userVisible>',
             o + '  <dataPath xsi:type="form:DataPath">', o + '    <segments>%s</segments>' % name,
             o + '  </dataPath>', o + '  <defaultItem>true</defaultItem>',
             o + '  <titleLocation>None</titleLocation>']
    main = 0
    for i, (cname, _p, _w) in enumerate(columns):
        if cname in ('Наименование', 'Description'):
            main = i
            break
    for i, (cname, cpath, cwidth) in enumerate(columns):
        lines += field(ids, cname, cpath, indent + 2, 'LabelField', width=cwidth,
                       default_item=(i == main))
    lines += [o + '  <commandBarLocation>None</commandBarLocation>',
              o + '  <autoCommandBar>', o + '    <name>%sКоманднаяПанель</name>' % name,
              o + '    <id>%d</id>' % ids(), o + '    <horizontalAlign>Left</horizontalAlign>',
              o + '  </autoCommandBar>']
    lines += table_companions(ids, name, indent + 2)
    lines += tooltip(name, ids(), indent + 2)
    lines += context_menu(name, ids(), indent + 2)
    if hierarchical:
        lines.append(o + '  <representation>HierarchicalList</representation>')
    lines += [o + '  <changeRowSet>true</changeRowSet>', o + '  <changeRowOrder>true</changeRowOrder>',
              o + '  <autoMaxWidth>true</autoMaxWidth>', o + '  <autoMaxHeight>true</autoMaxHeight>',
              o + '  <autoMaxRowsCount>true</autoMaxRowsCount>',
              o + '  <selectionMode>MultiRow</selectionMode>', o + '  <header>true</header>',
              o + '  <headerHeight>1</headerHeight>', o + '  <footerHeight>1</footerHeight>',
              o + '  <horizontalScrollBar>AutoUse</horizontalScrollBar>',
              o + '  <verticalScrollBar>AutoUse</verticalScrollBar>',
              o + '  <searchOnInput>Auto</searchOnInput>', o + '  <initialListView>Auto</initialListView>',
              o + '  <initialTreeView>ExpandTopLevel</initialTreeView>',
              o + '  <horizontalStretch>true</horizontalStretch>',
              o + '  <verticalStretch>true</verticalStretch>',
              o + '  <enableStartDrag>true</enableStartDrag>', o + '  <enableDrag>true</enableDrag>',
              o + '  <extInfo xsi:type="form:DynamicListTableExtInfo">',
              o + '    <autoRefreshPeriod>60</autoRefreshPeriod>', o + '    <period>',
              o + '      <startDate>0001-01-01T00:00:00</startDate>',
              o + '      <endDate>0001-01-01T00:00:00</endDate>', o + '    </period>',
              o + '    <topLevelParent xsi:type="core:UndefinedValue"/>',
              o + '    <showRoot>true</showRoot>',
              o + '    <allowGettingCurrentRowURL>true</allowGettingCurrentRowURL>',
              o + '    <userSettingsGroup>%s</userSettingsGroup>' % settings_group,
              o + '  </extInfo>', o + '</items>']
    return lines


def list_form_settings_group(ids, indent, name='СписокКомпоновщикНастроекПользовательскиеНастройки'):
    """Группа пользовательских настроек — её требует динамический список."""
    o = ' ' * indent
    lines = [o + '<items xsi:type="form:FormGroup">', o + '  <name>%s</name>' % name,
             o + '  <id>%d</id>' % ids(), o + '  <visible>true</visible>',
             o + '  <enabled>true</enabled>', o + '  <userVisible>',
             o + '    <common>true</common>', o + '  </userVisible>']
    lines += title_xml('Группа пользовательских настроек', indent + 2)
    lines.append(o + '  <verticalStretch>false</verticalStretch>')
    lines += tooltip(name, ids(), indent + 2)
    lines += [o + '  <type>UsualGroup</type>', o + '  <extInfo xsi:type="form:UsualGroupExtInfo">',
              o + '    <group>Vertical</group>', o + '    <representation>WeakSeparation</representation>',
              o + '    <showLeftMargin>true</showLeftMargin>', o + '    <united>true</united>',
              o + '    <throughAlign>Auto</throughAlign>', o + '    <currentRowUse>Auto</currentRowUse>',
              o + '  </extInfo>', o + '</items>']
    return lines


def _qualifiers(kind, indent):
    """Квалификаторы у реквизита формы. Число БЕЗ numberQualifiers ломает
    форму целиком — пустой лист в EDT (case 001). kind может быть
    'Number(15,3)' (разрядность и точность) и 'String(100)' (ФРЕГАТ EAM)."""
    o = ' ' * indent
    m = re.match(r'^Number\((\d+),(\d+)\)$', kind)
    if m:
        lines = [o + '<numberQualifiers>', o + '  <precision>%s</precision>' % m.group(1)]
        if int(m.group(2)):
            lines.append(o + '  <scale>%s</scale>' % m.group(2))
        return lines + [o + '</numberQualifiers>']
    m = re.match(r'^String\((\d+)\)$', kind)
    if m:
        return [o + '<stringQualifiers>', o + '  <length>%s</length>' % m.group(1), o + '</stringQualifiers>']
    if kind == 'String':
        return [o + '<stringQualifiers/>']
    if kind == 'Number':
        return [o + '<numberQualifiers>', o + '  <precision>10</precision>', o + '</numberQualifiers>']
    if kind == 'Date':
        return [o + '<dateQualifiers>', o + '  <dateFractions>DateTime</dateFractions>', o + '</dateQualifiers>']
    return []


def _value_type_lines(kind, indent):
    """<types> + квалификаторы; составной тип — 'CatalogRef.X|DocumentRef.Y' (ФРЕГАТ EAM)."""
    o = ' ' * indent
    lines, quals = [], []
    for k in kind.split('|'):
        lines.append(o + '<types>%s</types>' % re.sub(r'\(.*\)$', '', k))
        quals += _qualifiers(k, indent)
    return lines + quals


def form_attribute(nums, name, title, kind, columns=(), main=False, saved_data=False, indent=2,
                   ext=None):
    """Реквизит формы. kind — тип в терминах EDT: String, Number, Boolean,
    Date, ValueTable, CatalogRef.X, DocumentRef.X, CatalogObject.X,
    DataProcessorObject.X, DynamicList… Номер — из ОБЩЕГО счётчика с
    колонками таблиц (case 003)."""
    o = ' ' * indent
    lines = [o + '<attributes>', o + '  <name>%s</name>' % name]
    if title:
        lines += title_xml(title, indent + 2)
    lines += [o + '  <id>%d</id>' % nums(), o + '  <valueType>']
    lines += _value_type_lines(kind, indent + 4)
    lines += [o + '  </valueType>', o + '  <view>', o + '    <common>true</common>', o + '  </view>',
              o + '  <edit>', o + '    <common>true</common>', o + '  </edit>']
    if main:
        lines.append(o + '  <main>true</main>')
    if saved_data:
        lines.append(o + '  <savedData>true</savedData>')
    for cname, ctitle, ckind in columns:
        lines += [o + '  <columns>', o + '    <name>%s</name>' % cname]
        lines += title_xml(ctitle, indent + 4)
        lines += [o + '    <id>%d</id>' % nums(), o + '    <valueType>']
        lines += _value_type_lines(ckind, indent + 6)
        lines += [o + '    </valueType>', o + '    <view>', o + '      <common>true</common>',
                  o + '    </view>', o + '    <edit>', o + '      <common>true</common>',
                  o + '    </edit>', o + '  </columns>']
    if ext:
        lines += [o + '  ' + l for l in ext]
    lines.append(o + '</attributes>')
    return lines


def dynamic_list_ext(main_table, indent=2):
    o = ' ' * indent
    return [o + '<extInfo xsi:type="form:DynamicListExtInfo">',
            o + '  <mainTable>%s</mainTable>' % main_table,
            o + '  <dynamicDataRead>true</dynamicDataRead>',
            o + '  <autoFillAvailableFields>true</autoFillAvailableFields>',
            o + '  <autoSaveUserSettings>true</autoSaveUserSettings>',
            o + '  <getInvisibleFieldPresentations>true</getInvisibleFieldPresentations>',
            o + '</extInfo>']


def form_command(number, name, title, tip, handler=None, picture=None):
    """Команда формы. Номера команд — своё пространство, с единицы."""
    lines = ['  <formCommands>', '    <name>%s</name>' % name]
    lines += title_xml(title, 4)
    lines += ['    <id>%d</id>' % number]
    if tip:
        lines += ['    <toolTip>', '      <key>ru</key>', '      <value>%s</value>' % esc(tip), '    </toolTip>']
    lines += ['    <use>', '      <common>true</common>', '    </use>']
    if picture:
        lines += ['    <picture xsi:type="core:PictureRef">', '      <picture>%s</picture>' % picture,
                  '    </picture>']
    lines += ['    <action xsi:type="form:FormCommandHandlerContainer">', '      <handler>',
              '        <name>%s</name>' % (handler or name), '      </handler>', '    </action>',
              '    <currentRowUse>Auto</currentRowUse>', '  </formCommands>']
    return lines


def form_file(items, attributes, commands=(), handlers=(), title=None, auto_title=True,
              ext='form:ObjectFormExtInfo', window_mode=None, auto_bar_id=-1, auto_bar_fill=True,
              bar_items=(), parameters=()):
    """Каркас Form.form. handlers — [(событие, процедура)]. Хвост в порядке
    модели EDT: autoCommandBar → handlers → windowOpeningMode →
    saveWindowSettings (без него EDT форму не рисует — case 002) → …
    bar_items — строки кнопок (bar_button) командной панели формы;
    ext — 'form:DocumentFormExtInfo' у формы документа, 'form:DynamicListFormExtInfo'
    у формы списка."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<form:Form %s>' % XMLNS_FORM]
    if title:
        lines += title_xml(title, 2)
    lines += items
    lines += ['  <autoCommandBar>', '    <name>ФормаКоманднаяПанель</name>',
              '    <id>%d</id>' % auto_bar_id]
    lines += list(bar_items)
    lines += ['    <horizontalAlign>Left</horizontalAlign>']
    if auto_bar_fill:
        lines.append('    <autoFill>true</autoFill>')
    lines.append('  </autoCommandBar>')
    for event, proc in handlers:
        lines += ['  <handlers>', '    <event>%s</event>' % event, '    <name>%s</name>' % proc, '  </handlers>']
    if window_mode:
        lines.append('  <windowOpeningMode>%s</windowOpeningMode>' % window_mode)
    lines += ['  <saveWindowSettings>true</saveWindowSettings>',
              '  <autoTitle>%s</autoTitle>' % ('true' if auto_title else 'false'),
              '  <autoUrl>true</autoUrl>', '  <group>Vertical</group>',
              '  <autoFillCheck>true</autoFillCheck>', '  <allowFormCustomize>true</allowFormCustomize>',
              '  <enabled>true</enabled>', '  <showTitle>true</showTitle>',
              '  <showCloseButton>true</showCloseButton>']
    lines += attributes
    lines += commands
    # параметры формы — после команд, до commandInterface (снято с CommonForm.АдреснаяКнига ФРЕГАТ EAM);
    # parameters — [(имя, тип|None)], тип как у form_attribute ('ValueList', 'CatalogRef.X|DocumentRef.Y')
    for pname, ptype in parameters:
        lines += ['  <parameters>', '    <name>%s</name>' % pname]
        if ptype:
            lines += ['    <valueType>'] + _value_type_lines(ptype, 6) + ['    </valueType>']
        else:
            lines.append('    <valueType/>')
        lines.append('  </parameters>')
    lines += ['  <commandInterface>', '    <navigationPanel/>', '    <commandBar/>',
              '  </commandInterface>', '  <extInfo xsi:type="%s"/>' % ext, '</form:Form>', '']
    return join(lines)


# ============================================================ Template.dcs
DCS_HEAD = ('<DataCompositionSchema xmlns="http://v8.1c.ru/8.1/data-composition-system/schema" '
            'xmlns:dcscom="http://v8.1c.ru/8.1/data-composition-system/common" '
            'xmlns:dcscor="http://v8.1c.ru/8.1/data-composition-system/core" '
            'xmlns:dcsset="http://v8.1c.ru/8.1/data-composition-system/settings" '
            'xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" '
            'xmlns:xs="http://www.w3.org/2001/XMLSchema" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">')
DCS_SETTINGS = ('<dcsset:settings xmlns:style="http://v8.1c.ru/8.1/data/ui/style" '
                'xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" '
                'xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" '
                'xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows">')


def _local_string(tag, text, t):
    return ['%s<%s xsi:type="v8:LocalStringType">' % (t, tag), '%s\t<v8:item>' % t,
            '%s\t\t<v8:lang>ru</v8:lang>' % t, '%s\t\t<v8:content>%s</v8:content>' % (t, esc(text)),
            '%s\t</v8:item>' % t, '%s</%s>' % (t, tag)]


def dcs_schema(name, title, fields, query, selection, filters=(), total=None, groups=(),
               parameters=()):
    """Схема компоновки: один набор-запрос, один вариант настроек.
    fields — [(поле, подпись)]; filters — [(поле, пустое_значение)], где
    пустое — «Справочник.X.ПустаяСсылка» для ссылок и '' для строк (строке
    DesignTimeValue не годится — case 034); parameters — [(имя, подпись,
    StandardBeginningDateVariant)]; groups — поля группировки; при группах
    добавляется вложенная группировка детальных записей (case 035)."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', DCS_HEAD, '\t<dataSource>',
             '\t\t<name>ИсточникДанных1</name>', '\t\t<dataSourceType>Local</dataSourceType>',
             '\t</dataSource>', '\t<dataSet xsi:type="DataSetQuery">', '\t\t<name>Данные</name>']
    for f, ftitle in fields:
        lines += ['\t\t<field xsi:type="DataSetFieldField">', '\t\t\t<dataPath>%s</dataPath>' % f,
                  '\t\t\t<field>%s</field>' % f]
        if ftitle:
            lines += _local_string('title', ftitle, '\t\t\t')
        lines.append('\t\t</field>')
    q = query.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    lines += ['\t\t<dataSource>ИсточникДанных1</dataSource>', '\t\t<query>%s</query>' % q.replace('\n', CRLF),
              '\t</dataSet>']
    if total:
        lines += ['\t<totalField>', '\t\t<dataPath>%s</dataPath>' % total,
                  '\t\t<expression>Сумма(%s)</expression>' % total, '\t</totalField>']
    for pname, ptitle, _v in parameters:
        lines += ['\t<parameter>', '\t\t<name>%s</name>' % pname]
        lines += _local_string('title', ptitle, '\t\t')
        lines += ['\t\t<valueType>', '\t\t\t<v8:Type>xs:dateTime</v8:Type>', '\t\t\t<v8:DateQualifiers>',
                  '\t\t\t\t<v8:DateFractions>DateTime</v8:DateFractions>', '\t\t\t</v8:DateQualifiers>',
                  '\t\t</valueType>', '\t\t<value xsi:type="xs:dateTime">0001-01-01T00:00:00</value>',
                  '\t\t<useRestriction>false</useRestriction>',
                  '\t\t<denyIncompleteValues>true</denyIncompleteValues>', '\t\t<use>Always</use>',
                  '\t</parameter>']
    lines += ['\t<settingsVariant>', '\t\t<dcsset:name>Основной</dcsset:name>']
    lines += _local_string('dcsset:presentation', title, '\t\t')
    lines += ['\t\t' + DCS_SETTINGS, '\t\t\t<dcsset:selection>']
    for f in selection:
        lines += ['\t\t\t\t<dcsset:item xsi:type="dcsset:SelectedItemField">',
                  '\t\t\t\t\t<dcsset:field>%s</dcsset:field>' % f, '\t\t\t\t</dcsset:item>']
    lines.append('\t\t\t</dcsset:selection>')
    if filters:
        lines.append('\t\t\t<dcsset:filter>')
        for f, empty in filters:
            lines += ['\t\t\t\t<dcsset:item xsi:type="dcsset:FilterItemComparison">',
                      '\t\t\t\t\t<dcsset:use>false</dcsset:use>',
                      '\t\t\t\t\t<dcsset:left xsi:type="dcscor:Field">%s</dcsset:left>' % f,
                      '\t\t\t\t\t<dcsset:comparisonType>Equal</dcsset:comparisonType>',
                      ('\t\t\t\t\t<dcsset:right xsi:type="dcscor:DesignTimeValue">%s</dcsset:right>' % empty)
                      if empty else '\t\t\t\t\t<dcsset:right xsi:type="xs:string"/>',
                      '\t\t\t\t\t<dcsset:viewMode>QuickAccess</dcsset:viewMode>',
                      '\t\t\t\t\t<dcsset:userSettingID>%s</dcsset:userSettingID>'
                      % uuid.uuid5(uuid.NAMESPACE_OID, name + f),
                      '\t\t\t\t</dcsset:item>']
        lines.append('\t\t\t</dcsset:filter>')
    if parameters:
        lines.append('\t\t\t<dcsset:dataParameters>')
        for pname, _t, variant in parameters:
            lines += ['\t\t\t\t<dcscor:item xsi:type="dcsset:SettingsParameterValue">',
                      '\t\t\t\t\t<dcscor:parameter>%s</dcscor:parameter>' % pname,
                      '\t\t\t\t\t<dcscor:value xsi:type="v8:StandardBeginningDate">',
                      '\t\t\t\t\t\t<v8:variant xsi:type="v8:StandardBeginningDateVariant">%s</v8:variant>' % variant,
                      '\t\t\t\t\t</dcscor:value>',
                      '\t\t\t\t\t<dcsset:userSettingID>%s</dcsset:userSettingID>'
                      % uuid.uuid5(uuid.NAMESPACE_OID, name + pname),
                      '\t\t\t\t</dcscor:item>']
        lines.append('\t\t\t</dcsset:dataParameters>')
    lines += ['\t\t\t<dcsset:outputParameters>',
              '\t\t\t\t<dcscor:item xsi:type="dcsset:SettingsParameterValue">',
              '\t\t\t\t\t<dcscor:parameter>Заголовок</dcscor:parameter>']
    lines += _local_string('dcscor:value', title, '\t\t\t\t\t')
    lines += ['\t\t\t\t</dcscor:item>',
              '\t\t\t\t<dcscor:item xsi:type="dcsset:SettingsParameterValue">',
              '\t\t\t\t\t<dcscor:parameter>ВыводитьЗаголовок</dcscor:parameter>',
              '\t\t\t\t\t<dcscor:value xsi:type="dcsset:DataCompositionTextOutputType">Output</dcscor:value>',
              '\t\t\t\t</dcscor:item>', '\t\t\t</dcsset:outputParameters>',
              '\t\t\t<dcsset:item xsi:type="dcsset:StructureItemGroup">', '\t\t\t\t<dcsset:groupItems>']
    for g in groups:
        lines += ['\t\t\t\t\t<dcsset:item xsi:type="dcsset:GroupItemField">',
                  '\t\t\t\t\t\t<dcsset:field>%s</dcsset:field>' % g,
                  '\t\t\t\t\t\t<dcsset:groupType>Items</dcsset:groupType>',
                  '\t\t\t\t\t\t<dcsset:periodAdditionType>None</dcsset:periodAdditionType>',
                  '\t\t\t\t\t\t<dcsset:periodAdditionBegin xsi:type="xs:dateTime">0001-01-01T00:00:00</dcsset:periodAdditionBegin>',
                  '\t\t\t\t\t\t<dcsset:periodAdditionEnd xsi:type="xs:dateTime">0001-01-01T00:00:00</dcsset:periodAdditionEnd>',
                  '\t\t\t\t\t</dcsset:item>']
    lines += ['\t\t\t\t</dcsset:groupItems>', '\t\t\t\t<dcsset:order>',
              '\t\t\t\t\t<dcsset:item xsi:type="dcsset:OrderItemAuto"/>', '\t\t\t\t</dcsset:order>',
              '\t\t\t\t<dcsset:selection>', '\t\t\t\t\t<dcsset:item xsi:type="dcsset:SelectedItemAuto"/>',
              '\t\t\t\t</dcsset:selection>']
    if groups:
        lines += ['\t\t\t\t<dcsset:item xsi:type="dcsset:StructureItemGroup">', '\t\t\t\t\t<dcsset:order>',
                  '\t\t\t\t\t\t<dcsset:item xsi:type="dcsset:OrderItemAuto"/>', '\t\t\t\t\t</dcsset:order>',
                  '\t\t\t\t\t<dcsset:selection>',
                  '\t\t\t\t\t\t<dcsset:item xsi:type="dcsset:SelectedItemAuto"/>',
                  '\t\t\t\t\t</dcsset:selection>', '\t\t\t\t</dcsset:item>']
    lines += ['\t\t\t</dcsset:item>', '\t\t</dcsset:settings>', '\t</settingsVariant>',
              '</DataCompositionSchema>', '']
    return join(lines)


# ============================================================ BSL: правка модулей
def insert_into_procedure(text, name, line, at_start):
    """Идемпотентная вставка строки в тело процедуры типового модуля.
    В начало — за ЦЕЛЫМ переводом строки объявления (иначе остаётся
    одиночный LF — case 026); в конец — перед КонецПроцедуры, добавляя «;»
    к последнему оператору, если его нет (перед КонецПроцедуры «;» можно
    опускать, а после него наш вызов требует — case 026)."""
    m = re.search(r'^Процедура %s\(.*?\)\s*$' % re.escape(name), text, re.M)
    if not m:
        raise ValueError('в модуле нет процедуры %s' % name)
    start = m.end()
    end = text.index(CRLF + 'КонецПроцедуры', start)
    body = text[start:end]
    if line.strip() in body:
        return text
    if at_start:
        after = text.index(CRLF, m.start()) + len(CRLF)
        return text[:after] + line + CRLF + text[after:]
    tail = body.rstrip()
    last = [s for s in tail.split(CRLF) if s.strip() and not s.strip().startswith('//')]
    if last and not last[-1].rstrip().endswith(';'):
        text = text[:start] + body.rstrip() + ';' + body[len(body.rstrip()):] + text[end:]
        end = text.index(CRLF + 'КонецПроцедуры', start)
    return text[:end] + CRLF + line + text[end:]


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
    #    булево «Интерактивно»; компилятор молчит, в клиенте «Несоответствие типов (параметр номер '4')» (case 076)
    for n, raw in enumerate(lines, 1):
        m = re.search(r'НачатьПомещениеФайлов\(([^;]*)\)\s*;', raw)
        if not m:
            continue
        parts = [x.strip() for x in m.group(1).split(',')]
        if len(parts) == 4 and 'Диалог' in parts[2] and re.search(r'УникальныйИдентификатор|Идентификатор', parts[3]):
            problems.append('строка %d: НачатьПомещениеФайлов с диалогом — 4-й параметр «Интерактивно» (Булево), '
                            'идентификатор формы — 5-м: (Оповещение, , Диалог, Истина, УникальныйИдентификатор) '
                            '(case 076)' % n)
    return problems


# ------------------------------------------------ запросы: псевдоним и ТЧ (case 062)
QUERY_KINDS = {'Справочник': 'Catalog', 'Документ': 'Document', 'РегистрСведений': 'InformationRegister',
               'РегистрНакопления': 'AccumulationRegister', 'ПланВидовХарактеристик': 'ChartOfCharacteristicTypes'}


def tabular_sections_of_mdo(text):
    """Имена табличных частей объекта из его .mdo."""
    names = []
    for m in re.finditer(r'<tabularSections uuid="[^"]+">\s*<name>([^<]+)</name>', text):
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


# ============================================================ проверки: формы
def _local(tag):
    return tag.split('}')[-1]


def check_form(text, module_text=None, mdo_text=None):
    """Претензии к Form.form. Все — про пустой лист в редакторе EDT или
    «Неверный путь к данным» при открытии, при валидном XML."""
    problems = []
    if text.count('\n') != text.count(CRLF):
        problems.append('переводы строк не CRLF')
    try:
        root = ET.fromstring(text.encode('utf-8'))
    except ET.ParseError as e:
        return ['XML не разбирается: %s' % e]
    if '<saveWindowSettings>' not in text:
        problems.append('нет <saveWindowSettings> — EDT форму не нарисует (case 002)')
    for piece in text.split('<types>Number</types>')[1:]:
        if 'numberQualifiers' not in piece[:200]:
            problems.append('числовой реквизит без numberQualifiers — форма будет пустой (case 001)')
            break
    # ids элементов
    ids = []
    for branch in root:
        if _local(branch.tag) in ('items', 'autoCommandBar'):
            for node in branch.iter():
                for ch in node:
                    if _local(ch.tag) == 'id' and (ch.text or '').strip().lstrip('-').isdigit():
                        ids.append(int(ch.text))
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        problems.append('повторяющиеся id элементов формы: %s' % dup)
    # имена элементов: группа и поле с одним именем (и их спутники «…РасширеннаяПодсказка») —
    # EDT и проверки молчат, тонкий клиент 8.5.1 падает (mngui.dll, 0xc0000005) при закрытии формы (UP, 2026-10)
    names = []
    for branch in root:
        if _local(branch.tag) in ('items', 'autoCommandBar'):
            for node in branch.iter():
                if _local(node.tag) in ('items', 'extendedTooltip', 'contextMenu', 'autoCommandBar'):
                    n = next((c.text for c in node if _local(c.tag) == 'name'), None)
                    if n:
                        names.append(n)
    dup_names = sorted({n for n in names if names.count(n) > 1})
    if dup_names:
        problems.append('повторяющиеся имена элементов формы: %s — клиент падает при закрытии формы' % ', '.join(dup_names))
    # реквизиты и колонки — одно пространство (case 003)
    attr_ids = []
    attr_names = set()
    for a in root:
        if _local(a.tag) != 'attributes':
            continue
        for ch in a:
            if _local(ch.tag) == 'name':
                attr_names.add(ch.text)
            if _local(ch.tag) == 'id':
                attr_ids.append(int(ch.text))
            if _local(ch.tag) == 'columns':
                for cc in ch:
                    if _local(cc.tag) == 'id':
                        attr_ids.append(int(cc.text))
    dup = sorted({i for i in attr_ids if attr_ids.count(i) > 1})
    if dup:
        problems.append('номера реквизитов и колонок повторяются: %s — форма не отобразится (case 003)' % dup)
    # пути данных ведут к реквизитам
    for m in re.finditer(r'<segments>([^<]+)</segments>', text):
        rootname = m.group(1).split('.')[0]
        if rootname not in attr_names:
            problems.append('путь данных «%s» не ведёт к реквизиту формы («Неверный путь к данным»)' % m.group(1))
    # таблицы: спутники
    for tbl in root.iter():
        if _local(tbl.tag) == 'items' and tbl.get('{http://www.w3.org/2001/XMLSchema-instance}type') == 'form:Table':
            kids = {_local(c.tag) for c in tbl}
            tname = next((c.text for c in tbl if _local(c.tag) == 'name'), '?')
            for need in ('searchStringAddition', 'viewStatusAddition', 'searchControlAddition', 'autoCommandBar'):
                if need not in kids:
                    problems.append('таблица «%s» без %s — EDT её не нарисует (case 004)' % (tname, need))
    if '<rowFilter' in text and 'xmlns:core=' not in text.split('>', 2)[1]:
        problems.append('rowFilter требует объявления xmlns:core в корне формы')
    # имя команды формы — имя процедуры: ключевое слово BSL недопустимо (case 057)
    for cname in re.findall(r'<formCommands>\s*<name>(\w+)</name>', text):
        if cname.lower() in BSL_KEYWORDS:
            problems.append('команда «%s» — ключевое слово BSL, «Ожидается имя процедуры» (case 057)' % cname)
    # реквизиты формы в процедурах без контекста (case 060)
    if module_text is not None and attr_names:
        problems += check_form_attributes_in_no_context(module_text, attr_names - {'Объект', 'Запись'})
    # обработчики и команды — в модуле
    if module_text is not None:
        for proc in re.findall(r'<handlers>\s*<event>\w+</event>\s*<name>(\w+)</name>', text):
            if not re.search(r'^(?:Асинх\s+)?(Процедура|Функция)\s+%s\(' % re.escape(proc), module_text, re.M):
                problems.append('обработчик «%s» не описан в модуле формы' % proc)
        for name in re.findall(r'<handler>\s*<name>(\w+)</name>', text):
            if not re.search(r'^(?:Асинх\s+)?Процедура\s+%s\(' % re.escape(name), module_text, re.M):
                problems.append('у команды нет обработчика «%s» в модуле' % name)
    # группы: типовые свойства
    for g in root.iter():
        if _local(g.tag) == 'extInfo' and g.get('{http://www.w3.org/2001/XMLSchema-instance}type') == 'form:UsualGroupExtInfo':
            kids = {_local(c.tag) for c in g}
            if 'throughAlign' not in kids:
                problems.append('предупреждение: группа без throughAlign/united/showLeftMargin/currentRowUse — '
                                'строка может расползтись по колонкам (case 007)')
                break
    for h in root.iter():
        if _local(h.tag) == 'extInfo' and h.get('{http://www.w3.org/2001/XMLSchema-instance}type') == 'form:HtmlFieldExtInfo':
            kids = {_local(c.tag) for c in h}
            if 'width' not in kids or 'height' not in kids:
                problems.append('поле HTML без width/height — документ нулевой высоты (case 022)')
    return problems


def check_mdo(text):
    problems = []
    if text.count('\n') != text.count(CRLF):
        problems.append('переводы строк не CRLF')
    try:
        ET.fromstring(text.encode('utf-8'))
    except ET.ParseError as e:
        return ['XML не разбирается: %s' % e]
    for m in re.finditer(r'<length>(\d+)</length>', text):
        if int(m.group(1)) > 1024:
            problems.append('строка длиной %s: обновление базы падает «Ошибка SDBL» — ставьте 0 (case 024)' % m.group(1))
    uids = re.findall(r'uuid="([0-9a-f-]{36})"', text)
    dup = sorted({u for u in uids if uids.count(u) > 1})
    if dup:
        problems.append('повторяющиеся uuid внутри файла: %s' % dup)
    # у реквизита ТЧ нет fillValue (case 025)
    for ts in re.finditer(r'<tabularSections uuid.*?</tabularSections>', text, re.S):
        for a in re.finditer(r'<attributes uuid.*?</attributes>', ts.group(0), re.S):
            if '<fillValue' in a.group(0):
                problems.append('реквизит табличной части с fillValue — у ТЧ его нет (case 025)')
                break
    # имена: у объекта — среди прямых детей (отступ два пробела), у каждой ТЧ — свои
    for tag in ('tabularSections', 'attributes', 'dimensions', 'resources', 'enumValues', 'forms'):
        names = re.findall(r'\n  <%s uuid="[^"]+">\r?\n    <name>([^<]+)</name>' % tag, text)
        dup = sorted({n for n in names if names.count(n) > 1})
        if dup:
            problems.append('повторяющиеся имена <%s>: %s' % (tag, dup))
    for ts in re.finditer(r'<tabularSections uuid.*?</tabularSections>', text, re.S):
        names = re.findall(r'<attributes uuid="[^"]+">\s*<name>([^<]+)</name>', ts.group(0))
        dup = sorted({n for n in names if names.count(n) > 1})
        if dup:
            problems.append('повторяющиеся имена реквизитов внутри ТЧ: %s' % dup)
    for m in re.finditer(r'<(dimensions|resources|attributes) uuid="[^"]+">\s*<name>([^<]+)</name>', text):
        if m.group(2).upper() in QUERY_KEYWORDS:
            problems.append('имя «%s» — ключевое слово языка запросов (case 016)' % m.group(2))
    return problems


# ============================================================ добавлено: ФРЕГАТ EAM (2026-09)
# Функции, которых не хватило при массовой реализации ТЗ в конфигурации ФРЕГАТ EAM
# (EDT 2026.1, БСП 3.1.3). Формат сверен с живыми объектами того проекта и
# проверен `1cedtcli validate` (без ошибок, только замечания стандартов).

_UUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def preserve_uuids(new_text, old_text):
    """Перегенерация ЗАГОТОВКИ, уже лежащей в проекте (и, возможно, в базе):
    uuid объекта, его producedTypes и uuid одноимённых реквизитов/ТЧ/форм/
    значений перечислений берутся из старого .mdo — база не увидит «новый»
    объект вместо старого (case 020)."""
    m_new = re.search(r'(<mdclass:\w+ [^>]*uuid=")([^"]+)(")', new_text)
    m_old = re.search(r'<mdclass:\w+ [^>]*uuid="([^"]+)"', old_text)
    text = new_text[:m_new.start(2)] + m_old.group(1) + new_text[m_new.end(2):]
    pt_old = re.search(r'\n  <producedTypes>.*?\n  </producedTypes>', old_text, re.S)
    pt_new = re.search(r'\n  <producedTypes>.*?\n  </producedTypes>', text, re.S)
    if pt_old and pt_new:
        text = text[:pt_new.start()] + pt_old.group(0).replace('\r\n', '\n').replace('\n', CRLF) + text[pt_new.end():]
    pat = r'(\n {2,4}<(attributes|tabularSections|forms|enumValues|dimensions|resources|templates|commands) uuid=")([^"]+)(">\s*(?:<producedTypes>.*?</producedTypes>\s*)?<name>([^<]+)</name>)'

    def slots(t):
        """[(начало uuid, конец uuid, ключ)]; ключ реквизита ТЧ содержит имя ТЧ —
        одноимённые реквизиты разных ТЧ (КлючСвязи и т.п.) не путаются."""
        spans = []
        for m in re.finditer(r'\n  <tabularSections uuid="[^"]+">.*?\n  </tabularSections>', t, re.S):
            nm = re.search(r'</producedTypes>\s*<name>([^<]+)</name>|^\s*<tabularSections[^>]*>\s*<name>([^<]+)</name>',
                           m.group(0), re.S)
            spans.append((m.start(), m.end(), (nm.group(1) or nm.group(2)) if nm else ''))
        res = []
        for m in re.finditer(pat, t, re.S):
            pos = m.start(3)
            scope = ''
            if m.group(2) != 'tabularSections':
                scope = next((n for s, e, n in spans if s < pos < e), '')
            res.append((m.start(3), m.end(3), (scope, m.group(2), m.group(5))))
        return res

    old = {k: old_text[s:e] for s, e, k in slots(old_text)}
    old_ts_pt = {}
    for m in re.finditer(r'<tabularSections uuid="[^"]+">\s*(<producedTypes>.*?</producedTypes>)\s*<name>([^<]+)</name>', old_text, re.S):
        old_ts_pt[m.group(2)] = m.group(1)
    for s, e, k in reversed(slots(text)):
        if k in old:
            text = text[:s] + old[k] + text[e:]

    def repl_pt(m):
        pt = old_ts_pt.get(m.group(3))
        if not pt:
            return m.group(0)
        return m.group(1) + pt.replace('\r\n', '\n').replace('\n', CRLF) + m.group(2) + m.group(3) + m.group(4)
    text = re.sub(r'(<tabularSections uuid="[^"]+">\s*)<producedTypes>.*?</producedTypes>(\s*<name>)([^<]+)(</name>)',
                  repl_pt, text, flags=re.S)
    return text


def add_content_to_subsystem(text, full_names):
    """Состав подсистемы: строки <content>Вид.Имя</content> (идемпотентно).
    Встают после последней строки состава, а у пустой подсистемы — после
    includeInCommandInterface/explanation/picture (порядок как в .mdo подсистем)."""
    added = []
    for fn in full_names:
        line = '  <content>%s</content>' % fn
        if line + CRLF in text:
            continue
        last = text.rfind('  <content>')
        if last < 0:
            end = -1
            for tag in ('  <includeInCommandInterface>', '  <explanation>', '  </explanation>',
                        '  <picture ', '  </picture>'):
                i = text.rfind(tag)
                if i >= 0:
                    end = max(end, text.index(CRLF, i) + len(CRLF))
            if end < 0:
                end = text.index(CRLF, text.rfind('  </synonym>')) + len(CRLF)
        else:
            end = text.index(CRLF, last) + len(CRLF)
        text = text[:end] + line + CRLF + text[end:]
        added.append(fn)
    return text, added


def add_type_to_defined_type(text, type_name):
    """Тип в состав определяемого типа (CatalogRef.X / DocumentRef.X /
    CatalogObject.X …) — например, для подключения файлов БСП
    (ВладелецПрисоединенныхФайлов, ПрисоединенныйФайл, ПрисоединенныйФайлОбъект)."""
    line = '    <types>%s</types>' % type_name
    if line + CRLF in text:
        return text, False
    i = text.rfind('    <types>')
    end = text.index(CRLF, i) + len(CRLF)
    return text[:end] + line + CRLF + text[end:], True


def add_attributes_to_ts(text, ts_name, attributes):
    """Идемпотентно добавляет реквизиты [(имя, синоним, тип)] в СУЩЕСТВУЮЩУЮ
    табличную часть .mdo (перед её закрытием, отступ 4 — у реквизитов ТЧ нет
    fillValue, case 025)."""
    m = re.search(r'<tabularSections uuid="[^"]+">\s*(?:<producedTypes>.*?</producedTypes>\s*)?<name>%s</name>.*?\r\n  </tabularSections>'
                  % re.escape(ts_name), text, re.S)
    if not m:
        raise ValueError('нет ТЧ %s' % ts_name)
    block = m.group(0)
    added = []
    new_lines = []
    for a in attributes:
        if ('<name>%s</name>' % a[0]) in block:
            continue
        mo = re.search(r'<name>([^<]+)</name>', text)
        new_lines += attribute(a[0], a[1], a[2], 4, in_ts=True,
                               seed='addtsattr/%s/%s/%s' % (mo.group(1) if mo else '', ts_name, a[0]))
        added.append(a[0])
    if not new_lines:
        return text, added
    close = CRLF + '  </tabularSections>'
    nb = block[:-len(close)] + CRLF + CRLF.join(new_lines) + close
    return text[:m.start()] + nb + text[m.end():], added


def clone_object_dir(src_dir, dst_dir, replacements, uuid_salt):
    """Копия работающего объекта проекта под новым именем: во всех текстовых
    файлах (.mdo/.bsl/.form/.dcss/.html/.cmi) выполняются replacements
    [(старое, новое)], а все uuid в .mdo/.dcss заменяются устойчиво
    (uuid5 от uuid_salt + старый uuid) — повторная копия даёт те же uuid.
    Так собирается, например, справочник присоединённых файлов БСП для нового
    владельца (копия <Владелец>ПрисоединенныеФайлы)."""
    for root, _dirs, files in os.walk(src_dir):
        for f in files:
            sp = os.path.join(root, f)
            rel = os.path.relpath(sp, src_dir)
            for a, b in replacements:  # имя файла тоже: <Имя>.mdo, <Имя>ПрисоединенныеФайлы.mdo
                rel = rel.replace(a, b)
            dp = os.path.join(dst_dir, rel)
            os.makedirs(os.path.dirname(dp), exist_ok=True)
            if f.endswith(('.mdo', '.bsl', '.form', '.dcss', '.html', '.cmi', '.dcs')):
                t = io.open(sp, encoding='utf-8', newline='').read()
                for a, b in replacements:
                    t = t.replace(a, b)
                if f.endswith(('.mdo', '.dcss')):
                    t = _UUID_RE.sub(lambda m: str(uuid.uuid5(uuid.NAMESPACE_OID,
                                                               uuid_salt + os.path.relpath(dp, dst_dir) + m.group(0))), t)
                io.open(dp, 'w', encoding='utf-8', newline='').write(t)
            else:
                io.open(dp, 'wb').write(io.open(sp, 'rb').read())


def list_settings_dcss(seed):
    """Attributes/Список/ExtInfo/ListSettings.dcss формы списка (пользовательские
    настройки динамического списка) — формат снят с форм ФРЕГАТ EAM."""
    ids = [stable_uid(seed + '/' + k) for k in ('filter', 'order', 'ca', 'items')]
    return join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Settings xmlns="http://v8.1c.ru/8.1/data-composition-system/settings" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xs="http://www.w3.org/2001/XMLSchema" '
        'xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" '
        'xmlns:pal="http://v8.1c.ru/8.1/data/ui/colors/palette" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" '
        'xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" '
        'xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" '
        'xmlns:dcscor="http://v8.1c.ru/8.1/data-composition-system/core">',
        '\t<filter>', '\t\t<viewMode>Normal</viewMode>', '\t\t<userSettingID>%s</userSettingID>' % ids[0], '\t</filter>',
        '\t<order>', '\t\t<viewMode>Normal</viewMode>', '\t\t<userSettingID>%s</userSettingID>' % ids[1], '\t</order>',
        '\t<conditionalAppearance>', '\t\t<viewMode>Normal</viewMode>',
        '\t\t<userSettingID>%s</userSettingID>' % ids[2], '\t</conditionalAppearance>',
        '\t<itemsViewMode>Normal</itemsViewMode>', '\t<itemsUserSettingID>%s</itemsUserSettingID>' % ids[3],
        '</Settings>', ''])


# ---- расширенная схема компоновки: несколько вариантов, ресурсы, вычисляемые поля,
#      условное оформление, типизированные параметры, период как в eamГрафикТОиР
class DcsField(object):
    """Поле набора: путь, заголовок, формат ('ЧДЦ=2'), ширина, роль измерения."""

    def __init__(self, path, title=None, fmt=None, width=None, dim=False):
        self.path, self.title, self.fmt, self.width, self.dim = path, title, fmt, width, dim


class DcsAppearance(object):
    """Элемент условного оформления: fields — поля (пусто — вся строка),
    conds — [(поле, вид_сравнения, значение)] (значение: число/булево/строка,
    'Поле:Имя' — другое поле, 'Знач:Перечисление.X.Y' — значение конфигурации,
    None — без правой части), appearance — {'ЦветФона'|'ЦветТекста': 'web:LightPink'
    или '#RRGGBB', 'Шрифт': 'bold', 'Текст': 'строка'}."""

    def __init__(self, fields, conds, appearance, title=None):
        self.fields, self.conds, self.appearance, self.title = fields, conds, appearance, title


def _dcs_color(v):
    if v.startswith('#'):
        r, g, b = int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16)
        return '#%02X%02X%02X' % (r, g, b)
    return v


def _dcs_right(v):
    if isinstance(v, bool):
        return '<dcsset:right xsi:type="xs:boolean">%s</dcsset:right>' % ('true' if v else 'false')
    if isinstance(v, (int, float)):
        return '<dcsset:right xsi:type="xs:decimal">%s</dcsset:right>' % v
    if v is None:
        return ''
    if v.startswith('Поле:'):
        return '<dcsset:right xsi:type="dcscor:Field">%s</dcsset:right>' % v[5:]
    if v.startswith('Знач:'):
        return '<dcsset:right xsi:type="dcscor:DesignTimeValue">%s</dcsset:right>' % v[5:]
    return '<dcsset:right xsi:type="xs:string">%s</dcsset:right>' % esc(v)


def _dcs_ca(items, o):
    if not items:
        return []
    lines = [o + '<dcsset:conditionalAppearance>']
    for ca in items:
        lines += [o + '\t<dcsset:item>', o + '\t\t<dcsset:selection>']
        for f in ca.fields:
            lines += [o + '\t\t\t<dcsset:item>', o + '\t\t\t\t<dcsset:field>%s</dcsset:field>' % f,
                      o + '\t\t\t</dcsset:item>']
        lines += [o + '\t\t</dcsset:selection>', o + '\t\t<dcsset:filter>']
        for left, cmp_, right in ca.conds:
            lines += [o + '\t\t\t<dcsset:item xsi:type="dcsset:FilterItemComparison">',
                      o + '\t\t\t\t<dcsset:left xsi:type="dcscor:Field">%s</dcsset:left>' % left,
                      o + '\t\t\t\t<dcsset:comparisonType>%s</dcsset:comparisonType>' % cmp_]
            r = _dcs_right(right)
            if r:
                lines.append(o + '\t\t\t\t' + r)
            lines.append(o + '\t\t\t</dcsset:item>')
        lines += [o + '\t\t</dcsset:filter>', o + '\t\t<dcsset:appearance>']
        for k, v in ca.appearance.items():
            lines += [o + '\t\t\t<dcscor:item xsi:type="dcsset:SettingsParameterValue">',
                      o + '\t\t\t\t<dcscor:parameter>%s</dcscor:parameter>' % k]
            if k.startswith('Цвет'):
                lines.append(o + '\t\t\t\t<dcscor:value xsi:type="v8ui:Color">%s</dcscor:value>' % _dcs_color(v))
            elif k == 'Шрифт':
                lines.append(o + '\t\t\t\t<dcscor:value xsi:type="v8ui:Font" ref="sys:DefaultGUIFont" '
                                 'bold="true" italic="false" underline="false" strikeout="false" kind="WindowsFont"/>')
            elif k == 'Текст':
                lines += _local_string('dcscor:value', v, o + '\t\t\t\t')
            lines.append(o + '\t\t\t</dcscor:item>')
        lines.append(o + '\t\t</dcsset:appearance>')
        if ca.title:
            lines += _local_string('dcsset:presentation', ca.title, o + '\t\t')
        lines.append(o + '\t</dcsset:item>')
    return lines + [o + '</dcsset:conditionalAppearance>']


def _dcs_group_field(f, o):
    return [o + '<dcsset:item xsi:type="dcsset:GroupItemField">', o + '\t<dcsset:field>%s</dcsset:field>' % f,
            o + '\t<dcsset:groupType>Items</dcsset:groupType>',
            o + '\t<dcsset:periodAdditionType>None</dcsset:periodAdditionType>',
            o + '\t<dcsset:periodAdditionBegin xsi:type="xs:dateTime">0001-01-01T00:00:00</dcsset:periodAdditionBegin>',
            o + '\t<dcsset:periodAdditionEnd xsi:type="xs:dateTime">0001-01-01T00:00:00</dcsset:periodAdditionEnd>',
            o + '</dcsset:item>']


def _dcs_auto(o):
    return [o + '<dcsset:order>', o + '\t<dcsset:item xsi:type="dcsset:OrderItemAuto"/>', o + '</dcsset:order>',
            o + '<dcsset:selection>', o + '\t<dcsset:item xsi:type="dcsset:SelectedItemAuto"/>', o + '</dcsset:selection>']


def _dcs_structure(levels, o, detail=True, level_ca=()):
    """levels — [[поля уровня 1], [поля уровня 2], …]; последним уровнем —
    детальные записи (case 035). level_ca — оформление уровней (по индексу)."""
    if not levels:
        if not detail:
            return []
        return [o + '<dcsset:item xsi:type="dcsset:StructureItemGroup">'] + _dcs_auto(o + '\t') + [o + '</dcsset:item>']
    lines = [o + '<dcsset:item xsi:type="dcsset:StructureItemGroup">', o + '\t<dcsset:groupItems>']
    for f in levels[0]:
        lines += _dcs_group_field(f, o + '\t\t')
    lines.append(o + '\t</dcsset:groupItems>')
    lines += _dcs_auto(o + '\t')
    if level_ca and level_ca[0]:
        lines += _dcs_ca(level_ca[0], o + '\t')
    lines += _dcs_structure(levels[1:], o + '\t', detail, level_ca[1:] if level_ca else ())
    lines.append(o + '</dcsset:item>')
    return lines


def dcs_param_value(ptype, value=None):
    """Значение параметра СКД для dcs_schema_ex(params=…)."""
    if ptype == 'xs:decimal':
        return '<value xsi:type="xs:decimal">%s</value>' % (value if value is not None else 0)
    if ptype == 'xs:boolean':
        return '<value xsi:type="xs:boolean">%s</value>' % ('true' if value else 'false')
    if ptype == 'xs:dateTime':
        return '<value xsi:type="xs:dateTime">0001-01-01T00:00:00</value>'
    return '<value xsi:nil="true"/>'


def dcs_schema_ex(fields, query, variants, params=(), calc=(), totals=(), period=True, name='Данные'):
    """Схема компоновки: один набор-запрос, НЕСКОЛЬКО вариантов.
    fields — [DcsField]; calc — [(поле, выражение, заголовок)] вычисляемые поля;
    totals — [(поле, выражение)] ресурсы (проценты считать выражением на каждом
    уровне: ВЫБОР КОГДА Сумма(Зн)=0 ТОГДА 0 ИНАЧЕ Сумма(Ч)/Сумма(Зн)*100 КОНЕЦ);
    params — [(имя, заголовок, тип, dcs_param_value(...))], тип: 'xs:decimal' |
    'xs:boolean' | 'xs:dateTime' | 'cfg:CatalogRef.X' (ссылка конфигурации);
    period=True — ПериодОтчета (StandardPeriod) + НачалоПериода/КонецПериода из него
    (как у отчёта eamГрафикТОиР ФРЕГАТ EAM).
    variant = dict(name, title, selection=[поля], groups=[[уровень1],…], filters=[(поле,
    'Справочник.X.ПустаяСсылка' | '' [, вид_сравнения])], ca=[DcsAppearance], level_ca=[[…],[…]],
    period_variant='ThisMonth', order=[(поле,'Asc')], detail=True, totals=True,
    data_params=[(имя, значение_xml)], output_title=…)."""
    L = ['<?xml version="1.0" encoding="UTF-8"?>', DCS_HEAD, '\t<dataSource>', '\t\t<name>ИсточникДанных1</name>',
         '\t\t<dataSourceType>Local</dataSourceType>', '\t</dataSource>', '\t<dataSet xsi:type="DataSetQuery">',
         '\t\t<name>%s</name>' % name]
    for f in fields:
        L += ['\t\t<field xsi:type="DataSetFieldField">', '\t\t\t<dataPath>%s</dataPath>' % f.path,
              '\t\t\t<field>%s</field>' % f.path]
        if f.title:
            L += _local_string('title', f.title, '\t\t\t')
        if f.dim:
            L += ['\t\t\t<role>', '\t\t\t\t<dcscom:dimension>true</dcscom:dimension>', '\t\t\t</role>']
        if f.fmt or f.width:
            L.append('\t\t\t<appearance>')
            if f.fmt:
                L += ['\t\t\t\t<dcscor:item xsi:type="dcsset:SettingsParameterValue">',
                      '\t\t\t\t\t<dcscor:parameter>Формат</dcscor:parameter>']
                L += _local_string('dcscor:value', f.fmt, '\t\t\t\t\t')
                L.append('\t\t\t\t</dcscor:item>')
            if f.width:
                for p in ('МинимальнаяШирина', 'МаксимальнаяШирина'):
                    L += ['\t\t\t\t<dcscor:item xsi:type="dcsset:SettingsParameterValue">',
                          '\t\t\t\t\t<dcscor:parameter>%s</dcscor:parameter>' % p,
                          '\t\t\t\t\t<dcscor:value xsi:type="xs:decimal">%d</dcscor:value>' % f.width,
                          '\t\t\t\t</dcscor:item>']
            L.append('\t\t\t</appearance>')
        L.append('\t\t</field>')
    q = query.strip('\r\n').replace('\r\n', '\n').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    L += ['\t\t<dataSource>ИсточникДанных1</dataSource>', '\t\t<query>%s</query>' % q.replace('\n', CRLF), '\t</dataSet>']
    for cpath, cexpr, ctitle in calc:
        L += ['\t<calculatedField>', '\t\t<dataPath>%s</dataPath>' % cpath,
              '\t\t<expression>%s</expression>' % esc(cexpr)]
        L += _local_string('title', ctitle, '\t\t')
        L.append('\t</calculatedField>')
    for tpath, texpr in totals:
        L += ['\t<totalField>', '\t\t<dataPath>%s</dataPath>' % tpath,
              '\t\t<expression>%s</expression>' % esc(texpr), '\t</totalField>']
    if period:
        for pn, pt, ex in (('НачалоПериода', 'Начало периода', '&ПериодОтчета.ДатаНачала'),
                           ('КонецПериода', 'Конец периода', '&ПериодОтчета.ДатаОкончания')):
            L += ['\t<parameter>', '\t\t<name>%s</name>' % pn]
            L += _local_string('title', pt, '\t\t')
            L += ['\t\t<valueType>', '\t\t\t<v8:Type>xs:dateTime</v8:Type>', '\t\t\t<v8:DateQualifiers>',
                  '\t\t\t\t<v8:DateFractions>DateTime</v8:DateFractions>', '\t\t\t</v8:DateQualifiers>',
                  '\t\t</valueType>', '\t\t<value xsi:type="xs:dateTime">0001-01-01T00:00:00</value>',
                  '\t\t<useRestriction>true</useRestriction>', '\t\t<expression>%s</expression>' % esc(ex),
                  '\t</parameter>']
        L += ['\t<parameter>', '\t\t<name>ПериодОтчета</name>'] + _local_string('title', 'Период', '\t\t') + [
            '\t\t<valueType>', '\t\t\t<v8:Type>v8:StandardPeriod</v8:Type>', '\t\t</valueType>',
            '\t\t<value xsi:type="v8:StandardPeriod">',
            '\t\t\t<v8:variant xsi:type="v8:StandardPeriodVariant">Custom</v8:variant>',
            '\t\t\t<v8:startDate>0001-01-01T00:00:00</v8:startDate>',
            '\t\t\t<v8:endDate>0001-01-01T00:00:00</v8:endDate>', '\t\t</value>',
            '\t\t<useRestriction>false</useRestriction>', '\t\t<use>Always</use>', '\t</parameter>']
    for pn, pt, ptype, pval in params:
        L += ['\t<parameter>', '\t\t<name>%s</name>' % pn] + _local_string('title', pt, '\t\t')
        L.append('\t\t<valueType>')
        if ptype.startswith('cfg:'):
            L.append('\t\t\t<v8:Type xmlns:d4p1="http://v8.1c.ru/8.1/data/enterprise/current-config">d4p1:%s</v8:Type>'
                     % ptype[4:])
        elif ptype == 'xs:decimal':
            L += ['\t\t\t<v8:Type>xs:decimal</v8:Type>', '\t\t\t<v8:NumberQualifiers>',
                  '\t\t\t\t<v8:Digits>15</v8:Digits>', '\t\t\t\t<v8:FractionDigits>2</v8:FractionDigits>',
                  '\t\t\t\t<v8:AllowedSign>Any</v8:AllowedSign>', '\t\t\t</v8:NumberQualifiers>']
        elif ptype == 'xs:dateTime':
            L += ['\t\t\t<v8:Type>xs:dateTime</v8:Type>', '\t\t\t<v8:DateQualifiers>',
                  '\t\t\t\t<v8:DateFractions>Date</v8:DateFractions>', '\t\t\t</v8:DateQualifiers>']
        else:
            L.append('\t\t\t<v8:Type>%s</v8:Type>' % ptype)
        # use=Always: параметр запроса (без необязательных {…}) передается всегда, даже если в настройках
        # варианта он выключен — иначе «Не задано значение параметра» (ФРЕГАТ EAM, 8.5.1.1529)
        L += ['\t\t</valueType>', '\t\t' + pval, '\t\t<useRestriction>false</useRestriction>', '\t\t<use>Always</use>',
              '\t</parameter>']
    for v in variants:
        L += ['\t<settingsVariant>', '\t\t<dcsset:name>%s</dcsset:name>' % v['name']]
        L += _local_string('dcsset:presentation', v['title'], '\t\t')
        L.append('\t\t' + DCS_SETTINGS)
        o = '\t\t\t'
        L.append(o + '<dcsset:selection>')
        for f in v.get('selection', ()):
            L += [o + '\t<dcsset:item xsi:type="dcsset:SelectedItemField">', o + '\t\t<dcsset:field>%s</dcsset:field>' % f,
                  o + '\t</dcsset:item>']
        L.append(o + '</dcsset:selection>')
        if v.get('filters'):
            L.append(o + '<dcsset:filter>')
            for fl in v['filters']:
                fpath, fempty = fl[0], fl[1]
                cmp_ = fl[2] if len(fl) > 2 else 'Equal'
                # 4-й элемент — включённый отбор с правой частью-значением (_dcs_right: число/булево/'Знач:…')
                use_val = fl[3] if len(fl) > 3 else None
                L += [o + '\t<dcsset:item xsi:type="dcsset:FilterItemComparison">']
                if use_val is None:
                    L.append(o + '\t\t<dcsset:use>false</dcsset:use>')
                L += [o + '\t\t<dcsset:left xsi:type="dcscor:Field">%s</dcsset:left>' % fpath,
                      o + '\t\t<dcsset:comparisonType>%s</dcsset:comparisonType>' % cmp_]
                if use_val is not None:
                    r = _dcs_right(use_val)
                    if r:
                        L.append(o + '\t\t' + r)
                elif fempty:
                    L.append(o + '\t\t<dcsset:right xsi:type="dcscor:DesignTimeValue">%s</dcsset:right>' % fempty)
                L += [o + '\t\t<dcsset:viewMode>QuickAccess</dcsset:viewMode>',
                      o + '\t\t<dcsset:userSettingID>%s</dcsset:userSettingID>' % stable_uid(v['name'] + '/f/' + fpath + query[:60]),
                      o + '\t</dcsset:item>']
            L.append(o + '</dcsset:filter>')
        dp = []
        if period:
            dp += [o + '\t<dcscor:item xsi:type="dcsset:SettingsParameterValue">',
                   o + '\t\t<dcscor:parameter>ПериодОтчета</dcscor:parameter>',
                   o + '\t\t<dcscor:value xsi:type="v8:StandardPeriod">',
                   o + '\t\t\t<v8:variant xsi:type="v8:StandardPeriodVariant">%s</v8:variant>' % v.get('period_variant', 'ThisMonth'),
                   o + '\t\t</dcscor:value>',
                   o + '\t\t<dcsset:userSettingID>%s</dcsset:userSettingID>' % stable_uid(v['name'] + '/period/' + query[:60]),
                   o + '\t</dcscor:item>']
        for pn, pval in v.get('data_params', ()):
            dp += [o + '\t<dcscor:item xsi:type="dcsset:SettingsParameterValue">',
                   o + '\t\t<dcscor:parameter>%s</dcscor:parameter>' % pn,
                   o + '\t\t' + pval.replace('<value', '<dcscor:value').replace('</value>', '</dcscor:value>'),
                   o + '\t\t<dcsset:userSettingID>%s</dcsset:userSettingID>' % stable_uid(v['name'] + '/p/' + pn + query[:60]),
                   o + '\t</dcscor:item>']
        if dp:
            L += [o + '<dcsset:dataParameters>'] + dp + [o + '</dcsset:dataParameters>']
        if v.get('order'):
            L.append(o + '<dcsset:order>')
            for f, d in v['order']:
                L += [o + '\t<dcsset:item xsi:type="dcsset:OrderItemField">', o + '\t\t<dcsset:field>%s</dcsset:field>' % f,
                      o + '\t\t<dcsset:orderType>%s</dcsset:orderType>' % d, o + '\t</dcsset:item>']
            L.append(o + '</dcsset:order>')
        L += _dcs_ca(v.get('ca', ()), o)
        L += [o + '<dcsset:outputParameters>', o + '\t<dcscor:item xsi:type="dcsset:SettingsParameterValue">',
              o + '\t\t<dcscor:parameter>РасположениеРеквизитов</dcscor:parameter>',
              o + '\t\t<dcscor:value xsi:type="dcsset:DataCompositionAttributesPlacement">Separately</dcscor:value>',
              o + '\t</dcscor:item>']
        if v.get('totals_top'):
            # общий итог вверху (ВертикальноеРасположениеОбщихИтогов = Начало)
            L += [o + '\t<dcscor:item xsi:type="dcsset:SettingsParameterValue">',
                  o + '\t\t<dcscor:parameter>ВертикальноеРасположениеОбщихИтогов</dcscor:parameter>',
                  o + '\t\t<dcscor:value xsi:type="dcscor:DataCompositionTotalPlacement">Begin</dcscor:value>',
                  o + '\t</dcscor:item>']
        if not v.get('totals', True):
            for p in ('ГоризонтальноеРасположениеОбщихИтогов', 'ВертикальноеРасположениеОбщихИтогов'):
                L += [o + '\t<dcscor:item xsi:type="dcsset:SettingsParameterValue">',
                      o + '\t\t<dcscor:parameter>%s</dcscor:parameter>' % p,
                      o + '\t\t<dcscor:value xsi:type="dcscor:DataCompositionTotalPlacement">None</dcscor:value>',
                      o + '\t</dcscor:item>']
        L += [o + '\t<dcscor:item xsi:type="dcsset:SettingsParameterValue">', o + '\t\t<dcscor:parameter>Заголовок</dcscor:parameter>']
        L += _local_string('dcscor:value', v.get('output_title', v['title']), o + '\t\t')
        L += [o + '\t</dcscor:item>', o + '</dcsset:outputParameters>']
        L += _dcs_structure(v.get('groups', []), o, v.get('detail', True), v.get('level_ca', ()))
        L += ['\t\t</dcsset:settings>', '\t</settingsVariant>']
    L += ['</DataCompositionSchema>', '']
    return join(L)


def add_predefined_items(text, items):
    """Плоские предопределённые элементы справочника/ПВХ в .mdo (идемпотентно по имени).
    items — [(Имя, Наименование, Код|None, это_группа, тип|None)]; тип — спецификация
    type_xml (для ПВХ). Блок <predefined> встаёт после <defaultPresentation> (или после
    descriptionLength), как в eamРесурсныеСпецификации / ОбъектыАдресацииЗадач.
    Вложенные предопределённые (иерархия) не поддерживаются — создавать обработчиком
    обновления ИБ."""
    block = []
    for name, descr, code, folder, spec in items:
        if ('<name>%s</name>' % name) in text:
            continue
        block += ['    <items id="%s">' % stable_uid('predefined/' + name + descr),
                  '      <name>%s</name>' % name, '      <description>%s</description>' % esc(descr)]
        if code:
            block += ['      <code xsi:type="core:StringValue">', '        <value>%s</value>' % esc(code),
                      '      </code>']
        if spec:
            block += type_xml(spec, 6)
        if folder:
            block.append('      <isFolder>true</isFolder>')
        block.append('    </items>')
    if not block:
        return text, False
    if '  </predefined>' in text:
        i = text.index('  </predefined>')
        return text[:i] + CRLF.join(block) + CRLF + text[i:], True
    for anchor in ('  <defaultPresentation>', '  <descriptionLength>'):
        i = text.find(anchor)
        if i >= 0:
            end = text.index(CRLF, i) + len(CRLF)
            return text[:end] + CRLF.join(['  <predefined>'] + block + ['  </predefined>']) + CRLF + text[end:], True
    raise ValueError('не найдено место для <predefined>')


def set_mdo_property(text, tag, value):
    """Замена значения простого свойства верхнего уровня .mdo (<tag>value</tag>, отступ 2):
    например descriptionLength/codeLength/numberLength/numberPeriodicity. Если свойства нет —
    ValueError (добавлять свойства этой функцией нельзя: порядок тегов задаёт схема)."""
    new, n = re.subn(r'(\r\n  <%s>)[^<]*(</%s>)' % (tag, tag), r'\g<1>%s\g<2>' % value, text, count=1)
    if not n:
        raise ValueError('нет свойства <%s>' % tag)
    return new


def extend_attribute_type(text, attr_name, type_names, ts_name=None):
    """Добавляет типы в составной тип существующего реквизита (шапки или ТЧ ts_name):
    type_names — ['DocumentRef.X', …]. Идемпотентно."""
    scope = text
    off = 0
    if ts_name:
        m = re.search(r'<tabularSections uuid="[^"]+">\s*(?:<producedTypes>.*?</producedTypes>\s*)?<name>%s</name>.*?</tabularSections>'
                      % re.escape(ts_name), text, re.S)
        scope, off = m.group(0), m.start()
    m = re.search(r'<attributes uuid="[^"]+">\s*<name>%s</name>.*?<type>(.*?)</type>' % re.escape(attr_name), scope, re.S)
    if not m:
        raise ValueError('нет реквизита %s' % attr_name)
    tb = m.group(1)
    ind = re.search(r'(\s*)<types>', tb).group(1)
    add = ''.join('%s<types>%s</types>' % (ind, t) for t in type_names if '<types>%s</types>' % t not in tb)
    if not add:
        return text, False
    last = tb.rfind('</types>') + len('</types>')
    pos = off + m.start(1) + last
    return text[:pos] + add + text[pos:], True


def add_document_ref_property(text, tag, value):
    """Строка-ссылка документа (идемпотентно): tag='basedOn' (ввод на основании, value='Document.X')
    или 'registerRecords' (регистратор, value='AccumulationRegister.X'). Встаёт после последней
    такой же строки; первая basedOn — перед createOnInput, первая registerRecords — перед
    postInPrivilegedMode (порядок снят с eamСмета / eamГрафикТОиР ФРЕГАТ EAM)."""
    line = '  <%s>%s</%s>' % (tag, value, tag)
    if line + CRLF in text:
        return text, False
    last = text.rfind('  <%s>' % tag)
    if last >= 0:
        end = text.index(CRLF, last) + len(CRLF)
    else:
        anchor = {'basedOn': '  <createOnInput>', 'registerRecords': '  <postInPrivilegedMode>'}[tag]
        end = text.index(anchor)
    return text[:end] + line + CRLF + text[end:], True


def common_command_mdo(name, syn, group='NavigationPanelOrdinary', tooltip=None, seed=None):
    """Общая команда без параметра (панель навигации раздела и т.п.); формат снят с
    БСП CommonCommand.ПанельОтчетовАдминистрирование (ФРЕГАТ EAM). Модуль — CommandModule.bsl
    с &НаКлиенте Процедура ОбработкаКоманды(ПараметрКоманды, ПараметрыВыполнения)."""
    s = seed or 'CommonCommand/' + name
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<mdclass:CommonCommand xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass" uuid="%s">' % stable_uid(s),
             '  <name>%s</name>' % name]
    lines += synonym(syn, 2)
    lines += ['  <group>%s</group>' % group, '  <representation>Auto</representation>']
    if tooltip:
        lines += ['  <toolTip>', '    <key>ru</key>', '    <value>%s</value>' % esc(tooltip), '  </toolTip>']
    lines += ['</mdclass:CommonCommand>', '']
    return join(lines)


def object_command(owner, name, syn, param_type, group='FormCommandBarImportant', multiple=False, tooltip=None):
    """Команда объекта (обработки, отчёта, документа) с параметром: платформа сама выводит её в
    формы объектов типа param_type (группа FormCommandBarImportant — командная панель формы с
    autoFill, FormNavigationPanelImportant — панель навигации), сама форма не меняется.
    Возвращает текст <commands> — вставлять ПОСЛЕДНИМ перед закрывающим тегом .mdo (после
    forms/templates). owner — 'DataProcessor.Имя' для устойчивого uuid. Формат снят с
    КоммерческоеПредложение.Печать и СтатистикаЗадач.СтатистикаПоЗадаче (UP, 2026-10).
    Модуль — Commands/<name>/CommandModule.bsl: &НаКлиенте Процедура ОбработкаКоманды(
    ПараметрКоманды, ПараметрыВыполненияКоманды)."""
    lines = ['  <commands uuid="%s">' % stable_uid('%s/Command/%s' % (owner, name)), '    <name>%s</name>' % name]
    lines += synonym(syn, 4)
    lines += ['    <group>%s</group>' % group, '    <commandParameterType>',
              '      <types>%s</types>' % param_type, '    </commandParameterType>']
    if multiple:
        lines.append('    <parameterUseMode>Multiple</parameterUseMode>')
    lines.append('    <representation>Auto</representation>')
    if tooltip:
        lines += ['    <toolTip>', '      <key>ru</key>', '      <value>%s</value>' % esc(tooltip), '    </toolTip>']
    lines.append('  </commands>')
    return join(lines)


def scheduled_job_mdo(name, syn, method, use=True, predefined=True, seed=None):
    """Регламентное задание; method — 'CommonModule.Модуль.Процедура' (модуль серверный,
    процедура экспортная). Формат снят с bpmОтправкаУведомленийПоПочте (ФРЕГАТ EAM).
    Расписание — отдельный файл Schedule.schedule (schedule_file)."""
    s = seed or 'ScheduledJob/' + name
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<mdclass:ScheduledJob xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass" uuid="%s">' % stable_uid(s),
             '  <name>%s</name>' % name]
    lines += synonym(syn, 2)
    lines.append('  <methodName>%s</methodName>' % method)
    if use:
        lines.append('  <use>true</use>')
    if predefined:
        lines.append('  <predefined>true</predefined>')
    lines += ['  <restartCountOnFailure>3</restartCountOnFailure>',
              '  <restartIntervalOnFailure>10</restartIntervalOnFailure>', '</mdclass:ScheduledJob>', '']
    return join(lines)


def schedule_file(begin_time='00:00:00', repeat_period_in_day=0, days_repeat_period=1):
    """Schedule.schedule регламентного задания: ежедневно (все дни недели и месяцы) с
    begin_time; repeat_period_in_day — повтор в течение дня, сек (0 — один раз в сутки)."""
    attrs = ('beginDate="0001-01-01" endDate="0001-01-01" daysRepeatPeriod="%d" beginTime="%s" '
             'endTime="00:00:00" completionTime="00:00:00" repeatPeriodInDay="%d" weeksPeriod="1"'
             % (days_repeat_period, begin_time, repeat_period_in_day))
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<schedule:Schedule xmlns:schedule="http://g5.1c.ru/v8/dt/schedule" %s>' % attrs]
    lines += ['  <weekDays>%s</weekDays>' % d for d in ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')]
    lines += ['  <months>%s</months>' % m for m in ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug',
                                                     'Sep', 'Oct', 'Nov', 'Dec')]
    lines += ['</schedule:Schedule>', '']
    return join(lines)


def dcs_postprocess(text, hierarchy=(), group_filled=(), total_groups=()):
    """Дополнения к тексту схемы, который вернул edt_lib.dcs_schema_ex (формат снят с типовых схем ФРЕГАТ EAM (перенесено из G6.py, ТЗ-61…71):
    <group>ОбщийИтог</group> — ЗаменаИОбъединениеЭлементов, <group> — eamГрафикТОиР, отбор группировки Filled —
    ИнтерактивноеИзменениеВыгрузки):
      hierarchy     — поля группировок с типом «Иерархия» (groupType Hierarchy);
      group_filled  — поля, по группировке которых ставится отбор «Заполнено» (запись без значения не выводится);
      total_groups  — для каждого ресурса (в порядке totals) список группировок <group>;
      пустой <groupItems> (уровень детальных записей со своим оформлением) удаляется."""
    t = text.replace("\r\n", "\n")
    for f in hierarchy:
        t, n = re.subn(r"(<dcsset:field>%s</dcsset:field>\n\t*<dcsset:groupType>)Items(</dcsset:groupType>)"
                       % re.escape(f), r"\1Hierarchy\2", t)
        assert n, "нет группировки %s" % f
    for f in group_filled:
        pat = re.compile(r"(\n(\t*)<dcsset:groupItems>\n\t*<dcsset:item xsi:type=\"dcsset:GroupItemField\">\n"
                         r"\t*<dcsset:field>%s</dcsset:field>.*?\n\t*</dcsset:groupItems>)" % re.escape(f), re.S)

        def rep(m, f=f):
            o = m.group(2)
            return m.group(1) + "\n".join([
                "", o + "<dcsset:filter>", o + "\t<dcsset:item xsi:type=\"dcsset:FilterItemComparison\">",
                o + "\t\t<dcsset:left xsi:type=\"dcscor:Field\">%s</dcsset:left>" % f,
                o + "\t\t<dcsset:comparisonType>Filled</dcsset:comparisonType>",
                o + "\t</dcsset:item>", o + "</dcsset:filter>"])
        t, n = pat.subn(rep, t)
        assert n, "нет группировки %s для отбора" % f
    t = re.sub(r"\n\t*<dcsset:groupItems>\n\t*</dcsset:groupItems>", "", t)
    if any(total_groups):
        blocks = list(re.finditer(r"\t<totalField>\n.*?\n\t</totalField>", t, re.S))
        assert len(blocks) == len(total_groups), "ресурсов %d, групп %d" % (len(blocks), len(total_groups))
        out, pos = [], 0
        for m, grs in zip(blocks, total_groups):
            body = t[m.start():m.end() - len("\t</totalField>")]
            out.append(t[pos:m.start()] + body + "".join("\t\t<group>%s</group>\n" % x for x in grs)
                       + "\t</totalField>")
            pos = m.end()
        out.append(t[pos:])
        t = "".join(out)
    return t


def add_child_subsystem(parent_text, child_name):
    """Ссылка родителя на дочернюю подсистему: <subsystems>Имя</subsystems> (короткое имя, как в
    подсистемах ФРЕГАТ EAM) — после последней такой строки, иначе в конец перед закрывающим тегом.
    Саму дочернюю подсистему строить subsystem_mdo(..., parent=<родитель>) в папке
    Subsystems/<Родитель>/Subsystems/<Имя>/<Имя>.mdo (case 019)."""
    line = '  <subsystems>%s</subsystems>' % child_name
    if line + CRLF in parent_text:
        return parent_text, False
    last = parent_text.rfind('  <subsystems>')
    if last >= 0:
        end = parent_text.index(CRLF, last) + len(CRLF)
    else:
        end = parent_text.index('</mdclass:Subsystem>')
    return parent_text[:end] + line + CRLF + parent_text[end:], True


def remove_content_from_subsystem(text, full_names):
    """Убрать строки <content>Вид.Имя</content> из подсистемы (перенос объекта в дочернюю подсистему)."""
    removed = []
    for fn in full_names:
        line = '  <content>%s</content>' % fn + CRLF
        if line in text:
            text = text.replace(line, '', 1)
            removed.append(fn)
    return text, removed


def set_attribute_type(text, attr_name, spec):
    """Замена типа существующего реквизита шапки (блок <type> на отступе 4) на spec в нотации type_xml —
    для безопасных расширений (Число(3,0) → Число+(4,1), длина строки больше). Идемпотентно."""
    m = re.search(r'(\r\n  <attributes uuid="[^"]+">\r\n    <name>%s</name>.*?)(\r\n    <type>.*?\r\n    </type>)'
                  % re.escape(attr_name), text, re.S)
    if not m:
        raise ValueError('нет реквизита %s' % attr_name)
    new_type = CRLF + CRLF.join(type_xml(spec, 4))
    if m.group(2) == new_type:
        return text, False
    return text[:m.start(2)] + new_type + text[m.end(2):], True


def add_register_fields(text, tag, fields, register_kind='InformationRegister'):
    """Измерения/ресурсы/реквизиты в СУЩЕСТВУЮЩИЙ регистр, в том числе в регистр без ресурсов
    (tag: 'resources' | 'dimensions' | 'attributes'; fields — [(имя, синоним, тип)]). Порядок блоков
    в .mdo регистра: resources → attributes → dimensions → forms (снято с eamСтоимостьТМЦ ФРЕГАТ EAM)."""
    order = ['resources', 'attributes', 'dimensions', 'forms', 'commands', 'templates']
    added = []
    for n, sy, sp in fields:
        if re.search(r'<(resources|dimensions|attributes) uuid="[^"]+">\s*<name>%s</name>' % re.escape(n), text):
            continue
        extra = ['<mainFilter>true</mainFilter>'] if (tag == 'dimensions' and register_kind == 'InformationRegister') else []
        block = attribute(n, sy, sp, 2, tag=tag, extra_before_close=extra)
        last = text.rfind('\r\n  </%s>' % tag)
        if last >= 0:
            pos = text.index(CRLF, last + 2) + len(CRLF)
        else:
            pos = None
            for later in order[order.index(tag) + 1:]:
                m = re.search(r'\r\n  <%s ' % later, text)
                if m:
                    pos = m.start() + len(CRLF)
                    break
            if pos is None:
                pos = text.index('</mdclass:')
        text = text[:pos] + CRLF.join(block) + CRLF + text[pos:]
        added.append(n)
    return text, added


def picture_zip(path, draw):
    """Picture.zip общей картинки из функции рисования draw(size) -> PIL.Image (RGBA, size×size):
    восемь масштабов PICTURE_SCALES + Picture.png 16 px (интерфейс 8.2) + manifest.xml (раздел 3
    knowledge/subsystems-and-ui.md). Рисовать лучше крупно и уменьшать LANCZOS внутри draw."""
    import zipfile
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for fname, size, _d in PICTURE_SCALES:
            buf = io.BytesIO()
            draw(size).save(buf, 'PNG', optimize=True)
            z.writestr(fname, buf.getvalue())
        buf = io.BytesIO()
        draw(16).save(buf, 'PNG', optimize=True)
        z.writestr('Picture.png', buf.getvalue())
        z.writestr('manifest.xml', picture_manifest().encode('utf-8'))


def set_subsystem_picture(text, picture_name):
    """<picture xsi:type="core:PictureRef"> подсистемы: после explanation / includeInCommandInterface
    (порядок как у типового «Администрирование»), с пространствами имён xsi и core в корне, если их нет.
    Идемпотентно; заменяет прежнюю картинку."""
    if 'xmlns:xsi=' not in text.split('\n', 2)[1]:
        text = text.replace('<mdclass:Subsystem xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass"',
                            '<mdclass:Subsystem ' + XMLNS_MD, 1)
    block = CRLF.join(['  <picture xsi:type="core:PictureRef">',
                       '    <picture>CommonPicture.%s</picture>' % picture_name, '  </picture>'])
    m = re.search(r'  <picture xsi:type="core:PictureRef">\r?\n.*?\r?\n  </picture>', text)
    if m:
        return text[:m.start()] + block + text[m.end():]
    for anchor in (r'  </explanation>\r?\n', r'  <includeInCommandInterface>[^<]*</includeInCommandInterface>\r?\n'):
        m = re.search(anchor, text)
        if m:
            return text[:m.end()] + block + CRLF + text[m.end():]
    raise ValueError('нет места для <picture> в подсистеме')


def set_configuration_splash(config_text):
    """<splash/> в Configuration.mdo — заставка берётся из src/Configuration/Splash.png (формат снят с
    УАТ МВМ, EDT 2026.1: картинка 600×255). Встаёт перед copyright / defaultReportForm, иначе после
    version. Идемпотентно."""
    if '<splash/>' in config_text:
        return config_text, False
    for tag in ('copyright', 'vendorInformationAddress', 'configurationInformationAddress', 'defaultReportForm'):
        m = re.search(r'\r?\n  <%s[ >]' % tag, config_text)
        if m:
            pos = m.start() + (2 if config_text[m.start()] == '\r' else 1)
            return config_text[:pos] + '  <splash/>' + CRLF + config_text[pos:], True
    m = re.search(r'  <version>[^<]*</version>\r?\n', config_text)
    return config_text[:m.end()] + '  <splash/>' + CRLF + config_text[m.end():], True


def style_mdo(name, syn, seed=None):
    """Объект метаданных «Стиль» (src/Styles/Имя/Имя.mdo). Сами элементы — внешнее свойство style,
    файл Style.style (style_file). Модель: MdClass.xcore class Style / Style.xcore (EDT 2026.1)."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<mdclass:Style xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass" uuid="%s">'
             % stable_uid(seed or 'Style/' + name),
             '  <name>%s</name>' % name]
    lines += synonym(syn, 2)
    lines += ['</mdclass:Style>', '']
    return join(lines)


def style_file(colors):
    """Style.style: переопределения системных цветов стиля платформы (FormBackColor, ButtonBackColor, BorderColor,
    FieldBackColor, ToolTipBackColor…). colors — [(ИмяЭлементаСтиля, (r, g, b))]. Цвет — core:ColorDef, как
    значение элемента стиля (StyleItems/*.mdo) в проекте."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<style:Style xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
             'xmlns:core="http://g5.1c.ru/v8/dt/mcore" xmlns:style="http://g5.1c.ru/v8/dt/style">']
    for name, (r, g, b) in colors:
        lines += ['  <items xsi:type="style:ColorStyleItem">', '    <name>%s</name>' % name,
                  '    <color xsi:type="core:ColorDef">', '      <red>%d</red>' % r, '      <green>%d</green>' % g,
                  '      <blue>%d</blue>' % b, '    </color>', '  </items>']
    lines += ['</style:Style>', '']
    return join(lines)


def set_default_style(config_text, style_name):
    """<defaultStyle>Style.Имя</defaultStyle> в Configuration.mdo (основной стиль конфигурации). Встаёт перед
    defaultLanguage (порядок свойств MdClass.xcore: …shortCaption, defaultStyle, defaultLanguage…). Идемпотентно."""
    tag = '  <defaultStyle>Style.%s</defaultStyle>' % style_name
    if tag in config_text:
        return config_text, False
    m = re.search(r'  <defaultStyle>[^<]*</defaultStyle>\r?\n', config_text)
    if m:
        return config_text[:m.start()] + tag + CRLF + config_text[m.end():], True
    m = re.search(r'\r?\n  <defaultLanguage>', config_text)
    pos = m.start() + (2 if config_text[m.start()] == '\r' else 1)
    return config_text[:pos] + tag + CRLF + config_text[pos:], True


def html_field_ex(ids, name, data_path, indent, on_complete=None, on_click=None, width=70, height=10):
    """Поле HTML с обработчиками DocumentComplete и OnClick (ДанныеСобытия.href — щелчок по ссылке
    страницы). Порядок обработчиков в HtmlFieldExtInfo — DocumentComplete, затем OnClick (снято с
    УАТ МВМ Catalog.Новости.ФормаНовости; одиночный OnClick — БСП DataProcessor.ИнформацияПриЗапуске).
    Остальное — как html_field (width/height обязательны вместе с растяжением, case 022)."""
    lines = html_field(ids, name, data_path, indent, on_complete=on_complete, width=width, height=height)
    if on_click:
        o = ' ' * (indent + 4)
        block = [o + '<handlers>', o + '  <event>OnClick</event>', o + '  <name>%s</name>' % on_click,
                 o + '</handlers>']
        pos = [i for i, l in enumerate(lines) if l.strip() == '<extInfo xsi:type="form:HtmlFieldExtInfo">'][0] + 1
        if on_complete:
            pos += 4
        lines[pos:pos] = block
    return lines


def write_binary(path, data):
    """Двоичный макет (templateType BinaryData): EDT хранит его СЫРЫМ файлом
    <Объект>/Templates/<Макет>/Template.bin — байты как есть, без обёртки (снято с БСП
    DataProcessor.СкрытиеКонфиденциальнойИнформации.Template.НастройкиБСП и
    Catalog.ЕдиницыИзмерения.КлассификаторЕдиницИзмерения; knowledge/html-field-and-templates.md §2).
    Текст JS/HTML удобнее класть так, чем текстовым макетом: нет лимита длины строки и склейки
    по Символ(1) (case 023). На сервере: ПолучитьСтрокуИзДвоичныхДанных(ПолучитьМакет(…), КодировкаТекста.UTF8).
    Пишет только при изменении; возвращает True, если записал."""
    if os.path.exists(path) and io.open(path, 'rb').read() == data:
        return False
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    io.open(path, 'wb').write(data)
    return True


def home_page_work_area(forms, template='OneColumn'):
    """src/Configuration/HomePageWorkArea.hpwa — состав начальной страницы (свойства в
    Configuration.mdo нет, case 061). forms — [(полное имя формы, высота)], например
    ('DataProcessor.X.Form.Форма', 10). Формат снят с УАТ МВМ (EDT 2026.1) и
    cases/061-home-page-work-area-file/after: шаблон OneColumn, <columns><items> с form/height/
    <visibility><common>true</common>. ВНИМАНИЕ: пустой <visibility/> выгружается как Видимость.Общая = Ложь —
    форма на начальной странице скрыта для всех (ФРЕГАТ EAM, проверено загрузкой в 8.5.1.1529).
    Разметку двух колонок в образцах не встречали — поддержан только OneColumn."""
    if template != 'OneColumn':
        raise ValueError('home_page_work_area: образец есть только для OneColumn')
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<hpwa:HomePageWorkArea xmlns:hpwa="http://g5.1c.ru/v8/dt/hpwa">',
             '  <workingAreaTemplate>%s</workingAreaTemplate>' % template, '  <columns>']
    for form, height in forms:
        lines += ['    <items>', '      <form>%s</form>' % form, '      <height>%d</height>' % height,
                  '      <visibility>', '        <common>true</common>', '      </visibility>', '    </items>']
    lines += ['  </columns>', '</hpwa:HomePageWorkArea>', '']
    return join(lines)


def add_form_to_home_page(text, form, height=10, first=True):
    """Добавить форму в существующий HomePageWorkArea.hpwa (первой или последней в <columns>),
    не трогая остальные формы. Идемпотентно: (текст, добавлена ли)."""
    if '<form>%s</form>' % form in text:
        return text, False
    block = CRLF.join(['    <items>', '      <form>%s</form>' % form, '      <height>%d</height>' % height,
                       '      <visibility>', '        <common>true</common>', '      </visibility>',
                       '    </items>']) + CRLF
    m = re.search(r'  <columns>\r?\n', text)
    if m and first:
        return text[:m.end()] + block + text[m.end():], True
    m = re.search(r'  </columns>\r?\n', text)
    if m:
        return text[:m.start()] + block + text[m.start():], True
    m = re.search(r'</hpwa:HomePageWorkArea>', text)
    return text[:m.start()] + '  <columns>' + CRLF + block + '  </columns>' + CRLF + text[m.start():], True


# ============================================================ перекомпоновка СУЩЕСТВУЮЩЕЙ Form.form (текст)
# Разбор готовой формы на элементы <items> по отступам (как пишет EDT: 2 пробела на уровень), перенос
# элементов в новые группы без переписывания их XML (id, dataPath, обработчики не меняются), правка
# ширины/заголовка поля в порядке тегов EDT. Группы — usual_group (четыре свойства, case 007).

class FormNode(object):
    """Элемент <items> существующей формы: строки [start, end] (включительно) списка строк формы,
    отступ, имя, xsi-вид (FormField/FormGroup/Button/Decoration/Table), <type> (UsualGroup, Page,
    InputField, …), свой id и id расширенной подсказки."""

    def __init__(self, lines, start, end, indent):
        self.start, self.end, self.indent = start, end, indent
        m = re.search(r'xsi:type="form:(\w+)"', lines[start])
        self.xsi = m.group(1) if m else None
        m = re.match(r'\s*<name>(.*)</name>$', lines[start + 1])
        self.name = m.group(1) if m else None
        self.kind = self.id = self.tooltip_id = None
        own = ' ' * (indent + 2)
        k = start + 1
        while k < end:
            line = lines[k]
            if line.startswith(own + '<'):
                s = line[len(own):]
                if s.startswith('<type>') and self.kind is None:
                    self.kind = re.match(r'<type>(\w+)</type>', s).group(1)
                elif s.startswith('<id>') and self.id is None:
                    self.id = int(re.match(r'<id>(-?\d+)</id>', s).group(1))
                elif s == '<extendedTooltip>' and self.tooltip_id is None:
                    for j in range(k + 1, end):
                        mm = re.match(r'%s  <id>(-?\d+)</id>$' % own, lines[j])
                        if mm:
                            self.tooltip_id = int(mm.group(1))
                            break
                        if lines[j] == own + '</extendedTooltip>':
                            break
            k += 1

    def block(self, lines):
        return lines[self.start:self.end + 1]

    def is_container(self):
        """Группа, в которую можно заходить: обычная группа, страница, страницы (не таблица и не панель)."""
        return self.xsi == 'FormGroup' and self.kind in ('UsualGroup', 'Page', 'Pages')


def form_children(lines, parent=None):
    """Прямые дочерние <items> корня формы (parent=None, отступ 2) или элемента parent."""
    if parent is None:
        lo, hi, ind = 0, len(lines), 2
    else:
        lo, hi, ind = parent.start + 1, parent.end, parent.indent + 2
    opening, closing = ' ' * ind + '<items ', ' ' * ind + '</items>'
    out, i = [], lo
    while i < hi:
        if lines[i].startswith(opening):
            if lines[i].rstrip().endswith('/>'):
                raise ValueError('пустой элемент <items/> в строке %d' % (i + 1))
            j = i + 1
            while lines[j] != closing:
                j += 1
            out.append(FormNode(lines, i, j, ind))
            i = j + 1
        else:
            i += 1
    return out


def form_find(lines, name):
    """Элемент формы по имени (любой вложенности) или None."""
    for i in range(1, len(lines)):
        s = lines[i].lstrip(' ')
        if s == '<name>%s</name>' % name:
            ind = len(lines[i]) - len(s) - 2
            if ind >= 2 and lines[i - 1].startswith(' ' * ind + '<items '):
                closing = ' ' * ind + '</items>'
                j = i
                while lines[j] != closing:
                    j += 1
                return FormNode(lines, i - 1, j, ind)
    return None


def form_walk(lines, node):
    """Все элементы поддерева node (включая сам node), в порядке документа; в таблицы и панели не заходит."""
    out = [node]
    if node.is_container():
        for ch in form_children(lines, node):
            out += form_walk(lines, ch)
    return out


def form_max_item_id(text):
    """Наибольший id пространства элементов (items + autoCommandBar, до <attributes>)."""
    cut = text.find(CRLF + '  <attributes>')
    part = text if cut < 0 else text[:cut]
    return max([0] + [int(x) for x in re.findall(r'<id>(-?\d+)</id>', part)])


def reindent_lines(block, delta):
    """Сдвиг блока элемента на delta пробелов. Многострочный текст внутри значения сдвиг бы испортил —
    такие блоки не переносим (исключение)."""
    if not block:
        return []
    base = len(block[0]) - len(block[0].lstrip(' '))
    for line in block:
        if line.strip() and (not line.startswith(' ' * base) or not line.lstrip(' ').startswith('<')):
            raise ValueError('в блоке элемента многострочный текст — перенос сдвигом отступа невозможен: %r'
                             % line[:60])
    if delta >= 0:
        return [' ' * delta + line if line else line for line in block]
    if base < -delta:
        raise ValueError('отступ блока меньше сдвига')
    return [line[-delta:] if line else line for line in block]


def _xml_chunks(lines, lo, hi, ind):
    """Дочерние теги на отступе ind в строках [lo, hi): [(тег, начало, конец включительно)]."""
    out, k, pre = [], lo, ' ' * ind + '<'
    while k < hi:
        line = lines[k]
        if not line.startswith(pre) or line.startswith(pre + '/'):
            k += 1
            continue
        tag = re.match(r'<([\w:]+)', line[ind:]).group(1)
        if line.rstrip().endswith('/>') or '</%s>' % tag in line:
            out.append((tag, k, k))
            k += 1
            continue
        j = k + 1
        while lines[j] != ' ' * ind + '</%s>' % tag:
            j += 1
        out.append((tag, k, j))
        k = j + 1
    return out


FIELD_WIDTH_TAGS = ('width', 'autoMaxWidth', 'maxWidth', 'horizontalStretch')
_BEFORE_STRETCH = ('handlers', 'width', 'autoMaxWidth', 'maxWidth', 'height', 'autoMaxHeight', 'maxHeight')


def set_field_width(block, width=None, stretch=None):
    """Ширина поля ввода/надписи (блок <items> поля). Порядок тегов extInfo — как пишет EDT:
    handlers → width → autoMaxWidth → maxWidth → height → autoMaxHeight → maxHeight →
    horizontalStretch → verticalStretch → wrap … . Прежние width/autoMaxWidth/maxWidth/
    horizontalStretch заменяются: width пишется ВМЕСТЕ с autoMaxWidth=true (case 008);
    stretch=False — поле не растягивается шире width, True — тянется на ширину группы,
    None — растяжение не пишется (авто). Флажки и прочие поля — без изменений."""
    block = list(block)
    ind = len(block[0]) - len(block[0].lstrip(' '))
    own = ' ' * (ind + 2)
    try:
        s = next(k for k, l in enumerate(block)
                 if re.match(own + r'<extInfo xsi:type="form:(InputFieldExtInfo|LabelFieldExtInfo)">$', l))
    except StopIteration:
        return block
    e = block.index(own + '</extInfo>', s)
    chunks = [c for c in _xml_chunks(block, s + 1, e, ind + 4)]
    kept = []
    for tag, a, b in chunks:
        if tag not in FIELD_WIDTH_TAGS:
            kept.append((tag, block[a:b + 1]))
    o = own + '  '
    head = []
    if width:
        head.append(('width', [o + '<width>%d</width>' % width]))
    head.append(('autoMaxWidth', [o + '<autoMaxWidth>true</autoMaxWidth>']))
    pos = 0
    while pos < len(kept) and kept[pos][0] == 'handlers':
        pos += 1
    kept[pos:pos] = head
    if stretch is not None:
        pos = 0
        for i, (tag, _) in enumerate(kept):
            if tag in _BEFORE_STRETCH:
                pos = i + 1
        kept[pos:pos] = [('horizontalStretch', [o + '<horizontalStretch>%s</horizontalStretch>'
                                                % str(bool(stretch)).lower()])]
    body = [l for _, ls in kept for l in ls]
    return block[:s + 1] + body + block[e:]


def set_item_title(block, text):
    """Заголовок элемента (<title> сразу за <id>, порядок EDT; заменяется целиком, если был)."""
    block = list(block)
    ind = len(block[0]) - len(block[0].lstrip(' '))
    own = ' ' * (ind + 2)
    new = title_xml(text, ind + 2)
    chunks = _xml_chunks(block, 1, len(block) - 1, ind + 2)
    for tag, a, b in chunks:
        if tag == 'title':
            return block[:a] + new + block[b + 1:]
    k = next(k for k, l in enumerate(block) if l.startswith(own + '<id>'))
    return block[:k + 1] + new + block[k + 1:]


class PresetIds(object):
    """Счётчик id, который сначала отдаёт заданные номера (сохранить id пересоздаваемой группы и её
    подсказки), затем — из общего счётчика fallback (Ids)."""

    def __init__(self, preset, fallback):
        self.preset = [x for x in preset if x is not None]
        self.fallback = fallback

    def __call__(self):
        return self.preset.pop(0) if self.preset else self.fallback()
