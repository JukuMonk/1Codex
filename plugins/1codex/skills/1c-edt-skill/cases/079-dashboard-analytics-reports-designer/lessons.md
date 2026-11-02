# Уроки

**Интерфейс конфигурации — файлы `Ext/`, Configuration.xml их не упоминает.** `Ext/CommandInterface.xml` —
порядок разделов (`SubsystemsOrder`); `Ext/ClientApplicationInterface.xml` — раскладка (разделы слева «картинка
слева и текст» — копия ТОИР, `designer_lib.CLIENT_INTERFACE_LEFT_SECTIONS`; панель `13322b22…` — «Избранное»);
`Ext/MainSectionPicture.xml` + `MainSectionPicture/Picture.svg`; `Ext/HomePageWorkArea.xml` (`home_page_xml`).
Командный интерфейс подсистемы — `Subsystems/X/Ext/CommandInterface.xml`: важное — `CommandsPlacement` в
`NavigationPanelImportant` + `CommandsOrder`; скрыть — `CommandsVisibility` (`command_interface_xml`).

**SVG — одна общая картинка на все масштабы:** `CommonPictures/X/Ext/Picture.xml` (`<xr:Abs>Picture.svg`) +
`Ext/Picture/Picture.svg` в UTF-8 БЕЗ BOM (`common_picture_xml`, `picture_ext_xml`). Совместимость 8.3.21 принимает.

**Мост страница → 1С ссылкой.** `<a href="#zp-команда">` (и программный `a.click()` по скрытой ссылке) →
`ПриНажатии` с `ДанныеСобытия.Href = "e1c://filev/<путь>#zp-…"`, `Element` — ссылка; детям плитки
`pointer-events:none`. 1С → страница — `value` скрытых полей + метка «длина|номер», опрос `setInterval`.
Проверка без человека — параметр запуска `/C "…=eq-<уид>"`: форма кладёт команду в `#in_cmd`, страница
«нажимает» ссылку. Карточка открывается отдельным окном — снимать ВСЕ окна процесса.

**ECharts в поле HTML:** одна метка `/*ECHARTS*/` (не упоминать в комментариях: заменяются все вхождения);
данные в пробнике — перед ПОСЛЕДНИМ `</body>`; `progressive: 0` у `custom`/`heatmap` с тысячами элементов.

**Формы:** справочник — без `ExtendedPresentation` в `Forms/<Имя>.xml`, форма элемента — `UseForFoldersAndItems`,
основной реквизит — `SavedData`, `DataPath` стандартных реквизитов — `Объект.Description`. Неверное имя
`StdPicture.*` = «Исключение XDTO» всей формы. `…StandardCommand.OpenByValue.<Измерение>` у непериодических
регистров загрузка отвергает. Динамический список: `CommandBarLocation=None` у таблицы, постоянные
`userSettingID` (`dfcece9d…`, `88619765…`, `911b6018…`), `AllowGettingCurrentRowURL`.

**Отчёт без БСП:** `report_xml` + макет `DataCompositionSchema` (тот же XML, что `edt_lib.dcs_schema_ex`);
внешний набор — `DataSetObject` с `objectName`, `ПриКомпоновкеРезультата` с `СтандартнаяОбработка = Ложь`;
служебные параметры ставить, только если `ДоступныеПараметры.НайтиПараметр` их нашёл. Проверка — все варианты
через COM в PDF (`Инициализировать(ИсточникДоступныхНастроек)`, `ЗагрузитьНастройки`, `СкомпоноватьРезультат`).

**Снимки форм без TestManager:** `/URL"e1cib/list|app|command|data?ref=…"`, `ref` — UUID частями 4+5+3+2+1.

**Ссылки.** ZHDRM: `инструменты/конфигурация.py`, `инструменты/html/*.html`, `инструменты/отчеты.py`,
`инструменты/список_оборудования.py`, `ЛОВУШКИ.md` Ж-112…Ж-125; набор: `knowledge/html-field-and-templates.md`,
`knowledge/subsystems-and-ui.md`, `knowledge/skd.md`; кейсы 061, 066, 069, 076, 078.
