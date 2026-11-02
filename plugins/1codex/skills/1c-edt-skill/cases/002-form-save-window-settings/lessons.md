# Уроки

**Что было не так.** В хвосте Form.form не было `<saveWindowSettings>true</saveWindowSettings>`.

**Симптом.** Пустой лист вместо предпросмотра, иногда «Возникла внутренняя
ошибка» при обновлении команд. Тег необязательный по схеме, XML валиден, ни
одна проверка не ругается.

**Почему.** Так устроена модель форм EDT; объяснения нет, есть факт: у ВСЕХ
форм типовой конфигурации тег стоит, у нашей — нет.

**Что изменилось.** Порядок хвоста формы: `autoCommandBar → handlers →
[windowOpeningMode] → saveWindowSettings → autoTitle → autoUrl → group →
autoFillCheck → allowFormCustomize → enabled → showTitle → showCloseButton`.

**Правило.** Каркас формы копировать с рабочего образца целиком
(`tools/edt_lib.form_file`), не собирать «минимально необходимое».

**Коммиты.** MVM ac260bf, 5a50607.

**Ссылки.** case 006 (метод), `examples/forms/*`.
