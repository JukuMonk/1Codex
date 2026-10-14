# index/patterns — «хочу сделать X»

Каждая строка: что сделать → с чего скопировать → чем собрать/проверить →
что обязательно помнить (кейсы). Читать сверху вниз: пример, инструмент, правила.

| Хочу | Пример (копировать) | Инструмент | Обязательно (кейсы) |
|---|---|---|---|
| Новый справочник | `examples/metadata/catalog/` | `tools/scaffold.py <root> catalog ПримерСправочник Имя`; `edt_lib.catalog_mdo` | регистрация в Configuration.mdo (021), подсистема + роль, uuid5 (020), строка ≤ 1024 (024), имена не ключевые (016), иерархия только по ТЗ (029) |
| Добавить реквизит/ТЧ в существующий объект | фрагмент реквизита в `examples/metadata/catalog/…mdo` | `edt_lib.add_attributes_to_mdo` (якорь `\r\n  </attributes>\r\n`) | порядок свойств, у ТЧ без fillValue (025); поле на форму — `edt_lib.field` |
| Новый регистр сведений | `examples/metadata/information-register/` | `scaffold … information-register ПримерНедоступность Имя` | ссылки на формы до dataLockControlMode (039), чтение запросом (018) |
| Перечисление / константа | `examples/metadata/enum/`, `constant/` | `edt_lib.enum_mdo`, `constant_mdo` | имена значений из .mdo (045); константа-переключатель для правки типовой формы (037) |
| Общий модуль | `examples/metadata/common-module/` | `edt_lib.common_module_mdo`; `check_bsl.py --common` | помощники свои (013), флаги контекста |
| Обработка с формой и таблицей | `examples/metadata/data-processor/` | `scaffold … data-processor ПримерОбработка Имя` | пространство номеров (003), спутники (004), saveWindowSettings (002), numberQualifiers (001) |
| Форма элемента / записи | `examples/forms/simple-item-form/`, `record-form/` | `edt_lib.form_file(items, attrs, …)` | группы с 4 свойствами (007), width+autoMaxWidth (008), verticalStretch (009), порядок EDT (027) |
| Ускорить долгую операцию | `cases/049…053` (профили и правки) | профилировщик EDT, цель «Сервер»; `tools/check_bsl.py` | замер, а не довод (049); запрос в цикле (050); писать только изменённое (051, 053); прямоугольники перед геометрией (052); индекс по замеру (055); `returnValuesReuse` из модели (048) |
| Форма списка | `examples/forms/list-form/` | `edt_lib.list_form_settings_group + dynamic_list_table` | группа настроек до таблицы (038) |
| Панель поиска над списком / отбор из параметров | `examples/bsl/dynamic-list-filter.bsl` | `ОтборыСписковКлиентСервер` | клиент+сервер версии (033), плоский вид при отборе |
| Открыть форму выбора с отбором | `examples/bsl/open-form-with-callback.bsl` | — | ПараметрыВыбора не доезжают (036), имя `Параметры` занято (010) |
| Кнопка/команда на форме | `examples/metadata/data-processor/` | `edt_lib.form_command + bar_button/page_button` | процедура в модуле с `&НаКлиенте` (011) |
| Мобильный экран | `examples/mobile/mobile-form/` | `edt_lib.pages/page_button/value_table(mobile=True)`; `enable_mobile_purpose` | MobileDevice у корня (005), Swipe только у страниц (030), таблицы без панелей и булевых (041), пустой лист → лесенка (006) |
| Поле HTML со страницей | `examples/forms/html-field-form/` | `edt_lib.html_field`; макет CRLF ≤ 900 | width/height (022), CRLF и разрез (023), мост через DOM-поля |
| Отчёт на СКД | `examples/metadata/report/`, `reports/report-with-parameters-and-grouping/` | `edt_lib.dcs_schema` | строка vs ссылка в отборе (034), детальные записи (035), группы иерархических (017) |
| Раздел / группа подсистем | `examples/metadata/subsystem/` | `edt_lib.subsystem_mdo + command_interface_cmi`; картинка `make_examples.make_picture` | parentSubsystem (019), только верхняя в корне (021), полное обновление (020), zip картинки (040) |
| Роль | `examples/metadata/role/` | `edt_lib.rights_file` | имя целевой конфигурации в `Configuration.<Имя>`; базовые роли типовой |
| Изменить ТИПОВУЮ форму | `examples/bsl/hide-by-constant.bsl`; `reference/generators/упростить_форму_заказа.py` | `edt_lib.insert_into_procedure` | в модуле под константой, не в XML (037); `;` и CRLF (026); якорь директива+объявление (012); своя область целиком |
| Вынести доработки типовой в расширение / обновить поставку под расширением | `cases/081-…/after/build_ext.py` (генератор по двум выгрузкам), `082-…/after/migrate.py`, `083-…/after/` | `/DumpConfigToFiles`, `git merge-file`, `/LoadConfigFromFiles -Extension`, COM | поставка из ParentConfigurations; регистры-спутники ≤8.3.25 (081); перенос данных до замены (082); слияние и ошибки обработчиков при скачке (083) |
| Запрос | `examples/bsl/query-patterns.bsl` | `check_bsl.py --hier …` | кавычки (015), ключевые слова (016), ЭтоГруппа (017), ВЫРАЗИТЬ для строк (031), индексы пакета (042), разделители (046) |
| Запись в чужой объект / регистр | `examples/bsl/register-read-by-query.bsl` | — | ОбменДанными.Загрузка (014), ПустаяСсылка() (032), пропуски при записи (044), украшения в Попытка (043) |
| Периодическое обновление формы | `examples/bsl/timer-refresh.bsl` | — | отключать на время записи |
| Условное оформление | `examples/bsl/conditional-appearance.bsl` | — | из модуля, не из XML |
| Проверить проект перед EDT | `tests/sandbox/` | `tools/check_project.py <root> --prefix X` | `knowledge/validation.md`: check → EDT → база (полная при новых объектах) → платформа |
| Найти, что сломало форму (пустой лист) | case 006 | `reference/generators/проба_мобильной_формы.py` | лесенка проб; не гадать по «мобильности» |
| Обновление базы упало | `knowledge/common-errors.md` (первый раздел) | — | новые объекты (020), parentSubsystem (019), 1024 (024), formItem null → «Очистить» (028) |
| Перенести правки пользователя из EDT в генератор | `reference/generators/выделить_правки.py` | — | порядок EDT, цель «0 строк разницы» (027) |
