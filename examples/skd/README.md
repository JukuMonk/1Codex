# examples/skd — схемы компоновки данных

Сами схемы лежат рядом с отчётами (папка `Templates/…/Template.dcs`
принадлежит объекту), поэтому здесь — указатель.

| Схема | Что показывает |
|---|---|
| `examples/metadata/report/ПримерОтчет/Templates/ОсновнаяСхемаКомпоновкиДанных/Template.dcs` | один набор-запрос, поля, итог, отбор по ссылке (`DesignTimeValue`) и по строке (`xs:string`, case 034), одна группировка + детальные записи (case 035), `userSettingID` |
| `examples/reports/report-with-parameters-and-grouping/ПримерОтчетПоПериоду/Templates/ОсновнаяСхемаКомпоновкиДанных/Template.dcs` | параметры периода `StandardBeginningDate`, две группировки |
| `reference/Reports/*/Templates/…/Template.dcs` | девять боевых схем: отбор по нескольким полям, группировки по состоянию/дню/машине |

Правила — `knowledge/skd.md`. Коротко:

- файл: табуляция, CRLF, без BOM; корень `DataCompositionSchema` с семью
  пространствами имён (`edt_lib.DCS_HEAD`);
- порядок: `dataSource → dataSet(field…, dataSource, query) → totalField →
  parameter → settingsVariant(settings: selection, filter, order, structure)`;
- запрос в схеме компилируется только при формировании отчёта: те же
  ловушки, что в BSL (кавычки, ключевые слова, `ЭтоГруппа`, строки
  неограниченной длины — cases 015–017, 031); `tools/check_bsl.py` умеет
  проверить `.dcs` как текст запроса, если передать ему файл;
- отбор строкового поля — `xs:string`, ссылочного — `DesignTimeValue`;
- детальные записи — вложенная пустая `StructureItemGroup`;
- `.dcs` — модель EDT, не XML Конфигуратора: ничего не копировать из старых выгрузок.

Генератор: `tools/edt_lib.dcs_schema(name, title, fields, query, selection,
filters, total, groups, parameters)`.
