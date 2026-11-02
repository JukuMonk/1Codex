> Актуальные маршруты Designer: [index/designer.md](designer.md). Ниже исторический указатель EDT.

> Codex: текущий проект работает без EDT; порядок выполнения — `knowledge/codex.md`.
> Указания EDT/Claude ниже относятся к исходным проектам; для XML Конфигуратора
> применять `knowledge/designer-format.md` и `knowledge/validation.md`.

# index/topics — по темам

Формат строки: тема → knowledge (раздел) → рабочий пример → боевой образец → кейсы.
Цель: найти нужное за 1–3 чтения. Confidence указан у самих правил.

## Формат и структура проекта EDT

- Что где лежит, FQN, Configuration.mdo, отличие от выгрузки Конфигуратора →
  `knowledge/edt-project-structure.md` §1–7 → `examples/metadata/configuration-registration/` →
  `reference/edt-format-guide.md` (§5–8, §30) → cases 021, 020.
- Файлы: кодировка, CRLF, отступы, BOM → `knowledge/edt-project-structure.md` §2 →
  все `examples/` → case 023 (макет), 024.
- uuid, устойчивые идентификаторы, ссылки на формы/макеты → `knowledge/uuid-and-references.md` §1–4 →
  `tools/edt_lib.stable_uid` → case 020, 039.

## Метаданные (.mdo)

- Анатомия .mdo, порядок тегов, `producedTypes` → `knowledge/metadata.md` §1 → `examples/metadata/catalog/` → `reference/Catalogs/мвмУзлыКарты/`.
- Типы и квалификаторы, строка ≤ 1024 → `knowledge/metadata.md` §2 → case 024.
- Реквизит: порядок свойств, реквизит ТЧ без `fillValue`, имена не ключевые, индекс по замеру → `knowledge/metadata.md` §3 → cases 025, 016, 055.
- Справочник, иерархия (только по ТЗ) → `knowledge/metadata.md` §4 → `examples/metadata/catalog/` → cases 029, 017.
- Регистр сведений, место ссылок на формы → `knowledge/metadata.md` §5 → `examples/metadata/information-register/` → `reference/InformationRegisters/*` → cases 018, 039.
- Регистр накопления, документ (MEDIUM) → `knowledge/metadata.md` §6 → `examples/metadata/accumulation-register/`, `document/`.
- Перечисление, константа, общий модуль (`returnValuesReuse` из модели EDT) → `knowledge/metadata.md` §7 → `examples/metadata/enum/`, `constant/`, `common-module/` → cases 045, 013, 037, 048.
- Обработка, отчёт → `knowledge/metadata.md` §8 → `examples/metadata/data-processor/`, `report/` → `reference/DataProcessors/*`.
- Добавить реквизит/ТЧ в существующий объект (якорь) → `knowledge/metadata.md` §9 → `tools/edt_lib.add_attributes_to_mdo` → `reference/generators/формы_edt.py`.
- Переименование, удаление → `knowledge/metadata.md` §10 → `knowledge/uuid-and-references.md` §4 → case 019 (attempt-2).

## Управляемые формы (Form.form)

- Анатомия, три пространства номеров, обязательные теги → `knowledge/managed-forms.md` §1–2 → `examples/forms/simple-item-form/` → cases 001, 002, 003, 004.
- Порядок тегов как у EDT, умолчания не писать → `knowledge/managed-forms.md` §3 → case 027 → `reference/generators/выделить_правки.py`.
- Элементы: поле, группа (4 свойства), таблица (спутники), кнопка, страницы, поле HTML → `knowledge/managed-forms.md` §4 → `tools/edt_lib.py` (field, usual_group, value_table, page_button, html_field) → cases 007, 008, 009, 022, 038.
- Реквизиты формы, `numberQualifiers`, таблица значений с колонками, динамический список → `knowledge/managed-forms.md` §5 → `examples/forms/list-form/` → cases 001, 003, 038, 063 (запрос списка не компилируется при загрузке).
- Модуль формы (директивы, имена) → `knowledge/managed-forms.md` §6, `knowledge/bsl.md` §1–2 → `examples/bsl/form-module-skeleton.bsl` → cases 010, 011, 012.
- Правка ТИПОВОЙ формы (вставки, константа) → `knowledge/managed-forms.md` §7 → `examples/bsl/hide-by-constant.bsl` → `reference/generators/упростить_форму_заказа.py` → cases 026, 037.
- Формы выбора, параметры, отбор списка → `knowledge/managed-forms.md` §8 → `examples/bsl/open-form-with-callback.bsl`, `dynamic-list-filter.bsl` → cases 033, 036.
- Диагностика пустого листа → `knowledge/managed-forms.md` §9, `knowledge/mobile-forms.md` §4 → case 006 → `reference/generators/проба_мобильной_формы.py`.

## Мобильные формы

- Что включить (корень, назначения формы, роль) → `knowledge/mobile-forms.md` §1 → `examples/mobile/mobile-form/` → case 005.
- Что не работает или иначе (swipe, командные панели, булевы колонки, кнопки) → `knowledge/mobile-forms.md` §2 → cases 030, 041.
- Как строить экран (одна функция «что показать», страницы, кнопки на странице) → `knowledge/mobile-forms.md` §3 → `reference/DataProcessors/мвмМоиРейсы/`.

## BSL

- Директивы, `&НаКлиентеНаСервере`, серверные по умолчанию → `knowledge/bsl.md` §1 → cases 011, 012, 033.
- Зарезервированные имена формы, реквизит против локальной, глобальные методы платформы, ключевые слова в именах команд → `knowledge/bsl.md` §2 → cases 010, 047, 057, 059.
- Реквизит формы в процедуре без контекста → `knowledge/bsl.md` §1 → case 060.
- `ОбменДанными.Загрузка`, `ПустаяСсылка()`, `Получить` регистра, имена значений перечислений, «Число + Строка» → `knowledge/bsl.md` §3 → cases 014, 032, 018, 045, 058.
- Запросы: кавычки, псевдонимы, группы, неограниченные строки, пакеты → `knowledge/bsl.md` §4 → `examples/bsl/query-patterns.bsl` → cases 015, 016, 017, 031, 042, 046.
- Записи, объекты, «лишнее», необязательные расчёты, «только изменённые» → `knowledge/bsl.md` §5 → cases 043, 044, 051, 053.
- Производительность: профиль «Сервер», Дейкстра на куче, кэш сеанса, запрос в цикле, прямоугольники, разностный пересчёт → `knowledge/bsl.md` §9 → cases 049, 050, 051, 052, 053.
- Вставка в типовой модуль → `knowledge/bsl.md` §6 → `tools/edt_lib.insert_into_procedure` → case 026.
- Общие модули, чужие вызовы, повторное использование значений → `knowledge/bsl.md` §7 → `examples/metadata/common-module/` → cases 013, 048.
- Клиент: оповещения, таймер → `knowledge/bsl.md` §8 → `examples/bsl/open-form-with-callback.bsl`, `timer-refresh.bsl`.

## СКД и отчёты

- Отчёт в .mdo, формы БСП → `knowledge/skd.md` §1 → `examples/metadata/report/`.
- Структура Template.dcs, отборы, группировки, параметры → `knowledge/skd.md` §2 → `examples/reports/report-with-parameters-and-grouping/` → cases 034, 035.
- Запрос в схеме → `knowledge/skd.md` §3 → `examples/skd/README.md` → case 017.

## Подсистемы, интерфейс, картинки, роли

- Раздел с группами, `parentSubsystem`, cmi → `knowledge/subsystems-and-ui.md` §1–2 → `examples/metadata/subsystem/` → `reference/Subsystems/мвмЗаводскаяЛогистика/` → cases 019, 021.
- Картинка раздела → `knowledge/subsystems-and-ui.md` §3 → case 040.
- Роли: файлы, права, чего не даёт → `knowledge/roles.md` §1–4 → `examples/metadata/role/` → `reference/Roles/мвмВодитель/`.

## Поле HTML и макеты

- Поле HTML (width/height), макет CRLF/короткие строки, мост, поведение движка, `confirm`/`alert` и делегирование → `knowledge/html-field-and-templates.md` §1–5 → `examples/forms/html-field-form/` → `reference/DataProcessors/мвмАРМДиспетчера/` → cases 022, 023, 054.

## Проверка в платформе

- Загрузка в пустую базу, обновление ИБ, внешнее соединение, снимки форм → `knowledge/testing.md` → `tools/platform.py`, `tools/register_com.py`, `bootstrap/platform.json.example` → `knowledge/validation.md` §5.
- Демоданные: откуда база, посев (метка, одна транзакция, пропуски с причиной), сброс, перенос со сверкой → `knowledge/demo-data.md` → `tools/platform.py` (`com call`, `com fill`) → `knowledge/testing.md` §6–7 → cases 044, 064, 077, 080, 082.

## Новый проект

- Старт с нуля из `.dt`: база, проект EDT, git, стартовый набор, первый объект → `knowledge/new-project.md` → `tools/new_project.py`, `bootstrap/` → `knowledge/deployment.md` §2.

## Развёртывание, проверка, генераторы

- Только через EDT; полное/инкрементальное обновление; что ломает обновление → `knowledge/deployment.md` §1–3 → cases 020, 024, 028.
- Уровни проверки и отчёт → `knowledge/validation.md` → `tools/check_project.py`, `tools/check_bsl.py`.
- Генераторы: идемпотентность, якоря, правки пользователя → `knowledge/generators.md` → `reference/generators/` → cases 027, 056, 070 (вся цепочка).
- Начальная страница базы (`HomePageWorkArea.hpwa`) → `knowledge/subsystems-and-ui.md` §6 → case 061.
- Каталог ошибок по симптомам → `knowledge/common-errors.md`.
