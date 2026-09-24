# СКД: отчёты и `Template.dcs`

Девять отчётов проекта-источника собраны одной функцией
(`tools/edt_lib.dcs_schema`) и работают в базе. Примеры:
`examples/metadata/report/` (простой), `examples/reports/report-with-parameters-and-grouping/`
(параметры периода, группировки), эталоны — `reference/Reports/*`.

## 1. Отчёт в `.mdo`

```xml
<mdclass:Report … uuid>
  <producedTypes> objectType, managerType
  <name>, <synonym>, <useStandardCommands>true
  <defaultForm>CommonForm.ФормаОтчета</defaultForm>                       — БСП
  <mainDataCompositionSchema>Report.X.Template.ОсновнаяСхемаКомпоновкиДанных</mainDataCompositionSchema>
  <defaultSettingsForm>CommonForm.ФормаНастроекОтчета</defaultSettingsForm>
  <defaultVariantForm>CommonForm.ФормаВариантаОтчета</defaultVariantForm>
  <variantsStorage>SettingsStorage.ХранилищеВариантовОтчетов</variantsStorage>
  <templates uuid><name>ОсновнаяСхемаКомпоновкиДанных</name>…<templateType>DataCompositionSchema
```

Файл схемы — `Templates/ОсновнаяСхемаКомпоновкиДанных/Template.dcs`,
отступы табами, CRLF. Отчёт прописывается в Configuration.mdo
(`<reports>`), в подсистему (`Report.X.StandardCommand.Open`) и в роль
(`Use`, `View`), иначе его негде открыть.

## 2. Структура `Template.dcs` (HIGH)

```xml
<DataCompositionSchema xmlns=… dcscom dcscor dcsset v8 v8ui xs xsi>
  <dataSource><name>ИсточникДанных1</name><dataSourceType>Local</dataSourceType></dataSource>
  <dataSet xsi:type="DataSetQuery">
    <name>Данные</name>
    <field xsi:type="DataSetFieldField"><dataPath>Поле</dataPath><field>Поле</field><title …/></field>  × N
    <dataSource>ИсточникДанных1</dataSource>
    <query>текст запроса, & < > экранированы</query>
  </dataSet>
  <totalField><dataPath>Пунктов</dataPath><expression>Сумма(Пунктов)</expression></totalField>
  <parameter>…</parameter>                                     — параметры схемы
  <settingsVariant>
    <dcsset:name>Основной</dcsset:name>
    <dcsset:presentation …>
    <dcsset:settings xmlns:style xmlns:sys xmlns:web xmlns:win>
      <dcsset:selection> выбранные поля
      <dcsset:filter>    отборы (use=false, viewMode QuickAccess, userSettingID)
      <dcsset:dataParameters> значения параметров (StandardBeginningDate)
      <dcsset:outputParameters> Заголовок, ВыводитьЗаголовок
      <dcsset:item xsi:type="dcsset:StructureItemGroup">   — группировки и детальные записи
```

Правила, полученные в работе:

- **Отбор по ссылочному полю** — `dcsset:right xsi:type="dcscor:DesignTimeValue"`
  со значением `Справочник.X.ПустаяСсылка`; **по строковому** —
  `<dcsset:right xsi:type="xs:string"/>`: `DesignTimeValue` строку не описывает,
  и такой отбор не работает (case 034, MEDIUM — из кода, не из падения).
- `viewMode QuickAccess` — отбор виден в шапке отчёта; ради него отчёт и
  делался, прятать в «прочие настройки» незачем.
- `userSettingID` — устойчивый uuid5 от имени отчёта и поля: пересборка не
  сбрасывает сохранённые настройки пользователей.
- **Детальные записи** — вложенная `StructureItemGroup` БЕЗ `groupItems` в
  конце родительской группировки. Без неё отчёт показывает одни итоги:
  видно «не привязано 47», а какие именно — нет (case 035, MEDIUM).
- **Параметры-даты**: `<parameter>` с `xs:dateTime`, `use Always`,
  `denyIncompleteValues`, а начальное значение — в `dataParameters` вариантом
  `StandardBeginningDate` (`BeginningOfThisDay` / `BeginningOfNextDay`), а не
  пустой датой.
- `totalField` — `Сумма(Поле)` по полю-счётчику `1 КАК Пунктов` в запросе.
- Заголовок в `outputParameters` (`Заголовок`, `ВыводитьЗаголовок Output`).

## 3. Запрос в схеме

Тот же язык запросов и те же ловушки, что в BSL (`knowledge/bsl.md`), плюс:

- `ВЫБРАТЬ РАЗРЕШЕННЫЕ` — один раз, в первом запросе объединения; в типовой
  оно стоит в 40 % запросов, при RLS понадобится.
- Иерархический справочник — `НЕ X.ЭтоГруппа` (case 017); у плоского этого
  поля нет.
- В объединении (`ОБЪЕДИНИТЬ ВСЕ`) числа держать в одинаковых позициях, иначе
  поле не сведётся; «раздел» строкой (`"1. Узлы" КАК Раздел`) даёт
  группировку по смыслу.
- Запрос лежит в XML и до боя его не увидит ни один компилятор — проверять
  текстом (`tools/check_bsl.py` умеет читать `.dcs` при передаче файла;
  проверка кавычек там не нужна: в XML кавычки не удваиваются).
- Реквизит через точку (`Пункты.мвмУзелКарты.Тип`) — нормально; ТЧ через
  ссылку — только `Документ.X.ТЧ КАК Строки`.

## 4. Чего не делали (LOW)

Несколько наборов данных со связями, вычисляемые поля, макеты оформления
СКД, вложенные схемы, ресурсы с выражениями сложнее `Сумма` — в проекте не
встречались. Для них брать образец из типовой конфигурации той же
платформы (`Reports/*/Templates/*/Template.dcs`) и добавлять фрагмент по
образцу, а не по памяти.
