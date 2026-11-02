# Актуальные маршруты без EDT

Перед изменением определить формат выгрузки, версию платформы, совместимость,
тип конфигурации и отдельную тестовую базу. Не переносить пути из кейсов.

| Задача | Читать | Образцы |
|---|---|---|
| Новый проект | knowledge/new-project.md, раздел 6 knowledge/designer-format.md | cases/078, cases/084 |
| Внешняя обработка | разделы 2–4 knowledge/designer-format.md | cases/074 |
| Правка готовой формы/XML | раздел 1 knowledge/designer-format.md, knowledge/project-runner.md | cases/092, cases/096, cases/097 |
| Поставщик и расширение | раздел 7 knowledge/designer-format.md | cases/081, cases/082, cases/083, cases/091 |
| BSL и запросы | knowledge/bsl.md, tools/bsl_checks.py | Каталог index/catalog.json, формат shared |
| СКД | knowledge/skd.md, tools/skd_builder.py | Схема из целевой выгрузки |
| Тестирование | knowledge/validation.md, knowledge/project-runner.md | tests/designer/ |
| Защита выпуска и UI | knowledge/reliable-workflow.md | tools/workflow/ |
| Анализ времени | knowledge/task-timing.md, knowledge/self-improvement.md | tools/workflow/analyze_timing.py |

`index/topics.md`, `examples/` и `tests/sandbox/` сохраняют исторические примеры
EDT. Для нового проекта выбирайте этот указатель и tests/designer/.

Поиск: `python tools/case_catalog.py search --format designer --query "остатки"`.
Confidence относится к историческому прогону. Null в версии означает отсутствие
структурированной проверки, а не совместимость со всеми версиями.
`platform_mentions` — упоминания в исходном тексте, не диапазон совместимости.
