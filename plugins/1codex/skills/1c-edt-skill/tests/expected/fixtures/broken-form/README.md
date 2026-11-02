# broken-form — фикстура к T06

Получена из `examples/metadata/data-processor/ПримерОбработка/Forms/Форма/Form.form`
скриптом `../make_fixtures.py`. Четыре дефекта, каждый из которых в EDT даёт
ПУСТОЙ ЛИСТ вместо формы при валидном XML:

| № | Дефект | Кейс | Как находит `check_form` |
|---|---|---|---|
| 1 | нет `<saveWindowSettings>true</saveWindowSettings>` | 002 | «нет saveWindowSettings» |
| 2 | реквизит формы `Лимит` типа `Number` без `<numberQualifiers>` | 001 | «числовой реквизит без numberQualifiers» |
| 3 | колонка `Отметка` таблицы `Строки` имеет `<id>1</id>` — как реквизит `Объект` | 003 | «дубль номера реквизита/колонки» |
| 4 | у таблицы `Строки` удалён `<searchStringAddition>` | 004 | «у таблицы нет спутника» |

Исправленный файл должен совпасть с исходным примером плюс реквизит `Лимит`
с квалификаторами (`<numberQualifiers><precision>15</precision><scale>2</scale>…`
как выдаёт `edt_lib.form_attribute(…, 'Number')`) — либо без него, если
модель решила реквизит удалить (оба варианта верны, если объяснены).
