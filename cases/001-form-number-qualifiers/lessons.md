# Уроки

**Что было не так.** У реквизита формы `<valueType><types>Number</types></valueType>`
без `<numberQualifiers>`. У строк и дат квалификаторы писались, у чисел — нет.

**Симптом.** Пустой лист вместо предпросмотра формы в EDT, «Ошибка построения
модели FormMapping» в журнале EDT. ВСЯ форма, не одно поле. XML валиден.

**Почему.** Тип без квалификаторов для модели EDT неполон — модель формы не
строится. Пробные формы рисовались все, потому что в них квалификаторы были.

**Что изменилось.** У каждого числового реквизита и колонки таблицы значений
— `<numberQualifiers><precision>10</precision></numberQualifiers>`; генератор
отказывается собирать форму без них.

**Правило.** Реквизит формы типа Number — всегда с numberQualifiers; String —
`<stringQualifiers/>`; Date — `<dateQualifiers><dateFractions>`.

**Когда применять.** Любой `<attributes>`/`<columns>` в Form.form.

**Коммиты.** MVM 37e2ec1 (исправление), 6934ec8 (снятие ложных гипотез),
8cebf0f/5a50607 (лесенка проб).

**Ссылки.** `examples/metadata/data-processor/…/Form.form` (реквизиты),
`tools/edt_lib.form_attribute`, `tools/edt_lib.check_form`, case 006.
