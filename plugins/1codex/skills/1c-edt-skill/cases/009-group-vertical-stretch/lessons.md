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
