# -*- coding: utf-8 -*-
"""designer_lib — объекты 1С в формате ВЫГРУЗКИ КОНФИГУРАТОРА (DumpConfigToFiles) и
пакетный Конфигуратор для работы БЕЗ EDT.

edt_lib пишет формат EDT (.mdo, Form.form); здесь — XML Конфигуратора (MDClasses
2.20, logform), каким его выгружает 8.3.27. Эталоны сняты с живой выгрузки
1С:ТОИР КОРП 3.0.8.1 и её расширения (проект АЗОТ, октябрь 2026). Порядок тегов
и состав свойств — как в выгрузке: Конфигуратор ругается на лишнее и пропущенное.

Цикл без EDT (knowledge/designer-format.md):
    DumpConfigToFiles → git → правка (этот модуль + .bsl) → LoadConfigFromFiles -files
    → UpdateDBCfg → CheckModules → проверка через COM.

Файлы выгрузки: UTF-8 С BOM, CRLF, отступы табуляцией.
"""
import io
import os
import re
import subprocess
import time
import uuid
from xml.sax.saxutils import escape

# --------------------------------------------------------------------- общее
MD_NS = ('xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" '
         'xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" '
         'xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" '
         'xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" '
         'xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" '
         'xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" '
         'xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" '
         'xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" '
         'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"')
FORM_NS = ('xmlns="http://v8.1c.ru/8.3/xcf/logform" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" '
           'xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:dcscor="http://v8.1c.ru/8.1/data-composition-system/core" '
           'xmlns:dcssch="http://v8.1c.ru/8.1/data-composition-system/schema" xmlns:dcsset="http://v8.1c.ru/8.1/data-composition-system/settings" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" '
           'xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" '
           'xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" '
           'xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" '
           'xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" '
           'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"')
# порядок событий формы в выгрузке 8.3.27 (Конфигуратор переставляет их при загрузке; снят по большинству форм
# ТОИР КОРП). Иначе сверка «исходник = обратная выгрузка» показывает расхождение (ZHDRM, case 078).
FORM_EVENT_ORDER = ('AfterWrite', 'OnSaveDataInSettingsAtServer', 'ChoiceProcessing', 'AfterWriteAtServer',
                    'BeforeLoadVariantAtServer', 'NotificationProcessing', 'NavigationProcessing', 'NewWriteProcessing',
                    'OnReadAtServer', 'OnOpen', 'BeforeLoadUserSettingsAtServer', 'BeforeClose', 'ExternalEvent',
                    'OnReopen', 'OnSaveVariantAtServer', 'OnLoadDataFromSettingsAtServer', 'BeforeWrite',
                    'OnLoadUserSettingsAtServer', 'OnLoadVariantAtServer', 'OnSaveUserSettingsAtServer',
                    'OnCreateAtServer', 'BeforeWriteAtServer', 'OnMainServerAvailabilityChange', 'OnWriteAtServer',
                    'OnClose', 'OnUpdateUserSettingSetAtServer', 'URLProcessing', 'FillCheckProcessingAtServer',
                    'BeforeLoadDataFromSettingsAtServer')
VERSION = '2.20'      # атрибут version у MetaDataObject/Form (8.3.27, совместимость 8.3.21)

NS_UID = uuid.UUID('6f1c1c1e-6c1d-4d7a-9a8e-1c0de51a7e01')


def uid(*parts):
    """Устойчивый uuid5: пересборка не делает объект «новым» (case 020)."""
    return str(uuid.uuid5(NS_UID, '/'.join(str(p) for p in parts)))


def t(level):
    return '\t' * level


def ml(text, level):
    """Многоязычная строка (только ru)."""
    if not text:
        return None
    return (t(level) + '<v8:item>\n' + t(level + 1) + '<v8:lang>ru</v8:lang>\n' +
            t(level + 1) + '<v8:content>%s</v8:content>\n' % escape(text) + t(level) + '</v8:item>')


def ml_tag(tag, text, level, empty_if_none=True):
    body = ml(text, level + 1)
    if body is None:
        return t(level) + '<%s/>' % tag if empty_if_none else None
    return t(level) + '<%s>\n%s\n' % (tag, body) + t(level) + '</%s>' % tag


def synonym(text):
    """Синоним по имени: ПроцентПотерьВхода → «Процент потерь входа»."""
    words = re.findall(r'[А-ЯЁA-Z][а-яёa-z0-9]*|[0-9]+', text)
    return ' '.join([words[0]] + [w.lower() for w in words[1:]]) if words else text


# --------------------------------------------------------------------- типы
def type_xml(spec, level, tag='Type'):
    """spec: 'string' (неогр.), 'string:150', 'number:15.3', 'number:15.3+' (неотрицательное),
    'boolean', 'date', 'datetime', 'cfg:CatalogRef.X' / 'cfg:EnumRef.X' / …, список — составной,
    'ValueTable', 'ValueList', 'SpreadsheetDocument', 'FormattedString'."""
    specs = spec if isinstance(spec, (list, tuple)) else [spec]
    out = []
    for s in specs:
        if s.startswith('string'):
            n = s.split(':')[1] if ':' in s else '0'
            out += [t(level + 1) + '<v8:Type>xs:string</v8:Type>',
                    t(level + 1) + '<v8:StringQualifiers>',
                    t(level + 2) + '<v8:Length>%s</v8:Length>' % n,
                    t(level + 2) + '<v8:AllowedLength>Variable</v8:AllowedLength>',
                    t(level + 1) + '</v8:StringQualifiers>']
        elif s.startswith('number'):
            q = s.split(':')[1]
            sign = 'Nonnegative' if q.endswith('+') else 'Any'
            d, f = q.rstrip('+').split('.')
            out += [t(level + 1) + '<v8:Type>xs:decimal</v8:Type>',
                    t(level + 1) + '<v8:NumberQualifiers>',
                    t(level + 2) + '<v8:Digits>%s</v8:Digits>' % d,
                    t(level + 2) + '<v8:FractionDigits>%s</v8:FractionDigits>' % f,
                    t(level + 2) + '<v8:AllowedSign>%s</v8:AllowedSign>' % sign,
                    t(level + 1) + '</v8:NumberQualifiers>']
        elif s == 'boolean':
            out.append(t(level + 1) + '<v8:Type>xs:boolean</v8:Type>')
        elif s in ('date', 'datetime'):
            out += [t(level + 1) + '<v8:Type>xs:dateTime</v8:Type>',
                    t(level + 1) + '<v8:DateQualifiers>',
                    t(level + 2) + '<v8:DateFractions>%s</v8:DateFractions>' % ('Date' if s == 'date' else 'DateTime'),
                    t(level + 1) + '</v8:DateQualifiers>']
        elif s == 'ValueTable':
            out.append(t(level + 1) + '<v8:Type>v8:ValueTable</v8:Type>')
        elif s == 'ValueList':
            out.append(t(level + 1) + '<v8:Type>v8:ValueListType</v8:Type>')
        elif s == 'SpreadsheetDocument':
            out.append(t(level + 1) + '<v8:Type xmlns:mxl="http://v8.1c.ru/8.2/data/spreadsheet">mxl:SpreadsheetDocument</v8:Type>')
        elif s == 'FormattedString':
            out.append(t(level + 1) + '<v8:Type>v8ui:FormattedString</v8:Type>')
        elif s == 'AnyRef':
            out.append(t(level + 1) + '<v8:TypeSet>cfg:AnyRef</v8:TypeSet>')
        else:
            out.append(t(level + 1) + '<v8:Type>%s</v8:Type>' % s)
    return t(level) + '<%s>\n' % tag + '\n'.join(out) + '\n' + t(level) + '</%s>' % tag


def _is_string(spec):
    return not isinstance(spec, (list, tuple)) and spec.startswith('string')


# --------------------------------------------------------------- реквизиты объекта
def md_attribute(owner_key, name, spec, title=None, in_ts=False, level=3, tooltip=None):
    """Реквизит обработки/отчёта (in_ts=False) или реквизит ТЧ (in_ts=True) — полный набор
    свойств, как в выгрузке 8.3.27. У реквизита ТЧ есть FillFromFillingValue/FillValue."""
    L = level
    p = [t(L) + '<Attribute uuid="%s">' % uid(owner_key, 'attr', name),
         t(L + 1) + '<Properties>',
         t(L + 2) + '<Name>%s</Name>' % name,
         ml_tag('Synonym', title or synonym(name), L + 2),
         t(L + 2) + '<Comment/>',
         type_xml(spec, L + 2),
         t(L + 2) + '<PasswordMode>false</PasswordMode>',
         t(L + 2) + '<Format/>',
         t(L + 2) + '<EditFormat/>',
         ml_tag('ToolTip', tooltip, L + 2),
         t(L + 2) + '<MarkNegatives>false</MarkNegatives>',
         t(L + 2) + '<Mask/>',
         t(L + 2) + '<MultiLine>false</MultiLine>',
         t(L + 2) + '<ExtendedEdit>false</ExtendedEdit>',
         t(L + 2) + '<MinValue xsi:nil="true"/>',
         t(L + 2) + '<MaxValue xsi:nil="true"/>']
    if in_ts:
        p.append(t(L + 2) + '<FillFromFillingValue>false</FillFromFillingValue>')
        p.append(t(L + 2) + ('<FillValue xsi:type="xs:string"/>' if _is_string(spec) else '<FillValue xsi:nil="true"/>'))
    p += [t(L + 2) + '<FillChecking>DontCheck</FillChecking>',
          t(L + 2) + '<ChoiceFoldersAndItems>Items</ChoiceFoldersAndItems>',
          t(L + 2) + '<ChoiceParameterLinks/>',
          t(L + 2) + '<ChoiceParameters/>',
          t(L + 2) + '<QuickChoice>Auto</QuickChoice>',
          t(L + 2) + '<CreateOnInput>Auto</CreateOnInput>',
          t(L + 2) + '<ChoiceForm/>',
          t(L + 2) + '<LinkByType/>',
          t(L + 2) + '<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>',
          t(L + 1) + '</Properties>',
          t(L) + '</Attribute>']
    return '\n'.join(p)


def md_tabular_section(kind, owner, name, columns, title=None, level=3):
    """kind: 'DataProcessor' / 'Report'. columns: [(имя, тип[, заголовок])]."""
    L = level
    key = '%s.%s.%s' % (kind, owner, name)
    p = [t(L) + '<TabularSection uuid="%s">' % uid(key),
         t(L + 1) + '<InternalInfo>']
    for gen, cat in (('TabularSection', 'TabularSection'), ('TabularSectionRow', 'TabularSectionRow')):
        p += [t(L + 2) + '<xr:GeneratedType name="%s%s.%s.%s" category="%s">' % (kind, gen, owner, name, cat),
              t(L + 3) + '<xr:TypeId>%s</xr:TypeId>' % uid(key, gen, 'type'),
              t(L + 3) + '<xr:ValueId>%s</xr:ValueId>' % uid(key, gen, 'value'),
              t(L + 2) + '</xr:GeneratedType>']
    p += [t(L + 1) + '</InternalInfo>',
          t(L + 1) + '<Properties>',
          t(L + 2) + '<Name>%s</Name>' % name,
          ml_tag('Synonym', title or synonym(name), L + 2),
          t(L + 2) + '<Comment/>',
          t(L + 2) + '<ToolTip/>',
          t(L + 2) + '<FillChecking>DontCheck</FillChecking>',
          t(L + 1) + '</Properties>',
          t(L + 1) + '<ChildObjects>']
    for c in columns:
        p.append(md_attribute(key, c[0], c[1], c[2] if len(c) > 2 else None, in_ts=True, level=L + 2))
    p += [t(L + 1) + '</ChildObjects>', t(L) + '</TabularSection>']
    return '\n'.join(p)


def md_object_file(body):
    return '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject %s version="%s">\n%s\n</MetaDataObject>\n' % (
        MD_NS, VERSION, body)


def data_processor_xml(name, title, attributes=(), tabular_sections=(), forms=(), default_form=None,
                       explanation=None, templates=(), commands=()):
    """attributes: [(имя, тип[, заголовок])]; tabular_sections: [(имя, [колонки][, заголовок])];
    forms: [имя]; templates: [имя] (файлы — template_meta_xml + Templates/<Имя>/Ext/Template.txt);
    commands: [dict для md_command] (модуль — Commands/<Имя>/Ext/CommandModule.bsl). Порядок детей как в
    выгрузке: реквизиты, табличные части, формы, макеты, команды. Свой объект расширения — без
    ObjectBelonging (как в выгрузке)."""
    key = 'DataProcessor.' + name
    p = [t(1) + '<DataProcessor uuid="%s">' % uid(key),
         t(2) + '<InternalInfo>']
    for gen, cat in (('DataProcessorObject', 'Object'), ('DataProcessorManager', 'Manager')):
        p += [t(3) + '<xr:GeneratedType name="%s.%s" category="%s">' % (gen, name, cat),
              t(4) + '<xr:TypeId>%s</xr:TypeId>' % uid(key, gen, 'type'),
              t(4) + '<xr:ValueId>%s</xr:ValueId>' % uid(key, gen, 'value'),
              t(3) + '</xr:GeneratedType>']
    p += [t(2) + '</InternalInfo>',
          t(2) + '<Properties>',
          t(3) + '<Name>%s</Name>' % name,
          ml_tag('Synonym', title, 3),
          t(3) + '<Comment/>',
          t(3) + '<UseStandardCommands>true</UseStandardCommands>',
          t(3) + ('<DefaultForm>DataProcessor.%s.Form.%s</DefaultForm>' % (name, default_form or forms[0])
                  if (default_form or forms) else '<DefaultForm/>'),
          t(3) + '<AuxiliaryForm/>',
          t(3) + '<IncludeHelpInContents>false</IncludeHelpInContents>',
          t(3) + '<ExtendedPresentation/>',
          ml_tag('Explanation', explanation, 3),
          t(2) + '</Properties>',
          t(2) + '<ChildObjects>']
    for a in attributes:
        p.append(md_attribute(key, a[0], a[1], a[2] if len(a) > 2 else None, level=3))
    for ts in tabular_sections:
        p.append(md_tabular_section('DataProcessor', name, ts[0], ts[1], ts[2] if len(ts) > 2 else None, level=3))
    p += _children_tail(key, forms, templates, commands, 3)
    p += [t(2) + '</ChildObjects>', t(1) + '</DataProcessor>']
    return md_object_file('\n'.join(p))


EXTERNAL_DP_CLASS = 'c3831ec8-d8d5-4f93-8a22-f9bfae07327f'   # ClassId внешней обработки (из выгрузки .epf)


def external_data_processor_xml(name, title, attributes=(), tabular_sections=(), forms=(), templates=(),
                                default_form=None, comment=None):
    """Корневой файл <Имя>.xml внешней обработки (DumpExternalDataProcessorOrReportToFiles).
    Отличия от обработки конфигурации: xr:ContainedObject с постоянным ClassId, GeneratedType
    только Object, в свойствах нет UseStandardCommands/Explanation. Макеты — templates: [имя]."""
    key = 'ExternalDataProcessor.' + name
    p = [t(1) + '<ExternalDataProcessor uuid="%s">' % uid(key),
         t(2) + '<InternalInfo>',
         t(3) + '<xr:ContainedObject>',
         t(4) + '<xr:ClassId>%s</xr:ClassId>' % EXTERNAL_DP_CLASS,
         t(4) + '<xr:ObjectId>%s</xr:ObjectId>' % uid(key, 'object'),
         t(3) + '</xr:ContainedObject>',
         t(3) + '<xr:GeneratedType name="ExternalDataProcessorObject.%s" category="Object">' % name,
         t(4) + '<xr:TypeId>%s</xr:TypeId>' % uid(key, 'Object', 'type'),
         t(4) + '<xr:ValueId>%s</xr:ValueId>' % uid(key, 'Object', 'value'),
         t(3) + '</xr:GeneratedType>',
         t(2) + '</InternalInfo>',
         t(2) + '<Properties>',
         t(3) + '<Name>%s</Name>' % name,
         ml_tag('Synonym', title, 3),
         t(3) + ('<Comment>%s</Comment>' % escape(comment) if comment else '<Comment/>'),
         t(3) + ('<DefaultForm>ExternalDataProcessor.%s.Form.%s</DefaultForm>' % (name, default_form or forms[0])
                 if (default_form or forms) else '<DefaultForm/>'),
         t(3) + '<AuxiliaryForm/>',
         t(2) + '</Properties>',
         t(2) + '<ChildObjects>']
    for a in attributes:
        p.append(md_attribute(key, a[0], a[1], a[2] if len(a) > 2 else None, level=3))
    for ts in tabular_sections:
        p.append(md_tabular_section('ExternalDataProcessor', name, ts[0], ts[1], ts[2] if len(ts) > 2 else None, level=3))
    for f in forms:
        p.append(t(3) + '<Form>%s</Form>' % f)
    for tm in templates:
        p.append(t(3) + '<Template>%s</Template>' % tm)
    p += [t(2) + '</ChildObjects>', t(1) + '</ExternalDataProcessor>']
    return md_object_file('\n'.join(p))


def template_meta_xml(owner_key, name, title=None, kind='TextDocument'):
    """<Объект>/Templates/<Имя>.xml; содержимое — Ext/Template.txt (TextDocument, CRLF!)."""
    p = [t(1) + '<Template uuid="%s">' % uid(owner_key, 'template', name),
         t(2) + '<Properties>',
         t(3) + '<Name>%s</Name>' % name,
         ml_tag('Synonym', title or synonym(name), 3),
         t(3) + '<Comment/>',
         t(3) + '<TemplateType>%s</TemplateType>' % kind,
         t(2) + '</Properties>',
         t(1) + '</Template>']
    return md_object_file('\n'.join(p))


def form_meta_xml(owner_key, name, title=None):
    """Файл <Объект>/Forms/<Имя>.xml — описание формы (сама форма — Ext/Form.xml)."""
    p = [t(1) + '<Form uuid="%s">' % uid(owner_key, 'form', name),
         t(2) + '<Properties>',
         t(3) + '<Name>%s</Name>' % name,
         ml_tag('Synonym', title or synonym(name), 3),
         t(3) + '<Comment/>',
         t(3) + '<FormType>Managed</FormType>',
         t(3) + '<IncludeHelpInContents>false</IncludeHelpInContents>',
         t(3) + '<UsePurposes>',
         t(4) + '<v8:Value xsi:type="app:ApplicationUsePurpose">PlatformApplication</v8:Value>',
         t(4) + '<v8:Value xsi:type="app:ApplicationUsePurpose">MobilePlatformApplication</v8:Value>',
         t(3) + '</UsePurposes>']
    # у форм справочников и документов ExtendedPresentation в выгрузке нет (8.3.27, ZHDRM), у обработок — есть
    if not owner_key.startswith(('Catalog.', 'Document.')):
        p.append(t(3) + '<ExtendedPresentation/>')
    p += [t(2) + '</Properties>',
          t(1) + '</Form>']
    return md_object_file('\n'.join(p))


# ------------------------------------------------- объекты конфигурации (с нуля)
# Эталоны — выгрузка 1С:ТОИР КОРП 3.0.8.1 на 8.3.27 (АЗОТ); проверено загрузкой своей
# конфигурации «ЖДРМ ПУЛЬС» в пустую базу (проект ZHDRM, октябрь 2026).
# Поле — кортеж (имя, тип[, заголовок[, опции]]); опции: index (True | 'additional'),
# password, fill_checking ('ShowError'), multiline, tooltip, comment, main_filter (измерение),
# master (измерение), deny_incomplete (измерение).

def _internal_info(key, gens, level):
    """gens: [(префикс_типа, категория)] → <InternalInfo> с устойчивыми TypeId/ValueId."""
    name = key.split('.', 1)[1]
    p = [t(level) + '<InternalInfo>']
    for gen, cat in gens:
        p += [t(level + 1) + '<xr:GeneratedType name="%s.%s" category="%s">' % (gen, name, cat),
              t(level + 2) + '<xr:TypeId>%s</xr:TypeId>' % uid(key, gen, 'type'),
              t(level + 2) + '<xr:ValueId>%s</xr:ValueId>' % uid(key, gen, 'value'),
              t(level + 1) + '</xr:GeneratedType>']
    p.append(t(level) + '</InternalInfo>')
    return p


def _field_parts(f):
    name, spec = f[0], f[1]
    title = f[2] if len(f) > 2 else None
    opts = f[3] if len(f) > 3 else {}
    return name, spec, title, opts


def _indexing(opts):
    i = opts.get('index')
    return 'IndexWithAdditionalOrder' if i == 'additional' else ('Index' if i else 'DontIndex')


def md_field(owner_key, tag, field, level=3, tail=()):
    """Реквизит / измерение / ресурс объекта конфигурации: общий набор свойств выгрузки 8.3.27
    + хвост, свой для вида владельца (tail — готовые строки без отступа)."""
    name, spec, title, opts = _field_parts(field)
    L = level
    short = {'Attribute': 'attr', 'Dimension': 'dim', 'Resource': 'res'}.get(tag, tag)
    p = [t(L) + '<%s uuid="%s">' % (tag, uid(owner_key, short, name)),
         t(L + 1) + '<Properties>',
         t(L + 2) + '<Name>%s</Name>' % name,
         ml_tag('Synonym', title or synonym(name), L + 2),
         t(L + 2) + ('<Comment>%s</Comment>' % escape(opts['comment']) if opts.get('comment') else '<Comment/>'),
         type_xml(spec, L + 2),
         t(L + 2) + '<PasswordMode>%s</PasswordMode>' % ('true' if opts.get('password') else 'false'),
         t(L + 2) + '<Format/>',
         t(L + 2) + '<EditFormat/>',
         ml_tag('ToolTip', opts.get('tooltip'), L + 2),
         t(L + 2) + '<MarkNegatives>false</MarkNegatives>',
         t(L + 2) + '<Mask/>',
         t(L + 2) + '<MultiLine>%s</MultiLine>' % ('true' if opts.get('multiline') else 'false'),
         t(L + 2) + '<ExtendedEdit>%s</ExtendedEdit>' % ('true' if opts.get('multiline') else 'false'),
         t(L + 2) + '<MinValue xsi:nil="true"/>',
         t(L + 2) + '<MaxValue xsi:nil="true"/>',
         t(L + 2) + '<FillFromFillingValue>false</FillFromFillingValue>',
         t(L + 2) + ('<FillValue xsi:type="xs:string"/>' if _is_string(spec) else '<FillValue xsi:nil="true"/>'),
         t(L + 2) + '<FillChecking>%s</FillChecking>' % opts.get('fill_checking', 'DontCheck'),
         t(L + 2) + '<ChoiceFoldersAndItems>Items</ChoiceFoldersAndItems>',
         t(L + 2) + '<ChoiceParameterLinks/>',
         t(L + 2) + '<ChoiceParameters/>',
         t(L + 2) + '<QuickChoice>Auto</QuickChoice>',
         t(L + 2) + '<CreateOnInput>Auto</CreateOnInput>',
         t(L + 2) + '<ChoiceForm/>',
         t(L + 2) + '<LinkByType/>',
         t(L + 2) + '<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>']
    p += [t(L + 2) + x for x in tail]
    p += [t(L + 1) + '</Properties>', t(L) + '</%s>' % tag]
    return '\n'.join(p)


def _tail_object(opts, use=None):
    """Хвост реквизита справочника (use='ForItem') / документа / ТЧ."""
    out = ['<Use>%s</Use>' % use] if use else []
    return out + ['<Indexing>%s</Indexing>' % _indexing(opts), '<FullTextSearch>Use</FullTextSearch>',
                  '<DataHistory>Use</DataHistory>']


def md_object_tabular_section(kind, owner, ts, level=3):
    """ТЧ справочника/документа. ts: (имя, [поля][, заголовок])."""
    name, columns = ts[0], ts[1]
    title = ts[2] if len(ts) > 2 else None
    L = level
    key = '%s.%s.%s' % (kind, owner, name)
    p = [t(L) + '<TabularSection uuid="%s">' % uid(key), t(L + 1) + '<InternalInfo>']
    for gen, cat in (('TabularSection', 'TabularSection'), ('TabularSectionRow', 'TabularSectionRow')):
        p += [t(L + 2) + '<xr:GeneratedType name="%s%s.%s.%s" category="%s">' % (kind, gen, owner, name, cat),
              t(L + 3) + '<xr:TypeId>%s</xr:TypeId>' % uid(key, gen, 'type'),
              t(L + 3) + '<xr:ValueId>%s</xr:ValueId>' % uid(key, gen, 'value'),
              t(L + 2) + '</xr:GeneratedType>']
    p += [t(L + 1) + '</InternalInfo>',
          t(L + 1) + '<Properties>',
          t(L + 2) + '<Name>%s</Name>' % name,
          ml_tag('Synonym', title or synonym(name), L + 2),
          t(L + 2) + '<Comment/>',
          t(L + 2) + '<ToolTip/>',
          t(L + 2) + '<FillChecking>DontCheck</FillChecking>']
    if kind == 'Catalog':
        p.append(t(L + 2) + '<Use>ForItem</Use>')
    p += [t(L + 2) + '<LineNumberLength>5</LineNumberLength>',
          t(L + 1) + '</Properties>',
          t(L + 1) + '<ChildObjects>']
    for c in columns:
        p.append(md_field(key, 'Attribute', c, L + 2, _tail_object(_field_parts(c)[3])))
    p += [t(L + 1) + '</ChildObjects>', t(L) + '</TabularSection>']
    return '\n'.join(p)


def _children_tail(key, forms=(), templates=(), commands=(), level=3):
    p = [t(level) + '<Form>%s</Form>' % f for f in forms]
    p += [t(level) + '<Template>%s</Template>' % x for x in templates]
    for c in commands:
        p.append(md_command(key, c, level))
    return p


def md_command(owner_key, cmd, level=3):
    """Команда объекта (ChildObjects/Command; модуль — Commands/<Имя>/Ext/CommandModule.bsl).
    cmd: dict(name, title, group='FormCommandBarImportant', parameter='CatalogRef.X',
    use_mode='Single', modifies=False, tooltip, representation='Auto', picture)."""
    L = level
    c = cmd
    p = [t(L) + '<Command uuid="%s">' % uid(owner_key, 'command', c['name']),
         t(L + 1) + '<Properties>',
         t(L + 2) + '<Name>%s</Name>' % c['name'],
         ml_tag('Synonym', c.get('title') or synonym(c['name']), L + 2),
         t(L + 2) + '<Comment/>',
         t(L + 2) + '<Group>%s</Group>' % c.get('group', 'FormCommandBarImportant')]
    if c.get('parameter'):
        p += [t(L + 2) + '<CommandParameterType>', t(L + 3) + '<v8:Type>cfg:%s</v8:Type>' % c['parameter'],
              t(L + 2) + '</CommandParameterType>']
    else:
        p.append(t(L + 2) + '<CommandParameterType/>')
    p += [t(L + 2) + '<ParameterUseMode>%s</ParameterUseMode>' % c.get('use_mode', 'Single'),
          t(L + 2) + '<ModifiesData>%s</ModifiesData>' % ('true' if c.get('modifies') else 'false'),
          t(L + 2) + '<Representation>%s</Representation>' % c.get('representation', 'Auto'),
          ml_tag('ToolTip', c.get('tooltip'), L + 2)]
    if c.get('picture'):
        p += [t(L + 2) + '<Picture>', t(L + 3) + '<xr:Ref>%s</xr:Ref>' % c['picture'],
              t(L + 3) + '<xr:LoadTransparent>true</xr:LoadTransparent>', t(L + 2) + '</Picture>']
    else:
        p.append(t(L + 2) + '<Picture/>')
    p += [t(L + 2) + '<Shortcut/>',
          t(L + 2) + '<OnMainServerUnavalableBehavior>Auto</OnMainServerUnavalableBehavior>',
          t(L + 1) + '</Properties>',
          t(L) + '</Command>']
    return '\n'.join(p)


def catalog_xml(name, title, attributes=(), tabular_sections=(), forms=(), templates=(), commands=(),
                code_length=9, description_length=150, hierarchical=False, default_forms=None,
                object_presentation=None, list_presentation=None, explanation=None, owners=()):
    """Справочник. default_forms: {'Object': 'ФормаЭлемента', 'List': 'ФормаСписка', 'Choice': …}."""
    key = 'Catalog.' + name
    df = default_forms or {}
    p = [t(1) + '<Catalog uuid="%s">' % uid(key)]
    p += _internal_info(key, (('CatalogObject', 'Object'), ('CatalogRef', 'Ref'), ('CatalogSelection', 'Selection'),
                              ('CatalogList', 'List'), ('CatalogManager', 'Manager')), 2)
    p += [t(2) + '<Properties>',
          t(3) + '<Name>%s</Name>' % name,
          ml_tag('Synonym', title, 3),
          t(3) + '<Comment/>',
          t(3) + '<Hierarchical>%s</Hierarchical>' % ('true' if hierarchical else 'false'),
          t(3) + '<HierarchyType>HierarchyFoldersAndItems</HierarchyType>',
          t(3) + '<LimitLevelCount>false</LimitLevelCount>',
          t(3) + '<LevelCount>2</LevelCount>',
          t(3) + '<FoldersOnTop>true</FoldersOnTop>',
          t(3) + '<UseStandardCommands>true</UseStandardCommands>']
    if owners:
        p.append(t(3) + '<Owners>')
        p += [t(4) + '<xr:Item xsi:type="xr:MDObjectRef">%s</xr:Item>' % o for o in owners]
        p.append(t(3) + '</Owners>')
    else:
        p.append(t(3) + '<Owners/>')
    p += [t(3) + '<SubordinationUse>ToItems</SubordinationUse>',
          t(3) + '<CodeLength>%d</CodeLength>' % code_length,
          t(3) + '<DescriptionLength>%d</DescriptionLength>' % description_length,
          t(3) + '<CodeType>String</CodeType>',
          t(3) + '<CodeAllowedLength>Variable</CodeAllowedLength>',
          t(3) + '<CodeSeries>WholeCatalog</CodeSeries>',
          t(3) + '<CheckUnique>true</CheckUnique>',
          t(3) + '<Autonumbering>true</Autonumbering>',
          t(3) + '<DefaultPresentation>AsDescription</DefaultPresentation>',
          t(3) + '<Characteristics/>',
          t(3) + '<PredefinedDataUpdate>Auto</PredefinedDataUpdate>',
          t(3) + '<EditType>InDialog</EditType>',
          t(3) + '<QuickChoice>false</QuickChoice>',
          t(3) + '<ChoiceMode>BothWays</ChoiceMode>',
          t(3) + '<InputByString>',
          t(4) + '<xr:Field>Catalog.%s.StandardAttribute.Description</xr:Field>' % name,
          t(4) + '<xr:Field>Catalog.%s.StandardAttribute.Code</xr:Field>' % name,
          t(3) + '</InputByString>',
          t(3) + '<SearchStringModeOnInputByString>Begin</SearchStringModeOnInputByString>',
          t(3) + '<FullTextSearchOnInputByString>DontUse</FullTextSearchOnInputByString>',
          t(3) + '<ChoiceDataGetModeOnInputByString>Directly</ChoiceDataGetModeOnInputByString>']
    for k in ('Object', 'Folder', 'List', 'Choice', 'FolderChoice'):
        v = df.get(k)
        p.append(t(3) + ('<Default%sForm>Catalog.%s.Form.%s</Default%sForm>' % (k, name, v, k) if v
                         else '<Default%sForm/>' % k))
    p += [t(3) + '<Auxiliary%sForm/>' % k for k in ('Object', 'Folder', 'List', 'Choice', 'FolderChoice')]
    p += [t(3) + '<IncludeHelpInContents>false</IncludeHelpInContents>',
          t(3) + '<BasedOn/>',
          t(3) + '<DataLockFields/>',
          t(3) + '<DataLockControlMode>Managed</DataLockControlMode>',
          t(3) + '<FullTextSearch>Use</FullTextSearch>',
          ml_tag('ObjectPresentation', object_presentation, 3),
          t(3) + '<ExtendedObjectPresentation/>',
          ml_tag('ListPresentation', list_presentation, 3),
          t(3) + '<ExtendedListPresentation/>',
          ml_tag('Explanation', explanation, 3),
          t(3) + '<CreateOnInput>Use</CreateOnInput>',
          t(3) + '<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>',
          t(3) + '<DataHistory>DontUse</DataHistory>',
          t(3) + '<UpdateDataHistoryImmediatelyAfterWrite>false</UpdateDataHistoryImmediatelyAfterWrite>',
          t(3) + '<ExecuteAfterWriteDataHistoryVersionProcessing>false</ExecuteAfterWriteDataHistoryVersionProcessing>',
          t(2) + '</Properties>']
    body = [md_field(key, 'Attribute', a, 3, _tail_object(_field_parts(a)[3], 'ForItem')) for a in attributes]
    body += [md_object_tabular_section('Catalog', name, ts, 3) for ts in tabular_sections]
    body += _children_tail(key, forms, templates, commands)
    p += ([t(2) + '<ChildObjects>'] + body + [t(2) + '</ChildObjects>']) if body else [t(2) + '<ChildObjects/>']
    p.append(t(1) + '</Catalog>')
    return md_object_file('\n'.join(p))


def document_xml(name, title, attributes=(), tabular_sections=(), forms=(), templates=(), commands=(),
                 register_records=(), posting=True, number_length=11, default_forms=None,
                 object_presentation=None, list_presentation=None, explanation=None):
    """Документ. register_records: ['InformationRegister.X', …]."""
    key = 'Document.' + name
    df = default_forms or {}
    p = [t(1) + '<Document uuid="%s">' % uid(key)]
    p += _internal_info(key, (('DocumentObject', 'Object'), ('DocumentRef', 'Ref'), ('DocumentSelection', 'Selection'),
                              ('DocumentList', 'List'), ('DocumentManager', 'Manager')), 2)
    p += [t(2) + '<Properties>',
          t(3) + '<Name>%s</Name>' % name,
          ml_tag('Synonym', title, 3),
          t(3) + '<Comment/>',
          t(3) + '<UseStandardCommands>true</UseStandardCommands>',
          t(3) + '<Numerator/>',
          t(3) + '<NumberType>String</NumberType>',
          t(3) + '<NumberLength>%d</NumberLength>' % number_length,
          t(3) + '<NumberAllowedLength>Variable</NumberAllowedLength>',
          t(3) + '<NumberPeriodicity>Year</NumberPeriodicity>',
          t(3) + '<CheckUnique>true</CheckUnique>',
          t(3) + '<Autonumbering>true</Autonumbering>',
          t(3) + '<Characteristics/>',
          t(3) + '<BasedOn/>',
          t(3) + '<InputByString>',
          t(4) + '<xr:Field>Document.%s.StandardAttribute.Number</xr:Field>' % name,
          t(3) + '</InputByString>',
          t(3) + '<CreateOnInput>Use</CreateOnInput>',
          t(3) + '<SearchStringModeOnInputByString>Begin</SearchStringModeOnInputByString>',
          t(3) + '<FullTextSearchOnInputByString>DontUse</FullTextSearchOnInputByString>',
          t(3) + '<ChoiceDataGetModeOnInputByString>Directly</ChoiceDataGetModeOnInputByString>']
    for k in ('Object', 'List', 'Choice'):
        v = df.get(k)
        p.append(t(3) + ('<Default%sForm>Document.%s.Form.%s</Default%sForm>' % (k, name, v, k) if v
                         else '<Default%sForm/>' % k))
    p += [t(3) + '<Auxiliary%sForm/>' % k for k in ('Object', 'List', 'Choice')]
    p += [t(3) + '<Posting>%s</Posting>' % ('Allow' if posting else 'Deny'),
          t(3) + '<RealTimePosting>Deny</RealTimePosting>',
          t(3) + '<RegisterRecordsDeletion>AutoDeleteOnUnpost</RegisterRecordsDeletion>',
          t(3) + '<RegisterRecordsWritingOnPost>WriteSelected</RegisterRecordsWritingOnPost>',
          t(3) + '<SequenceFilling>AutoFill</SequenceFilling>']
    if register_records:
        p.append(t(3) + '<RegisterRecords>')
        p += [t(4) + '<xr:Item xsi:type="xr:MDObjectRef">%s</xr:Item>' % r for r in register_records]
        p.append(t(3) + '</RegisterRecords>')
    else:
        p.append(t(3) + '<RegisterRecords/>')
    p += [t(3) + '<PostInPrivilegedMode>true</PostInPrivilegedMode>',
          t(3) + '<UnpostInPrivilegedMode>true</UnpostInPrivilegedMode>',
          t(3) + '<IncludeHelpInContents>false</IncludeHelpInContents>',
          t(3) + '<DataLockFields/>',
          t(3) + '<DataLockControlMode>Managed</DataLockControlMode>',
          t(3) + '<FullTextSearch>Use</FullTextSearch>',
          ml_tag('ObjectPresentation', object_presentation, 3),
          t(3) + '<ExtendedObjectPresentation/>',
          ml_tag('ListPresentation', list_presentation, 3),
          t(3) + '<ExtendedListPresentation/>',
          ml_tag('Explanation', explanation, 3),
          t(3) + '<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>',
          t(3) + '<DataHistory>DontUse</DataHistory>',
          t(3) + '<UpdateDataHistoryImmediatelyAfterWrite>false</UpdateDataHistoryImmediatelyAfterWrite>',
          t(3) + '<ExecuteAfterWriteDataHistoryVersionProcessing>false</ExecuteAfterWriteDataHistoryVersionProcessing>',
          t(2) + '</Properties>']
    # порядок выгрузки документа: реквизиты, формы, ТЧ, макеты, команды (у справочника ТЧ — до форм)
    body = [md_field(key, 'Attribute', a, 3, _tail_object(_field_parts(a)[3])) for a in attributes]
    body += [t(3) + '<Form>%s</Form>' % f for f in forms]
    body += [md_object_tabular_section('Document', name, ts, 3) for ts in tabular_sections]
    body += _children_tail(key, (), templates, commands)
    p += ([t(2) + '<ChildObjects>'] + body + [t(2) + '</ChildObjects>']) if body else [t(2) + '<ChildObjects/>']
    p.append(t(1) + '</Document>')
    return md_object_file('\n'.join(p))


def information_register_xml(name, title, dimensions=(), resources=(), attributes=(), periodicity='Nonperiodical',
                             write_mode='Independent', forms=(), commands=(), default_forms=None,
                             record_presentation=None, list_presentation=None, explanation=None,
                             use_standard_commands=True):
    """Регистр сведений. periodicity: Nonperiodical | Second | Day | Month …; write_mode:
    Independent | RecorderSubordinate. Измерение: опции main_filter (по умолчанию True), master."""
    key = 'InformationRegister.' + name
    df = default_forms or {}
    p = [t(1) + '<InformationRegister uuid="%s">' % uid(key)]
    p += _internal_info(key, (('InformationRegisterRecord', 'Record'), ('InformationRegisterManager', 'Manager'),
                              ('InformationRegisterSelection', 'Selection'), ('InformationRegisterList', 'List'),
                              ('InformationRegisterRecordSet', 'RecordSet'), ('InformationRegisterRecordKey', 'RecordKey'),
                              ('InformationRegisterRecordManager', 'RecordManager')), 2)
    p += [t(2) + '<Properties>',
          t(3) + '<Name>%s</Name>' % name,
          ml_tag('Synonym', title, 3),
          t(3) + '<Comment/>',
          t(3) + '<UseStandardCommands>%s</UseStandardCommands>' % ('true' if use_standard_commands else 'false'),
          t(3) + '<EditType>InDialog</EditType>',
          t(3) + ('<DefaultRecordForm>InformationRegister.%s.Form.%s</DefaultRecordForm>' % (name, df['Record'])
                  if df.get('Record') else '<DefaultRecordForm/>'),
          t(3) + ('<DefaultListForm>InformationRegister.%s.Form.%s</DefaultListForm>' % (name, df['List'])
                  if df.get('List') else '<DefaultListForm/>'),
          t(3) + '<AuxiliaryRecordForm/>',
          t(3) + '<AuxiliaryListForm/>',
          t(3) + '<InformationRegisterPeriodicity>%s</InformationRegisterPeriodicity>' % periodicity,
          t(3) + '<WriteMode>%s</WriteMode>' % write_mode,
          t(3) + '<MainFilterOnPeriod>%s</MainFilterOnPeriod>' % ('true' if periodicity != 'Nonperiodical' else 'false'),
          t(3) + '<IncludeHelpInContents>false</IncludeHelpInContents>',
          t(3) + '<DataLockControlMode>Managed</DataLockControlMode>',
          t(3) + '<FullTextSearch>DontUse</FullTextSearch>',
          t(3) + '<EnableTotalsSliceFirst>false</EnableTotalsSliceFirst>',
          t(3) + '<EnableTotalsSliceLast>false</EnableTotalsSliceLast>',
          ml_tag('RecordPresentation', record_presentation, 3),
          t(3) + '<ExtendedRecordPresentation/>',
          ml_tag('ListPresentation', list_presentation, 3),
          t(3) + '<ExtendedListPresentation/>',
          ml_tag('Explanation', explanation, 3),
          t(3) + '<DataHistory>DontUse</DataHistory>',
          t(3) + '<UpdateDataHistoryImmediatelyAfterWrite>false</UpdateDataHistoryImmediatelyAfterWrite>',
          t(3) + '<ExecuteAfterWriteDataHistoryVersionProcessing>false</ExecuteAfterWriteDataHistoryVersionProcessing>',
          t(2) + '</Properties>']
    body = []
    for r in resources:
        body.append(md_field(key, 'Resource', r, 3, ['<Indexing>%s</Indexing>' % _indexing(_field_parts(r)[3]),
                                                     '<FullTextSearch>Use</FullTextSearch>', '<DataHistory>Use</DataHistory>']))
    for a in attributes:
        body.append(md_field(key, 'Attribute', a, 3, ['<Indexing>%s</Indexing>' % _indexing(_field_parts(a)[3]),
                                                      '<FullTextSearch>Use</FullTextSearch>', '<DataHistory>Use</DataHistory>']))
    for d in dimensions:
        o = _field_parts(d)[3]
        body.append(md_field(key, 'Dimension', d, 3, [
            '<Master>%s</Master>' % ('true' if o.get('master') else 'false'),
            '<MainFilter>%s</MainFilter>' % ('false' if o.get('main_filter') is False else 'true'),
            '<DenyIncompleteValues>%s</DenyIncompleteValues>' % ('true' if o.get('deny_incomplete') else 'false'),
            '<Indexing>%s</Indexing>' % _indexing(o), '<FullTextSearch>Use</FullTextSearch>',
            '<DataHistory>Use</DataHistory>', '<TypeReductionMode>TransformValues</TypeReductionMode>']))
    body += _children_tail(key, forms, (), commands)
    p += ([t(2) + '<ChildObjects>'] + body + [t(2) + '</ChildObjects>']) if body else [t(2) + '<ChildObjects/>']
    p.append(t(1) + '</InformationRegister>')
    return md_object_file('\n'.join(p))


def enum_xml(name, title, values, explanation=None):
    """Перечисление. values: [(имя[, синоним[, комментарий]])]."""
    key = 'Enum.' + name
    p = [t(1) + '<Enum uuid="%s">' % uid(key)]
    p += _internal_info(key, (('EnumRef', 'Ref'), ('EnumManager', 'Manager'), ('EnumList', 'List')), 2)
    p += [t(2) + '<Properties>',
          t(3) + '<Name>%s</Name>' % name,
          ml_tag('Synonym', title, 3),
          t(3) + '<Comment/>',
          t(3) + '<UseStandardCommands>false</UseStandardCommands>',
          t(3) + '<Characteristics/>',
          t(3) + '<QuickChoice>true</QuickChoice>',
          t(3) + '<ChoiceMode>BothWays</ChoiceMode>',
          t(3) + '<DefaultListForm/>',
          t(3) + '<DefaultChoiceForm/>',
          t(3) + '<AuxiliaryListForm/>',
          t(3) + '<AuxiliaryChoiceForm/>',
          t(3) + '<ListPresentation/>',
          t(3) + '<ExtendedListPresentation/>',
          ml_tag('Explanation', explanation, 3),
          t(3) + '<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>',
          t(2) + '</Properties>',
          t(2) + '<ChildObjects>']
    for v in values:
        v = (v,) if isinstance(v, str) else v
        p += [t(3) + '<EnumValue uuid="%s">' % uid(key, 'value', v[0]),
              t(4) + '<Properties>',
              t(5) + '<Name>%s</Name>' % v[0],
              ml_tag('Synonym', v[1] if len(v) > 1 and v[1] else synonym(v[0]), 5),
              t(5) + ('<Comment>%s</Comment>' % escape(v[2]) if len(v) > 2 and v[2] else '<Comment/>'),
              t(4) + '</Properties>',
              t(3) + '</EnumValue>']
    p += [t(2) + '</ChildObjects>', t(1) + '</Enum>']
    return md_object_file('\n'.join(p))


def constant_xml(name, title, spec, explanation=None, tooltip=None, password=False):
    key = 'Constant.' + name
    p = [t(1) + '<Constant uuid="%s">' % uid(key)]
    p += _internal_info(key, (('ConstantManager', 'Manager'), ('ConstantValueManager', 'ValueManager'),
                              ('ConstantValueKey', 'ValueKey')), 2)
    p += [t(2) + '<Properties>',
          t(3) + '<Name>%s</Name>' % name,
          ml_tag('Synonym', title, 3),
          t(3) + '<Comment/>',
          type_xml(spec, 3),
          t(3) + '<UseStandardCommands>true</UseStandardCommands>',
          t(3) + '<DefaultForm/>',
          t(3) + '<ExtendedPresentation/>',
          ml_tag('Explanation', explanation, 3),
          t(3) + '<PasswordMode>%s</PasswordMode>' % ('true' if password else 'false'),
          t(3) + '<Format/>',
          t(3) + '<EditFormat/>',
          ml_tag('ToolTip', tooltip, 3),
          t(3) + '<MarkNegatives>false</MarkNegatives>',
          t(3) + '<Mask/>',
          t(3) + '<MultiLine>false</MultiLine>',
          t(3) + '<ExtendedEdit>false</ExtendedEdit>',
          t(3) + '<MinValue xsi:nil="true"/>',
          t(3) + '<MaxValue xsi:nil="true"/>',
          t(3) + '<FillChecking>DontCheck</FillChecking>',
          t(3) + '<ChoiceFoldersAndItems>Items</ChoiceFoldersAndItems>',
          t(3) + '<ChoiceParameterLinks/>',
          t(3) + '<ChoiceParameters/>',
          t(3) + '<QuickChoice>Auto</QuickChoice>',
          t(3) + '<ChoiceForm/>',
          t(3) + '<LinkByType/>',
          t(3) + '<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>',
          t(3) + '<DataLockControlMode>Managed</DataLockControlMode>',
          t(3) + '<DataHistory>DontUse</DataHistory>',
          t(3) + '<UpdateDataHistoryImmediatelyAfterWrite>false</UpdateDataHistoryImmediatelyAfterWrite>',
          t(3) + '<ExecuteAfterWriteDataHistoryVersionProcessing>false</ExecuteAfterWriteDataHistoryVersionProcessing>',
          t(2) + '</Properties>',
          t(1) + '</Constant>']
    return md_object_file('\n'.join(p))


def common_module_xml(name, title, kind='server', privileged=False, reuse='DontUse'):
    """kind: 'server' (Сервер + ВнешнееСоединение), 'server_call' (+ ВызовСервера), 'client'
    (КлиентУправляемоеПриложение), 'client_server' (клиент + сервер + внешнее соединение), 'global_client'.
    reuse: DontUse | DuringRequest | DuringSession. Модуль — CommonModules/<Имя>/Ext/Module.bsl."""
    server = kind in ('server', 'server_call', 'client_server')
    client = kind in ('client', 'client_server', 'global_client')
    p = [t(1) + '<CommonModule uuid="%s">' % uid('CommonModule.' + name),
         t(2) + '<Properties>',
         t(3) + '<Name>%s</Name>' % name,
         ml_tag('Synonym', title, 3),
         t(3) + '<Comment/>',
         t(3) + '<Global>%s</Global>' % ('true' if kind == 'global_client' else 'false'),
         t(3) + '<ClientManagedApplication>%s</ClientManagedApplication>' % ('true' if client else 'false'),
         t(3) + '<Server>%s</Server>' % ('true' if server else 'false'),
         t(3) + '<ExternalConnection>%s</ExternalConnection>' % ('true' if server else 'false'),
         t(3) + '<ClientOrdinaryApplication>%s</ClientOrdinaryApplication>' % ('true' if (server or client) else 'false'),
         t(3) + '<ServerCall>%s</ServerCall>' % ('true' if kind == 'server_call' else 'false'),
         t(3) + '<Privileged>%s</Privileged>' % ('true' if privileged else 'false'),
         t(3) + '<ReturnValuesReuse>%s</ReturnValuesReuse>' % reuse,
         t(2) + '</Properties>',
         t(1) + '</CommonModule>']
    return md_object_file('\n'.join(p))


def subsystem_xml(name, title, content=(), children=(), include_in_ci=True, explanation=None, picture=None,
                  parent_key=None):
    """Подсистема. content: ['Catalog.X', …]; children: имена дочерних (их файлы —
    Subsystems/<Имя>/Subsystems/<Дочерняя>.xml). parent_key — для устойчивого uuid дочерней."""
    key = (parent_key + '.' if parent_key else '') + 'Subsystem.' + name
    p = [t(1) + '<Subsystem uuid="%s">' % uid(key),
         t(2) + '<Properties>',
         t(3) + '<Name>%s</Name>' % name,
         ml_tag('Synonym', title, 3),
         t(3) + '<Comment/>',
         t(3) + '<IncludeHelpInContents>true</IncludeHelpInContents>',
         t(3) + '<IncludeInCommandInterface>%s</IncludeInCommandInterface>' % ('true' if include_in_ci else 'false'),
         t(3) + '<UseOneCommand>false</UseOneCommand>',
         ml_tag('Explanation', explanation, 3)]
    if picture:
        p += [t(3) + '<Picture>', t(4) + '<xr:Ref>%s</xr:Ref>' % picture,
              t(4) + '<xr:LoadTransparent>true</xr:LoadTransparent>', t(3) + '</Picture>']
    else:
        p.append(t(3) + '<Picture/>')
    if content:
        p.append(t(3) + '<Content>')
        p += [t(4) + '<xr:Item xsi:type="xr:MDObjectRef">%s</xr:Item>' % c for c in content]
        p.append(t(3) + '</Content>')
    else:
        p.append(t(3) + '<Content/>')
    p.append(t(2) + '</Properties>')
    if children:
        p += [t(2) + '<ChildObjects>'] + [t(3) + '<Subsystem>%s</Subsystem>' % c for c in children] + [t(2) + '</ChildObjects>']
    else:
        p.append(t(2) + '<ChildObjects/>')
    p.append(t(1) + '</Subsystem>')
    return md_object_file('\n'.join(p))


def role_xml(name, title):
    p = [t(1) + '<Role uuid="%s">' % uid('Role.' + name),
         t(2) + '<Properties>',
         t(3) + '<Name>%s</Name>' % name,
         ml_tag('Synonym', title, 3),
         t(3) + '<Comment/>',
         t(2) + '</Properties>',
         t(1) + '</Role>']
    return md_object_file('\n'.join(p))


def rights_xml(objects=(), set_for_new_objects=False):
    """Roles/<Роль>/Ext/Rights.xml. set_for_new_objects=True и пустой objects — ВСЕ права на всё
    (так устроена «ПолныеПрава» БСП: в ней перечислены только запреты). objects: [(объект, {право: bool})]."""
    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<Rights xmlns="http://v8.1c.ru/8.2/roles" xmlns:xs="http://www.w3.org/2001/XMLSchema" '
         'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="Rights" version="%s">' % VERSION,
         t(1) + '<setForNewObjects>%s</setForNewObjects>' % ('true' if set_for_new_objects else 'false'),
         t(1) + '<setForAttributesByDefault>true</setForAttributesByDefault>',
         t(1) + '<independentRightsOfChildObjects>false</independentRightsOfChildObjects>']
    for obj, rights in objects:
        p += [t(1) + '<object>', t(2) + '<name>%s</name>' % obj]
        for r, v in rights.items():
            p += [t(2) + '<right>', t(3) + '<name>%s</name>' % r, t(3) + '<value>%s</value>' % ('true' if v else 'false'),
                  t(2) + '</right>']
        p.append(t(1) + '</object>')
    p.append('</Rights>')
    return '\n'.join(p) + '\n'


def scheduled_job_xml(name, title, method, use=False, predefined=True, restart_count=3, restart_interval=10,
                      description=None, key_=None):
    """Регламентное задание. method: 'CommonModule.<Модуль>.<Процедура>'. Расписание в XML
    выгрузки не хранится — задаётся в базе (РегламентныеЗадания) или кодом."""
    p = [t(1) + '<ScheduledJob uuid="%s">' % uid('ScheduledJob.' + name),
         t(2) + '<Properties>',
         t(3) + '<Name>%s</Name>' % name,
         ml_tag('Synonym', title, 3),
         t(3) + '<Comment/>',
         t(3) + '<MethodName>%s</MethodName>' % method,
         t(3) + ('<Description>%s</Description>' % escape(description) if description else '<Description/>'),
         t(3) + ('<Key>%s</Key>' % escape(key_) if key_ else '<Key/>'),
         t(3) + '<Use>%s</Use>' % ('true' if use else 'false'),
         t(3) + '<Predefined>%s</Predefined>' % ('true' if predefined else 'false'),
         t(3) + '<RestartCountOnFailure>%d</RestartCountOnFailure>' % restart_count,
         t(3) + '<RestartIntervalOnFailure>%d</RestartIntervalOnFailure>' % restart_interval,
         t(2) + '</Properties>',
         t(1) + '</ScheduledJob>']
    return md_object_file('\n'.join(p))


# порядок видов в ChildObjects Configuration.xml (по выгрузке 8.3.27)
CONFIGURATION_KINDS = ('Language', 'Subsystem', 'StyleItem', 'CommonPicture', 'SessionParameter', 'Role',
                       'CommonTemplate', 'FilterCriterion', 'CommonModule', 'CommonAttribute', 'ExchangePlan',
                       'XDTOPackage', 'WebService', 'HTTPService', 'EventSubscription', 'ScheduledJob',
                       'SettingsStorage', 'FunctionalOption', 'FunctionalOptionsParameter', 'DefinedType',
                       'CommonCommand', 'CommandGroup', 'Constant', 'CommonForm', 'Catalog', 'Document',
                       'DocumentJournal', 'Enum', 'Report', 'DataProcessor', 'InformationRegister',
                       'AccumulationRegister', 'ChartOfCharacteristicTypes', 'BusinessProcess', 'Task',
                       'ExternalDataSource')
# папка выгрузки по виду
KIND_DIRS = {'Language': 'Languages', 'Subsystem': 'Subsystems', 'Role': 'Roles', 'CommonModule': 'CommonModules',
             'ScheduledJob': 'ScheduledJobs', 'Constant': 'Constants', 'Catalog': 'Catalogs', 'Document': 'Documents',
             'Enum': 'Enums', 'Report': 'Reports', 'DataProcessor': 'DataProcessors',
             'InformationRegister': 'InformationRegisters', 'AccumulationRegister': 'AccumulationRegisters',
             'CommonForm': 'CommonForms', 'CommonTemplate': 'CommonTemplates', 'CommonCommand': 'CommonCommands',
             'CommonPicture': 'CommonPictures', 'DefinedType': 'DefinedTypes', 'EventSubscription': 'EventSubscriptions',
             'HTTPService': 'HTTPServices', 'SessionParameter': 'SessionParameters'}


def configuration_child_objects(children, level=2):
    """children: {вид: [имена]} → блок <ChildObjects> в порядке видов выгрузки."""
    p = [t(level) + '<ChildObjects>']
    for k in CONFIGURATION_KINDS:
        p += [t(level + 1) + '<%s>%s</%s>' % (k, n, k) for n in children.get(k, ())]
    p.append(t(level) + '</ChildObjects>')
    return '\n'.join(p)


def load_config(v8, ib, dump, log, **kw):
    """ПОЛНАЯ загрузка выгрузки в базу. Только для СВОЕЙ конфигурации, написанной с нуля:
    у типовой ломает защиту вендоров (load_files — частичная)."""
    return designer(v8, ib, ['/LoadConfigFromFiles "%s"' % dump], log, **kw)


# ------------------------------------------- картинки, макеты, отчёты, интерфейс (ZHDRM, итерация 9)
# Форматы сняты с выгрузки 1С:ТОИР КОРП 3.0 на 8.3.27 (АЗОТ): CommonPictures/GoogleMaps (SVG),
# CommonTemplates/EmptyProjectXMLDoc, Reports/АнализВерсийОбъектов, Ext/CommandInterface.xml подсистем,
# Ext/HomePageWorkArea.xml и Ext/ClientApplicationInterface.xml конфигурации.
EXT_NS = ('xmlns="http://v8.1c.ru/8.3/xcf/extrnprops" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" '
          'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"')


def picture_ext_xml(file_name='Picture.svg'):
    """Ext/Picture.xml общей картинки (и Ext/MainSectionPicture.xml конфигурации): сама картинка —
    файл рядом, в папке Ext/Picture/ (Ext/MainSectionPicture/). SVG — один файл на все масштабы."""
    return '\n'.join(['<?xml version="1.0" encoding="UTF-8"?>', '<ExtPicture %s version="%s">' % (EXT_NS, VERSION),
                      t(1) + '<Picture>', t(2) + '<xr:Abs>%s</xr:Abs>' % file_name,
                      t(2) + '<xr:LoadTransparent>false</xr:LoadTransparent>', t(1) + '</Picture>', '</ExtPicture>'])


def common_picture_xml(name, title=None):
    """CommonPictures/<Имя>.xml; файлы: <Имя>/Ext/Picture.xml (picture_ext_xml) + <Имя>/Ext/Picture/Picture.svg
    (UTF-8 без BOM — как в выгрузке). Ссылка — 'CommonPicture.<Имя>' (subsystem_xml(picture=…), md_command)."""
    p = [t(1) + '<CommonPicture uuid="%s">' % uid('CommonPicture.' + name),
         t(2) + '<Properties>',
         t(3) + '<Name>%s</Name>' % name,
         ml_tag('Synonym', title or synonym(name), 3),
         t(3) + '<Comment/>',
         t(3) + '<AvailabilityForChoice>false</AvailabilityForChoice>',
         t(3) + '<AvailabilityForAppearance>false</AvailabilityForAppearance>',
         t(2) + '</Properties>',
         t(1) + '</CommonPicture>']
    return md_object_file('\n'.join(p))


def common_template_xml(name, title=None, kind='TextDocument'):
    """CommonTemplates/<Имя>.xml; текст — <Имя>/Ext/Template.txt (BOM, CRLF, строки ≤ 900 — html-field-and-templates.md §2).
    В модуле: ПолучитьОбщийМакет("<Имя>").ПолучитьТекст()."""
    p = [t(1) + '<CommonTemplate uuid="%s">' % uid('CommonTemplate.' + name),
         t(2) + '<Properties>',
         t(3) + '<Name>%s</Name>' % name,
         ml_tag('Synonym', title or synonym(name), 3),
         t(3) + '<Comment/>',
         t(3) + '<TemplateType>%s</TemplateType>' % kind,
         t(2) + '</Properties>',
         t(1) + '</CommonTemplate>']
    return md_object_file('\n'.join(p))


def split_template_text(text, width=900):
    """Текст для текстового макета: CRLF, строки длиннее width режутся с Символ(1) в КОНЦЕ куска (case 076).
    Склейка в модуле: СтрЗаменить(Т, Символ(1) + Символы.ВК + Символы.ПС, "") и т.д."""
    if '\x01' in text:
        raise ValueError('в тексте уже есть Символ(1) — маркер разреза')
    out = []
    for line in text.replace('\r\n', '\n').split('\n'):
        while len(line) > width:
            out.append(line[:width - 1] + '\x01')
            line = line[width - 1:]
        out.append(line)
    res = '\r\n'.join(out)
    assert res.replace('\x01\r\n', '').replace('\r\n', '\n') == text.replace('\r\n', '\n')
    return res


def report_xml(name, title, forms=(), templates=('ОсновнаяСхемаКомпоновкиДанных',), commands=(),
               main_dcs='ОсновнаяСхемаКомпоновкиДанных', default_form=None, settings_form=None, explanation=None,
               attributes=()):
    """Отчёт. Схема — Templates/<main_dcs>.xml (template_meta_xml(kind='DataCompositionSchema'))
    + Templates/<main_dcs>/Ext/Template.xml (текст схемы, edt_lib.dcs_schema_ex — тот же XML).
    Модуль объекта — Ext/ObjectModule.bsl (ПриКомпоновкеРезультата). Без БСП: VariantsStorage пустое."""
    key = 'Report.' + name
    p = [t(1) + '<Report uuid="%s">' % uid(key),
         '\n'.join(_internal_info(key, (('ReportObject', 'Object'), ('ReportManager', 'Manager')), 2)),
         t(2) + '<Properties>',
         t(3) + '<Name>%s</Name>' % name,
         ml_tag('Synonym', title, 3),
         t(3) + '<Comment/>',
         t(3) + '<UseStandardCommands>true</UseStandardCommands>',
         t(3) + ('<DefaultForm>Report.%s.Form.%s</DefaultForm>' % (name, default_form) if default_form
                 else '<DefaultForm/>'),
         t(3) + '<AuxiliaryForm/>',
         t(3) + ('<MainDataCompositionSchema>Report.%s.Template.%s</MainDataCompositionSchema>' % (name, main_dcs)
                 if main_dcs else '<MainDataCompositionSchema/>'),
         t(3) + ('<DefaultSettingsForm>Report.%s.Form.%s</DefaultSettingsForm>' % (name, settings_form)
                 if settings_form else '<DefaultSettingsForm/>'),
         t(3) + '<AuxiliarySettingsForm/>',
         t(3) + '<DefaultVariantForm/>',
         t(3) + '<VariantsStorage/>',
         t(3) + '<SettingsStorage/>',
         t(3) + '<IncludeHelpInContents>false</IncludeHelpInContents>',
         t(3) + '<ExtendedPresentation/>',
         ml_tag('Explanation', explanation, 3),
         t(2) + '</Properties>',
         t(2) + '<ChildObjects>']
    for a in attributes:
        p.append(md_attribute(key, a[0], a[1], a[2] if len(a) > 2 else None, level=3))
    p += _children_tail(key, forms, templates, commands, 3)
    p += [t(2) + '</ChildObjects>', t(1) + '</Report>']
    return md_object_file('\n'.join(p))


def command_interface_xml(visibility=(), placement=(), order=(), subsystems=(), groups=()):
    """Ext/CommandInterface.xml подсистемы (и Ext/MainSectionCommandInterface.xml, Ext/CommandInterface.xml
    конфигурации — там только subsystems: порядок разделов). Команды — полные имена:
    'Catalog.X.StandardCommand.OpenList', 'DataProcessor.X.StandardCommand.Open', 'Report.X.Command.Y'.
    visibility: [(команда, bool)]; placement: [(команда, группа)] — перенос в другую группу
    (NavigationPanelImportant/Ordinary/SeeAlso, ActionsPanelCreate/Reports/Tools);
    order: [(группа, [команды])]; subsystems: ['Subsystem.X', …]; groups: порядок групп."""
    p = ['<?xml version="1.0" encoding="UTF-8"?>', '<CommandInterface %s version="%s">' % (EXT_NS, VERSION)]
    if visibility:
        p.append(t(1) + '<CommandsVisibility>')
        for c, vis in visibility:
            p += [t(2) + '<Command name="%s">' % c, t(3) + '<Visibility>',
                  t(4) + '<xr:Common>%s</xr:Common>' % ('true' if vis else 'false'), t(3) + '</Visibility>',
                  t(2) + '</Command>']
        p.append(t(1) + '</CommandsVisibility>')
    if placement:
        p.append(t(1) + '<CommandsPlacement>')
        for c, g in placement:
            p += [t(2) + '<Command name="%s">' % c, t(3) + '<CommandGroup>%s</CommandGroup>' % g,
                  t(3) + '<Placement>Auto</Placement>', t(2) + '</Command>']
        p.append(t(1) + '</CommandsPlacement>')
    if order:
        p.append(t(1) + '<CommandsOrder>')
        for g, cmds in order:
            for c in cmds:
                p += [t(2) + '<Command name="%s">' % c, t(3) + '<CommandGroup>%s</CommandGroup>' % g, t(2) + '</Command>']
        p.append(t(1) + '</CommandsOrder>')
    if subsystems:
        p += [t(1) + '<SubsystemsOrder>'] + [t(2) + '<Subsystem>%s</Subsystem>' % s for s in subsystems] + \
             [t(1) + '</SubsystemsOrder>']
    if groups:
        p += [t(1) + '<GroupsOrder>'] + [t(2) + '<Group>%s</Group>' % g for g in groups] + [t(1) + '</GroupsOrder>']
    p.append('</CommandInterface>')
    return '\n'.join(p)


def home_page_xml(forms, template='OneColumn'):
    """Ext/HomePageWorkArea.xml конфигурации: forms — [(форма, высота[, видимость])], форма —
    'DataProcessor.X.Form.Y' | 'CommonForm.X'. Видимость явно true: пустая = скрыта для всех (case 061)."""
    p = ['<?xml version="1.0" encoding="UTF-8"?>', '<HomePageWorkArea %s version="%s">' % (EXT_NS, VERSION),
         t(1) + '<WorkingAreaTemplate>%s</WorkingAreaTemplate>' % template, t(1) + '<Column>']
    for f in forms:
        p += [t(2) + '<Item>', t(3) + '<Form>%s</Form>' % f[0], t(3) + '<Height>%d</Height>' % f[1],
              t(3) + '<Visibility>', t(4) + '<xr:Common>%s</xr:Common>' % ('false' if len(f) > 2 and not f[2] else 'true'),
              t(3) + '</Visibility>', t(2) + '</Item>']
    p += [t(1) + '</Column>', '</HomePageWorkArea>']
    return '\n'.join(p)


# Раскладка панелей тонкого клиента 1С:ТОИР КОРП 3.0 (АЗОТ): разделы СЛЕВА «картинка слева и текст»,
# панель открытых — сверху. Идентификаторы панелей — платформенные, менять нельзя.
CLIENT_INTERFACE_LEFT_SECTIONS = '''<?xml version="1.0" encoding="UTF-8"?>
<ClientApplicationInterface xmlns="http://v8.1c.ru/8.2/managed-application/core" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="InterfaceLayouter">
	<top>
		<panel id="b9693e0d-2d75-4e15-bfb9-9c55b716e958">
			<uuid>cbab57f2-a0f3-4f0a-89ea-4cb19570ab75</uuid>
			<height>1</height>
		</panel>
	</top>
	<left>
		<group id="a558db2a-807d-4dc1-b91f-0a6d9b6e6e93">
			<group>
				<panel id="02bdc45c-3ac2-45b6-b2a4-f98aa2c8f6c2">
					<uuid>8e10648b-f52d-4ec2-b4dd-87de33778d95</uuid>
				</panel>
			</group>
			<group>
				<panel id="d14246f8-dc15-4233-ba8b-e7c52682b1d0">
					<uuid>b553047f-c9aa-4157-978d-448ecad24248</uuid>
				</panel>
			</group>
			<group>
				<panel id="a79d7a1a-3fda-406f-b823-8e7aa8970514">
					<uuid>13322b22-3960-4d68-93a6-fe2dd7f28ca3</uuid>
				</panel>
			</group>
		</group>
	</left>
	<panelDef id="b553047f-c9aa-4157-978d-448ecad24248">
		<spr>PictureOnLeftAndText</spr>
	</panelDef>
	<panelDef id="13322b22-3960-4d68-93a6-fe2dd7f28ca3"/>
	<panelDef id="c933ac92-92cd-459d-81cc-e0c8a83ced99"/>
	<panelDef id="cbab57f2-a0f3-4f0a-89ea-4cb19570ab75"/>
	<panelDef id="b2735bd3-d822-4430-ba59-c9e869693b24"/>
</ClientApplicationInterface>'''


# --------------------------------------------------------------------- форма
class Form:
    """Построитель Ext/Form.xml. Элементы — вложенные списки, id раздаются по порядку.

        f = Form()
        f.attr('Объект', 'cfg:DataProcessorObject.X', main=True)
        f.command('Рассчитать', 'Рассчитать')
        f.items = [f.group('Шапка', [f.input('Объект.Цех')], 'horizontal'), f.table('Стадии', 'Объект.Стадии', [...])]
        text = f.xml(events={'OnCreateAtServer': 'ПриСозданииНаСервере'})
    """

    def __init__(self, title=None):
        self.title = title
        self.next_id = 1
        self.attrs = []
        self.cmds = []
        self.items = []
        self.cmdbar = []        # кнопки командной панели формы: имена команд
        self.autofill_cmdbar = True
        self.params = []        # параметры формы: (имя, тип, ключевой) — после Commands, как в выгрузке
        self.navigation = []    # панель навигации формы: (команда, видимость) — 'InformationRegister.X.StandardCommand.OpenByValue.Измерение'

    def _id(self):
        i = self.next_id
        self.next_id += 1
        return i

    # --- реквизиты и команды
    def attr(self, name, spec, title=None, main=False, columns=(), save=False):
        self.attrs.append((name, spec, title, main, columns, save))

    def command(self, name, title, action=None, tooltip=None, picture=None, representation=None):
        self.cmds.append((name, title, action or name, tooltip, picture, representation))

    def param(self, name, spec, key=False):
        """Параметр формы (Параметры.Имя в ПриСозданииНаСервере); key — ключевой (уникальность окна)."""
        self.params.append((name, spec, key))

    # --- элементы: возвращают (функция_рендера) — id выдаются при рендере, по порядку
    def group(self, name, children, kind='vertical', title=None, show_title=False, representation='None'):
        return ('group', name, children, kind, title, show_title, representation)

    def pages(self, name, pages):
        return ('pages', name, pages)

    def page(self, name, title, children):
        return ('page', name, title, children)

    def input(self, path, name=None, title=None, read_only=False, events=None, width=None, title_loc=None,
              edit_mode=None, multiline=False, height=None, choice_button=None, clear_button=None,
              auto_max_width=None, stretch=None):
        """auto_max_width=False — ширина не ограничена длиной данных; stretch — HorizontalStretch (порядок тегов
        Width, AutoMaxWidth, Height, HorizontalStretch — по выгрузке ТОИР)."""
        return ('input', path, name, title, read_only, events, width, title_loc, edit_mode, multiline, height,
                choice_button, clear_button, auto_max_width, stretch)

    def check(self, path, name=None, title=None, events=None, edit_mode=None, read_only=False):
        return ('check', path, name, title, events, edit_mode, read_only)

    def label(self, name, text, font_bold=False, wide=False):
        """wide — AutoMaxWidth=false: длинный текст (строка состояния) не переносится по словам в узкой колонке."""
        return ('label', name, text, font_bold, wide)

    def button(self, command, name=None, kind='UsualButton', default=False):
        return ('button', command, name, kind, default)

    def spreadsheet(self, path, name=None, events=None):
        return ('sheet', path, name, events)

    def html(self, path, name=None, events=None, width=70, height=10):
        """Поле HTML документа. Ширина и высота — вместе с растяжением, иначе документ получает
        окно нулевой высоты и страница схлопывается (html-field-and-templates.md §1, case 022)."""
        return ('html', path, name, events, width, height)

    def table(self, name, path, columns, read_only=False, commands=(), events=None, change_rowset=False,
              header_height=None, autofill=False, height_rows=None):
        """columns: элементы input()/check() с путём 'Колонка' (путь таблицы добавится).
        height_rows — высота в строках (HeightInTableRows): короткая таблица не растягивается на пол-формы."""
        return ('table', name, path, columns, read_only, commands, events, change_rowset, header_height, autofill,
                height_rows)

    # --- рендер элементов
    def _title(self, text, L):
        return ml_tag('Title', text, L, empty_if_none=False)

    def _events(self, events, L):
        if not events:
            return []
        out = [t(L) + '<Events>']
        for ev, handler in events.items():
            out.append(t(L + 1) + '<Event name="%s">%s</Event>' % (ev, handler))
        out.append(t(L) + '</Events>')
        return out

    def _cm_et(self, name, L):
        return [t(L) + '<ContextMenu name="%sКонтекстноеМеню" id="%d"/>' % (name, self._id()),
                t(L) + '<ExtendedTooltip name="%sРасширеннаяПодсказка" id="%d"/>' % (name, self._id())]

    def _render(self, it, L, table_path=None):
        kind = it[0]
        out = []
        if kind == 'group':
            _, name, children, gkind, title, show_title, representation = it
            out.append(t(L) + '<UsualGroup name="%s" id="%d">' % (name, self._id()))
            if title:
                out.append(ml_tag('Title', title, L + 1))
            out.append(t(L + 1) + '<Group>%s</Group>' % {'vertical': 'Vertical', 'horizontal': 'AlwaysHorizontal',
                                                          'h': 'Horizontal'}[gkind])
            out.append(t(L + 1) + '<Representation>%s</Representation>' % representation)
            if not show_title:
                out.append(t(L + 1) + '<ShowTitle>false</ShowTitle>')
            out.append(t(L + 1) + '<ExtendedTooltip name="%sРасширеннаяПодсказка" id="%d"/>' % (name, self._id()))
            out += self._children(children, L + 1)
            out.append(t(L) + '</UsualGroup>')
        elif kind == 'pages':
            _, name, pages = it
            out.append(t(L) + '<Pages name="%s" id="%d">' % (name, self._id()))
            out.append(t(L + 1) + '<ExtendedTooltip name="%sРасширеннаяПодсказка" id="%d"/>' % (name, self._id()))
            out += self._children(pages, L + 1)
            out.append(t(L) + '</Pages>')
        elif kind == 'page':
            _, name, title, children = it
            out.append(t(L) + '<Page name="%s" id="%d">' % (name, self._id()))
            out.append(ml_tag('Title', title, L + 1))
            out.append(t(L + 1) + '<ExtendedTooltip name="%sРасширеннаяПодсказка" id="%d"/>' % (name, self._id()))
            out += self._children(children, L + 1)
            out.append(t(L) + '</Page>')
        elif kind == 'input':
            (_, path, name, title, ro, events, width, title_loc, edit_mode, multiline, height,
             choice_button, clear_button) = it[:13]
            auto_max_width, stretch = (it[13], it[14]) if len(it) > 14 else (None, None)
            full = table_path + '.' + path if table_path else path
            name = name or ((table_path.split('.')[-1] if table_path else '') + path.split('.')[-1])
            out.append(t(L) + '<InputField name="%s" id="%d">' % (name, self._id()))
            out.append(t(L + 1) + '<DataPath>%s</DataPath>' % full)
            if ro:
                out.append(t(L + 1) + '<ReadOnly>true</ReadOnly>')
            if title:
                out.append(ml_tag('Title', title, L + 1))
            if title_loc:
                out.append(t(L + 1) + '<TitleLocation>%s</TitleLocation>' % title_loc)
            if edit_mode or table_path:
                out.append(t(L + 1) + '<EditMode>%s</EditMode>' % (edit_mode or 'EnterOnInput'))
            if width:
                out.append(t(L + 1) + '<Width>%d</Width>' % width)
            if auto_max_width is not None:
                out.append(t(L + 1) + '<AutoMaxWidth>%s</AutoMaxWidth>' % ('true' if auto_max_width else 'false'))
            if height:
                out.append(t(L + 1) + '<Height>%d</Height>' % height)
            if stretch is not None:
                out.append(t(L + 1) + '<HorizontalStretch>%s</HorizontalStretch>' % ('true' if stretch else 'false'))
            if multiline:
                out.append(t(L + 1) + '<MultiLine>true</MultiLine>')
            if choice_button is not None:
                out.append(t(L + 1) + '<ChoiceButton>%s</ChoiceButton>' % ('true' if choice_button else 'false'))
            if clear_button is not None:
                out.append(t(L + 1) + '<ClearButton>%s</ClearButton>' % ('true' if clear_button else 'false'))
            out += self._cm_et(name, L + 1)
            out += self._events(events, L + 1)
            out.append(t(L) + '</InputField>')
        elif kind == 'check':
            _, path, name, title, events, edit_mode, ro = it
            full = table_path + '.' + path if table_path else path
            name = name or ((table_path.split('.')[-1] if table_path else '') + path.split('.')[-1])
            out.append(t(L) + '<CheckBoxField name="%s" id="%d">' % (name, self._id()))
            out.append(t(L + 1) + '<DataPath>%s</DataPath>' % full)
            if ro:
                out.append(t(L + 1) + '<ReadOnly>true</ReadOnly>')
            if title:
                out.append(ml_tag('Title', title, L + 1))
            if edit_mode or table_path:
                out.append(t(L + 1) + '<EditMode>%s</EditMode>' % (edit_mode or 'EnterOnInput'))
            out.append(t(L + 1) + '<CheckBoxType>Auto</CheckBoxType>')
            out += self._cm_et(name, L + 1)
            out += self._events(events, L + 1)
            out.append(t(L) + '</CheckBoxField>')
        elif kind == 'label':
            _, name, text, bold = it[:4]
            wide = it[4] if len(it) > 4 else False
            out.append(t(L) + '<LabelDecoration name="%s" id="%d">' % (name, self._id()))
            if wide:
                out.append(t(L + 1) + '<AutoMaxWidth>false</AutoMaxWidth>')   # порядок — по выгрузке ТОИР: первым
            if bold:
                out.append(t(L + 1) + '<Font ref="style:NormalTextFont" bold="true" italic="false" underline="false" strikeout="false" kind="StyleItem" scale="100"/>')
            out.append(ml_tag('Title', text, L + 1).replace('<Title>', '<Title formatted="false">'))
            out += self._cm_et(name, L + 1)
            out.append(t(L) + '</LabelDecoration>')
        elif kind == 'button':
            _, command, name, bkind, default = it
            name = name or command
            out.append(t(L) + '<Button name="%s" id="%d">' % (name, self._id()))
            out.append(t(L + 1) + '<Type>%s</Type>' % bkind)
            if default:
                out.append(t(L + 1) + '<DefaultButton>true</DefaultButton>')
            out.append(t(L + 1) + '<CommandName>%s</CommandName>' % (
                command if '.' in command else 'Form.Command.' + command))
            out.append(t(L + 1) + '<ExtendedTooltip name="%sРасширеннаяПодсказка" id="%d"/>' % (name, self._id()))
            out.append(t(L) + '</Button>')
        elif kind == 'sheet':
            _, path, name, events = it
            name = name or path.split('.')[-1]
            out.append(t(L) + '<SpreadSheetDocumentField name="%s" id="%d">' % (name, self._id()))
            out.append(t(L + 1) + '<DataPath>%s</DataPath>' % path)
            out.append(t(L + 1) + '<TitleLocation>None</TitleLocation>')
            out.append(t(L + 1) + '<ShowGrid>false</ShowGrid>')
            out.append(t(L + 1) + '<ShowHeaders>false</ShowHeaders>')
            out.append(t(L + 1) + '<EnableStartDrag>false</EnableStartDrag>')
            out.append(t(L + 1) + '<EnableDrag>false</EnableDrag>')
            out += self._cm_et(name, L + 1)
            out += self._events(events, L + 1)
            out.append(t(L) + '</SpreadSheetDocumentField>')
        elif kind == 'html':
            _, path, name, events, width, height = it
            name = name or path.split('.')[-1]
            out.append(t(L) + '<HTMLDocumentField name="%s" id="%d">' % (name, self._id()))
            out.append(t(L + 1) + '<DataPath>%s</DataPath>' % path)
            out.append(t(L + 1) + '<TitleLocation>None</TitleLocation>')
            out.append(t(L + 1) + '<Width>%d</Width>' % width)
            # высота 10 и растяжение по обеим осям — умолчания поля HTML в выгрузке Конфигуратора (8.3.27):
            # платформа их не пишет, сверка требует того же (ZHDRM, итерация 9)
            if height != 10:
                out.append(t(L + 1) + '<Height>%d</Height>' % height)
            out += self._cm_et(name, L + 1)
            out += self._events(events, L + 1)
            out.append(t(L) + '</HTMLDocumentField>')
        elif kind == 'table':
            (_, name, path, columns, ro, commands, events, change_rowset, header_height, autofill) = it[:10]
            height_rows = it[10] if len(it) > 10 else None
            out.append(t(L) + '<Table name="%s" id="%d">' % (name, self._id()))
            out.append(t(L + 1) + '<Representation>List</Representation>')
            if ro:
                out.append(t(L + 1) + '<ReadOnly>true</ReadOnly>')
            out.append(t(L + 1) + '<ChangeRowSet>%s</ChangeRowSet>' % ('true' if change_rowset else 'false'))
            out.append(t(L + 1) + '<ChangeRowOrder>false</ChangeRowOrder>')
            if height_rows:
                out.append(t(L + 1) + '<HeightInTableRows>%d</HeightInTableRows>' % height_rows)   # по выгрузке ТОИР
            if header_height:
                out.append(t(L + 1) + '<HeaderHeight>%d</HeaderHeight>' % header_height)
            out.append(t(L + 1) + '<AutoInsertNewRow>true</AutoInsertNewRow>')
            out.append(t(L + 1) + '<EnableStartDrag>true</EnableStartDrag>')
            out.append(t(L + 1) + '<EnableDrag>true</EnableDrag>')
            out.append(t(L + 1) + '<DataPath>%s</DataPath>' % path)
            out.append(t(L + 1) + '<RowFilter xsi:nil="true"/>')
            out.append(t(L + 1) + '<ContextMenu name="%sКонтекстноеМеню" id="%d"/>' % (name, self._id()))
            out.append(t(L + 1) + '<AutoCommandBar name="%sКоманднаяПанель" id="%d">' % (name, self._id()))
            if not autofill:
                out.append(t(L + 2) + '<Autofill>false</Autofill>')
            if commands:
                out.append(t(L + 2) + '<ChildItems>')
                for c in commands:
                    bname = name + c
                    out += [t(L + 3) + '<Button name="%s" id="%d">' % (bname, self._id()),
                            t(L + 4) + '<Type>CommandBarButton</Type>',
                            t(L + 4) + '<CommandName>Form.Command.%s</CommandName>' % c,
                            t(L + 4) + '<ExtendedTooltip name="%sРасширеннаяПодсказка" id="%d"/>' % (bname, self._id()),
                            t(L + 3) + '</Button>']
                out.append(t(L + 2) + '</ChildItems>')
            out.append(t(L + 1) + '</AutoCommandBar>')
            out.append(t(L + 1) + '<ExtendedTooltip name="%sРасширеннаяПодсказка" id="%d"/>' % (name, self._id()))
            for add, typ in (('СтрокаПоиска', 'SearchStringRepresentation'), ('СостояниеПросмотра', 'ViewStatusRepresentation'),
                             ('УправлениеПоиском', 'SearchControl')):
                tag = {'SearchStringRepresentation': 'SearchStringAddition', 'ViewStatusRepresentation': 'ViewStatusAddition',
                       'SearchControl': 'SearchControlAddition'}[typ]
                out += [t(L + 1) + '<%s name="%s%s" id="%d">' % (tag, name, add, self._id()),
                        t(L + 2) + '<AdditionSource>',
                        t(L + 3) + '<Item>%s</Item>' % name,
                        t(L + 3) + '<Type>%s</Type>' % typ,
                        t(L + 2) + '</AdditionSource>',
                        t(L + 2) + '<ContextMenu name="%s%sКонтекстноеМеню" id="%d"/>' % (name, add, self._id()),
                        t(L + 2) + '<ExtendedTooltip name="%s%sРасширеннаяПодсказка" id="%d"/>' % (name, add, self._id()),
                        t(L + 1) + '</%s>' % tag]
            out += self._events(events, L + 1)
            out.append(t(L + 1) + '<ChildItems>')
            for c in columns:
                # имя колонки по умолчанию: <Таблица><Колонка>
                if c[0] in ('input', 'check') and not c[2]:
                    c = c[:2] + (name + c[1].split('.')[-1],) + c[3:]
                out += self._render(c, L + 2, table_path=path)
            out.append(t(L + 1) + '</ChildItems>')
            out.append(t(L) + '</Table>')
        return out

    def _children(self, children, L):
        if not children:
            return []
        out = [t(L) + '<ChildItems>']
        for c in children:
            out += self._render(c, L + 1)
        out.append(t(L) + '</ChildItems>')
        return out

    def xml(self, events=None, extra_props=()):
        body = []
        if self.title:
            body.append(ml_tag('Title', self.title, 1))
        body += list(extra_props)
        body.append(t(1) + '<AutoCommandBar name="ФормаКоманднаяПанель" id="-1">')
        if not self.autofill_cmdbar:
            body.append(t(2) + '<Autofill>false</Autofill>')
        if self.cmdbar:
            body.append(t(2) + '<ChildItems>')
            for c in self.cmdbar:
                bname = 'Форма' + c
                body += [t(3) + '<Button name="%s" id="%d">' % (bname, self._id()),
                         t(4) + '<Type>CommandBarButton</Type>',
                         t(4) + '<CommandName>Form.Command.%s</CommandName>' % c,
                         t(4) + '<ExtendedTooltip name="%sРасширеннаяПодсказка" id="%d"/>' % (bname, self._id()),
                         t(3) + '</Button>']
            body.append(t(2) + '</ChildItems>')
        body.append(t(1) + '</AutoCommandBar>')
        if events:
            порядок = {e: i for i, e in enumerate(FORM_EVENT_ORDER)}
            events = dict(sorted(events.items(), key=lambda kv: порядок.get(kv[0], len(порядок))))
        body += self._events(events, 1)
        body += self._children(self.items, 1)
        # реквизиты
        body.append(t(1) + '<Attributes>')
        for n, (name, spec, title, main, columns, save) in enumerate(self.attrs, 1):
            body.append(t(2) + '<Attribute name="%s" id="%d">' % (name, n))
            if title:
                body.append(ml_tag('Title', title, 3))
            body.append(type_xml(spec, 3))
            if main:
                body.append(t(3) + '<MainAttribute>true</MainAttribute>')
                if spec.startswith(('cfg:CatalogObject.', 'cfg:DocumentObject.')):
                    body.append(t(3) + '<SavedData>true</SavedData>')     # форма объекта: «Записать» (как в выгрузке)
            if save:
                body += [t(3) + '<Save>', t(4) + '<Field>%s</Field>' % name, t(3) + '</Save>']
            if columns:
                body.append(t(3) + '<Columns>')
                for k, col in enumerate(columns, 1):
                    body.append(t(4) + '<Column name="%s" id="%d">' % (col[0], k))
                    body.append(ml_tag('Title', col[2] if len(col) > 2 and col[2] else synonym(col[0]), 5))
                    body.append(type_xml(col[1], 5))
                    body.append(t(4) + '</Column>')
                body.append(t(3) + '</Columns>')
            body.append(t(2) + '</Attribute>')
        body.append(t(1) + '</Attributes>')
        if self.cmds:
            body.append(t(1) + '<Commands>')
            for n, (name, title, action, tooltip, picture, representation) in enumerate(self.cmds, 1):
                body.append(t(2) + '<Command name="%s" id="%d">' % (name, n))
                body.append(ml_tag('Title', title, 3))
                body.append(ml_tag('ToolTip', tooltip or title, 3))
                if picture:
                    body += [t(3) + '<Picture>', t(4) + '<xr:Ref>%s</xr:Ref>' % picture,
                             t(4) + '<xr:LoadTransparent>true</xr:LoadTransparent>', t(3) + '</Picture>']
                body.append(t(3) + '<Action>%s</Action>' % action)
                if representation:
                    body.append(t(3) + '<Representation>%s</Representation>' % representation)
                body.append(t(2) + '</Command>')
            body.append(t(1) + '</Commands>')
        if self.params:
            body.append(t(1) + '<Parameters>')
            for name, spec, key in self.params:
                body.append(t(2) + '<Parameter name="%s">' % name)
                body.append(type_xml(spec, 3))
                if key:
                    body.append(t(3) + '<KeyParameter>true</KeyParameter>')
                body.append(t(2) + '</Parameter>')
            body.append(t(1) + '</Parameters>')
        if self.navigation:
            # связанные списки в панели навигации формы объекта (формат — ТОИР, Catalogs/ВидыЦен/ФормаЭлемента)
            body += [t(1) + '<CommandInterface>', t(2) + '<NavigationPanel>']
            for cmd, visible in self.navigation:
                body += [t(3) + '<Item>', t(4) + '<Command>%s</Command>' % cmd, t(4) + '<Type>Auto</Type>']
                if not visible:
                    body += [t(4) + '<DefaultVisible>false</DefaultVisible>', t(4) + '<Visible>',
                             t(5) + '<xr:Common>false</xr:Common>', t(4) + '</Visible>']
                body.append(t(3) + '</Item>')
            body += [t(2) + '</NavigationPanel>', t(1) + '</CommandInterface>']
        return ('<?xml version="1.0" encoding="UTF-8"?>\n<Form %s version="%s">\n' % (FORM_NS, VERSION) +
                '\n'.join(body) + '\n</Form>\n')


# --------------------------------------------------------------------- файлы
def write(path, text):
    """UTF-8 с BOM, CRLF — как пишет Конфигуратор. Возвращает True, если файл изменился."""
    data = text.replace('\r\n', '\n').replace('\n', '\r\n')
    if os.path.exists(path):
        with io.open(path, encoding='utf-8-sig', newline='') as f:
            if f.read() == data:
                return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, 'w', encoding='utf-8-sig', newline='') as f:
        f.write(data)
    return True


def read(path):
    with io.open(path, encoding='utf-8-sig', newline='') as f:
        return f.read()


def normalize(path):
    """Привести файл к виду выгрузки (BOM, CRLF) — модули, написанные редактором с LF."""
    return write(path, read(path))


def register_in_configuration(dump, kind, name):
    """Строка <Kind>Имя</Kind> в ChildObjects Configuration.xml — после последней того же вида."""
    path = os.path.join(dump, 'Configuration.xml')
    text = read(path)
    tag = '<%s>%s</%s>' % (kind, name, kind)
    if tag in text:
        return False
    items = list(re.finditer(r'\r\n(\t+)<%s>[^<]*</%s>' % (kind, kind), text))
    if not items:
        raise RuntimeError('в Configuration.xml нет ни одного %s — вставить вручную по образцу' % kind)
    last = items[-1]
    text = text[:last.end()] + '\r\n' + last.group(1) + tag + text[last.end():]
    write(path, text)
    return True


def add_rights(dump, role, obj, rights=('Use', 'View')):
    """Права роли на объект (Roles/<роль>/Ext/Rights.xml); объект — 'DataProcessor.Имя'."""
    path = os.path.join(dump, 'Roles', role, 'Ext', 'Rights.xml')
    text = read(path)
    if '<name>%s</name>' % obj in text:
        return False
    block = ['\t<object>', '\t\t<name>%s</name>' % obj]
    for r in rights:
        block += ['\t\t<right>', '\t\t\t<name>%s</name>' % r, '\t\t\t<value>true</value>', '\t\t</right>']
    block.append('\t</object>')
    i = text.index('\t<object>')
    text = text[:i] + '\r\n'.join(block) + '\r\n' + text[i:]
    write(path, text)
    return True


def add_to_subsystem(subsystem_xml, obj):
    """Объект в Content подсистемы (xr:Item MDObjectRef)."""
    text = read(subsystem_xml)
    item = '<xr:Item xsi:type="xr:MDObjectRef">%s</xr:Item>' % obj
    if item in text:
        return False
    m = re.search(r'(\r\n(\t+))</Content>', text)
    if m:
        text = text[:m.start()] + m.group(1) + '\t' + item + text[m.start():]
    else:
        m = re.search(r'(\r\n(\t+))<Content/>', text)
        ind = m.group(2)
        text = (text[:m.start()] + '\r\n' + ind + '<Content>\r\n' + ind + '\t' + item + '\r\n' + ind + '</Content>' +
                text[m.end():])
    write(subsystem_xml, text)
    return True


# ------------------------------------------------------------ пакетный Конфигуратор
def designer(v8, ib, args, log, user='Администратор', pwd='', timeout=3600):
    """Командная строка СТРОКОЙ: списком пустой пароль /P"" теряет кавычки и Конфигуратор
    ждёт окна авторизации (knowledge/testing.md). Возвращает (код, текст лога)."""
    cred = ' /N"%s" /P"%s"' % (user, pwd) if user else ''
    ib_arg = '/S"%s"' % ib[2:] if ib.startswith('S:') else '/F"%s"' % ib
    cmd = '"%s" DESIGNER %s%s /DisableStartupDialogs /DisableStartupMessages %s /Out "%s"' % (
        v8, ib_arg, cred, ' '.join(args), log)
    if os.path.exists(log):
        os.remove(log)
    t0 = time.time()
    r = subprocess.run(cmd, timeout=timeout)
    txt = ''
    if os.path.exists(log):
        with io.open(log, encoding='utf-8-sig', errors='replace') as f:
            txt = f.read().strip()
    return r.returncode, txt, time.time() - t0


def load_files(v8, ib, dump, files, log, extension=None, **kw):
    """Частичная загрузка: files — пути относительно dump. Configuration.xml добавляется
    сам (без него новые объекты не видны, deployment.md §6). Полную загрузку XML не делать:
    ломает ключи защиты вендоров (1С-Рарус, СЛК) — ЛОВУШКИ МВМ."""
    files = list(dict.fromkeys(['Configuration.xml'] + [f.replace('/', os.sep) for f in files]))
    lst = log + '.files.txt'
    with io.open(lst, 'w', encoding='utf-8-sig') as f:
        f.write('\n'.join(os.path.join(dump, x) for x in files))
    args = ['/LoadConfigFromFiles "%s"' % dump, '-listFile "%s"' % lst]
    if extension:
        args.append('-Extension "%s"' % extension)
    args.append('-updateConfigDumpInfo')
    return designer(v8, ib, args, log, **kw)


def update_db(v8, ib, log, extension=None, **kw):
    args = ['/UpdateDBCfg']
    if extension:
        args.append('-Extension "%s"' % extension)
    return designer(v8, ib, args, log, **kw)


def check_modules(v8, ib, log, extension=None, modes=('-ThinClient', '-Server', '-ExternalConnection'), **kw):
    """/CheckModules — компиляция модулей в режимах; код 0 и пустой лог — чисто."""
    args = ['/CheckModules'] + list(modes)
    if extension:
        args.append('-Extension "%s"' % extension)
    return designer(v8, ib, args, log, **kw)


def dump_epf(v8, ib, epf, out_dir, log, **kw):
    """Внешняя обработка/отчёт → XML (каталог; корневой файл <Имя>.xml)."""
    os.makedirs(out_dir, exist_ok=True)
    return designer(v8, ib, ['/DumpExternalDataProcessorOrReportToFiles "%s" "%s"' % (out_dir, epf)], log, **kw)


def build_epf(v8, ib, root_xml, epf, log, **kw):
    """XML → .epf/.erf. root_xml — корневой файл <Имя>.xml выгрузки. Типы из конфигурации
    базы ib разрешаются при сборке: собирать на базе с той же конфигурацией."""
    return designer(v8, ib, ['/LoadExternalDataProcessorOrReportFromFiles "%s" "%s"' % (root_xml, epf)], log, **kw)


def dump(v8, ib, out, log, extension=None, **kw):
    args = ['/DumpConfigToFiles "%s"' % out, '-Format Hierarchical']
    if extension:
        args.append('-Extension "%s"' % extension)
    return designer(v8, ib, args, log, **kw)
