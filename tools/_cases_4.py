# -*- coding: utf-8 -*-
"""Кейсы 037–046: константа вместо XML, динамический список, ссылки на формы, картинка, мобильные таблицы, пакеты запросов, Попытка, пропуски при записи, перечисления, пустой запрос."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cases_lib import case  # noqa: E402

W = '<!-- WRONG: так НЕ делать -->\n'
C = '<!-- CORRECT -->\n'
WB = '// WRONG: так НЕ делать\n'
CB = '// CORRECT\n'

case(37, 'hide-by-constant-in-module-not-xml',
     """
# Упрощённая типовая форма: скрывать и переставлять в модуле под константой, не в XML

**Объекты.** Форма документа «Заказ на ТС» (типовая), константа
мвмУпрощённаяФормаЗаявки.

**Confidence:** HIGH — первая версия правила скрывала в XML; переделано на
константу по запросу, работает; диагностика «почему появилось поле Договор»
показала побочный эффект перестановок.
""",
     """
# Уроки

**attempt-1 (WRONG).** Скрытие элементов правкой XML (убрать `<visible>`,
переставить группы). Форма перестала быть типовой, отключить упрощение
нельзя.

**final.** XML остаётся типовым (в него добавлены только свои элементы).
В модуле: `мвмУпроститьФорму()` в конце `ПриСозданииНаСервере` переносит
группы `Элементы.Переместить(Элементы.X, Элементы.ГруппаДополнительно, Перед)`
и зовёт `мвмСкрытьЛишнее()` — список имён в одну строку,
`Элементы[Имя].Видимость = Ложь`. Тот же `мвмСкрытьЛишнее()` вставлен и в
конец типовой `УстановитьВидимость`: она часть вкладок показывает заново.
Всё под `Константы.X.Получить()`; выключенная константа = типовая форма.
Умолчания нового объекта (вид доставки, заказчик, организация) — тоже в
модуле под константой, ПОСЛЕ типовых умолчаний из настроек пользователя,
иначе типовая перекроет (case 037-bis в истории: вид доставки не ставился).

**Побочный эффект.** Когда из правой колонки шапки уехали соседи, одинокая
типовая группа «Договор» стала видна — переносить группу целиком, а не
надеяться, что «спрячется».

**Коммиты.** MVM 20bc39f (XML), c9f9aa8 (константа), cf5d9e7, 38b8e20, 5a39ad8, 9d38eed.

**Ссылки.** `examples/bsl/hide-by-constant.bsl`, `reference/generators/упростить_форму_заказа.py`.
""",
     attempts=[
         ('attempt-1-xml', [('note.md', """
WRONG: убирать <visible> у типовых элементов и переставлять группы в
Form.form. Работает, но необратимо: типовая форма потеряна, переключить нельзя,
пересборка типовой затирает.
""")]),
         ('final', [('Module.bsl.fragment', CB + """
&НаСервереБезКонтекста
Функция мвмУпрощённаяФормаЗаявки()
	Возврат Константы.мвмУпрощённаяФормаЗаявки.Получить();
КонецФункции

&НаСервере
Процедура мвмУпроститьФорму()
	Если НЕ мвмУпрощённаяФормаЗаявки() Тогда
		Возврат;
	КонецЕсли;
	Перед = Элементы.ГруппаДополнительныеРеквизитыКолонки;
	Элементы.Переместить(Элементы.ГруппаЗаказчик, Элементы.ГруппаДополнительно, Перед);
	Элементы.Переместить(Элементы.ГруппаДетализация, Элементы.ГруппаДополнительно, Перед);
	Элементы.Переместить(Элементы.ГруппаОрганизация, Элементы.ГруппаДополнительно, Перед);
	мвмСкрытьЛишнее();
КонецПроцедуры

&НаСервере
Процедура мвмСкрытьЛишнее()
	Если НЕ мвмУпрощённаяФормаЗаявки() Тогда
		Возврат;
	КонецЕсли;
	Лишнее = "ПодменюФинансы,ГруппаКонтактноеЛицоЗаказчика,ГруппаСтраницаДопУслуги,СтраницыИтогов";
	Для Каждого Имя Из СтрРазделить(Лишнее, ",") Цикл
		Элементы[Имя].Видимость = Ложь;
	КонецЦикла;
КонецПроцедуры

// вызовы вставлены генератором:
//   в конец ПриСозданииНаСервере:  мвмУпроститьФорму();
//   в конец УстановитьВидимость:   мвмСкрытьЛишнее();
""")])])

case(38, 'dynamic-list-settings-group',
     """
# Форме списка нужна группа пользовательских настроек динамического списка

**Объекты.** Формы списков справочников и регистров (10 форм), собранные
генератором по образцу типовой формы списка.

**Confidence:** MEDIUM — образец снят с типовой (ItobВидыГруппировок), формы работают.
""",
     """
# Уроки

**Что.** Динамический список ссылается `<userSettingsGroup>` на группу
формы (`СписокКомпоновщикНастроекПользовательскиеНастройки`), которая стоит
ПЕРЕД таблицей: обычная группа Vertical/WeakSeparation с `verticalStretch
false`. Таблица списка: `defaultItem` у таблицы и у основной колонки, колонки
`LabelField`, `commandBarLocation None` (панель формы рисует команды сама),
спутники, `DynamicListTableExtInfo` (autoRefreshPeriod, period, topLevelParent,
showRoot, allowGettingCurrentRowURL, userSettingsGroup); у иерархического
справочника — `representation HierarchicalList`. Реквизит `Список :
DynamicList` с `DynamicListExtInfo` (mainTable, dynamicDataRead,
autoFillAvailableFields, autoSaveUserSettings, getInvisibleFieldPresentations),
extInfo формы `DynamicListFormExtInfo`.

**Коммиты.** MVM 1575b57 (`формы_логистики.py`).

**Ссылки.** `examples/forms/list-form/`, `tools/edt_lib.dynamic_list_table`.
""",
     after=[('list-form.skeleton.xml', C + """
  <items xsi:type="form:FormGroup">              ← группа настроек ПЕРЕД списком
    <name>СписокКомпоновщикНастроекПользовательскиеНастройки</name>
    …
    <verticalStretch>false</verticalStretch>
    …
    <type>UsualGroup</type>
    <extInfo xsi:type="form:UsualGroupExtInfo">
      <group>Vertical</group>
      <representation>WeakSeparation</representation>
      <showLeftMargin>true</showLeftMargin>
      <united>true</united>
      <throughAlign>Auto</throughAlign>
      <currentRowUse>Auto</currentRowUse>
    </extInfo>
  </items>
  <items xsi:type="form:Table">
    <name>Список</name>
    … <defaultItem>true</defaultItem> <titleLocation>None</titleLocation>
    … колонки LabelField, у основной <defaultItem>true</defaultItem> после </dataPath>
    <commandBarLocation>None</commandBarLocation>
    <autoCommandBar>…</autoCommandBar>
    … спутники … <extendedTooltip> <contextMenu>
    … свойства …
    <extInfo xsi:type="form:DynamicListTableExtInfo">
      <autoRefreshPeriod>60</autoRefreshPeriod>
      <period><startDate>0001-01-01T00:00:00</startDate><endDate>0001-01-01T00:00:00</endDate></period>
      <topLevelParent xsi:type="core:UndefinedValue"/>
      <showRoot>true</showRoot>
      <allowGettingCurrentRowURL>true</allowGettingCurrentRowURL>
      <userSettingsGroup>СписокКомпоновщикНастроекПользовательскиеНастройки</userSettingsGroup>
    </extInfo>
  </items>
  …
  <attributes>
    <name>Список</name> <id>1</id>
    <valueType><types>DynamicList</types></valueType>
    … <main>true</main>
    <extInfo xsi:type="form:DynamicListExtInfo">
      <mainTable>Catalog.ПримерСправочник</mainTable>
      <dynamicDataRead>true</dynamicDataRead>
      <autoFillAvailableFields>true</autoFillAvailableFields>
      <autoSaveUserSettings>true</autoSaveUserSettings>
      <getInvisibleFieldPresentations>true</getInvisibleFieldPresentations>
    </extInfo>
  </attributes>
  …
  <extInfo xsi:type="form:DynamicListFormExtInfo"/>
""")])

case(39, 'mdo-form-reference-tag-order',
     """
# Место ссылки на форму в .mdo зависит от вида объекта

**Объекты.** Справочники (defaultObjectForm после choiceMode) и регистры
сведений (defaultRecordForm ДО dataLockControlMode).

**Confidence:** MEDIUM — сверено с типовыми объектами, формы открываются.
""",
     """
# Уроки

**Что.** Порядок тегов в .mdo задан схемой, и «куда-нибудь перед
реквизитами» мало: у регистра `dataLockControlMode` стоит ПОСЛЕ ссылок на
формы, у справочника — ДО. Генератор ищет последний тег-предшественник по
виду объекта (`choiceMode/editType/quickChoice/useStandardCommands/
hierarchical` у справочника; `editType/useStandardCommands/
informationRegisterPeriodicity/writeMode` у регистра) и соблюдает порядок
`defaultObjectForm → defaultRecordForm → defaultListForm → defaultChoiceForm`.

**Коммиты.** MVM 1575b57.

**Ссылки.** `tools/edt_lib.add_form_to_mdo`, `examples/metadata/information-register/`.
""",
     after=[('register.mdo.fragment.xml', C + """
  <useStandardCommands>true</useStandardCommands>
  <editType>InDialog</editType>
  <defaultRecordForm>InformationRegister.X.Form.ФормаЗаписи</defaultRecordForm>
  <defaultListForm>InformationRegister.X.Form.ФормаСписка</defaultListForm>
  <dataLockControlMode>Managed</dataLockControlMode>
  <dimensions uuid="…">
"""), ('catalog.mdo.fragment.xml', C + """
  <defaultPresentation>AsDescription</defaultPresentation>
  <editType>InDialog</editType>
  <choiceMode>BothWays</choiceMode>
  <defaultObjectForm>Catalog.X.Form.ФормаЭлемента</defaultObjectForm>
  <defaultListForm>Catalog.X.Form.ФормаСписка</defaultListForm>
  <attributes uuid="…">
""")])

case(40, 'picture-zip-manifest',
     """
# Общая картинка раздела — zip с восемью масштабами и манифестом

**Объекты.** CommonPictures/мвмЗаводскаяЛогистика (Picture.zip + .mdo),
подсистема с `<picture>`.

**Confidence:** MEDIUM — формат снят с типового «Раздел Администрирование»,
иконка отображается чётко.
""",
     """
# Уроки

**Что.** С одним PNG платформа показывает иконку мыльной. В zip: `85.png`
(14) bldpi, `100.png` (16) ldpi, `125.png` (20) aldpi, `150.png` (24) mdpi,
`175.png` (28) amdpi, `200.png` (32) hdpi, `300.png` (48) xdpi, `400.png`
(64) udpi, `Picture.png` (16, interfaceVariant version8_2) и `manifest.xml`
(с BOM). Рисовать крупно и уменьшать — края мягче. В Configuration.mdo
`<commonPictures>` по алфавиту.

**Коммиты.** MVM 1575b57.

**Ссылки.** `tools/edt_lib.picture_manifest`, `tools/make_examples.py:make_picture`,
`reference/CommonPictures/мвмЗаводскаяЛогистика/`.
""",
     after=[('manifest.xml', C + """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Picture>
	<PictureVariant name="85.png" screenDensity="bldpi" glyphWidth="14" glyphHeight="14"/>
	<PictureVariant name="100.png" screenDensity="ldpi" glyphWidth="16" glyphHeight="16"/>
	<PictureVariant name="125.png" screenDensity="aldpi" glyphWidth="20" glyphHeight="20"/>
	<PictureVariant name="150.png" screenDensity="mdpi" glyphWidth="24" glyphHeight="24"/>
	<PictureVariant name="175.png" screenDensity="amdpi" glyphWidth="28" glyphHeight="28"/>
	<PictureVariant name="200.png" screenDensity="hdpi" glyphWidth="32" glyphHeight="32"/>
	<PictureVariant name="300.png" screenDensity="xdpi" glyphWidth="48" glyphHeight="48"/>
	<PictureVariant name="400.png" screenDensity="udpi" glyphWidth="64" glyphHeight="64"/>
	<PictureVariant name="Picture.png" interfaceVariant="version8_2" screenDensity="ldpi" glyphWidth="16" glyphHeight="16"/>
</Picture>
""")])

case(41, 'mobile-table-and-buttons',
     """
# Мобильная таблица и кнопки после первого просмотра на телефоне

**Объекты.** Мобильная форма АРМ водителя.

**Confidence:** HIGH — правки по итогам просмотра на телефоне.
""",
     """
# Уроки

- Командная панель таблицы: телефон подставлял «More actions» на своём
  языке, а нужного там не было → `commandBarLocation None`.
- Строка поиска, состояние просмотра и управление поиском — три полосы над
  таблицей в две строки → `searchStringLocation/viewStatusLocation/
  searchControlLocation None`; сами спутники в XML остаются (case 004).
- Булевы колонки показывались словом «No» → в мобильных списках их не держать.
- Кнопки верхней панели мобильный клиент прячет в «ещё» → главное действие
  `UsualButton` во всю ширину на странице, с цветами (`главная` синяя,
  `осторожно` красная рамка).
- Три колонки в очереди и четыре в маршруте — столько влезает без обрезания.
- Заголовок и пояснение — надписи, не поля: на ходу читают как команду, а
  поле с подписью читается как бланк; вышедший норматив — красным цветом текста.
- Пустые поля скрывать (`Видимость = НЕ ПустаяСтрока`).
- Кнопка называется тем, что сделает («Я на месте», «Погрузка закончена»),
  а не «Дальше».

**Коммиты.** MVM c7fa1a6, 0184346, 86ea75e, 6178074.

**Ссылки.** `tools/edt_lib.value_table(mobile=True)`, `tools/edt_lib.page_button`,
`examples/mobile/mobile-form/`.
""",
     before=[('table.fragment.xml', W + """
    <items xsi:type="form:Table">
      <name>Рейсы</name>
      … колонки, среди них CheckBoxField «Готово» …
      <autoCommandBar>…</autoCommandBar>          ← «More actions»
      … спутники …
      <searchStringLocation>Auto … (умолчание)     ← три полосы над таблицей
""")],
     after=[('table.fragment.xml', C + """
    <items xsi:type="form:Table">
      <name>Рейсы</name>
      … только текстовые колонки, только чтение …
      <commandBarLocation>None</commandBarLocation>
      <autoCommandBar>…</autoCommandBar>
      … спутники (обязательны для EDT) …
      <searchStringLocation>None</searchStringLocation>
      <viewStatusLocation>None</viewStatusLocation>
      <searchControlLocation>None</searchControlLocation>
      <rowFilter xsi:type="core:UndefinedValue"/>
    </items>
    <items xsi:type="form:Button">                 ← главное действие на странице
      <name>Дальше</name>
      … <type>UsualButton</type> <commandName>Form.Command.Дальше</commandName>
      <defaultButton>true</defaultButton>
      <horizontalStretch>true</horizontalStretch>
      <textColor xsi:type="core:ColorDef">…255,255,255…</textColor>
      <backColor xsi:type="core:ColorDef">…30,99,214…</backColor>
      <borderColor xsi:type="core:ColorDef">…30,99,214…</borderColor>
      <font xsi:type="core:FontRef"><font>Style.NormalTextFont</font><height>12.0</height><bold>true</bold>…</font>
""")])

case(42, 'query-packet-result-index',
     """
# Читать Результаты[N] по голому числу нельзя

**Объекты.** Модуль формы АРМ, пакет запросов геозоны (контур, весогабариты,
техника, типы ТС).

**Confidence:** HIGH.
""",
     """
# Уроки

**Симптом.** «Поле объекта не обнаружено (ТС)» при перечитывании из 1С —
и только когда появилась геозона с техникой: пустая табличная часть к полю
не обращается.

**Почему.** Позиция — единственная связь запроса пакета с его результатом.
Три запроса встали после контура, типы ТС уехали с позиции 2 на 5, и «ТС»
читалось из запроса типов.

**Что изменилось.** Индексы держатся поимённо (`ТипыТСЗапрос = 5`),
инструмент сверяет: поле из `Результаты[N]` обязано существовать в N-м
запросе пакета.

**Коммиты.** MVM 08e10a1.
""",
     before=[('Module.bsl.fragment', WB + """
	Результаты = Запрос.ВыполнитьПакет();
	…
	Выборка = Результаты[2].Выбрать();     // после вставки трёх запросов это уже не типы ТС
	Пока Выборка.Следующий() Цикл
		Список.Добавить(Выборка.ТС);       // «Поле объекта не обнаружено (ТС)»
""")],
     after=[('Module.bsl.fragment', CB + """
	// Индексы результатов пакета — поимённо: вставка запроса в середину
	// молча сдвигает всё ниже.
	КонтурЗапрос = 1;
	ВесогабаритыЗапрос = 2;
	УстановленнаяЗапрос = 3;
	ЗакреплённаяЗапрос = 4;
	ТипыТСЗапрос = 5;
	Результаты = Запрос.ВыполнитьПакет();
	Выборка = Результаты[ТипыТСЗапрос].Выбрать();
""")])

case(43, 'optional-calculation-in-try',
     """
# Необязательный расчёт в сборке данных — только внутри Попытка

**Объекты.** Модуль формы АРМ: `ЗаполнитьПутиРейсов` (украшение для анимации)
внутри сборки пакета для карты.

**Confidence:** HIGH — дважды: пути рейсов и подача от гаража.
""",
     """
# Уроки

**Симптом.** Одна опечатка/непривязанный пункт в необязательном расчёте — и
АРМ открылся пустым: без узлов, заявок и парка. Второй раз назначение
отказывало по всем четырнадцати заявкам разом, потому что не строился
отрезок подачи от гаража, который к узлу никто не привязывал.

**Правило.** Украшение не имеет права ронять данные: расчёт в `Попытка`, а
необязательная точка добавляется только если путь действительно есть.
Проверять надо ВСЕ пункты, участвующие в расчёте, и называть виноватого по
имени в сообщении.

**Коммиты.** MVM 535ba9a, dc6a823, 52900e7f (EDT).
""",
     before=[('Module.bsl.fragment', WB + """
	Пакет.Вставить("рейсы", РейсыДляПакета());
	ЗаполнитьПутиРейсов(Пакет);             // падает — падает всё
""")],
     after=[('Module.bsl.fragment', CB + """
	Пакет.Вставить("рейсы", РейсыДляПакета());
	// Пути для анимации — украшение: не построились — карта живёт без них.
	Попытка
		ЗаполнитьПутиРейсов(Пакет);
	Исключение
		СообщитьПользователю("Пути рейсов не построены: " + ОписаниеОшибки());
	КонецПопытки;
""")])

case(44, 'skipped-object-kept-on-write',
     """
# «Лишнее» — то, чего нет в пакете, а не то, что не записалось

**Объекты.** Запись графа (узлы, проезды, геозоны) из карты в справочники.

**Confidence:** HIGH.
""",
     """
# Уроки

**Симптом.** Геозона, которую диспетчер только что нарисовал, исчезала после
перечитывания. Молча: транзакция фиксировалась.

**Почему.** Запись пропускала зону с контуром короче трёх точек
(`Продолжить`), а следом «пометка лишних» снимала всё, чего нет в списке
ЗАПИСАННЫХ.

**Правило.** Каждый `Продолжить` в записи кладёт объект в список
оставшихся (`ОставитьПропущенную`) и называет причину. Похожее: список типов
ТС из карты, где ни один идентификатор не разрешился в ссылку, — табличную
часть не трогать (`НечегоПисать`), иначе сохранение очищает то, что завели руками.

**Коммиты.** MVM b59df2d, 70efe6c.
""",
     before=[('Module.bsl.fragment', WB + """
	Для Каждого Зона Из Пакет["геозоны"] Цикл
		Если Зона["контур"].Количество() < 3 Тогда
			Продолжить;                          // и зона выпадает из «записанных»
		КонецЕсли;
		Записанные.Добавить(ЗаписатьЗону(Зона));
	КонецЦикла;
	ПометитьЛишнее(Записанные);                  // снимет и пропущенную
""")],
     after=[('Module.bsl.fragment', CB + """
	Для Каждого Зона Из Пакет["геозоны"] Цикл
		Если Зона["контур"].Количество() < 3 Тогда
			ОставитьПропущенную(Записанные, Зона, "контур короче трёх точек");
			Продолжить;
		КонецЕсли;
		Записанные.Добавить(ЗаписатьЗону(Зона));
	КонецЦикла;
	ПометитьЛишнее(Записанные);
""")])

case(45, 'enum-value-names-from-mdo',
     """
# Имена значений перечислений сверять с .mdo, а не сочинять

**Объекты.** Перечисление мвмРежимДоступаГеозоны, проверка геозон в маршрутизации.

**Confidence:** HIGH.
""",
     """
# Уроки

**Симптом.** «Поле объекта не обнаружено (Запрет)» — только в бою.

**Почему.** Написали `Перечисления.мвмРежимДоступаГеозоны.Запрет`, а значение
называется `ЗапретитьВыбранным`.

**Что изменилось.** Инструмент сверяет все `Перечисления.X.Y` наших модулей
с `<enumValues><name>` в выгрузке EDT (`проверить_перечисления.py` проекта;
в pack — правило и пример).

**Коммиты.** MVM 535ba9a; EDT dde46e83.

**Ссылки.** `examples/metadata/enum/`.
""",
     before=[('Module.bsl.fragment', WB + """
	Если Зона.РежимДоступа = Перечисления.мвмРежимДоступаГеозоны.Запрет Тогда
""")],
     after=[('Module.bsl.fragment', CB + """
	// имя значения — из .mdo: <enumValues><name>ЗапретитьВыбранным</name>
	Если Зона.РежимДоступа = Перечисления.мвмРежимДоступаГеозоны.ЗапретитьВыбранным Тогда
""")])

case(46, 'empty-query-in-packet',
     """
# Выбрасывая запрос из пакета, считай разделители

**Объекты.** Пакет запросов сборки данных АРМ (убран мёртвый запрос расписаний).

**Confidence:** HIGH.
""",
     """
# Уроки

**Симптом.** «Ожидается выражение "ВЫБРАТЬ"» — весь пакет не выполняется, всё
назначение рейсов разом.

**Почему.** Убрали запрос вместе с «;» ПЕРЕД ним — остался «;» ПОСЛЕ, два
подряд означают пустой запрос.

**Что изменилось.** Проверка «два `|;` подряд» в инструменте; при выбросе
запроса — считать разделители и индексы результатов (case 042).

**Коммиты.** MVM a6f97f4 / f02aba7f (EDT).
""",
     before=[('query.fragment', WB + """
		|	…предыдущий запрос…
		|;
		|;                                   ← сирота от выброшенного запроса
		|
		|ВЫБРАТЬ
""")],
     after=[('query.fragment', CB + """
		|	…предыдущий запрос…
		|;
		|
		|ВЫБРАТЬ
""")])
print('cases 037-046 ok')
