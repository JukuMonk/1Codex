# Управляемые формы: `Form.form` и `Module.bsl`

Главное правило (HIGH, четыре кейса подряд): форма собирается ТОЛЬКО по
образцу формы, сделанной руками в EDT или проверенной в базе. Валидный XML
без нужного тега EDT принимает молча и показывает пустой лист вместо
предпросмотра. Образцы: `examples/forms/*`, `reference/*/Forms/*`.
Сборка — `tools/edt_lib.py` (field, usual_group, value_table, …).

## 1. Анатомия `Form.form`

```xml
<form:Form xmlns:xsi… xmlns:core… xmlns:form…>
  <title>…</title>                 — только если autoTitle=false
  <items xsi:type="form:…">…       — элементы: FormField, FormGroup, Table, Button, Decoration
  <autoCommandBar>…                — панель формы (id −1 у форм объектов; у обработок — свой номер)
  <handlers><event>OnCreateAtServer</event><name>ПриСозданииНаСервере</name></handlers>
  <windowOpeningMode>LockOwnerWindow</windowOpeningMode>   — у форм элементов/записей
  <saveWindowSettings>true</saveWindowSettings>            — ОБЯЗАТЕЛЕН (case 002)
  <autoTitle>, <autoUrl>, <group>Vertical</group>, <autoFillCheck>, <allowFormCustomize>,
  <enabled>, <showTitle>, <showCloseButton>
  <attributes>…                    — реквизиты формы (первый — основной, main=true)
  <formCommands>…                  — команды формы (id с единицы, своё пространство)
  <commandInterface><navigationPanel/><commandBar/></commandInterface>
  <extInfo xsi:type="form:CatalogFormExtInfo"/>
</form:Form>
```

Основной реквизит и `extInfo` по виду формы:

| Форма | Реквизит | extInfo формы | Пример |
|---|---|---|---|
| элемент справочника | `Объект : CatalogObject.X`, `main`, `savedData` | `form:CatalogFormExtInfo` | `examples/forms/simple-item-form/` |
| список / выбор | `Список : DynamicList` + `DynamicListExtInfo(mainTable)` | `form:DynamicListFormExtInfo` | `examples/forms/list-form/` |
| запись регистра | `Запись : InformationRegisterRecordManager.X` | `form:InformationRegisterManagerFormExtInfo` | `examples/forms/record-form/` |
| документ | `Объект : DocumentObject.X` | `form:DocumentFormExtInfo` (MEDIUM) | `examples/metadata/document/` |
| обработка / отчёт | `Объект : DataProcessorObject.X` | `form:ObjectFormExtInfo` | `examples/metadata/data-processor/` |
| константы (общая форма) | `НаборКонстант : ConstantsSet` | `form:ConstantsFormExtInfo` | `reference/edt-format-guide.md` |

## 2. Три пространства номеров

- **Элементы** (`items`, их подсказки и меню, `autoCommandBar`, спутники
  таблиц): один счётчик, дубли ломают форму.
- **Реквизиты формы И КОЛОНКИ их таблиц значений**: одно пространство —
  «Объект» 1, следующий реквизит 2, колонка его таблицы 3. Колонки,
  пронумерованные заново с единицы, совпадают с «Объектом», и редактор
  перестаёт рисовать форму при валидном XML (case 003).
- **Команды формы** (`formCommands`): своё пространство, с единицы.

`tools/edt_lib.Ids` — счётчик; `check_form` ловит дубли.

## 3. Порядок тегов — как пишет EDT (case 027)

У поля: `name → id → title → visible → enabled → userVisible → dataPath →
defaultItem → handlers → titleLocation → extendedTooltip → contextMenu → type
→ readOnly → editMode → showInHeader → headerHorizontalAlign → showInFooter →
extInfo`. Значения по умолчанию EDT НЕ пишет: скрыть элемент = убрать
`<visible>`, `autoMaxWidth=false`, `representation=None`, `showTitle=false`,
`group=Horizontal` — тегов нет. Если писать иначе, после первого сохранения
в EDT diff расходится на каждом элементе и правку пользователя не отличить
от «EDT переписал». Сверка: `reference/generators/выделить_правки.py`.

У группы (`FormGroup`): `name → id → вложенные items → visible → enabled →
userVisible → title → [horizontalStretch/verticalStretch] → extendedTooltip →
type → extInfo`. Свойства растяжения — после `title`, до `extendedTooltip`:
порядок модели EDT (`Form.xcore`: `FormGroup extends Group,
ExtendedTooltipHolder`), case 009.

## 4. Элементы

**Поле** — `edt_lib.field`. Виды: `InputField` (ext `InputFieldExtInfo`:
autoMaxWidth, autoMaxHeight, wrap, chooseType, typeDomainEnabled, textEdit,
опционально width, format, clearButton, multiLine/extendedEdit, inputHint),
`CheckBoxField`, `LabelField` (для колонок динамического списка). Только
чтение — `<readOnly>true</readOnly>` сразу после `type`.

- Ширина: `width` — МИНИМАЛЬНАЯ; поле вне колонок с одной `width` тянется до
  края формы. Типовая у узких полей пишет `width` ВМЕСТЕ с
  `autoMaxWidth=true` (case 008).
- Формат числа — `<format><key>ru</key><value>ЧЦ=3; ЧДЦ=0; ЧН=</value></format>`
  в extInfo; `ЧН=` гасит ноль (пустое честнее «ограничения 0»).
- Обработчик события поля (`OnChange`) — `<handlers>` сразу за `</dataPath>`.

**Группа** — `edt_lib.usual_group`. Типовая пишет у КАЖДОЙ группы четыре
свойства: `showLeftMargin=true`, `united=true`, `throughAlign=Auto`,
`currentRowUse=Auto`. Без них EDT отдаёт платформе «сквозное выравнивание:
Использовать», и элементы горизонтальной строки расползаются по колонкам
всей страницы (case 007). `group`: Vertical / AlwaysHorizontal; умолчание
Horizontal без тега. Заголовок с рамкой — `representation WeakSeparation`
+ `showTitle true`. Группе в вертикальной колонке над таблицей ставить
`verticalStretch=false`, иначе она делит высоту с таблицей (case 009).

**Страницы** — `edt_lib.pages`: группа `Pages` с `PagesGroupExtInfo`
(`pagesRepresentation` TabsOnTop | Swipe), внутри `Page` с `PageGroupExtInfo`.
Страница с таблицей ТЧ и счётчиком строк в заголовке — `titleDataPath
Объект.ТЧ.RowsCount` (`reference/generators/формы_edt.py`).

**Кнопка** — в командной панели `edt_lib.bar_button` (без `<type>`), на
странице `edt_lib.page_button` (`UsualButton`, `horizontalStretch`, цвета
`textColor/backColor/borderColor` как `core:ColorDef`, шрифт `core:FontRef`).
Обе ссылаются на `Form.Command.Имя` — команда должна быть в `formCommands`,
а обработчик — в модуле.

**Надпись** — `edt_lib.decoration` (`Decoration`, `type Label`); текст ей
модуль задаёт через `Элементы.X.Заголовок`, длинный переносится.

**Таблица значений** — `edt_lib.value_table`. Без трёх спутников
(`searchStringAddition`, `viewStatusAddition`, `searchControlAddition`, у
каждого своя подсказка и меню) и полного набора свойств (`autoMaxRowsCount`,
`header`, скроллбары, `rowFilter`) редактор EDT таблицу не рисует (case 004).
`rowFilter xsi:type="core:UndefinedValue"` требует `xmlns:core` в корне.
Реквизит `ValueTable` с `<columns>` — колонки в общем пространстве номеров.

**Таблица ТЧ объекта** — `edt_lib.object_tabular_table` (dataPath
`Объект.ТЧ`, первая колонка `LineNumber` как LabelField).

**Динамический список** — `edt_lib.dynamic_list_table` +
`list_form_settings_group`: списку нужна группа пользовательских настроек
(`userSettingsGroup`), основная колонка — `defaultItem`, у
иерархического справочника `representation HierarchicalList`.

**Поле HTML** — `edt_lib.html_field`: `width` и `height` обязательны даже при
растяжении, иначе документ нулевой высоты (case 022). См.
`knowledge/html-field-and-templates.md`.

## 5. Реквизиты формы

`edt_lib.form_attribute`. Число БЕЗ `<numberQualifiers>` ломает модель формы
целиком (case 001): `<precision>10</precision>` минимум. Строка —
`<stringQualifiers/>`, дата — `<dateQualifiers><dateFractions>DateTime`.
Каждый `<segments>` в `dataPath` обязан вести к реквизиту (`Объект.X`,
`Список.X`, `Таблица.Колонка`), иначе платформа: «Неверный путь к данным»
(ловили на трёх полях сразу; `check_form` проверяет корень пути).
Колонки реквизита-таблицы держать НАДМНОЖЕСТВОМ колонок таблицы значений,
которую в него кладёт `ЗначениеВРеквизитФормы` (мобильная форма).

## 6. Модуль формы — коротко (подробно `knowledge/bsl.md`)

- У КАЖДОЙ процедуры директива: без неё она серверная (case 011, 012).
- `Параметры`, `Объект`, `Элементы`, `ЭтаФорма`, `ЭтотОбъект` — свойства
  формы, переменные так не называть (case 010).
- `&НаКлиентеНаСервере` при серверном вызове не нашлась — две процедуры
  (case 033, MEDIUM).
- Обработчик формы `ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)`,
  команды `Имя(Команда)`, поля `ИмяПриИзменении(Элемент)`, таблицы
  `ИмяПриАктивизацииСтроки(Элемент)`, `ИмяВыбор(Элемент, ВыбраннаяСтрока,
  Поле, СтандартнаяОбработка)`, страницы `ПриСменеСтраницы(Элемент,
  ТекущаяСтраница)`, поле HTML `ДокументСформирован(Элемент)`.

## 7. Правка ТИПОВОЙ формы

XML типовой формы не переписывать целиком — вставлять фрагменты по якорям
содержимого, идемпотентно, по образцу соседних элементов той же формы
(`reference/generators/формы_edt.py`: поле в корень/в группу, колонка в
таблицу, вкладка с ТЧ; `время_заказа_на_форме.py`: группа расчёта;
`поиск_пунктов_на_форме.py`: панель над динамическим списком).

Скрытие и перестановка типовых элементов по условию — в МОДУЛЕ
(`Элементы.X.Видимость = Ложь`, `Элементы.Переместить(...)`) под
константой, XML остаётся типовым: выключенная константа возвращает форму как
была; `мвмСкрытьЛишнее()` зовётся и из конца типовой `УстановитьВидимость`,
которая часть вкладок показывает заново (case 037). Вставка вызовов в
типовые процедуры — `edt_lib.insert_into_procedure` (case 026).

Пользователь правит форму в EDT → правки переносятся в генератор:
HEAD проекта → генераторы → разница с файлом пользователя = его правки
(`reference/generators/выделить_правки.py`, case 027).

## 8. Формы выбора и параметры

Открыть форму выбора с отбором из кода:
`ОткрытьФорму("Справочник.X.ФормаВыбора", Новый Структура("Отбор", Новый Структура("Склад", Склад)), ЭтотОбъект, , , , ОписаниеОповещения)`;
на стороне формы — `Параметры.Отбор` в `ПриСозданииНаСервере` и
`ОтборыСписковКлиентСервер.ИзменитьЭлементОтбораСписка` (БСП). При отборе
у иерархического списка переводить его в плоский вид (`Элементы.Список.
Отображение = ОтображениеТаблицы.Список`, отбор `ЭтоГруппа = Ложь`):
элементы лежат по разным группам (`examples/bsl/dynamic-list-filter.bsl`).
Параметры выбора у поля: `Элементы.X.ПараметрыВыбора = Новый
ФиксированныйМассив(СписокПараметров)` — но типовой обработчик начала выбора
их может не смотреть, тогда форму открывать самим (case 036).

## 9. Диагностика пустого листа

Пустой предпросмотр в EDT НЕ говорит, что именно неполно. Метод — лесенка
проб: временная обработка с N формами, каждая на один элемент больше
предыдущей; первая не нарисовавшаяся называет виновника
(`reference/generators/проба_мобильной_формы.py`, case 006). Так нашли
`saveWindowSettings`, `numberQualifiers`, номера колонок, спутники таблиц.
Объяснять пустой лист свойствами формы («мобильная», «с таблицей») —
гадание: это уже опровергалось.
