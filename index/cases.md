# index/cases — 62 кейса

Каждый кейс: `task.md` (задача, объекты, confidence), `before/` (WRONG),
`after/` (CORRECT), `lessons.md` (симптом → причина → правило → коммиты →
ссылки); у многозаходных — `attempt-*/`. Поиск по симптому — колонка
«Симптом»; по теме — «Тема». HIGH — исправление подтверждено в базе/EDT;
MEDIUM — работает, причина не доказана или образец снят с типового без
падения в истории.

| № | Кейс | Тема | Симптом / ключевые слова | Conf. |
|---|---|---|---|---|
| 001 | form-number-qualifiers | форма | пустой лист в EDT; числовой реквизит без `numberQualifiers` | HIGH |
| 002 | form-save-window-settings | форма | пустой лист; нет `saveWindowSettings`; «Возникла внутренняя ошибка» | HIGH |
| 003 | form-attribute-column-id-space | форма | пустой лист; колонка с номером реквизита «Объект»; три пространства номеров | HIGH |
| 004 | form-table-companions | форма | таблица не рисуется; `searchStringAddition`/`viewStatusAddition`/`searchControlAddition` | HIGH |
| 005 | mobile-use-purposes-root | мобильные | форма есть, не открывается; `usePurposes MobileDevice` у корня | HIGH |
| 006 | mobile-form-ladder-of-probes | диагностика | «мобильную форму EDT не рисует» — не так; лесенка проб, три ложных диагноза | HIGH |
| 007 | group-through-align | форма | элементы строки разъехались по колонкам; 4 свойства группы | HIGH |
| 008 | field-width-automaxwidth | форма | поле до края формы; `width` + `autoMaxWidth` | HIGH |
| 009 | group-vertical-stretch | форма | панель наверху, пустота, таблица внизу; `verticalStretch=false`, место тегов Group | HIGH |
| 010 | form-module-reserved-names | BSL | «Поле объекта недоступно для записи (Параметры)»; Объект/Элементы/ЭтаФорма | HIGH |
| 011 | procedure-without-directive-is-server | BSL | «не определена (ОткрытьФорму)» при нажатии; процедура без директивы | HIGH |
| 012 | insertion-breaks-directive | BSL/генератор | вставка между директивой и объявлением; «не определена (ТочкаМаршрута)» | HIGH |
| 013 | cross-module-call | BSL | «{ОбщийМодуль…} не определена (ЧислоИлиНоль)»; чужой помощник | HIGH |
| 014 | exchange-data-load-property | BSL | «Поле объекта не обнаружено (ОбменДаннымиЗагрузка)» | HIGH |
| 015 | query-quote-in-string-literal | запросы | «Строка, не закрывающаяся кавычкой»; `<> ""` | HIGH |
| 016 | query-keyword-as-attribute-name | запросы/метаданные | «Ожидается имя»; ресурсы `С`, `По` | HIGH |
| 017 | hierarchical-catalog-groups-in-queries | запросы | «Преобразование значения к типу Число» на чистой базе; `ЭтоГруппа`; у плоского поля нет | HIGH |
| 018 | register-get-returns-structure | BSL | кэш «находит» запись, которой нет; `Получить` никогда не Неопределено | HIGH |
| 019 | parent-subsystem-tag | подсистемы | «нельзя добавлять объекты без загрузки родительского»; «Файл объекта не существует»; три ложных диагноза | HIGH |
| 020 | new-objects-need-full-update-stable-uuids | развёртывание | новый объект = полное обновление; uuid4 при пересборке | HIGH |
| 021 | configuration-registration | структура | объект на диске, конфигурация не видит | HIGH |
| 022 | html-field-width-height | поле HTML | белый экран, «окно:2711x0»; `width 70`/`height 10` | HIGH |
| 023 | text-template-crlf-line-length | макеты | пустая страница; LF = одна строка; 147 363 символа; `Символ(1)` | HIGH |
| 024 | string-attribute-length-1024 | метаданные | «Ошибка SDBL: слишком большое значение описателя длины» | HIGH |
| 025 | attribute-property-set-by-owner | метаданные | «Свойство … не входит в состав объекта метаданных Attribute»; у ТЧ без fillValue | HIGH |
| 026 | insert-into-vendor-procedure-semicolon-crlf | генератор/BSL | «Ожидается символ ';'»; одиночный LF | HIGH |
| 027 | edt-canonical-order-user-edits | форма/генератор | diff на каждом поле; порядок тегов EDT; правки пользователя | HIGH |
| 028 | edt-workspace-formitem-null | EDT | «NullPointerException … formItem is null»; «Проект → Очистить» | HIGH |
| 029 | catalog-hierarchy-vs-attribute | метаданные | «Группа» в ТЗ = реквизит, не иерархия | HIGH |
| 030 | mobile-pages-swipe-no-row-swipe | мобильные | смахивания по строке нет; `Form.xcore`; TabsOnTop vs Swipe | HIGH |
| 031 | aggregate-over-unlimited-string | запросы | «Неверные параметры МАКСИМУМ»; `ВЫРАЗИТЬ … КАК СТРОКА(150)` | HIGH |
| 032 | empty-ref-method-parens | BSL | «Поле объекта не обнаружено (ПустаяСсылка)» | HIGH |
| 033 | client-server-directive-not-found | BSL | «не определена (мвмИерархияПоОтбору)» у `&НаКлиентеНаСервере` | MEDIUM |
| 034 | dcs-filter-empty-value-string-vs-ref | СКД | отбор по строке не работает; `xs:string` vs `DesignTimeValue` | MEDIUM |
| 035 | dcs-detail-records-group | СКД | только итоги без строк; вложенная группировка | MEDIUM |
| 036 | choice-form-filter-parameters | формы | ПараметрыВыбора не доезжают; открыть форму самим с оповещением | HIGH |
| 037 | hide-by-constant-in-module-not-xml | типовая форма | скрытие в XML необратимо; константа + модуль; «откуда поле Договор» | HIGH |
| 038 | dynamic-list-settings-group | форма списка | группа настроек до таблицы; `DynamicListTableExtInfo` | MEDIUM |
| 039 | mdo-form-reference-tag-order | метаданные | `defaultRecordForm` до `dataLockControlMode`, у справочника после `choiceMode` | MEDIUM |
| 040 | picture-zip-manifest | интерфейс | мыльная иконка; 8 масштабов + manifest.xml | MEDIUM |
| 041 | mobile-table-and-buttons | мобильные | «More actions», три полосы, «No» в колонке, кнопки в «ещё» | HIGH |
| 042 | query-packet-result-index | запросы | «Поле объекта не обнаружено (ТС)»; индексы пакета поимённо | HIGH |
| 043 | optional-calculation-in-try | BSL | АРМ пустой из-за украшения; `Попытка`; подача от гаража | HIGH |
| 044 | skipped-object-kept-on-write | BSL | зона исчезла молча; `Продолжить` без учёта; `НечегоПисать` | HIGH |
| 045 | enum-value-names-from-mdo | BSL | «Поле объекта не обнаружено (Запрет)» | HIGH |
| 046 | empty-query-in-packet | запросы | «Ожидается выражение "ВЫБРАТЬ"»; два `;` | HIGH |
| 047 | global-platform-name-in-thick-client | BSL | «уже определена (Состояние)» в толстом клиенте; глобальные методы | HIGH |
| 048 | mdo-values-from-edt-model | метаданные | кэш «не работает»; `DuringCall` принят молча; `returnValuesReuse` | HIGH |
| 049 | profile-before-optimizing | BSL | автораздача 104 с; перебор минимума; граф на каждый маршрут; цель «Сервер» | HIGH |
| 050 | attribute-read-in-loop-is-query | BSL | тысячи `ЗначенияРеквизитовОбъекта`; реквизит через точку в цикле; два вызова сервера на экран | HIGH |
| 051 | write-only-changed-objects | BSL | запись 13,5 с; `Записать()` на каждый объект; сравнение с точностью реквизита | HIGH |
| 052 | bounding-box-before-geometry | BSL | запись 30 с; 767 тыс. «точка в полигоне»; описывающий прямоугольник; «сотня вершин» сочинена | HIGH |
| 053 | only-changed-everywhere-and-ref-keys | BSL | 69 зон пишутся всегда; полный пересчёт регистра; `Строка(Ключ)` для ссылки; набор с отбором | HIGH |
| 054 | html-field-no-confirm-alert | поле HTML | кнопки попапа не нажимаются; `confirm` вешает; делегирование на `document` | HIGH |
| 055 | index-by-query-measurement | метаданные | отбор по неиндексированному полю; `<indexing>Index</indexing>`; второе измерение регистра | HIGH |
| 056 | generator-idempotence-check | генераторы | второй прогон вставил дважды; `стало in текст and было not in текст` | HIGH |
| 057 | form-command-name-bsl-keyword | форма | «Ожидается имя процедуры»; команда `Прервать` | HIGH |
| 058 | number-plus-string | BSL | «Преобразование значения к типу Число»; `Номер + ". "` | HIGH |
| 059 | form-attribute-shadows-local-variable | BSL | «Нельзя изменять поле, содержащее объект данных формы»; реквизит и локальная | HIGH |
| 060 | form-attribute-in-no-context-procedure | BSL | «Переменная не определена»; реквизит формы в БезКонтекста | HIGH |
| 062 | alias-equals-tabular-section | запросы | «Неоднозначное поле "Тарировка.Ссылка"»; псевдоним = имя ТЧ | HIGH |
| 061 | home-page-work-area-file | интерфейс | начальная страница; `HomePageWorkArea.hpwa`; `transient` | HIGH |

Кейсы 047–062 записаны по ходу работы над АРМ диспетчера и упоминают его
объекты (граф проездов, геозоны, заявки, датчики топлива); уроки в них общие,
термины — в словаре `README.md`.

## По темам

- Форма не рисуется / разъехалась: 001, 002, 003, 004, 006, 007, 008, 009, 022, 027, 028, 038, 057.
- Мобильный клиент: 005, 006, 030, 041.
- Модуль формы и BSL: 010, 011, 012, 013, 014, 018, 032, 033, 043, 044, 045, 047, 057, 058, 059, 060.
- Производительность (по замеру, не по догадке): 049, 050, 051, 052, 053, 055.
- Запросы: 015, 016, 017, 031, 042, 046, 062 (+ СКД 034, 035).
- Метаданные и структура: 016, 021, 024, 025, 029, 039, 048, 055.
- Подсистемы, интерфейс, картинки: 019, 021, 040, 061.
- Развёртывание и EDT: 019, 020, 024, 028.
- Правка типовой конфигурации: 026, 036, 037.
- Поле HTML и макеты: 022, 023, 054.
- Генераторы и правки пользователя: 012, 026, 027, 056.
