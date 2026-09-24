# Уроки

**Что было не так.** Таблица собрана «минимально»: без `searchStringAddition`,
`viewStatusAddition`, `searchControlAddition`, без `autoMaxRowsCount`, `header`,
скроллбаров, `rowFilter`; вместо них `TableExtInfo/autoRefresh`.

**Симптом.** Пустой лист формы в EDT при валидном XML.

**Почему.** Редактор EDT строит таблицу только с полным составом
элементов-спутников (каждый со своей подсказкой и контекстным меню).

**Что изменилось.** Таблица собирается по образцу того, что делает сам EDT:
колонки → autoCommandBar → три спутника → extendedTooltip → contextMenu →
свойства (changeRowSet … rowFilter). `rowFilter xsi:type="core:UndefinedValue"`
требует `xmlns:core` в корне формы.

**Правило.** Таблицу собирать ТОЛЬКО по образцу рабочей формы; для
мобильной — те же спутники, но `searchStringLocation/viewStatusLocation/
searchControlLocation None`.

**Коммиты.** MVM 6631c1e.

**Ссылки.** `tools/edt_lib.value_table`, `examples/metadata/data-processor/`,
`reference/DataProcessors/мвмПривязкаПунктов/Forms/Форма/Form.form`.
