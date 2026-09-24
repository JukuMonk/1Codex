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
    elif re.match(r'^Число\(\d+,\d+\)$', spec):
        prec, scale = re.findall(r'\d+', spec)
        lines += [o + '  <types>Number</types>', o + '  <numberQualifiers>',
                  o + '    <precision>%s</precision>' % prec]
        if int(scale):
            lines.append(o + '    <scale>%s</scale>' % scale)
        lines.append(o + '  </numberQualifiers>')
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
                    'ОпределяемыйТип.': 'DefinedType.'}
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
    lines = [o + '<tabularSections uuid="%s">' % (stable_uid(seed) if seed else uid()),
             o + '  <name>%s</name>' % name]
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
                comment=None, forms=(), default_forms=(), seed=None):
    """Справочник. forms — [(имя, синоним)], default_forms —
    [('defaultObjectForm', 'ФормаЭлемента'), ...].
    manual_code=True: код — ключ, а не номер (autonumbering=false,
    fillChecking у Code)."""
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
    lines += ['  <codeLength>%d</codeLength>' % code_length,
              '  <descriptionLength>%d</descriptionLength>' % description_length,
              '  <codeType>String</codeType>',
              '  <codeAllowedLength>Variable</codeAllowedLength>',
              '  <checkUnique>true</checkUnique>',
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
                             forms=(), default_forms=(), seed=None):
    """Независимый непериодический регистр сведений (writeMode и периодичность
    по умолчанию, поэтому тегов нет). Имена ресурсов НЕ должны быть
    ключевыми словами запроса («С», «По» — case 016)."""
    s = seed or 'InformationRegister/' + name
    for n, _, _ in list(dimensions) + list(resources):
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
    for fname, fsyn in forms:
        lines += form_ref_block('InformationRegister', name, fname, fsyn, seed=s + '/form/' + fname)
    lines += ['</mdclass:InformationRegister>', '']
    return join(lines)


def accumulation_register_mdo(name, syn, dimensions, resources, comment=None, seed=None):
    """Регистр накопления остатков. MEDIUM: структура снята с типового объекта
    (у нас своих регистров накопления не было). У измерений и ресурсов
    регистра НЕТ fillValue/dataHistory — только minValue/maxValue/
    fullTextSearch, у измерений плюс useInTotals; ресурсы идут ДО измерений."""
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
    for dn, dsyn, dspec in dimensions:
        lines += reg_attr('dimensions', dn, dsyn, dspec, ['<useInTotals>true</useInTotals>'])
    lines += ['</mdclass:AccumulationRegister>', '']
    return join(lines)


def document_mdo(name, syn, attributes=(), tabular_sections=(), number_length=11,
                 forms=(), default_forms=(), register_records=(), posting=True,
                 comment=None, seed=None):
    """Документ. MEDIUM: порядок тегов снят с типового документа (своих
    документов в проекте-источнике не заводили — рейсы и заявки типовые)."""
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
    lines += ['  <createOnInput>Use</createOnInput>',
              '  <dataLockControlMode>Managed</dataLockControlMode>',
              '  <fullTextSearch>Use</fullTextSearch>',
              '  <numberType>String</numberType>',
              '  <numberLength>%d</numberLength>' % number_length,
              '  <numberAllowedLength>Variable</numberAllowedLength>',
              '  <checkUnique>true</checkUnique>',
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
    if global_:
        lines.append('  <global>true</global>')
    if client_managed:
        lines.append('  <clientManagedApplication>true</clientManagedApplication>')
    if server:
        lines.append('  <server>true</server>')
    if not client_managed:
        lines.append('  <clientOrdinaryApplication>false</clientOrdinaryApplication>')
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


def object_tabular_table(ids, name, ts_path, columns, indent, editable=True):
    """Таблица ТАБЛИЧНОЙ ЧАСТИ объекта (Объект.ИмяТЧ) на форме элемента /
    документа: первая колонка — номер строки (LabelField), остальные —
    поля ввода. Собрана по образцу вставки вкладки с ТЧ в типовую форму."""
    o = ' ' * indent
    lines = [o + '<items xsi:type="form:Table">', o + '  <name>%s</name>' % name,
             o + '  <id>%d</id>' % ids(), o + '  <visible>true</visible>',
             o + '  <enabled>true</enabled>', o + '  <userVisible>',
             o + '    <common>true</common>', o + '  </userVisible>',
             o + '  <dataPath xsi:type="form:DataPath">', o + '    <segments>%s</segments>' % ts_path,
             o + '  </dataPath>', o + '  <titleLocation>None</titleLocation>']
    lines += field(ids, name + 'НомерСтроки', ts_path + '.LineNumber', indent + 2, 'LabelField')
    for cname in columns:
        lines += field(ids, name + cname, '%s.%s' % (ts_path, cname), indent + 2)
    lines += [o + '  <autoCommandBar>', o + '    <name>%sКоманднаяПанель</name>' % name,
              o + '    <id>%d</id>' % ids(), o + '    <horizontalAlign>Left</horizontalAlign>',
              o + '    <autoFill>true</autoFill>', o + '  </autoCommandBar>']
    lines += table_companions(ids, name, indent + 2)
    lines += tooltip(name, ids(), indent + 2)
    lines += context_menu(name, ids(), indent + 2)
    ed = 'true' if editable else 'false'
    lines += [o + '  <changeRowSet>%s</changeRowSet>' % ed, o + '  <changeRowOrder>%s</changeRowOrder>' % ed,
              o + '  <autoMaxWidth>true</autoMaxWidth>', o + '  <autoMaxHeight>true</autoMaxHeight>',
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
}

FOLDERS = {
    'Subsystem': 'Subsystems', 'CommonModule': 'CommonModules', 'CommonPicture': 'CommonPictures',
    'Role': 'Roles', 'Constant': 'Constants', 'Catalog': 'Catalogs', 'Document': 'Documents',
    'Enum': 'Enums', 'Report': 'Reports', 'DataProcessor': 'DataProcessors',
    'InformationRegister': 'InformationRegisters', 'AccumulationRegister': 'AccumulationRegisters',
    'ChartOfCharacteristicTypes': 'ChartsOfCharacteristicTypes', 'CommonForm': 'CommonForms',
    'CommonCommand': 'CommonCommands', 'DefinedType': 'DefinedTypes',
}


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
        raise ValueError('в Configuration.mdo нет группы <%s>' % tag)
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
    new = [a for a in attributes if ('<name>%s</name>' % a[0]) not in text]
    if new:
        block = []
        for a in new:
            block += attribute(a[0], a[1], a[2], 2, required=(len(a) > 3 and a[3] == 'обязательный'))
            added.append('реквизит ' + a[0])
        text = _insert_after_last(text, CLOSE_ATTR, block, 'реквизиты')
    new_ts = [t for t in tabular_sections if ('<name>%s</name>' % t['name']) not in text]
    if new_ts:
        block = []
        for t in new_ts:
            block += tabular_section(t['name'], t['synonym'], t['attributes'], 2)
            added.append('ТЧ ' + t['name'])
        anchor = CLOSE_TS if CLOSE_TS in text else CLOSE_ATTR
        text = _insert_after_last(text, anchor, block, 'табличные части')
    return text, added


def _insert_after_last(text, anchor, block, what):
    pos = text.rfind(anchor)
    if pos < 0:
        raise ValueError('не найдено место для вставки (%s)' % what)
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
    block = ['  <forms uuid="%s">' % uid(), '    <name>%s</name>' % form_name]
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
          default_item=False, title_location=None, multiline=False, input_hint=None):
    """Поле формы. Порядок тегов — как пишет EDT: title за id, handlers за
    dataPath, значения по умолчанию не пишутся (case 027).
    kind: InputField | CheckBoxField | LabelField.
    width без max_width — поле вне колонок тянется до края формы; типовая
    у узких полей пишет width ВМЕСТЕ с autoMaxWidth=true (case 008)."""
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
            if max_width:
                lines.append(o + '    <autoMaxWidth>true</autoMaxWidth>')
        else:
            lines.append(o + '    <autoMaxWidth>true</autoMaxWidth>')
        if multiline:
            lines += [o + '    <height>3</height>', o + '    <autoMaxHeight>true</autoMaxHeight>',
                      o + '    <horizontalStretch>true</horizontalStretch>',
                      o + '    <verticalStretch>false</verticalStretch>',
                      o + '    <wrap>true</wrap>', o + '    <multiLine>true</multiLine>',
                      o + '    <extendedEdit>true</extendedEdit>']
        else:
            lines += [o + '    <autoMaxHeight>true</autoMaxHeight>', o + '    <wrap>true</wrap>']
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


def bar_button(ids, name, indent, default=False):
    """Кнопка в командной панели (без <type>): так пишет EDT для панели."""
    o = ' ' * indent
    lines = [o + '<items xsi:type="form:Button">', o + '  <name>%s</name>' % name,
             o + '  <id>%d</id>' % ids(), o + '  <visible>true</visible>',
             o + '  <enabled>true</enabled>', o + '  <userVisible>',
             o + '    <common>true</common>', o + '  </userVisible>']
    lines += tooltip(name, ids(), indent + 2)
    lines += [o + '  <commandName>Form.Command.%s</commandName>' % name,
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
    форму целиком — пустой лист в EDT (case 001)."""
    o = ' ' * indent
    if kind == 'String':
        return [o + '<stringQualifiers/>']
    if kind == 'Number':
        return [o + '<numberQualifiers>', o + '  <precision>10</precision>', o + '</numberQualifiers>']
    if kind == 'Date':
        return [o + '<dateQualifiers>', o + '  <dateFractions>DateTime</dateFractions>', o + '</dateQualifiers>']
    return []


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
    lines += [o + '  <id>%d</id>' % nums(), o + '  <valueType>', o + '    <types>%s</types>' % kind]
    lines += _qualifiers(kind, indent + 4)
    lines += [o + '  </valueType>', o + '  <view>', o + '    <common>true</common>', o + '  </view>',
              o + '  <edit>', o + '    <common>true</common>', o + '  </edit>']
    if main:
        lines.append(o + '  <main>true</main>')
    if saved_data:
        lines.append(o + '  <savedData>true</savedData>')
    for cname, ctitle, ckind in columns:
        lines += [o + '  <columns>', o + '    <name>%s</name>' % cname]
        lines += title_xml(ctitle, indent + 4)
        lines += [o + '    <id>%d</id>' % nums(), o + '    <valueType>',
                  o + '      <types>%s</types>' % ckind]
        lines += _qualifiers(ckind, indent + 6)
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
              ext='form:ObjectFormExtInfo', window_mode=None, auto_bar_id=-1, auto_bar_fill=True):
    """Каркас Form.form. handlers — [(событие, процедура)]. Хвост в порядке
    модели EDT: autoCommandBar → handlers → windowOpeningMode →
    saveWindowSettings (без него EDT форму не рисует — case 002) → …"""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<form:Form %s>' % XMLNS_FORM]
    if title:
        lines += title_xml(title, 2)
    lines += items
    lines += ['  <autoCommandBar>', '    <name>ФормаКоманднаяПанель</name>',
              '    <id>%d</id>' % auto_bar_id, '    <horizontalAlign>Left</horizontalAlign>']
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


def check_bsl(text, is_form_module=True, hierarchical_catalogs=()):
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
        if s.startswith(('Процедура ', 'Функция ')):
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
    # 5) имена процедур: глобальные методы (case 047) и ключевые слова (case 057)
    for m in re.finditer(r'^\s*(?:Процедура|Функция)\s+([А-Яа-яЁёA-Za-z_][А-Яа-яЁёA-Za-z_0-9]*)', clean, re.M):
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
        if s.startswith(('Процедура ', 'Функция ')):
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
    # обработчики и команды — в модуле
    if module_text is not None:
        for proc in re.findall(r'<handlers>\s*<event>\w+</event>\s*<name>(\w+)</name>', text):
            if not re.search(r'^(Процедура|Функция)\s+%s\(' % re.escape(proc), module_text, re.M):
                problems.append('обработчик «%s» не описан в модуле формы' % proc)
        for name in re.findall(r'<handler>\s*<name>(\w+)</name>', text):
            if not re.search(r'^Процедура\s+%s\(' % re.escape(name), module_text, re.M):
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
