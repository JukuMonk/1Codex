# UUID, идентификаторы и ссылки между файлами

## 1. Где какие идентификаторы

| Где | Что | Правило |
|---|---|---|
| `<mdclass:X uuid="…">` | uuid объекта метаданных | у существующего не менять никогда; переименование объекта — то же uuid, новое имя (case 019) |
| `<producedTypes>` | `typeId`/`valueTypeId` каждого типа объекта | уникальны по конфигурации; у нового объекта — свои; при пересборке брать ПРЕЖНИЕ из файла (`uuid_из`, `тип_ид` в генераторах) |
| `<attributes uuid>`, `<tabularSections uuid>`, `<dimensions uuid>`, `<resources uuid>`, `<enumValues uuid>`, `<forms uuid>`, `<templates uuid>`, `<commands uuid>` | uuid вложенного объекта | при добавлении — новый; при переименовании реквизита данные в базе теряются (case 016) |
| `Form.form`: `<id>` элементов | целые, три пространства (элементы / реквизиты+колонки / команды) | `knowledge/managed-forms.md` §2, case 003 |
| `Template.dcs`: `userSettingID` | uuid настройки отбора/параметра | устойчивый (uuid5), иначе сохранённые настройки пользователей сбрасываются |
| `Configuration.mdo`, `.cmi`, `.rights`, `<content>`, `<parentSubsystem>`, `dataPath`, `commandName` | ТЕКСТОВЫЕ ссылки по полному имени | нет uuid — только FQN; опечатка вылезает при сборке модели или в бою |

## 2. Устойчивые uuid для генерируемых объектов (HIGH, case 020)

Случайный uuid при каждой пересборке делает объект НОВЫМ для базы, а новый
объект принимается только полным обновлением конфигурации. Поэтому
генераторы берут uuid из существующего файла, а если его нет —
`uuid5(NAMESPACE, вид/имя/что)` (`tools/edt_lib.stable_uid`). Пробные
объекты после эксперимента удалять: каждый новый утяжеляет полное обновление.

`tools/scaffold.py` при копировании примера выдаёт свежие uuid всем
`uuid=`, `typeId`, `valueTypeId` — тоже устойчивые от нового имени.

## 3. Полные имена (FQN) — где какие

| Что | Форма записи | Где встречается |
|---|---|---|
| объект | `Catalog.Имя`, `Document.Имя`, `InformationRegister.Имя`, `AccumulationRegister.Имя`, `Enum.Имя`, `Constant.Имя`, `CommonModule.Имя`, `DataProcessor.Имя`, `Report.Имя`, `Role.Имя`, `Subsystem.Имя`, `CommonPicture.Имя`, `DefinedType.Имя` | Configuration.mdo, `<content>` подсистем, Rights.rights |
| форма | `Catalog.Имя.Form.ФормаЭлемента` | `defaultObjectForm`, `defaultListForm`, `defaultRecordForm`, `defaultChoiceForm`, `defaultForm` обработки; в коде — `"Справочник.Имя.ФормаВыбора"`, `"Обработка.Имя.Форма.ИмяФормы"` |
| макет | `Report.Имя.Template.ОсновнаяСхемаКомпоновкиДанных` | `mainDataCompositionSchema`; в коде — `ПолучитьМакет("Имя")` у объекта обработки |
| дочерняя подсистема | `Subsystem.Родитель.Subsystem.Дочерняя` в `.cmi`; `<parentSubsystem>Subsystem.Родитель</parentSubsystem>` в её `.mdo`; `<subsystems>Дочерняя</subsystems>` (короткое имя!) у родителя | case 019 |
| команда навигации | `Catalog.Имя.StandardCommand.OpenList`, `DataProcessor.Имя.StandardCommand.Open`, `Constant.Имя.StandardCommand.Open` | CommandInterface.cmi |
| стандартный реквизит | `Catalog.Имя.StandardAttribute.Description` | `inputByString` |
| тип значения | `CatalogRef.Имя`, `DocumentRef.Имя`, `EnumRef.Имя`, `CatalogObject.Имя`, `DocumentObject.Имя`, `DataProcessorObject.Имя`, `InformationRegisterRecordManager.Имя`, `DynamicList`, `ValueTable`, `ConstantsSet` | `<types>` в .mdo и в реквизитах форм |
| картинка | `CommonPicture.Имя` в `<picture xsi:type="core:PictureRef">`; стандартная — `StdPicture.SetTime` | подсистема, команда формы |
| стиль | `Style.NormalTextFont` в `core:FontRef` | кнопки, надписи |
| команда формы | `Form.Command.Имя` в `<commandName>` кнопки | Form.form |
| путь данных | `Объект.Реквизит`, `Объект.ТЧ.Колонка`, `Список.Code`, `Таблица.Колонка`, `Запись.Ресурс`, `НаборКонстант.Имя` в `<segments>` | Form.form; корень пути обязан быть реквизитом формы |

## 4. Что проверить после изменения ссылок

`python tools/check_project.py <проект> --prefix <ваш>`: регистрация в
Configuration.mdo, `parentSubsystem`, существование объектов из
`<content>`, ссылки на формы и папки форм, пути данных, обработчики в
модулях, дубли uuid и id. Опечатку в FQN внутри BSL (`"Справочник.Имя"`)
инструмент не видит — сверять с деревом `src/`.
