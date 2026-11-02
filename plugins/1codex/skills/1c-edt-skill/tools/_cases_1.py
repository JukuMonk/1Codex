# -*- coding: utf-8 -*-
"""Кейсы 001–012: формы в EDT и директивы BSL."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cases_lib import case  # noqa: E402

W = '<!-- WRONG: так НЕ делать -->\n'
C = '<!-- CORRECT -->\n'
WB = '// WRONG: так НЕ делать\n'
CB = '// CORRECT\n'

case(1, 'form-number-qualifiers',
     """
# Числовой реквизит формы без numberQualifiers ломает форму целиком

**Задача.** Обработка «АРМ водителя» с мобильной формой: реквизиты формы
строки, даты, ссылки и числа (`РейсовВсего`, колонка `Точек` в таблице значений).

**Объекты.** DataProcessor.мвмМоиРейсы, Forms/ФормаМобильная/Form.form.

**Ожидалось.** Форма рисуется в редакторе EDT и открывается в клиенте.

**Confidence:** HIGH — найдено лесенкой проб (одна форма отличается на один
элемент), после исправления форма ожила; правило встроено в генераторы.
""",
     """
# Уроки

**Что было не так.** У реквизита формы `<valueType><types>Number</types></valueType>`
без `<numberQualifiers>`. У строк и дат квалификаторы писались, у чисел — нет.

**Симптом.** Пустой лист вместо предпросмотра формы в EDT, «Ошибка построения
модели FormMapping» в журнале EDT. ВСЯ форма, не одно поле. XML валиден.

**Почему.** Тип без квалификаторов для модели EDT неполон — модель формы не
строится. Пробные формы рисовались все, потому что в них квалификаторы были.

**Что изменилось.** У каждого числового реквизита и колонки таблицы значений
— `<numberQualifiers><precision>10</precision></numberQualifiers>`; генератор
отказывается собирать форму без них.

**Правило.** Реквизит формы типа Number — всегда с numberQualifiers; String —
`<stringQualifiers/>`; Date — `<dateQualifiers><dateFractions>`.

**Когда применять.** Любой `<attributes>`/`<columns>` в Form.form.

**Коммиты.** MVM 37e2ec1 (исправление), 6934ec8 (снятие ложных гипотез),
8cebf0f/5a50607 (лесенка проб).

**Ссылки.** `examples/metadata/data-processor/…/Form.form` (реквизиты),
`tools/edt_lib.form_attribute`, `tools/edt_lib.check_form`, case 006.
""",
     before=[('Form.form.fragment.xml', W + """
  <attributes>
    <name>РейсовВсего</name>
    <title><key>ru</key><value>Рейсов у меня</value></title>
    <id>8</id>
    <valueType>
      <types>Number</types>
    </valueType>
    <view><common>true</common></view>
    <edit><common>true</common></edit>
  </attributes>
""")],
     after=[('Form.form.fragment.xml', C + """
  <attributes>
    <name>РейсовВсего</name>
    <title>
      <key>ru</key>
      <value>Рейсов у меня</value>
    </title>
    <id>8</id>
    <valueType>
      <types>Number</types>
      <numberQualifiers>
        <precision>10</precision>
      </numberQualifiers>
    </valueType>
    <view>
      <common>true</common>
    </view>
    <edit>
      <common>true</common>
    </edit>
  </attributes>
""")])

case(2, 'form-save-window-settings',
     """
# Форма без saveWindowSettings в EDT не рисуется

**Задача.** Две обработки с формами, собранными генератором: «Привязка
пунктов» и «АРМ водителя».

**Объекты.** Form.form обеих обработок.

**Ожидалось.** Предпросмотр формы в EDT.

**Confidence:** HIGH — лесенка проб, тег есть у каждой формы, которую EDT
рисует; после добавления формы рисуются.
""",
     """
# Уроки

**Что было не так.** В хвосте Form.form не было `<saveWindowSettings>true</saveWindowSettings>`.

**Симптом.** Пустой лист вместо предпросмотра, иногда «Возникла внутренняя
ошибка» при обновлении команд. Тег необязательный по схеме, XML валиден, ни
одна проверка не ругается.

**Почему.** Так устроена модель форм EDT; объяснения нет, есть факт: у ВСЕХ
форм типовой конфигурации тег стоит, у нашей — нет.

**Что изменилось.** Порядок хвоста формы: `autoCommandBar → handlers →
[windowOpeningMode] → saveWindowSettings → autoTitle → autoUrl → group →
autoFillCheck → allowFormCustomize → enabled → showTitle → showCloseButton`.

**Правило.** Каркас формы копировать с рабочего образца целиком
(`tools/edt_lib.form_file`), не собирать «минимально необходимое».

**Коммиты.** MVM ac260bf, 5a50607.

**Ссылки.** case 006 (метод), `examples/forms/*`.
""",
     before=[('Form.form.tail.xml', W + """
  <autoCommandBar>
    <name>ФормаКоманднаяПанель</name>
    <id>27</id>
  </autoCommandBar>
  <handlers>
    <event>OnCreateAtServer</event>
    <name>ПриСозданииНаСервере</name>
  </handlers>
  <autoTitle>true</autoTitle>
  <autoUrl>true</autoUrl>
  <group>Vertical</group>
  <autoFillCheck>true</autoFillCheck>
  <allowFormCustomize>true</allowFormCustomize>
  <enabled>true</enabled>
  <showTitle>true</showTitle>
  <showCloseButton>true</showCloseButton>
""")],
     after=[('Form.form.tail.xml', C + """
  <autoCommandBar>
    <name>ФормаКоманднаяПанель</name>
    <id>27</id>
  </autoCommandBar>
  <handlers>
    <event>OnCreateAtServer</event>
    <name>ПриСозданииНаСервере</name>
  </handlers>
  <saveWindowSettings>true</saveWindowSettings>
  <autoTitle>true</autoTitle>
  <autoUrl>true</autoUrl>
  <group>Vertical</group>
  <autoFillCheck>true</autoFillCheck>
  <allowFormCustomize>true</allowFormCustomize>
  <enabled>true</enabled>
  <showTitle>true</showTitle>
  <showCloseButton>true</showCloseButton>
""")])

case(3, 'form-attribute-column-id-space',
     """
# Реквизиты формы и колонки их таблиц — одно пространство номеров

**Задача.** Форма обработки с реквизитом-таблицей значений (`Строки`) и
колонками.

**Объекты.** Form.form обработок «Привязка пунктов» и «АРМ водителя».

**Ожидалось.** Форма рисуется в EDT.

**Confidence:** HIGH — найдено сравнением с формой, собранной руками в EDT;
после исправления формы рисуются; проверка встроена в генераторы.
""",
     """
# Уроки

**Что было не так.** Генератор нумеровал `<columns>` таблицы заново с
единицы; номер колонки совпал с номером реквизита «Объект» (1).

**Симптом.** Пустой лист и «Возникла внутренняя ошибка» при обновлении
команд. XML валиден, имена на месте.

**Почему.** EDT держит реквизиты формы и колонки их таблиц значений в ОДНОМ
пространстве номеров: «Объект» 1, следующий реквизит 2, колонка его таблицы 3.

**Что изменилось.** Один счётчик на реквизиты и колонки; проверка дублей
перед записью. У команд формы (`formCommands`) пространство своё, там
нумерация с единицы законна; у элементов — третье.

**Правило.** Три пространства номеров формы: элементы; реквизиты+колонки;
команды. Внутри каждого — без дублей.

**Коммиты.** MVM 97b40a2.

**Ссылки.** `tools/edt_lib.Ids`, `tools/edt_lib.form_attribute`,
`knowledge/managed-forms.md` §2.
""",
     before=[('Form.form.fragment.xml', W + """
  <attributes>
    <name>Объект</name>
    <id>1</id>
    …
  </attributes>
  <attributes>
    <name>Строки</name>
    <id>3</id>
    <valueType><types>ValueTable</types></valueType>
    …
    <columns>
      <name>Отметка</name>
      <id>1</id>          ← совпадает с «Объект»
      …
    </columns>
    <columns>
      <name>Пункт</name>
      <id>2</id>
      …
    </columns>
  </attributes>
""")],
     after=[('Form.form.fragment.xml', C + """
  <attributes>
    <name>Объект</name>
    <id>1</id>
    …
  </attributes>
  <attributes>
    <name>ТолькоНепривязанные</name>
    <id>2</id>
    …
  </attributes>
  <attributes>
    <name>Строки</name>
    <id>3</id>
    <valueType><types>ValueTable</types></valueType>
    …
    <columns>
      <name>Отметка</name>
      <id>6</id>          ← продолжает общий ряд реквизитов
      …
    </columns>
    <columns>
      <name>Пункт</name>
      <id>7</id>
      …
    </columns>
  </attributes>
""")])

case(4, 'form-table-companions',
     """
# Таблицу формы EDT не рисует без трёх спутников и полного набора свойств

**Задача.** Таблица значений на форме обработки.

**Объекты.** `<items xsi:type="form:Table">` в Form.form.

**Ожидалось.** Таблица видна в предпросмотре и в клиенте.

**Confidence:** HIGH — в форме геозоны спутники генерировались и она
рисовалась; в обработках упростили — пустой лист; вернули — рисуется.
""",
     """
# Уроки

**Что было не так.** Таблица собрана «минимально»: без `searchStringAddition`,
`viewStatusAddition`, `searchControlAddition`, без `autoMaxRowsCount`, `header`,
скроллбаров, `rowFilter`; вместо них `TableExtInfo/autoRefresh`.

**Симптом.** Пустой лист формы в EDT при валидном XML.

**Почему.** Редактор EDT строит таблицу только с полным составом
элементов-спутников (каждый со своей подсказкой и контекстным меню).

**Что изменилось.** Таблица собирается по образцу того, что делает сам EDT:
колонки → autoCommandBar → три спутника → extendedTooltip → contextMenu →
свойства (changeRowSet … rowFilter). `rowFilter xsi:type="core:UndefinedValue"`
требует `xmlns:core` в корне формы.

**Правило.** Таблицу собирать ТОЛЬКО по образцу рабочей формы; для
мобильной — те же спутники, но `searchStringLocation/viewStatusLocation/
searchControlLocation None`.

**Коммиты.** MVM 6631c1e.

**Ссылки.** `tools/edt_lib.value_table`, `examples/metadata/data-processor/`,
`reference/DataProcessors/мвмПривязкаПунктов/Forms/Форма/Form.form`.
""",
     before=[('table.fragment.xml', W + """
    <items xsi:type="form:Table">
      <name>Строки</name>
      <id>10</id>
      …колонки…
      <autoCommandBar>…</autoCommandBar>
      <changeRowSet>true</changeRowSet>
      <changeRowOrder>true</changeRowOrder>
      <selectionMode>MultiRow</selectionMode>
      <representation>List</representation>
      <horizontalStretch>true</horizontalStretch>
      <verticalStretch>true</verticalStretch>
      <extInfo xsi:type="form:TableExtInfo">
        <autoRefresh>false</autoRefresh>
      </extInfo>
    </items>
""")],
     after=[('table.fragment.xml', C + """
    <items xsi:type="form:Table">
      <name>Строки</name>
      <id>10</id>
      …колонки…
      <autoCommandBar>
        <name>СтрокиКоманднаяПанель</name>
        <id>31</id>
        <horizontalAlign>Left</horizontalAlign>
        <autoFill>true</autoFill>
      </autoCommandBar>
      <searchStringAddition>
        <name>СтрокиСтрокаПоиска</name>
        <id>32</id>
        <extendedTooltip>…</extendedTooltip>
        <contextMenu>…</contextMenu>
        <source>Строки</source>
        <extInfo xsi:type="form:SearchStringAdditionExtInfo">
          <autoMaxWidth>true</autoMaxWidth>
        </extInfo>
      </searchStringAddition>
      <viewStatusAddition>… <type>ViewStatusAddition</type> …</viewStatusAddition>
      <searchControlAddition>… <type>SearchControlAddition</type> …</searchControlAddition>
      <extendedTooltip>…</extendedTooltip>
      <contextMenu>…</contextMenu>
      <changeRowSet>false</changeRowSet>
      <changeRowOrder>false</changeRowOrder>
      <autoMaxWidth>true</autoMaxWidth>
      <autoMaxHeight>true</autoMaxHeight>
      <autoMaxRowsCount>true</autoMaxRowsCount>
      <selectionMode>MultiRow</selectionMode>
      <header>true</header>
      <headerHeight>1</headerHeight>
      <footerHeight>1</footerHeight>
      <horizontalScrollBar>AutoUse</horizontalScrollBar>
      <verticalScrollBar>AutoUse</verticalScrollBar>
      <horizontalLines>true</horizontalLines>
      <verticalLines>true</verticalLines>
      <autoInsertNewRow>false</autoInsertNewRow>
      <searchOnInput>Auto</searchOnInput>
      <initialListView>Auto</initialListView>
      <horizontalStretch>true</horizontalStretch>
      <verticalStretch>true</verticalStretch>
      <enableStartDrag>false</enableStartDrag>
      <enableDrag>false</enableDrag>
      <rowFilter xsi:type="core:UndefinedValue"/>
    </items>
""")])

case(5, 'mobile-use-purposes-root',
     """
# Мобильная форма невидима, пока назначение не включено у корня конфигурации

**Задача.** Форма обработки с назначением «Мобильное устройство».

**Объекты.** DataProcessor.мвмМоиРейсы (форма), Configuration/Configuration.mdo.

**Ожидалось.** Форма открывается в мобильном клиенте.

**Confidence:** HIGH.
""",
     """
# Уроки

**Что было не так.** У корня типовой конфигурации `<usePurposes>` содержал
только `PersonalComputer`.

**Симптом.** Форма с `MobileDevice` создавалась, лежала в дереве и не
открывалась: в EDT редактор пуст, в платформе её не выбрать.

**Почему.** Свойство корня перечисляет, для каких клиентов формы вообще
существуют.

**Что изменилось.** `<usePurposes>MobileDevice</usePurposes>` сразу за
`PersonalComputer` в Configuration.mdo; ставит тот же скрипт, что заводит
мобильную форму. После включения EDT проверяет ВСЕ формы конфигурации на
пригодность мобильному клиенту — много предупреждений, это норма.

**Правило.** Мобильная форма = назначение у формы + назначение у корня +
право MobileClient в роли.

**Коммиты.** MVM ff7cd02.

**Ссылки.** `tools/edt_lib.enable_mobile_purpose`, `knowledge/mobile-forms.md`.
""",
     before=[('Configuration.mdo.fragment.xml', W + """
  <usePurposes>PersonalComputer</usePurposes>
  <scriptVariant>Russian</scriptVariant>
""")],
     after=[('Configuration.mdo.fragment.xml', C + """
  <usePurposes>PersonalComputer</usePurposes>
  <usePurposes>MobileDevice</usePurposes>
  <scriptVariant>Russian</scriptVariant>
""")])

case(6, 'mobile-form-ladder-of-probes',
     """
# Пустой лист мобильной формы: как искали причину и что оказалось правдой

**Задача.** Форма АРМ водителя не рисуется в EDT; отличий от рабочей формы
много, гадать бессмысленно.

**Объекты.** DataProcessor.мвмМоиРейсы (ранее мвмАРМВодителя), временная
DataProcessor.мвмПробаФормы с формами Проба1…Проба10.

**Ожидалось.** Назвать виновника и починить.

**Confidence:** HIGH для метода и найденных причин; отвергнутые гипотезы
помечены.
""",
     """
# Уроки

**Метод.** Временная обработка с формами, каждая следующая отличается от
предыдущей ОДНИМ элементом (заголовок; обработчик; команда с кнопкой; поле
только для чтения; флажок; число; реквизит-документ; точный состав нашей
формы; вызов общего модуля). Открывать по очереди в EDT: первая
не нарисовавшаяся называет виновника. Лесенка накопительная.

**Что нашлось.** (1) `saveWindowSettings` отсутствовал у наших форм (case
002). (2) числовой реквизит без `numberQualifiers` — ИСТИННАЯ причина
пустого листа (case 001). (3) номера колонок = номера реквизитов (case 003).
(4) спутники таблицы (case 004).

**Что было ложным (attempt-*).**
- «Форму с одним мобильным назначением EDT не рисует» — добавляли
  PersonalComputer ключом `--видимая`; НЕ так: после (2) форма с единственным
  MobileDevice рисуется.
- «Таблица значений в мобильной форме не отображается» — переделали экран в
  карточку; НЕ так: не отображалась таблица с числовыми колонками по (2).
- «EDT держится за прежнюю версию объекта» — пересоздали обработку с новыми
  uuid (`--обработку-заново`), переименовали в мвмМоиРейсы. Помогло лишь
  отчасти и стоило полного обновления базы (case 020).

**Итог формы.** Одна форма с двумя назначениями (`MobileDevice` +
`PersonalComputer`): проверяется в тонком клиенте, страницы закладками
работают одинаково.

**Правило.** Пустой лист в EDT НЕ говорит, что именно неполно; объяснять его
свойствами формы («мобильная», «с таблицей») — гадание. Разделяет только
лесенка проб. Правку файлов снаружи EDT подхватывает после обновления проекта.

**Коммиты.** MVM 8cebf0f, 5a50607, ac260bf, 37e2ec1, 6934ec8, c479bb8,
1b53f41, ab3c569, 0184346, 8d3dc9e.

**Ссылки.** `reference/generators/проба_мобильной_формы.py`,
`knowledge/mobile-forms.md` §4.
""",
     attempts=[
         ('attempt-1-purpose', [('note.md', """
WRONG (гипотеза не подтвердилась): «EDT рисует форму только с назначением
PersonalComputer» — ключ `--видимая` добавлял назначение ради предпросмотра.
После исправления numberQualifiers форма с одним MobileDevice рисуется.
""")]),
         ('attempt-2-no-tables', [('note.md', """
WRONG (гипотеза не подтвердилась): «таблица значений в мобильной форме не
рисуется» — экран переделан в карточку без таблиц. Причина была в числовой
колонке без numberQualifiers; таблицы на телефоне работают (со спутниками и
commandBarLocation None).
""")]),
         ('attempt-3-recreate-object', [('note.md', """
ЧАСТИЧНО: обработка пересоздана с новыми uuid и новым именем (мвмМоиРейсы).
Само по себе не лечит — лечит numberQualifiers; цена — полное обновление
базы. Оставлено как последнее средство, когда модель EDT держится за старое.
""")]),
         ('final', [('Form.form.attribute.xml', C + """
  <attributes>
    <name>Точек</name>
    …
    <valueType>
      <types>Number</types>
      <numberQualifiers>
        <precision>10</precision>
      </numberQualifiers>
    </valueType>
""")])])

case(7, 'group-through-align',
     """
# Группа без showLeftMargin/united/throughAlign/currentRowUse расползается

**Задача.** Строка «время в пути: ч [ ] мин [ ] сек [ ]» в группе на типовой
форме заказа.

**Объекты.** Documents/уатЗаказГрузоотправителя/Forms/ФормаДокумента/Form.form,
группы мвмГруппаРасчёт, мвмГруппаВремяВПути и др.

**Ожидалось.** Поля строки стоят подряд, прижаты к подписи.

**Confidence:** HIGH — найдено сравнением выгрузки в формат платформы с
типовой группой «Отправление с».
""",
     """
# Уроки

**Что было не так.** У наших групп в extInfo стояли только `group` и
`horizontalAlign` — «остальное по умолчанию».

**Симптом.** «ч» у подписи, «мин/сек» у правого края формы: элементы
горизонтальной строки выровнялись по колонкам всей страницы.

**Почему.** Для EDT «нет тега» ≠ «как у типовой»: без `throughAlign` EDT
отдаёт платформе «сквозное выравнивание: Использовать». Типовая пишет у
КАЖДОЙ группы `showLeftMargin=true`, `united=true`, `throughAlign=Auto`,
`currentRowUse=Auto`. В XML EDT этого не видно — только в выгрузке в формат
платформы (`1cedtcli export`).

**Что изменилось.** Четыре свойства у каждой нашей группы в порядке типовой:
`group → horizontalAlign → showLeftMargin → united → [showTitle] → throughAlign → currentRowUse`.

**Правило.** Сравнивать свой элемент с типовым В ВЫГРУЗКЕ ПЛАТФОРМЫ, а не в
XML EDT; умолчания EDT и умолчания платформы — не одно и то же.

**Коммиты.** MVM 87e12e2, 72219e3.

**Ссылки.** `tools/edt_lib.usual_group`, case 008, case 009.
""",
     before=[('group.fragment.xml', W + """
      <type>UsualGroup</type>
      <extInfo xsi:type="form:UsualGroupExtInfo">
        <group>AlwaysHorizontal</group>
        <horizontalAlign>Left</horizontalAlign>
      </extInfo>
""")],
     after=[('group.fragment.xml', C + """
      <type>UsualGroup</type>
      <extInfo xsi:type="form:UsualGroupExtInfo">
        <group>AlwaysHorizontal</group>
        <horizontalAlign>Left</horizontalAlign>
        <showLeftMargin>true</showLeftMargin>
        <united>true</united>
        <throughAlign>Auto</throughAlign>
        <currentRowUse>Auto</currentRowUse>
      </extInfo>
""")])

case(8, 'field-width-automaxwidth',
     """
# Поле с width вне колонок тянется до края формы

**Объекты.** Поля «ч/мин/сек» и «Путь, км» формы заказа.

**Ожидалось.** Узкое поле остаётся узким.

**Confidence:** HIGH.
""",
     """
# Уроки

**Что было не так.** `<width>4</width>` без `autoMaxWidth`.

**Симптом.** «ч: [0]» встало у подписи, а «мин/сек» уехали к правому краю.

**Почему.** `width` — минимальная ширина; максимальная без `autoMaxWidth`
не ограничена. Типовая у полей «ч/мин/сек» пишет `width` ВМЕСТЕ с
`autoMaxWidth=true`.

**Правило.** Узкое поле — `width` + `autoMaxWidth=true` (`edt_lib.field(...,
width=4, max_width=True)`).

**Коммиты.** MVM a401896.
""",
     before=[('field.fragment.xml', W + """
      <extInfo xsi:type="form:InputFieldExtInfo">
        <width>4</width>
        <autoMaxHeight>true</autoMaxHeight>
        <wrap>true</wrap>
""")],
     after=[('field.fragment.xml', C + """
      <extInfo xsi:type="form:InputFieldExtInfo">
        <width>4</width>
        <autoMaxWidth>true</autoMaxWidth>
        <autoMaxHeight>true</autoMaxHeight>
        <wrap>true</wrap>
""")])

case(9, 'group-vertical-stretch',
     """
# Панель полей поиска над таблицей делила высоту с таблицей

**Объекты.** Формы выбора и списка справочника пунктов назначения: группа
мвмПанельПоиска над деревом и списком.

**Ожидалось.** Панель занимает одну строку, таблица — остальное.

**Confidence:** HIGH.
""",
     """
# Уроки

**Симптом.** Поля наверху, пустота, таблица прижата к низу («всё разъехалось»).

**Что изменилось.** У группы-панели `<verticalStretch>false</verticalStretch>`,
у колонки со списком — растяжение в обе стороны. Свойства `Group` (`width`,
`height`, `horizontalStretch`, `verticalStretch`) в XML идут ПОСЛЕ
`userVisible`/`title` и ДО `extendedTooltip` — порядок модели EDT (`Form.xcore`:
`FormGroup extends Group, ExtendedTooltipHolder`); типовая у групп их не
пишет, образца нет.

**Правило.** Группе в вертикальной колонке над таблицей — `verticalStretch=false`
явно. Когда непонятно, умеет ли платформа свойство у формы, открывать
`Form.xcore` в jar модели форм EDT: там все свойства с пометками «since».

**Коммиты.** MVM c6ae68e, ac8d144.

**Ссылки.** `tools/edt_lib.usual_group(vertical_stretch=False)`.
""",
     before=[('group.fragment.xml', W + """
      <title>
        <key>ru</key>
        <value>Поиск</value>
      </title>
      <extendedTooltip>
""")],
     after=[('group.fragment.xml', C + """
      <title>
        <key>ru</key>
        <value>Поиск</value>
      </title>
      <verticalStretch>false</verticalStretch>
      <extendedTooltip>
""")])

case(10, 'form-module-reserved-names',
     """
# В модуле формы «Параметры», «Объект», «Элементы», «ЭтаФорма» заняты

**Объекты.** Модуль формы АРМ (переход в документ), модуль формы заказа
(параметры выбора поля). Ловили ДВАЖДЫ.

**Ожидалось.** Открыть форму документа / задать ПараметрыВыбора.

**Confidence:** HIGH.
""",
     """
# Уроки

**Симптом.** «Поле объекта недоступно для записи (Параметры)» при выполнении.

**Почему.** Это свойства самой формы, только для чтения; локальную переменную
платформа под таким именем не заводит. Исключение — процедуры
`&НаСервереБезКонтекста`: формы там нет, имя свободно (в АРМ так читается
объект пункта в переменную `Объект`).

**Что изменилось.** `КлючФормы`, `СписокПараметров`; проверка присваиваний в
`tools/check_bsl.py` (кроме процедур без контекста). Ещё `Команды` — тоже
свойство формы.

**Коммиты.** MVM 694d01f, c0495aa, c6ae68e; EDT 0035ec68.
""",
     before=[('Module.bsl.fragment', WB + """
&НаКлиенте
Процедура ОткрытьДокумент(Ссылка)
	Параметры = Новый Структура("Ключ", Ссылка);
	ОткрытьФорму("Документ." + ИмяДокумента + ".ФормаОбъекта", Параметры, ЭтаФорма, Истина);
КонецПроцедуры

&НаКлиенте
Процедура мвмСкладВыбран(Сторона)
	Параметры = Новый Массив;
	Параметры.Добавить(Новый ПараметрВыбора("Отбор.мвмСклад", Склад));
	ЭлементАдреса.ПараметрыВыбора = Новый ФиксированныйМассив(Параметры);
КонецПроцедуры
""")],
     after=[('Module.bsl.fragment', CB + """
&НаКлиенте
Процедура ОткрытьДокумент(Ссылка)
	// Не «Параметры»: так называется свойство самой формы, и оно только для
	// чтения — присваивание падает «Поле объекта недоступно для записи».
	КлючФормы = Новый Структура("Ключ", Ссылка);
	ОткрытьФорму("Документ." + ИмяДокумента + ".ФормаОбъекта", КлючФормы, ЭтаФорма, Истина);
КонецПроцедуры

&НаКлиенте
Процедура мвмСкладВыбран(Сторона)
	СписокПараметров = Новый Массив;
	СписокПараметров.Добавить(Новый ПараметрВыбора("Отбор.мвмСклад", Склад));
	ЭлементАдреса.ПараметрыВыбора = Новый ФиксированныйМассив(СписокПараметров);
КонецПроцедуры
""")])

case(11, 'procedure-without-directive-is-server',
     """
# Процедура модуля формы без директивы компилируется серверной

**Объекты.** Модуль формы АРМ диспетчера, процедура `ОткрытьФормуТипа`
(переход в настройки типа узла).

**Ожидалось.** Кнопка открывает форму справочника.

**Confidence:** HIGH.
""",
     """
# Уроки

**Симптом.** «Процедура или функция с указанным именем не определена
(ОткрытьФорму)» — только при нажатии кнопки, компилятор молчит.

**Почему.** `ОткрытьФорму` — клиентский метод; процедура без директивы в
модуле управляемой формы — серверная.

**Что изменилось.** `&НаКлиенте` у процедуры; проверка перед укладкой:
клиентские методы (`ОткрытьФорму`, `ПоказатьВопрос`, `ПоказатьПредупреждение`,
`ПодключитьОбработчикОжидания`, …) в процедурах `&НаСервере` или без
директивы — отказ.

**Правило.** У КАЖДОЙ процедуры модуля формы — явная директива.

**Коммиты.** MVM dc5924f; EDT ce3d60af.

**Ссылки.** `tools/check_bsl.py`, case 012.
""",
     before=[('Module.bsl.fragment', WB + """
// Форма элемента справочника типов по коду — ключу карты.
Процедура ОткрытьФормуТипа(ИмяСправочника, Ключ)

	Ссылка = ТипПоКоду(ИмяСправочника, Ключ);
	ОткрытьФорму("Справочник." + ИмяСправочника + ".ФормаОбъекта",
		Новый Структура("Ключ", Ссылка), ЭтаФорма);

КонецПроцедуры
""")],
     after=[('Module.bsl.fragment', CB + """
// Форма элемента справочника типов по коду — ключу карты.
//
// Директива обязательна: процедура модуля формы БЕЗ директивы
// компилируется серверной, а ОткрытьФорму — клиентский метод.
&НаКлиенте
Процедура ОткрытьФормуТипа(ИмяСправочника, Ключ)

	Ссылка = ТипПоКоду(ИмяСправочника, Ключ);
	ОткрытьФорму("Справочник." + ИмяСправочника + ".ФормаОбъекта",
		Новый Структура("Ключ", Ссылка), ЭтаФорма);

КонецПроцедуры
""")])

case(12, 'insertion-breaks-directive',
     """
# Вставка кода между директивой и объявлением функции

**Объекты.** Модуль формы АРМ: шаг генератора вставил служебные функции
перед `Функция ТочкаМаршрута`, якорь был `Функция ТочкаМаршрута(` без
директивы.

**Ожидалось.** Обработка открывается.

**Confidence:** HIGH.
""",
     """
# Уроки

**Симптом.** Обработка падала сразу при открытии: «Процедура или функция с
указанным именем не определена (ТочкаМаршрута)» — функция на месте.

**Почему.** `&НаСервереБезКонтекста` осталась над ВСТАВЛЕННЫМ кодом, а
`ТочкаМаршрута` без директивы стала серверной С контекстом; звали её из
функции без контекста. Компилятор молчит.

**Что изменилось.** Якорь вставки — директива ВМЕСТЕ с объявлением
(`'&НаСервереБезКонтекста' + CRLF + 'Функция ТочкаМаршрута('`), и он обязан
встречаться ровно один раз. Проверка: у каждой функции модуля формы есть
директива (список исключений задан явно).

**Коммиты.** MVM 67c74c5; EDT 2dbee541.

**Ссылки.** `tools/check_bsl.py`, `knowledge/generators.md` §2.
""",
     before=[('Module.bsl.fragment', WB + """
&НаСервереБезКонтекста
// Пункты назначения по узлам: «ссылка узла → массив ид пунктов».
Функция ПунктыПоУзлам()
	…
КонецФункции

Функция ТочкаМаршрута(Пункт, Узлы)     ← осталась без директивы
	…
"""), ('generator.py.fragment', """
# WRONG: якорь без директивы
якорь = 'Функция ТочкаМаршрута('
текст = текст.replace(якорь, помощники + якорь, 1)
""")],
     after=[('Module.bsl.fragment', CB + """
// Пункты назначения по узлам: «ссылка узла → массив ид пунктов».
&НаСервереБезКонтекста
Функция ПунктыПоУзлам()
	…
КонецФункции

&НаСервереБезКонтекста
Функция ТочкаМаршрута(Пункт, Узлы)
	…
"""), ('generator.py.fragment', """
# CORRECT: якорь — директива вместе с объявлением, и ровно один
якорь = '&НаСервереБезКонтекста' + СТР + 'Функция ТочкаМаршрута('
if текст.count(якорь) != 1:
    sys.exit('ОШИБКА: якорь найден %d раз' % текст.count(якорь))
текст = текст.replace(якорь, помощники + якорь, 1)
""")])
print('cases 001-012 ok')
