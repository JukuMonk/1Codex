# Форма списка — ФормаСписка (динамический список)

**Что демонстрирует.** `DynamicListFormExtInfo`; реквизит `Список :
DynamicList` с `DynamicListExtInfo` (`mainTable Catalog.ПримерСправочник`,
`dynamicDataRead`, `autoSaveUserSettings`…); группа пользовательских
настроек списка ПЕРЕД таблицей и ссылка на неё `userSettingsGroup`
(case 038); таблица `Список` с `commandBarLocation None`, колонками
`LabelField` (основная — `defaultItem`), спутниками и
`DynamicListTableExtInfo` (`autoRefreshPeriod`, `period`, `topLevelParent`,
`showRoot`, `allowGettingCurrentRowURL`). MEDIUM/HIGH — образец снят с
типовой формы списка, десять таких форм работают в бою.

**Обязательные файлы.** `ПримерСправочник/Forms/ФормаСписка/Form.form`;
в .mdo — `<forms>` + `defaultListForm`. Модуля у примера нет; отбор и поиск —
`examples/bsl/dynamic-list-filter.bsl`.

**Что можно менять.** Колонки (`dynamic_list_table`: `(имя, путь,
ширина)`), `hierarchical=True` для иерархического справочника (представление
`HierarchicalList`), `mainTable` на регистр/документ (тогда `Список.Объект`
и т.п. — поля таблицы), `autoRefreshPeriod`. Панель полей поиска над
таблицей — группа с `verticalStretch=false` (case 009).

**Что согласовано.** Пути `Список.Code`, `Список.Description`, `Список.Тип`
↔ поля основной таблицы; имя группы настроек ↔ `userSettingsGroup`.

**Похожее.** `knowledge/managed-forms.md` §4, §8; `metadata/information-register/…/ФормаСписка`
(список регистра); `reference/Catalogs/*/Forms/ФормаСписка`, `reference/generators/поиск_пунктов_на_форме.py`
(панель поиска над формой выбора типового справочника, cases 033, 036).
