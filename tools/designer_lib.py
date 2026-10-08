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
           'xmlns:dcsset="http://v8.1c.ru/8.1/data-composition-system/settings" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" '
           'xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" '
           'xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" '
           'xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" '
           'xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" '
           'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"')
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
                       explanation=None):
    """attributes: [(имя, тип[, заголовок])]; tabular_sections: [(имя, [колонки][, заголовок])];
    forms: [имя]. Свой объект расширения — без ObjectBelonging (как в выгрузке)."""
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
    for f in forms:
        p.append(t(3) + '<Form>%s</Form>' % f)
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
         t(3) + '</UsePurposes>',
         t(3) + '<ExtendedPresentation/>',
         t(2) + '</Properties>',
         t(1) + '</Form>']
    return md_object_file('\n'.join(p))


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

    def _id(self):
        i = self.next_id
        self.next_id += 1
        return i

    # --- реквизиты и команды
    def attr(self, name, spec, title=None, main=False, columns=(), save=False):
        self.attrs.append((name, spec, title, main, columns, save))

    def command(self, name, title, action=None, tooltip=None, picture=None, representation=None):
        self.cmds.append((name, title, action or name, tooltip, picture, representation))

    # --- элементы: возвращают (функция_рендера) — id выдаются при рендере, по порядку
    def group(self, name, children, kind='vertical', title=None, show_title=False, representation='None'):
        return ('group', name, children, kind, title, show_title, representation)

    def pages(self, name, pages):
        return ('pages', name, pages)

    def page(self, name, title, children):
        return ('page', name, title, children)

    def input(self, path, name=None, title=None, read_only=False, events=None, width=None, title_loc=None,
              edit_mode=None, multiline=False, height=None, choice_button=None, clear_button=None):
        return ('input', path, name, title, read_only, events, width, title_loc, edit_mode, multiline, height,
                choice_button, clear_button)

    def check(self, path, name=None, title=None, events=None, edit_mode=None, read_only=False):
        return ('check', path, name, title, events, edit_mode, read_only)

    def label(self, name, text, font_bold=False):
        return ('label', name, text, font_bold)

    def button(self, command, name=None, kind='UsualButton', default=False):
        return ('button', command, name, kind, default)

    def spreadsheet(self, path, name=None, events=None):
        return ('sheet', path, name, events)

    def table(self, name, path, columns, read_only=False, commands=(), events=None, change_rowset=False,
              header_height=None, autofill=False):
        """columns: элементы input()/check() с путём 'Колонка' (путь таблицы добавится)."""
        return ('table', name, path, columns, read_only, commands, events, change_rowset, header_height, autofill)

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
             choice_button, clear_button) = it
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
            if height:
                out.append(t(L + 1) + '<Height>%d</Height>' % height)
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
            _, name, text, bold = it
            out.append(t(L) + '<LabelDecoration name="%s" id="%d">' % (name, self._id()))
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
        elif kind == 'table':
            (_, name, path, columns, ro, commands, events, change_rowset, header_height, autofill) = it
            out.append(t(L) + '<Table name="%s" id="%d">' % (name, self._id()))
            out.append(t(L + 1) + '<Representation>List</Representation>')
            if ro:
                out.append(t(L + 1) + '<ReadOnly>true</ReadOnly>')
            out.append(t(L + 1) + '<ChangeRowSet>%s</ChangeRowSet>' % ('true' if change_rowset else 'false'))
            out.append(t(L + 1) + '<ChangeRowOrder>false</ChangeRowOrder>')
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
