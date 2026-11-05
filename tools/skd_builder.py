"""Shared SKD generation; stable legacy UUID seeds retained."""
import re
import uuid
import xml.etree.ElementTree as ET

CRLF = '\r\n'


def stable_uid(seed):
    """Устойчивый uuid от строки: повторная сборка не плодит НОВЫЕ объекты
    (новый объект база принимает только полным обновлением — case 020)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'edt-skill/' + seed))


def join(lines):
    return CRLF.join(lines)


def esc(text):
    return (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


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

