# Метаданные: файлы `.mdo`

Перед созданием нового `.mdo` — открыть пример того же вида в
`examples/metadata/` и рабочий объект в `reference/`, а собирать через
`tools/edt_lib.py` или `tools/scaffold.py`. Структуру по памяти не
воспроизводить: порядок тегов задан схемой EDT, и «валидный XML» EDT
принимает, а платформа при обновлении базы — нет (case 024, 025).

## 1. Анатомия `.mdo`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<mdclass:Catalog xmlns:xsi=… xmlns:core=… xmlns:mdclass=… uuid="…">
  <producedTypes>            — набор typeId/valueTypeId зависит от вида объекта
  <name>, <synonym>, <comment>
  <useStandardCommands>, <inputByString>, <fullTextSearchOnInputByString>
  <standardAttributes>…      — стандартные реквизиты вида объекта, по одному блоку
  свойства вида объекта      — в порядке схемы (см. примеры)
  <defaultObjectForm> …      — ссылки на формы (место зависит от вида, п. 7)
  <attributes uuid>…         — реквизиты
  <tabularSections uuid>…    — табличные части
  <forms uuid>…              — объявления форм (папка Forms/<Имя>/ обязана существовать)
  <templates uuid>…          — макеты
  <commands uuid>…           — команды объекта (код в Commands/<Имя>/CommandModule.bsl)
</mdclass:Catalog>
```

`producedTypes` по видам (снято с рабочих объектов):

| Вид | typeId-блоки |
|---|---|
| Catalog, Document | objectType, refType, selectionType, listType, managerType |
| Enum | refType, listType, managerType |
| Constant | managerType, valueManagerType, valueKeyType |
| InformationRegister | selectionType, listType, managerType, recordSetType, recordKeyType, recordType, recordManagerType |
| AccumulationRegister | те же без recordManagerType |
| DataProcessor, Report | objectType, managerType |
| CommonModule, Subsystem, Role, CommonPicture | нет |

Каждый `uuid` в файле уникален; у существующего объекта uuid не менять
никогда (переименование — то же uuid, новое имя: case 019). У нового объекта
uuid можно делать УСТОЙЧИВЫМ (uuid5 от имени) — повторная сборка тогда не
рождает «новый» объект (case 020). `tools/edt_lib.stable_uid`.

## 2. Типы и квалификаторы

| Описание | XML | Замечание |
|---|---|---|
| Строка(150) | `<types>String</types><stringQualifiers><length>150</length></stringQualifiers>` | длина ≤ 1024, иначе «Ошибка SDBL: слишком большое значение описателя длины» при обновлении базы (case 024) |
| Строка(0) | `<types>String</types><stringQualifiers/>` | неограниченная — штатный способ для длинного текста (в типовой 1876 раз) |
| Число(15,3) | `<numberQualifiers><precision>15</precision><scale>3</scale>` | без scale, если 0 |
| Булево | `<types>Boolean</types>` | |
| Дата | `<dateQualifiers><dateFractions>DateTime</dateFractions>` | Date / DateTime / Time |
| Справочник.X | `CatalogRef.X` | Документ → `DocumentRef.X`, Перечисление → `EnumRef.X`, ПВХ → `ChartOfCharacteristicTypesRef.X`, определяемый тип → `DefinedType.X` |
| составной | несколько `<types>` внутри одного `<type>` | только ссылки |

## 3. Реквизит

```xml
  <attributes uuid="…">
    <name>Радиус</name>
    <synonym><key>ru</key><value>Радиус, пикселей</value></synonym>
    <type>…</type>
    <minValue xsi:type="core:UndefinedValue"/>
    <maxValue xsi:type="core:UndefinedValue"/>
    <fillChecking>ShowError</fillChecking>          — только у обязательного
    <fillValue xsi:type="core:UndefinedValue"/>     — НЕТ у реквизита табличной части
    <fullTextSearch>Use</fullTextSearch>
    <dataHistory>Use</dataHistory>
  </attributes>
```

Порядок `minValue → maxValue → fillChecking → fillValue` снят с живого
образца: у документа выгрузки Конфигуратора значение однажды уехало в
соседний тег, и 1С отвергла файл при валидном XML (case 025).

Состав свойств зависит от того, ЧЕЙ реквизит: у реквизита ТЧ нет
`fillValue` (в формате Конфигуратора — нет `FillFromFillingValue`,
`FillValue`, `Use`; у реквизита документа нет `Use`). Сверять с живым
образцом того же владельца, не с «реквизитом вообще» (case 025).

Индекс (`<indexing>Index</indexing>`) ставится ПОСЛЕ `fillValue` и ПЕРЕД
`fullTextSearch` — место по типовым объектам; ставить по сверке запросов
(поля в `ГДЕ`/`ПО` растущих таблиц), а не по привычке. У регистра сведений
основной индекс не покрывает второе измерение — отбор по нему требует
своего. Индекс на типовом реквизите — реструктуризация при обновлении (case 055).

Имя реквизита/ресурса не должно быть ключевым словом языка запросов:
`С`, `По` роняли запрос «Ожидается имя» (case 016). Имена, которые точно
ломают: `По, В, Из, Где, Для, Все, Как, Есть, Не, И, Или`.

## 4. Справочник — `examples/metadata/catalog/`

- `codeLength`, `descriptionLength`, `codeType String`, `checkUnique`,
  `autonumbering`. Если код — КЛЮЧ (`street`, `storage`), а не номер:
  `autonumbering=false` и `fillChecking ShowError` у стандартного `Code`,
  иначе новый элемент получал «two00000000000000001» (reference/мвмТипыУзлов).
- Иерархия: `<hierarchical>true</hierarchical><levelCount>2</levelCount><foldersOnTop>true</foldersOnTop>`
  между `fullTextSearch` и `codeLength`. Неиерархический — тегов нет.
  «Группа» в ТЗ может оказаться реквизитом-ссылкой на тот же справочник, а
  не иерархией — уточнять (case 029).
- Иерархический справочник в запросах требует `НЕ X.ЭтоГруппа` (case 017),
  а у плоского поля `ЭтоГруппа` нет вовсе — «Поле не обнаружено».
- Стандартные реквизиты: PredefinedDataName, Predefined, Ref, DeletionMark,
  IsFolder, Owner, Parent, Description (fillChecking), Code.
- Ссылки на формы (`defaultObjectForm`, `defaultListForm`,
  `defaultChoiceForm`) — после `choiceMode`, до реквизитов.

## 5. Регистр сведений — `examples/metadata/information-register/`

Независимый непериодический: тегов `writeMode`/`informationRegisterPeriodicity`
нет (умолчания). Измерения — `<dimensions>` с `<mainFilter>true</mainFilter>`
последним, ресурсы — `<resources>`; состав свойств как у реквизита.
Ссылки на формы (`defaultRecordForm`, `defaultListForm`) стоят ПОСЛЕ
`editType` и ДО `dataLockControlMode` — у справочника наоборот, после
`choiceMode` (case 039). Подчинённый регистратору регистр несёт стандартные
Recorder, LineNumber, Active, Period — независимый отличается их отсутствием.

Чтение: `РегистрыСведений.X.Получить(Отбор)` у независимого регистра
возвращает структуру ВСЕГДА (с пустыми ресурсами, если записи нет) —
факт наличия проверять запросом (case 018).

## 6. Регистр накопления, документ — MEDIUM

Своих в проекте-источнике не заводили; структура снята с типовых объектов
(`examples/metadata/accumulation-register/`, `examples/metadata/document/`):

- у регистра накопления измерения и ресурсы несут только `minValue`,
  `maxValue`, `fullTextSearch` (+ `useInTotals` у измерений); ресурсы идут
  ДО измерений; стандартные RecordType, Active, LineNumber, Recorder, Period;
- у документа: стандартные Posted, Ref, DeletionMark, Date (fillChecking),
  Number; `numberType`, `numberLength`, `numberAllowedLength`, `checkUnique`,
  `autonumbering`; проведение — `realTimePosting`,
  `registerRecordsWritingOnPost`, `<registerRecords>Регистр</registerRecords>`,
  `postInPrivilegedMode`. Реквизиты документа с ТЧ — как у справочника.

Перед использованием сверить с документом/регистром ВАШЕЙ конфигурации:
тегов у типовых больше (справка, `basedOn`, нумератор).

## 7. Перечисление, константа, общий модуль

- Перечисление: `quickChoice`, `choiceMode BothWays`, значения `<enumValues uuid>`
  с `<name>`; имена значений в коде (`Перечисления.X.Y`) сверять с .mdo —
  «Поле объекта не обнаружено (Запрет)», когда значение называлось
  `ЗапретитьВыбранным` (`reference/Enums/`).
- Константа: `type → explanation → minValue → maxValue → dataLockControlMode`;
  читается `Константы.X.Получить()`; в подсистеме открывается
  `Constant.X.StandardCommand.Open`. Генератор-константы у платформы ставит
  один раз демо-посев, XML форм под константу не меняется — поведение
  переключает модуль (case 037).
- Общий модуль: `<server>true</server>` + `<serverCall>true</serverCall>`,
  если его зовёт клиент; `clientOrdinaryApplication false` — так пишет EDT
  для серверного без клиента. Модуль должен быть самодостаточным: функция
  из ЧУЖОГО модуля, вызванная без префикса, падает в бою (case 013).
  `<returnValuesReuse>` — только `DuringRequest` или `DuringSession`; значение,
  которого нет в модели, EDT принимает молча и кэша не даёт. Перед новым
  тегом — `grep` его значений по `src/` типовой (case 048).

## 8. Обработка, отчёт

- Обработка: `defaultForm`, `<forms>` с `usePurposes`, `<templates>` с
  `templateType` (TextDocument, BinaryData, DataCompositionSchema). Двоичный
  макет — сырой файл `Template.bin` (PNG кладётся как есть), текстовый —
  `Template.txt` в CRLF с короткими строками (case 023).
- Отчёт на СКД: `mainDataCompositionSchema` → `Templates/ОсновнаяСхемаКомпоновкиДанных/Template.dcs`;
  формы — общие формы БСП (`CommonForm.ФормаОтчета`,
  `ФормаНастроекОтчета`, `ФормаВариантаОтчета`) и
  `SettingsStorage.ХранилищеВариантовОтчетов`; без БСП эти теги убрать.
  Подробно — `knowledge/skd.md`.

## 9. Добавить реквизит/ТЧ в существующий объект

Вставка после ПОСЛЕДНЕГО `\r\n  </attributes>\r\n` (с отступом два пробела в
якоре!): голое `</attributes>` совпадает и с закрытием реквизита ВНУТРИ
ТЧ (четыре пробела), и новые реквизиты уезжают в чужую таблицу.
`tools/edt_lib.add_attributes_to_mdo` — идемпотентно (по `<name>`).
Порядок в схеме: attributes → tabularSections → forms.

Для типового объекта: реквизит с префиксом, тип из п. 2, состав как в п. 3.
Новый реквизит существующего объекта база принимает инкрементально
(меняется структура — нужен монопольный режим), НОВЫЙ объект — только
полным обновлением (case 020).

## 10. Переименование и удаление

- Переименование объекта = то же uuid, новое `<name>` + переименование папки
  и файла + все FQN-ссылки (Configuration.mdo, подсистемы, роли, формы,
  код). Новый uuid означает новый объект (case 019: подсистема).
- Удаление: убрать папку и строку из Configuration.mdo, из подсистем и
  ролей; проверить `tools/check_project.py`. Данные в базе при
  переименовании реквизита теряются — регистр в проекте пересоздали, только
  когда данных ещё не было (case 016).
