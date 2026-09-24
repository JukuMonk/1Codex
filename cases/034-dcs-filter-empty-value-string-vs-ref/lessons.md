# Уроки

**Что.** Ссылочному полю пустое значение отбора задаётся
`<dcsset:right xsi:type="dcscor:DesignTimeValue">Справочник.X.ПустаяСсылка</dcsset:right>`,
строковому — `<dcsset:right xsi:type="xs:string"/>`: `DesignTimeValue`
строку не описывает, и такой отбор в отчёте не работает.

**Прочее по отборам.** `use=false` (выключен по умолчанию), `viewMode
QuickAccess` (виден в шапке), `userSettingID` устойчивый.

**Коммиты.** MVM 7bb0e48, 3f6961d (генератор отчётов).

**Ссылки.** `tools/edt_lib.dcs_schema`, `examples/metadata/report/`.
