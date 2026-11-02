# Уроки

**Симптом.** Стиль создан и назначен основным (`<defaultStyle>`), но жёлтые панели и выделение не изменились.

**Почему.** Жёлто-бежевая гамма 8.5 задана другими элементами стиля (Navigation/AuxiliaryNavigation/Activity/Important…), а не `FormBackColor`. Точные имена и исходные значения — в модели платформы EDT: `resources/v8.5.1/colors/styleColors.xml` внутри jar `com._1c.g5.v8.dt.platform_v8.5.1`.

**Что изменилось.** Style.style с элементами `style:ColorStyleItem` + `core:ColorDef` по именам из модели; `<styles>` в Configuration.mdo идут после `<styleItems>`.

**Правило.** Имена цветов стиля брать из модели EDT нужной версии платформы, а не угадывать; проверять снимком клиента.

**Ссылки.** `tools/edt_lib.py` style_mdo / style_file / set_default_style.
