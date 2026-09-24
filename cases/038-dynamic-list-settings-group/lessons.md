# Уроки

**Что.** Динамический список ссылается `<userSettingsGroup>` на группу
формы (`СписокКомпоновщикНастроекПользовательскиеНастройки`), которая стоит
ПЕРЕД таблицей: обычная группа Vertical/WeakSeparation с `verticalStretch
false`. Таблица списка: `defaultItem` у таблицы и у основной колонки, колонки
`LabelField`, `commandBarLocation None` (панель формы рисует команды сама),
спутники, `DynamicListTableExtInfo` (autoRefreshPeriod, period, topLevelParent,
showRoot, allowGettingCurrentRowURL, userSettingsGroup); у иерархического
справочника — `representation HierarchicalList`. Реквизит `Список :
DynamicList` с `DynamicListExtInfo` (mainTable, dynamicDataRead,
autoFillAvailableFields, autoSaveUserSettings, getInvisibleFieldPresentations),
extInfo формы `DynamicListFormExtInfo`.

**Коммиты.** MVM 1575b57 (`формы_логистики.py`).

**Ссылки.** `examples/forms/list-form/`, `tools/edt_lib.dynamic_list_table`.
