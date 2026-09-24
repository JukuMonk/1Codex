# Подсистемы, командный интерфейс, картинки

Пример — `examples/metadata/subsystem/`, эталон —
`reference/Subsystems/мвмЗаводскаяЛогистика/` (раздел, 12 дочерних групп,
логотип).

## 1. Раздел с группами

```text
Subsystems/Раздел/Раздел.mdo               <subsystems>Группа</subsystems> — КОРОТКОЕ имя дочерней
Subsystems/Раздел/CommandInterface.cmi     порядок команд и порядок дочерних (полные имена)
Subsystems/Раздел/Subsystems/Группа/Группа.mdo   <parentSubsystem>Subsystem.Раздел</parentSubsystem>
Subsystems/Раздел/Subsystems/Группа/CommandInterface.cmi
CommonPictures/Картинка/Картинка.mdo + Picture.zip
Configuration.mdo: <subsystems>Subsystem.Раздел</subsystems> — ТОЛЬКО корневая
```

- **Вложенность задаёт тег `<parentSubsystem>`, а не папка** (case 019).
  Без него EDT не считает подсистему дочерней: в родителе ссылки есть, а
  объекта в модели нет — «нельзя добавлять объекты метаданных без загрузки
  родительского объекта» при инкрементальной загрузке, «Файл объекта не
  существует … .xml» при полной. Три захода (без групп → с группами →
  переименование) ушли на поиск причины не там.
- Новую подсистему с дочерними база принимает только ПОЛНЫМ обновлением
  (case 020).
- Объект в двух подсистемах — появится в интерфейсе дважды; состав
  проверять на дубли.
- Всё своё должно быть в составе какой-то подсистемы, иначе объект
  недостижим кроме «Все функции». Служебное (кэш, общие модули) — в группу
  с `includeInCommandInterface=false`: для прав и поиска по составу.
- `<explanation>` — пояснение группы, видно в интерфейсе.

## 2. CommandInterface.cmi

```xml
<cmi:CommandInterface xmlns:cmi="http://g5.1c.ru/v8/dt/cmi">
  <commandsOrder>
    <orderFragments><group>NavigationPanelImportant</group><commands>DataProcessor.X.StandardCommand.Open</commands></orderFragments>
    <orderFragments><group>NavigationPanelOrdinary</group><commands>Catalog.Y.StandardCommand.OpenList</commands>…</orderFragments>
  </commandsOrder>
  <subsystemsOrder><subsystems>Subsystem.Раздел.Subsystem.Группа</subsystems>…</subsystemsOrder>
</cmi:CommandInterface>
```

- Команда открытия по виду: `OpenList` у справочников, документов,
  регистров; `Open` у обработок, отчётов, констант. Перечисления и общие
  модули в панель не попадают — в порядок их не писать.
- Первый объект группы — «важное», остальные — «обычное».
- Порядок РАЗДЕЛОВ конфигурации — `Configuration/CommandInterface.cmi`,
  `<subsystemsOrder>`: не перечисленные идут после перечисленных (свой раздел
  без записи уезжал за два десятка типовых). Файл без BOM.

## 3. Общая картинка раздела

`Picture.zip` = восемь PNG по масштабам (`85.png` 14 px bldpi, `100.png` 16
ldpi, `125.png` 20 aldpi, `150.png` 24 mdpi, `175.png` 28 amdpi, `200.png` 32
hdpi, `300.png` 48 xdpi, `400.png` 64 udpi) + `Picture.png` 16 px для
интерфейса 8.2 + `manifest.xml` (с BOM, CRLF) — формат снят с типового
раздела «Администрирование». С одним PNG платформа покажет иконку мыльной.
`tools/edt_lib.picture_manifest`, сборка — `tools/make_examples.py:make_picture`.
В Configuration.mdo `<commonPictures>` платформа держит по алфавиту.
Подсистема ссылается `<picture xsi:type="core:PictureRef"><picture>CommonPicture.X</picture></picture>`.

## 4. Синонимы

В командном интерфейсе виден СИНОНИМ объекта: «АРМДиспетчера» вместо
«АРМ Диспетчера» — имя объекта, случайно попавшее в синоним. Проверять
`<synonym>` у обработок отдельно от заголовка формы.

## 5. Переименование раздела (история, MEDIUM)

Переименовать подсистему и добавить ей дочерние одним заходом нельзя было
загрузить инкрементально: для платформы переименованный родитель — другой
объект. Рабочий порядок: полное обновление один раз со всей структурой;
либо заход 0 (раздел без групп, прежнее имя) → заход 1 (группы) → заход 2
(имя). Причиной оказался отсутствующий `parentSubsystem`, но правило про
полное обновление новых объектов осталось (cases 019, 020).

## 6. Начальная страница (HIGH, case 061)

Свойства начальной страницы в `Configuration.mdo` нет — в модели EDT это
`transient`-ссылка. Состав хранит файл `Configuration/HomePageWorkArea.hpwa`
(пространство `homePageWorkArea`): шаблон колонок и формы слева/справа,
образец — `cases/061-home-page-work-area-file/after/`. Настройка
пользователя (Вид → Настройка начальной страницы) сильнее умолчания.
