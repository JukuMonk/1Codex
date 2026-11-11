# Требования и время по пунктам

`tools/workflow/task_plan.py` связывает карточки требований, журнал
`timing.py` и проверенные артефакты. Он не выполняет команды 1С и не задаёт
подключения. Хранить план, журналы и результаты в рабочем каталоге проекта;
пароли, командные строки и строки подключения в карточки не включать.

## Карточки

Перед реализацией подключить [экспертизу задачи](task-expertise.md) через
`expertise_cli.py init --task-plan`. Требования читаются из самой карточки.
Для подключённого плана `begin_stage(..., phase='implementation')` проверяет
актуальность заключения и допуск пункта. Независимый готовый пункт разрешён;
для `__shared__` нужны готовые заключения всех пунктов. Старые планы без
подключения сохраняют прежнее поведение.

Перед реализацией сохранить JSON-массив. Подпункты с разными действиями
оформлять отдельно, например `7.A`, `7.B`, `7.C`. Состав объектов и критерии
проверки задаёт конкретный проект, а не общий пример ниже.

```json
[
  {
    "id": "7.A",
    "requirement": "Заполнить участника в выделенных строках",
    "objects": ["Catalogs/Example/Forms/Main/Ext/Form.xml"],
    "acceptance": ["Невыделенные строки сохраняют прежнего участника"],
    "uncertainties": [],
    "tests": ["selected-participants"],
    "limitations": []
  }
]
```

`create(manifest, title, points, revision, project_root)` создаёт новый файл,
не перезаписывая существующий. `revision` — идентификатор проверяемого входа
или его отпечаток; он не должен обозначать постоянно меняющийся живой исходник.
`set_revision(manifest, revision)` сохраняет историю доказательств, но делает
прежние результаты устаревшими для нового входа.

```powershell
python tools/workflow/task_plan.py create .platform/task.json --project . --title "Доработка" --points .platform/points.json --revision source-sha256
```

## Этапы

Журнал сначала создаётся обычным `timing.py start`. Новый API добавляет к
его этапам `task_id`, `point_id`, `phase`; прежние журналы и команды timing
остаются совместимы. Для общих затрат использовать точный ID `__shared__`,
не распределять выпуск и общий отчёт поровну между пунктами.

```python
from tools.workflow import task_plan

stage_id = task_plan.begin_stage(manifest, journal, "7.A", "implementation")
task_plan.end_stage(manifest, journal, stage_id)
```

Фазы: `analysis`, `implementation`, `static`, `sandbox`, `load`, `compile`,
`com`, `ui`, `visual`, `repair`, `research`, `release`, `report`, `waiting`.
У проваленного этапа обязателен `failure_kind`: `product`, `tool` либо
`infrastructure`. Так ошибка тестового сценария не смешивается с ошибкой
продукта. Родитель должен быть незавершённым этапом этой же задачи; дочерние
этапы закрываются первыми. Неизвестные и уже закрытые этапы отклоняются.

Исследованию задавать осмысленный бюджет, например 180 секунд:

```python
stage_id = task_plan.begin_stage(manifest, journal, "7.A", "research", budget_seconds=180)
decision = task_plan.research_checkpoint(manifest, journal, stage_id)
```

До порога возвращается `within_budget`, после — `needs_probe`: перейти к
минимальному эксперименту или записать конкретное обоснование продолжения.
`research_checkpoint(..., reason="Проверяю конкретный документированный метод")`
возвращает `continue_with_reason`. Это контрольная точка, а не отмена работы,
разрешение изменить её область или новое согласие пользователя.

## Доказательства и отчёт

```python
task_plan.record_evidence(manifest, "7.A", "selected-participants", "ui", "passed",
                          "artifacts/ui-result.json", limitations=[])
task_plan.render_report(manifest, "artifacts/report.html", "html")
```

Уровни: `static`, `compile`, `com`, `ui`, `visual`, `integration`. Указывать
фактически выполненный уровень: наличие PNG не подтверждает UI-действие,
а линт не подтверждает компиляцию. Адаптер теста передаёт результат и путь
к настоящему артефакту. Модуль проверяет принадлежность теста пункту,
существование файла, SHA256 и совпадение ревизии. Он не интерпретирует
произвольный журнал платформы и не заменяет проверку адаптера.

Только последний результат назначенного теста участвует в текущем статусе;
история неудач сохраняется. Изменившийся или удалённый артефакт, устаревшая
ревизия и отсутствующее доказательство дают `unverified`. Актуальный отказ
даёт `failed`, все подтверждённые проверки с ограничением — `limited`, без
ограничений — `verified`. Пункт без назначенных тестов не считается проверенным.

JSON, HTML и Markdown строятся из одного вычисленного результата. Отчёт
включает требования, ссылки-идентификаторы доказательств, ограничения и время.
HTML экранирует пользовательский текст; пути артефактов и отчётов ограничены
корнем проекта, отчёт не может перезаписать план, журнал или доказательство.

Время родителей уменьшается на объединение дочерних интервалов. Пересекающиеся
интервалы одного пункта объединяются; покрытое календарное время всех пунктов
считается отдельно. Пункты могут выполняться параллельно, поэтому сумму
их времён нельзя выдавать за длительность задачи. Незавершённые этапы
показываются отдельно. Старые нетегированные этапы не распределяются задним
числом — для них остаётся прежний общий журнал.

```powershell
python tools/workflow/task_plan.py evidence .platform/task.json --point 7.A --test selected-participants --level ui --status passed --artifact artifacts/ui-result.json
python tools/workflow/task_plan.py report .platform/task.json --format json --output artifacts/report.json
python tools/workflow/task_plan.py report .platform/task.json --format html --output artifacts/report.html
python tools/workflow/task_plan.py report .platform/task.json --format markdown --output artifacts/report.md
python -m unittest tools.workflow.tests.test_task_plan -v
```
