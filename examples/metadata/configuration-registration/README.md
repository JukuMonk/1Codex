# Configuration.mdo — регистрация объектов

`Configuration.mdo` здесь — корень песочницы (`tests/sandbox/src/Configuration/`),
собранный `tools/make_sandbox.py`. В реальном проекте корень уже есть (у
типовой — тысячи строк); менять в нём надо ровно две вещи.

**1. Регистрация объекта верхнего уровня** — строка в группе своего вида,
последней в группе (case 021):

```xml
<subsystems>Subsystem.ПримерРаздел</subsystems>
<commonModules>CommonModule.ПримерОбщийМодуль</commonModules>
<commonPictures>CommonPicture.ПримерРаздел</commonPictures>      ← картинки по алфавиту
<roles>Role.ПримерРоль</roles>
<constants>Constant.ПримерУпрощённыйРежим</constants>
<catalogs>Catalog.ПримерСправочник</catalogs>
<documents>Document.ПримерДокумент</documents>
<enums>Enum.ПримерПеречисление</enums>
<reports>Report.ПримерОтчет</reports>
<dataProcessors>DataProcessor.ПримерОбработка</dataProcessors>
<informationRegisters>InformationRegister.ПримерНедоступность</informationRegisters>
<accumulationRegisters>AccumulationRegister.ПримерОстатки</accumulationRegisters>
```

Порядок групп фиксирован схемой (`edt_lib.CONFIG_GROUPS`);
`edt_lib.register_in_configuration(text, kind, name)` находит группу и
добавляет строку идемпотентно. Дочерние подсистемы, формы, макеты, команды —
не регистрируются: они внутри своего объекта.

**2. Назначения использования** — для мобильных форм у корня должно быть
`<usePurposes>MobileDevice</usePurposes>` рядом с `PersonalComputer` (case 005;
`edt_lib.enable_mobile_purpose`). После включения EDT проверяет все формы на
пригодность мобильному клиенту — предупреждения нормальны.

Больше в корне не трогать ничего: `compatibilityMode`, `defaultRoles`,
`scriptVariant` и прочее — свойства целевой конфигурации.

**Проверка.** `tools/check_project.py` сообщает «не прописан в
Configuration.mdo» для каждого объекта на диске без строки и «нет файла»
для строки без объекта.

**Похожее.** `knowledge/edt-project-structure.md` §4; case 020 (новый объект
— полное обновление базы).
