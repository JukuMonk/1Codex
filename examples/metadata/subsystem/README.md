# Подсистема с группой и картинкой — ПримерРаздел / ПримерГруппа

**Что демонстрирует.** Раздел командного интерфейса верхнего уровня с
дочерней подсистемой и общей картинкой:

```
ПримерРаздел/ПримерРаздел.mdo                       ← content, <subsystems>ПримерГруппа</subsystems> (короткое имя), <picture>
ПримерРаздел/CommandInterface.cmi                   ← commandsPlacement важные/обычные, subsystemsOrder
ПримерРаздел/Subsystems/ПримерГруппа/ПримерГруппа.mdo   ← <parentSubsystem>Subsystem.ПримерРаздел</parentSubsystem>  (case 019!)
ПримерРаздел/Subsystems/ПримерГруппа/CommandInterface.cmi
CommonPictures/ПримерРаздел/ПримерРаздел.mdo
CommonPictures/ПримерРаздел/Picture.zip             ← 8 масштабов + Picture.png + manifest.xml (case 040)
```

HIGH — сборка раздела «Заводская логистика» из 12 групп
(`reference/Subsystems/мвмЗаводскаяЛогистика`).

**Регистрация.** В Configuration.mdo — только верхняя: `<subsystems>Subsystem.ПримерРаздел</subsystems>`
и картинка `<commonPictures>CommonPicture.ПримерРаздел</commonPictures>` (по
алфавиту). Дочерние в корень не пишутся. Новая подсистема — полное
обновление базы (case 020).

**Что можно менять.** Состав `content` (полные имена объектов; объект
должен существовать, иначе EDT не загрузит), порядок команд в `.cmi`
(важные — `commandsPlacement` с `Important`, остальные обычные), порядок
групп в `subsystemsOrder` (полные имена `Subsystem.А.Subsystem.Б`),
`includeInCommandInterface`, синонимы (в интерфейсе видны они). Картинка:
`make_examples.make_picture` (нужен Pillow) или свой zip того же состава.

**Что согласовано.** uuid `stable_uid('Subsystem/…')` и
`stable_uid('CommonPicture/…')` — разные (в первой сборке совпали и EDT
считал их одним объектом); `<picture>CommonPicture.ПримерРаздел</picture>` ↔
папка `CommonPictures/ПримерРаздел`.

**Похожее.** `knowledge/subsystems-and-ui.md`; cases 019, 021, 040;
`tools/edt_lib.subsystem_mdo`, `command_interface_cmi`, `commands_of`.
