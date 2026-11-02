# -*- coding: utf-8 -*-
"""Кейсы 025–036: состав свойств, вставки в типовые модули, порядок EDT, EDT-модель, СКД, формы выбора."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cases_lib import case  # noqa: E402

W = '<!-- WRONG: так НЕ делать -->\n'
C = '<!-- CORRECT -->\n'
WB = '// WRONG: так НЕ делать\n'
CB = '// CORRECT\n'

case(25, 'attribute-property-set-by-owner',
     """
# Состав свойств реквизита зависит от того, чей он: справочник / ТЧ / документ

**Объекты.** Реквизиты и ТЧ, добавленные в типовые справочники и документ.
Три падения одного класса (формат выгрузки Конфигуратора); в EDT аналог —
у реквизита табличной части нет `fillValue`.

**Confidence:** HIGH для правила «по образцу владельца»; конкретные
наборы тегов EDT — из рабочих .mdo проекта.
""",
     """
# Уроки

**Симптомы.** «Свойство FillFromFillingValue не входит в состав объекта
метаданных Attribute» (и FillValue, Use — по три на каждый реквизит ТЧ);
«Свойство Use не входит…» у реквизита документа; ранее «Ошибка XDTO … при
чтении свойства AllowedLength» — длина уехала в соседний тег при валидном XML.

**Почему.** У реквизита ТЧ набор свойств короче (26 против 29), у реквизита
документа нет `Use` (ForItem/ForFolder осмысленно только при группах).
Предыдущий контроль сравнивал реквизит документа с эталоном справочника —
сверялся не с тем образцом.

**Что изменилось.** Эталонные наборы берутся из живых файлов конфигурации по
виду владельца (`сверить_состав_свойств`), а не выдумываются: список
зависит от версии метаданных. Проверка «осмысленности»: у листьев нет
текста из пробелов, квалификаторы — числа, после закрывающего тега ничего
не болтается.

**В EDT.** `edt_lib.attribute(in_ts=True)` не пишет `fillValue`; порядок
`minValue → maxValue → fillChecking → fillValue → fullTextSearch → dataHistory`
снят с рабочего .mdo.

**Коммиты.** MVM 4958426, 8f7a1da, 20f16ec.
""",
     before=[('tabular-attribute.edt.fragment.xml', W + """
    <attributes uuid="…">
      <name>X</name>
      …
      <minValue xsi:type="core:UndefinedValue"/>
      <maxValue xsi:type="core:UndefinedValue"/>
      <fillValue xsi:type="core:UndefinedValue"/>       ← у реквизита ТЧ нет
      <fullTextSearch>Use</fullTextSearch>
      <dataHistory>Use</dataHistory>
    </attributes>
""")],
     after=[('tabular-attribute.edt.fragment.xml', C + """
    <attributes uuid="…">
      <name>X</name>
      …
      <minValue xsi:type="core:UndefinedValue"/>
      <maxValue xsi:type="core:UndefinedValue"/>
      <dataHistory>Use</dataHistory>
      <fullTextSearch>Use</fullTextSearch>
    </attributes>
""")])

case(26, 'insert-into-vendor-procedure-semicolon-crlf',
     """
# Вставка вызова в типовую процедуру: «;» и CRLF

**Объекты.** Модуль типовой формы заказа: вызовы `мвмПодставитьСклад(...)`
в конец `АдресОтправленияПриИзменении`, `мвмНачалоВыбораПункта` в начало
`АдресОтправленияНачалоВыбора`.

**Confidence:** HIGH.
""",
     """
# Уроки

**Симптом 1.** «Ожидается символ ';'»: последний оператор типовой процедуры
стоял без `;` — перед `КонецПроцедуры` так можно, а после него наш вызов дал
ошибку.

**Симптом 2.** После вставки в начало в модуле остался одиночный LF: регулярное
выражение объявления съедало CR перед LF.

**Что изменилось.** Вставка в конец добавляет `;` последнему оператору, если
его нет; вставка в начало идёт за ЦЕЛЫМ переводом строки объявления.
Идемпотентность по подстроке.

**Коммиты.** MVM 9a5e231, 3189906.

**Ссылки.** `tools/edt_lib.insert_into_procedure`, `knowledge/bsl.md` §6.
""",
     before=[('insert.py.fragment', """
# WRONG
if в_начало:
    return текст[:начало] + СТР + строка + текст[начало:]   # рвёт CR|LF
return текст[:конец] + СТР + строка + текст[конец:]        # после «Х = 1» без «;»
""")],
     after=[('insert.py.fragment', """
# CORRECT
if в_начало:
    за_объявлением = текст.index(СТР, м.start()) + len(СТР)
    return текст[:за_объявлением] + строка + СТР + текст[за_объявлением:]
хвост = тело.rstrip()
последняя = [с for с in хвост.split(СТР) if с.strip() and not с.strip().startswith('//')]
if последняя and not последняя[-1].rstrip().endswith(';'):
    текст = текст[:начало] + тело.rstrip() + ';' + тело[len(тело.rstrip()):] + текст[конец:]
    конец = текст.index(СТР + 'КонецПроцедуры', начало)
return текст[:конец] + СТР + строка + текст[конец:]
""")])

case(27, 'edt-canonical-order-user-edits',
     """
# XML формы писать так, как его пишет EDT; правки пользователя переносить в генератор

**Объекты.** Формы заказа и выбора пунктов; пользователь перестраивал
группы в EDT.

**Confidence:** HIGH — после приведения к порядку EDT разница между выводом
генератора и файлом пользователя стала «0 строк».
""",
     """
# Уроки

**Симптом.** После сохранения формы в EDT наш вывод разошёлся с файлом на
КАЖДОМ поле, хотя форма та же: правку пользователя не отличить.

**Почему.** EDT пишет `<title>` сразу за `<id>`, `<handlers>` — сразу за
`</dataPath>`; значения по умолчанию не пишет вовсе (`visible=false` →
убрать тег, `autoMaxWidth=false`, `representation=None`, `showTitle=false`,
`group=Horizontal`).

**Что изменилось.** Единый `образец.поле` во всех генераторах; инструмент
`выделить_правки.py`: HEAD проекта → генераторы → разница с файлом
пользователя. Раскладка, выставленная пользователем (группа «всегда
горизонтально», панель над деревом), перенесена в спецификацию генератора.

**Правило.** Пользователь правит формы в EDT — это надо переносить в
генератор, иначе пересборка сотрёт. Цель — «строк разницы 0».

**Коммиты.** MVM d542df0, ac8d144, 085300e.

**Ссылки.** `reference/generators/выделить_правки.py`, `tools/edt_lib.field`.
""",
     before=[('field.fragment.xml', W + """
    <items xsi:type="form:FormField">
      <name>мвмПоискСклад</name>
      <id>…</id>
      <visible>true</visible>
      <enabled>true</enabled>
      <userVisible><common>true</common></userVisible>
      <dataPath …><segments>мвмПоискСклад</segments></dataPath>
      <title><key>ru</key><value>Склад</value></title>          ← не там
      <extendedTooltip>…</extendedTooltip>
      <contextMenu>…</contextMenu>
      <handlers><event>OnChange</event><name>…</name></handlers> ← не там
      <type>InputField</type>
      …
      <extInfo xsi:type="form:InputFieldExtInfo">
        <autoMaxWidth>false</autoMaxWidth>                        ← умолчание не пишется
""")],
     after=[('field.fragment.xml', C + """
    <items xsi:type="form:FormField">
      <name>мвмПоискСклад</name>
      <id>…</id>
      <title>
        <key>ru</key>
        <value>Склад</value>
      </title>
      <visible>true</visible>
      <enabled>true</enabled>
      <userVisible>
        <common>true</common>
      </userVisible>
      <dataPath xsi:type="form:DataPath">
        <segments>мвмПоискСклад</segments>
      </dataPath>
      <handlers>
        <event>OnChange</event>
        <name>мвмПоискСкладПриИзменении</name>
      </handlers>
      <extendedTooltip>…</extendedTooltip>
      <contextMenu>…</contextMenu>
      <type>InputField</type>
      …
      <extInfo xsi:type="form:InputFieldExtInfo">
        <width>22</width>
""")])

case(28, 'edt-workspace-formitem-null',
     """
# Генератор переписал форму, открытую в редакторе EDT — модель сломалась

**Объекты.** Форма заказа, открытая в EDT во время пересборки.

**Confidence:** HIGH — консольная выгрузка в чистое рабочее пространство
прошла (файлы целы), «Проект → Очистить» вылечило.
""",
     """
# Уроки

**Симптом.** Обновление базы падает «NullPointerException … "formItem" is
null» при экспорте; ни перезапуск EDT, ни правки файла не помогают.

**Диагностика.** `1cedtcli export` в отдельное чистое рабочее пространство
(10–15 минут) прошёл → сломан собранный EDT образ проекта, не файлы.

**Лечение.** «Проект → Очистить…». Профилактика: закрывать редакторы форм
перед запуском генераторов; правки в EDT сохранять или отвечать «Нет» на
«сохранить?» осознанно.

**Коммиты.** MVM a401896 (инструмент), запись в CLAUDE.md.

**Ссылки.** `reference/generators/проверить_экспорт_edt.py`.
""",
     before=[('note.md', """
WRONG: пересобрать форму генератором, пока её редактор открыт в EDT, и
потом «чинить файл», хотя файл цел.
""")],
     after=[('note.md', """
CORRECT: закрыть редактор формы → запустить генератор → «Обновить» проект.
При «formItem is null»: проверить файлы консольной выгрузкой, затем
«Проект → Очистить…».
""")])

case(29, 'catalog-hierarchy-vs-attribute',
     """
# «Группа» в ТЗ — реквизит-ссылка, а не иерархия справочника

**Объекты.** Catalogs/уатВидыГрузов/уатВидыГрузов.mdo и его форма элемента.

**Confidence:** HIGH (по замечанию методолога).
""",
     """
# Уроки

**Что было.** Строка ТЗ «ШАПКА / Группа: добавить новый реквизит, тип —
Справочник Виды грузов» прочитана как штатная иерархия групп: включили
`<hierarchical>true`.

**Что стало.** Иерархия убрана (у неиерархического справочника тега просто
нет), заведён реквизит `Группа` со ссылкой на тот же справочник; форма
пересобрана с группировкой полей.

**Правило.** Иерархия меняет физическую структуру, запросы (`ЭтоГруппа`) и
формы; включать её по догадке нельзя — уточнять формулировку ТЗ.

**Коммиты.** EDT 3c2a4146.
""",
     before=[('уатВидыГрузов.mdo.fragment.xml', W + """
  <dataLockControlMode>Managed</dataLockControlMode>
  <fullTextSearch>Use</fullTextSearch>
  <hierarchical>true</hierarchical>
  <levelCount>2</levelCount>
  <foldersOnTop>true</foldersOnTop>
  <codeLength>9</codeLength>
""")],
     after=[('уатВидыГрузов.mdo.fragment.xml', C + """
  <dataLockControlMode>Managed</dataLockControlMode>
  <fullTextSearch>Use</fullTextSearch>
  <levelCount>2</levelCount>
  <foldersOnTop>true</foldersOnTop>
  <codeLength>9</codeLength>
  …
  <attributes uuid="05218d43-9e49-44d7-be46-bb2c682c5ec3">
    <name>Группа</name>
    <synonym>
      <key>ru</key>
      <value>Группа</value>
    </synonym>
    <type>
      <types>CatalogRef.уатВидыГрузов</types>
    </type>
    <minValue xsi:type="core:UndefinedValue"/>
    <maxValue xsi:type="core:UndefinedValue"/>
    <fillValue xsi:type="core:UndefinedValue"/>
    <fullTextSearch>Use</fullTextSearch>
    <dataHistory>Use</dataHistory>
  </attributes>
""")])

case(30, 'mobile-pages-swipe-no-row-swipe',
     """
# Смахивания по строке в 1С нет — Swipe есть только у страниц

**Объекты.** Мобильная форма АРМ водителя: три страницы, контекстное меню строки.

**Confidence:** HIGH — проверено по модели форм EDT (`Form.xcore`) и на телефоне.
""",
     """
# Уроки

**Что.** В модели форм EDT (`com._1c.g5.v8.dt.form.model`, `model/Form.xcore`
внутри jar в `~/.p2/pool/plugins`) слово Swipe встречается дважды:
`FormPagesRepresentation.Swipe` и `MoveItemsToSwipeablePages` у карточек
8.5.1. Свойства «действия строки по смахиванию» нет — значит и в XML его не
записать.

**Что сделали.** Экран разбит на страницы `Pages` с `pagesRepresentation
Swipe`; действия над строкой — контекстное меню строки (`<contextMenu>` с
кнопками, долгое нажатие). Позже `Swipe` заменён на `TabsOnTop`: с
точками-индикатором водитель не понимал, на какой он странице, а на
компьютере без закладок между страницами не перейти.

**Правило.** Когда непонятно, умеет ли платформа свойство формы — открыть
`Form.xcore`: там все свойства с пометками «since 8.3.x».

**Коммиты.** MVM 116c3f2, 86ea75e, c7fa1a6.

**Ссылки.** `tools/edt_lib.pages`, `examples/mobile/mobile-form/`.
""",
     before=[('note.md', """
WRONG: искать/выдумывать свойство таблицы «смахивание строки» — его нет.
""")],
     after=[('pages.fragment.xml', C + """
  <items xsi:type="form:FormGroup">
    <name>Страницы</name>
    <id>…</id>
    <items xsi:type="form:FormGroup"> … <type>Page</type> … </items>   × N
    <visible>true</visible>
    <enabled>true</enabled>
    <userVisible><common>true</common></userVisible>
    <extendedTooltip>…</extendedTooltip>
    <type>Pages</type>
    <extInfo xsi:type="form:PagesGroupExtInfo">
      <handlers>
        <event>OnCurrentPageChange</event>
        <name>СтраницыПриСменеСтраницы</name>
      </handlers>
      <pagesRepresentation>TabsOnTop</pagesRepresentation>   ← или Swipe для телефона
      <currentRowUse>Auto</currentRowUse>
    </extInfo>
  </items>
"""), ('row-context-menu.fragment.xml', C + """
      <contextMenu>
        <name>ТочкиКонтекстноеМеню</name>
        <id>…</id>
        <items xsi:type="form:Button">
          <name>ОтметитьТочку</name>
          …
          <commandName>Form.Command.ОтметитьТочку</commandName>
          …
        </items>
        <autoFill>true</autoFill>
      </contextMenu>
""")])

case(31, 'aggregate-over-unlimited-string',
     """
# Агрегат по строке неограниченной длины падает в бою

**Объекты.** CommonModule.мвмРейсыВодителя, запрос очереди рейсов:
`МАКСИМУМ(Заказ.НазваниеГруза)`.

**Confidence:** HIGH.
""",
     """
# Уроки

**Симптом.** «Неверные параметры МАКСИМУМ» при открытии АРМ водителя.

**Почему.** У типовой много строк длины 0 (неограниченных); в агрегатах,
группировках и сравнениях они запрещены.

**Правило.** `МАКСИМУМ(ВЫРАЗИТЬ(Поле КАК СТРОКА(150)))`. Проверка запросов
длин не знает — только внимание к типу поля в .mdo.

**Коммиты.** MVM 0184346.
""",
     before=[('query.fragment', WB + """
		|	МАКСИМУМ(Строки.ЗаказГрузоотправителя.НазваниеГруза) КАК Груз,
""")],
     after=[('query.fragment', CB + """
		|	МАКСИМУМ(ВЫРАЗИТЬ(Строки.ЗаказГрузоотправителя.НазваниеГруза КАК СТРОКА(150))) КАК Груз,
""")])

case(32, 'empty-ref-method-parens',
     """
# `ПустаяСсылка()` — метод менеджера, а не свойство

**Объекты.** Модуль формы АРМ, снятие привязки пункта.

**Confidence:** HIGH.
""",
     """
# Уроки

**Симптом.** Запись графа падала «Поле объекта не обнаружено (ПустаяСсылка)».

**Что изменилось.** `Справочники.X.ПустаяСсылка()`; проверка ищет
`ПустаяСсылка` без скобок, не считая продолжения многострочных запросов
(`|…`) кодом — там `ЗНАЧЕНИЕ(Справочник.X.ПустаяСсылка)` законно.

**Коммиты.** MVM b08120a.
""",
     before=[('Module.bsl.fragment', WB + """
	Для Каждого Пункт Из Снять Цикл
		ЗаписатьУзелПункта(Пункт, Справочники.мвмУзлыКарты.ПустаяСсылка);
	КонецЦикла;
""")],
     after=[('Module.bsl.fragment', CB + """
	Для Каждого Пункт Из Снять Цикл
		ЗаписатьУзелПункта(Пункт, Справочники.мвмУзлыКарты.ПустаяСсылка());
	КонецЦикла;
""")])

case(33, 'client-server-directive-not-found',
     """
# `&НаКлиентеНаСервере` при серверном вызове: «процедура не определена»

**Объекты.** Формы выбора и списка справочника пунктов, процедура
переключения иерархии списка при отборе.

**Confidence:** MEDIUM — причина не доказана (возможно, порядок объявления
или особенность модуля формы списка); лечение проверено в базе.
""",
     """
# Уроки

**Симптом.** «{Справочник.уатПунктыНазначения.Форма.ФормаВыбора.Форма(71,3)}:
Процедура или функция с указанным именем не определена (мвмИерархияПоОтбору)»
при вызове из `&НаСервере` процедуры создания формы.

**Что изменилось.** Одно тело в двух процедурах: `&НаСервере
…НаСервере(Плоско)` для серверного вызова и `&НаКлиенте …(Плоско)` для
обработчиков полей.

**Правило (MEDIUM).** Для контекстных операций над элементами формы держать
клиентскую и серверную версии; `&НаКлиентеНаСервере` не полагаться без
проверки в базе. `tools/check_bsl.py` выдаёт предупреждение.

**Коммиты.** MVM 5a39ad8.
""",
     before=[('Module.bsl.fragment', WB + """
&НаСервере
Процедура мвмПоискИзПараметров()
	…
		мвмИерархияПоОтбору(Истина);
	…
КонецПроцедуры

&НаКлиентеНаСервере
Процедура мвмИерархияПоОтбору(Плоско)
	Если Плоско Тогда
		Элементы.Список.Отображение = ОтображениеТаблицы.Список;
	…
""")],
     after=[('Module.bsl.fragment', CB + """
&НаСервере
Процедура мвмПоискИзПараметров()
	…
		мвмИерархияПоОтборуНаСервере(Истина);
	…
КонецПроцедуры

&НаСервере
Процедура мвмИерархияПоОтборуНаСервере(Плоско)
	Если Плоско Тогда
		Элементы.Список.Отображение = ОтображениеТаблицы.Список;
		Попытка
			Элементы.Дерево.ТекущаяСтрока = Неопределено;
		Исключение
		КонецПопытки;
	Иначе
		Элементы.Список.Отображение = ОтображениеТаблицы.ИерархическийСписок;
	КонецЕсли;
	ОтборыСписковКлиентСервер.ИзменитьЭлементОтбораСписка(Список, "ЭтоГруппа", Ложь, Плоско);
КонецПроцедуры

&НаКлиенте
Процедура мвмИерархияПоОтбору(Плоско)
	… то же тело …
КонецПроцедуры
""")])

case(34, 'dcs-filter-empty-value-string-vs-ref',
     """
# Отбор СКД: пустое значение ссылки — DesignTimeValue, строки — xs:string

**Объекты.** Схемы отчётов «Состав плана» (отбор по строковым полям Раздел,
Настроен) и «Пункты и узлы» (отбор по ссылкам).

**Confidence:** MEDIUM — зафиксировано в генераторе как рабочее решение;
падения в истории нет.
""",
     """
# Уроки

**Что.** Ссылочному полю пустое значение отбора задаётся
`<dcsset:right xsi:type="dcscor:DesignTimeValue">Справочник.X.ПустаяСсылка</dcsset:right>`,
строковому — `<dcsset:right xsi:type="xs:string"/>`: `DesignTimeValue`
строку не описывает, и такой отбор в отчёте не работает.

**Прочее по отборам.** `use=false` (выключен по умолчанию), `viewMode
QuickAccess` (виден в шапке), `userSettingID` устойчивый.

**Коммиты.** MVM 7bb0e48, 3f6961d (генератор отчётов).

**Ссылки.** `tools/edt_lib.dcs_schema`, `examples/metadata/report/`.
""",
     before=[('filter.fragment.xml', W + """
  <dcsset:item xsi:type="dcsset:FilterItemComparison">
    <dcsset:use>false</dcsset:use>
    <dcsset:left xsi:type="dcscor:Field">Раздел</dcsset:left>
    <dcsset:comparisonType>Equal</dcsset:comparisonType>
    <dcsset:right xsi:type="dcscor:DesignTimeValue"></dcsset:right>   ← строка
""")],
     after=[('filter.fragment.xml', C + """
  <dcsset:item xsi:type="dcsset:FilterItemComparison">
    <dcsset:use>false</dcsset:use>
    <dcsset:left xsi:type="dcscor:Field">Раздел</dcsset:left>
    <dcsset:comparisonType>Equal</dcsset:comparisonType>
    <dcsset:right xsi:type="xs:string"/>
    <dcsset:viewMode>QuickAccess</dcsset:viewMode>
    <dcsset:userSettingID>…uuid5…</dcsset:userSettingID>
  </dcsset:item>
  <dcsset:item xsi:type="dcsset:FilterItemComparison">
    <dcsset:use>false</dcsset:use>
    <dcsset:left xsi:type="dcscor:Field">ТипУзла</dcsset:left>
    <dcsset:comparisonType>Equal</dcsset:comparisonType>
    <dcsset:right xsi:type="dcscor:DesignTimeValue">Справочник.мвмТипыУзлов.ПустаяСсылка</dcsset:right>
    <dcsset:viewMode>QuickAccess</dcsset:viewMode>
    <dcsset:userSettingID>…uuid5…</dcsset:userSettingID>
  </dcsset:item>
""")])

case(35, 'dcs-detail-records-group',
     """
# Отчёт с группировкой показывал одни итоги

**Объекты.** Схемы отчётов с `groupItems` (по состоянию, по дню и машине).

**Confidence:** MEDIUM — исправлено в генераторе, отчёты работают.
""",
     """
# Уроки

**Симптом.** Видно «не привязано 47 пунктов», а какие именно — нет.

**Что.** Детальные записи — это вложенная `StructureItemGroup` БЕЗ
`groupItems` в конце родительской группировки. Без неё выводятся только
уровни группировки.

**Коммиты.** MVM 3f6961d / 7bb0e48 (генератор).

**Ссылки.** `tools/edt_lib.dcs_schema(groups=…)`.
""",
     before=[('structure.fragment.xml', W + """
  <dcsset:item xsi:type="dcsset:StructureItemGroup">
    <dcsset:groupItems>
      <dcsset:item xsi:type="dcsset:GroupItemField">
        <dcsset:field>Состояние</dcsset:field>
        <dcsset:groupType>Items</dcsset:groupType>
        …
      </dcsset:item>
    </dcsset:groupItems>
    <dcsset:order><dcsset:item xsi:type="dcsset:OrderItemAuto"/></dcsset:order>
    <dcsset:selection><dcsset:item xsi:type="dcsset:SelectedItemAuto"/></dcsset:selection>
  </dcsset:item>
""")],
     after=[('structure.fragment.xml', C + """
  <dcsset:item xsi:type="dcsset:StructureItemGroup">
    <dcsset:groupItems>
      <dcsset:item xsi:type="dcsset:GroupItemField">
        <dcsset:field>Состояние</dcsset:field>
        <dcsset:groupType>Items</dcsset:groupType>
        …
      </dcsset:item>
    </dcsset:groupItems>
    <dcsset:order><dcsset:item xsi:type="dcsset:OrderItemAuto"/></dcsset:order>
    <dcsset:selection><dcsset:item xsi:type="dcsset:SelectedItemAuto"/></dcsset:selection>
    <dcsset:item xsi:type="dcsset:StructureItemGroup">      ← детальные записи
      <dcsset:order><dcsset:item xsi:type="dcsset:OrderItemAuto"/></dcsset:order>
      <dcsset:selection><dcsset:item xsi:type="dcsset:SelectedItemAuto"/></dcsset:selection>
    </dcsset:item>
  </dcsset:item>
""")])

case(36, 'choice-form-filter-parameters',
     """
# Типовой обработчик начала выбора не смотрит ПараметрыВыбора — форму открываем сами

**Объекты.** Форма заказа (поле «Адрес»), форма выбора пунктов назначения
с панелью поиска.

**Confidence:** HIGH — проверено в базе: отбор по складу передаётся.
""",
     """
# Уроки

**Что было.** Полю адреса задали `ПараметрыВыбора` с `Отбор.мвмСклад`; форму
выбора типовая открывает сама (`уатОбщегоНазначенияКлиент.ПунктНачалоВыбора`)
и параметры выбора элемента не смотрит — отбор не доезжал.

**Что стало.** В начало типового `АдресОтправленияНачалоВыбора` вставлен
вызов `мвмНачалоВыбораПункта(Элемент, СтандартнаяОбработка, Истина)`: при
нужных условиях он ставит `СтандартнаяОбработка = Ложь` и открывает форму
выбора с `Отбор` и `ТекущаяСтрока`, результат принимает типовое же
завершение выбора (`ОписаниеОповещения("АдресНачалоВыбораЖДЗавершение", …)`).
На стороне формы выбора `Параметры.Отбор` читается в `ПриСозданииНаСервере`,
отбор накладывается через `ОтборыСписковКлиентСервер.ИзменитьЭлементОтбораСписка`,
список переводится в плоский вид (case 033).

**Коммиты.** MVM 1ae88df, 5a39ad8, 38b8e20.

**Ссылки.** `examples/bsl/open-form-with-callback.bsl`, `examples/bsl/dynamic-list-filter.bsl`.
""",
     before=[('Module.bsl.fragment', WB + """
	СписокПараметров = Новый Массив;
	СписокПараметров.Добавить(Новый ПараметрВыбора("Отбор.мвмСклад", Склад));
	ЭлементАдреса.ПараметрыВыбора = Новый ФиксированныйМассив(СписокПараметров);
	// …и всё: типовое НачалоВыбора открывает форму без этих параметров
""")],
     after=[('Module.bsl.fragment', CB + """
&НаКлиенте
Процедура АдресОтправленияНачалоВыбора(Элемент, СтандартнаяОбработка)
	Если мвмНачалоВыбораПункта(Элемент, СтандартнаяОбработка, Истина) Тогда
		Возврат;
	КонецЕсли;
	… типовой код …
КонецПроцедуры

&НаКлиенте
Функция мвмНачалоВыбораПункта(Элемент, СтандартнаяОбработка, ЭтоОтправление)
	Склад = ?(ЭтоОтправление, Объект.Грузоотправитель, Объект.Грузополучатель);
	Если ТипЗнч(Склад) <> Тип("СправочникСсылка.Склады") ИЛИ НЕ ЗначениеЗаполнено(Склад) Тогда
		Возврат Ложь;
	КонецЕсли;
	СтандартнаяОбработка = Ложь;
	ПараметрыОткрытия = Новый Структура;
	ПараметрыОткрытия.Вставить("Отбор", Новый Структура("мвмСклад", Склад));
	ПараметрыОткрытия.Вставить("ТекущаяСтрока", ?(ЭтоОтправление, Объект.АдресОтправления, Объект.АдресНазначения));
	ОткрытьФорму("Справочник.уатПунктыНазначения.ФормаВыбора", ПараметрыОткрытия, ЭтотОбъект,,,,
		Новый ОписаниеОповещения("АдресНачалоВыбораЖДЗавершение", ЭтотОбъект,
			Новый Структура("АдресОтправления", ЭтоОтправление)));
	Возврат Истина;
КонецФункции
""")])
print('cases 025-036 ok')
