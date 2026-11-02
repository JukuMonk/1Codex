# -*- coding: utf-8 -*-
"""Форма списка «Оборудование» (итерация 9): динамический список с текущим состоянием из регистра, цвет
состояния — условным оформлением, автообновление раз в минуту. Формат — по выгрузке ТОИР
(Catalogs/Валюты/Forms/ФормаСписка): Table + SearchStringAddition/ViewStatusAddition/SearchControlAddition,
Attribute «Список» cfg:DynamicList с Settings xsi:type="DynamicList" (ManualQuery, QueryText, MainTable, ListSettings).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import платформа as пл  # noqa: E402
dl = пл.dl
t = dl.t
П = 'пульс_'

ЗАПРОС = '''ВЫБРАТЬ
	Обор.Ссылка КАК Ссылка,
	Обор.ПометкаУдаления КАК ПометкаУдаления,
	Обор.Наименование КАК Наименование,
	Обор.ИнвентарныйНомер КАК ИнвентарныйНомер,
	Обор.Цех КАК Цех,
	Обор.ВидОборудования КАК ВидОборудования,
	Обор.Модель КАК Модель,
	Обор.ПлановыйФондЧасовВСутки КАК ПлановыйФонд,
	Обор.Активно КАК Активно,
	ЕСТЬNULL(Тек.Состояние, ЗНАЧЕНИЕ(Перечисление.пульс_СостоянияОборудования.UNKNOWN)) КАК Состояние,
	ДОБАВИТЬКДАТЕ(Тек.ДатаНачалаСостоянияUTC, СЕКУНДА, &Смещение) КАК СостояниеС,
	Тек.ПоследнееЗначение КАК Ток
ИЗ
	Справочник.пульс_Оборудование КАК Обор
		ЛЕВОЕ СОЕДИНЕНИЕ РегистрСведений.пульс_ТекущиеСостоянияОборудования КАК Тек
		ПО Обор.Ссылка = Тек.Оборудование'''

# колонка, заголовок, ширина
КОЛОНКИ = [('Наименование', None, 34, None), ('ИнвентарныйНомер', 'Инв. номер', 11, None), ('Цех', None, 22, None),
           ('ВидОборудования', 'Вид', 18, None), ('Модель', None, 11, None), ('Состояние', None, 16, None),
           ('СостояниеС', 'С', 11, "ДФ='dd.MM HH:mm'"), ('Ток', 'Ток, А', 7, 'ЧДЦ=1; ЧН=—'),
           ('ПлановыйФонд', 'План, ч/сут', 8, 'ЧДЦ=0'), ('Активно', 'В мониторинге', 6, None)]
ЦВЕТА = [('WORK', '#2E7D32'), ('OVERLOAD', '#C62828'), ('IDLE', '#B7791F'), ('OFF', '#546E7A'),
         ('OFFLINE', '#8A939C'), ('UNKNOWN', '#7E57C2')]


# идентификаторы пользовательских настроек динамического списка платформа заменяет постоянными (сверка 8.3.27)
ИД_ОТБОРА = 'dfcece9d-5077-440b-b6b3-45a5cb4538eb'
ИД_ПОРЯДКА = '88619765-ccb3-46c6-ac52-38e9c992ebd4'
ИД_ЭЛЕМЕНТОВ = '911b6018-f537-43e8-a417-da56b22f9aec'


def _uid(*части):
    return str(dl.uid('Catalog.пульс_Оборудование', 'ФормаСписка', *части))


def _добавка(вид, имя, тип, ид):
    return [t(3) + '<%s name="Список%s" id="%d">' % (вид, имя, ид),
            t(4) + '<AdditionSource>', t(5) + '<Item>Список</Item>', t(5) + '<Type>%s</Type>' % тип, t(4) + '</AdditionSource>',
            t(4) + '<ContextMenu name="Список%sКонтекстноеМеню" id="%d"/>' % (имя, ид + 1),
            t(4) + '<ExtendedTooltip name="Список%sРасширеннаяПодсказка" id="%d"/>' % (имя, ид + 2),
            t(3) + '</%s>' % вид]


def форма_списка():
    p = ['<?xml version="1.0" encoding="UTF-8"?>', '<Form %s version="%s">' % (dl.FORM_NS, dl.VERSION),
         t(1) + '<AutoCommandBar name="ФормаКоманднаяПанель" id="-1"/>',
         t(1) + '<Events>', t(2) + '<Event name="OnCreateAtServer">ПриСозданииНаСервере</Event>', t(1) + '</Events>',
         t(1) + '<ChildItems>',
         t(2) + '<Table name="Список" id="1">',
         t(3) + '<Representation>List</Representation>',
         t(3) + '<CommandBarLocation>None</CommandBarLocation>',
         t(3) + '<DefaultItem>true</DefaultItem>',
         t(3) + '<UseAlternationRowColor>true</UseAlternationRowColor>',
         t(3) + '<DataPath>Список</DataPath>',
         t(3) + '<RowPictureDataPath>Список.DefaultPicture</RowPictureDataPath>',
         t(3) + '<AutoRefresh>true</AutoRefresh>',
         t(3) + '<AutoRefreshPeriod>60</AutoRefreshPeriod>',
         t(3) + '<Period>', t(4) + '<v8:variant xsi:type="v8:StandardPeriodVariant">Custom</v8:variant>',
         t(4) + '<v8:startDate>0001-01-01T00:00:00</v8:startDate>', t(4) + '<v8:endDate>0001-01-01T00:00:00</v8:endDate>',
         t(3) + '</Period>',
         t(3) + '<ChoiceFoldersAndItems>Items</ChoiceFoldersAndItems>',
         t(3) + '<RestoreCurrentRow>false</RestoreCurrentRow>',
         t(3) + '<TopLevelParent xsi:nil="true"/>',
         t(3) + '<ShowRoot>true</ShowRoot>',
         t(3) + '<AllowRootChoice>false</AllowRootChoice>',
         t(3) + '<UpdateOnDataChange>Auto</UpdateOnDataChange>',
         t(3) + '<AllowGettingCurrentRowURL>true</AllowGettingCurrentRowURL>',
         t(3) + '<ContextMenu name="СписокКонтекстноеМеню" id="2"/>',
         t(3) + '<AutoCommandBar name="СписокКоманднаяПанель" id="3"/>',
         t(3) + '<ExtendedTooltip name="СписокРасширеннаяПодсказка" id="4"/>']
    p += _добавка('SearchStringAddition', 'СтрокаПоиска', 'SearchStringRepresentation', 5)
    p += _добавка('ViewStatusAddition', 'СостояниеПросмотра', 'ViewStatusRepresentation', 8)
    p += _добавка('SearchControlAddition', 'УправлениеПоиском', 'SearchControl', 11)
    p.append(t(3) + '<ChildItems>')
    ид = 20
    for имя, заголовок, ширина, формат in КОЛОНКИ:
        вид = 'CheckBoxField' if имя == 'Активно' else 'LabelField'
        p += [t(4) + '<%s name="%s" id="%d">' % (вид, имя, ид), t(5) + '<DataPath>Список.%s</DataPath>' % имя]
        if заголовок:
            p.append(dl.ml_tag('Title', заголовок, 5))
        if вид == 'LabelField':
            p.append(t(5) + '<Width>%d</Width>' % ширина)
            if формат:
                p.append(dl.ml_tag('Format', формат, 5))
        else:
            p += [t(5) + '<EditMode>EnterOnInput</EditMode>', t(5) + '<CheckBoxType>Auto</CheckBoxType>']
        p += [t(5) + '<ContextMenu name="%sКонтекстноеМеню" id="%d"/>' % (имя, ид + 1),
              t(5) + '<ExtendedTooltip name="%sРасширеннаяПодсказка" id="%d"/>' % (имя, ид + 2),
              t(4) + '</%s>' % вид]
        ид += 3
    p += [t(3) + '</ChildItems>', t(2) + '</Table>', t(1) + '</ChildItems>']
    # реквизит «Список»
    q = ЗАПРОС.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    p += [t(1) + '<Attributes>', t(2) + '<Attribute name="Список" id="1">',
          t(3) + '<Type>', t(4) + '<v8:Type>cfg:DynamicList</v8:Type>', t(3) + '</Type>',
          t(3) + '<MainAttribute>true</MainAttribute>',
          t(3) + '<Settings xsi:type="DynamicList">',
          t(4) + '<ManualQuery>true</ManualQuery>', t(4) + '<DynamicDataRead>true</DynamicDataRead>',
          t(4) + '<QueryText>%s</QueryText>' % q,
          t(4) + '<MainTable>Catalog.%sОборудование</MainTable>' % П,
          t(4) + '<ListSettings>',
          t(5) + '<dcsset:filter>', t(6) + '<dcsset:viewMode>Normal</dcsset:viewMode>',
          t(6) + '<dcsset:userSettingID>%s</dcsset:userSettingID>' % ИД_ОТБОРА, t(5) + '</dcsset:filter>',
          t(5) + '<dcsset:order>', t(6) + '<dcsset:viewMode>Normal</dcsset:viewMode>',
          t(6) + '<dcsset:userSettingID>%s</dcsset:userSettingID>' % ИД_ПОРЯДКА, t(5) + '</dcsset:order>',
          t(5) + '<dcsset:conditionalAppearance>']
    for код, цвет in ЦВЕТА:
        p += [t(6) + '<dcsset:item>', t(7) + '<dcsset:selection>', t(8) + '<dcsset:item>',
              t(9) + '<dcsset:field>Состояние</dcsset:field>', t(8) + '</dcsset:item>', t(7) + '</dcsset:selection>',
              t(7) + '<dcsset:filter>', t(8) + '<dcsset:item xsi:type="dcsset:FilterItemComparison">',
              t(9) + '<dcsset:left xsi:type="dcscor:Field">Состояние</dcsset:left>',
              t(9) + '<dcsset:comparisonType>Equal</dcsset:comparisonType>',
              t(9) + '<dcsset:right xsi:type="dcscor:DesignTimeValue">Перечисление.пульс_СостоянияОборудования.%s</dcsset:right>' % код,
              t(8) + '</dcsset:item>', t(7) + '</dcsset:filter>', t(7) + '<dcsset:appearance>',
              t(8) + '<dcscor:item xsi:type="dcsset:SettingsParameterValue">',
              t(9) + '<dcscor:parameter>ЦветТекста</dcscor:parameter>',
              t(9) + '<dcscor:value xsi:type="v8ui:Color">%s</dcscor:value>' % цвет, t(8) + '</dcscor:item>',
              t(8) + '<dcscor:item xsi:type="dcsset:SettingsParameterValue">',
              t(9) + '<dcscor:parameter>Шрифт</dcscor:parameter>',
              t(9) + '<dcscor:value xsi:type="v8ui:Font" ref="sys:DefaultGUIFont" bold="true" italic="false" underline="false" strikeout="false" kind="WindowsFont"/>',
              t(8) + '</dcscor:item>', t(7) + '</dcsset:appearance>', t(6) + '</dcsset:item>']
    p += [t(6) + '<dcsset:viewMode>Normal</dcsset:viewMode>',
          t(6) + '<dcsset:userSettingID>%s</dcsset:userSettingID>' % _uid('ca'), t(5) + '</dcsset:conditionalAppearance>',
          t(5) + '<dcsset:itemsViewMode>Normal</dcsset:itemsViewMode>',
          t(5) + '<dcsset:itemsUserSettingID>%s</dcsset:itemsUserSettingID>' % ИД_ЭЛЕМЕНТОВ,
          t(4) + '</ListSettings>', t(3) + '</Settings>', t(2) + '</Attribute>', t(1) + '</Attributes>', '</Form>', '']
    return '\n'.join(p)
