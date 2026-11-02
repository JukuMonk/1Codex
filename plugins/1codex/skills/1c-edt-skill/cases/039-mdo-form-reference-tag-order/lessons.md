# Уроки

**Что.** Порядок тегов в .mdo задан схемой, и «куда-нибудь перед
реквизитами» мало: у регистра `dataLockControlMode` стоит ПОСЛЕ ссылок на
формы, у справочника — ДО. Генератор ищет последний тег-предшественник по
виду объекта (`choiceMode/editType/quickChoice/useStandardCommands/
hierarchical` у справочника; `editType/useStandardCommands/
informationRegisterPeriodicity/writeMode` у регистра) и соблюдает порядок
`defaultObjectForm → defaultRecordForm → defaultListForm → defaultChoiceForm`.

**Коммиты.** MVM 1575b57.

**Ссылки.** `tools/edt_lib.add_form_to_mdo`, `examples/metadata/information-register/`.
