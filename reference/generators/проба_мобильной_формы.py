# -*- coding: utf-8 -*-
"""Лесенка проб: с какого элемента мобильная форма перестаёт рисоваться.

Форма, собранная руками в EDT, отображается; наша — нет. Отличий несколько,
и гадать бессмысленно. Скрипт заводит отдельную обработку с пятью формами,
каждая следующая отличается от предыдущей ОДНИМ элементом:

    Проба1  минимум: одно поле-строка (точная копия того, что рисуется)
    Проба2  + заголовок формы и autoTitle = false
    Проба3  + обработчик «ПриСозданииНаСервере»
    Проба4  + команда формы и кнопка в командной панели
    Проба5  + поле только для чтения и поле-ссылка

Открывайте по очереди: первая, которая не нарисуется, и назовёт виноватого.

Обработка временная и живёт отдельно от АРМ водителя — рабочие формы она не
трогает. Убрать: python инструменты/проба_мобильной_формы.py --убрать

Запуск:  python инструменты/проба_мобильной_формы.py [--убрать]
"""
import io
import os
import shutil
import sys
import uuid
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import обработка_привязки_пунктов as образец                  # noqa: E402

ИСХ = образец.ИСХ
УБРАТЬ = '--убрать' in sys.argv

# Вторая форма — компьютерная, с таблицами, и она же основная: так устроена
# обработка мвмАРМВодителя. Ключ включает это отличие.
С_ФОРМОЙ_ПК = '--с-формой-пк' in sys.argv

ИМЯ = 'мвмПробаФормы'
СИНОНИМ = 'Проба мобильной формы (временная)'
ПАПКА = os.path.join(ИСХ, 'DataProcessors', ИМЯ)
СТР = '\r\n'

ПРОБЫ = ['Проба1', 'Проба2', 'Проба3', 'Проба4', 'Проба5',
         'Проба6', 'Проба7', 'Проба8', 'Проба9', 'Проба10']

ЧТО_ПРОВЕРЯЕТ = {
    'Проба1': 'минимум: одно поле-строка',
    'Проба2': 'заголовок формы и autoTitle = false',
    'Проба3': 'обработчик ПриСозданииНаСервере',
    'Проба4': 'команда формы и кнопка',
    'Проба5': 'поле только для чтения и поле-ссылка',
    'Проба6': 'поле-флажок',
    'Проба7': 'числовое поле',
    'Проба8': 'реквизит-документ, не выведенный на форму',
    'Проба9': 'ТОЧНЫЙ состав нашей мобильной формы',
    'Проба10': 'модуль зовёт общий модуль мвмРейсыВодителя',
}


def записать(путь, текст):
    if текст.count('\n') != текст.count(СТР):
        sys.exit('ОШИБКА: %s не в CRLF' % путь)
    if путь.endswith(('.mdo', '.form')):
        try:
            ET.fromstring(текст.encode('utf-8'))
        except ET.ParseError as e:
            sys.exit('ОШИБКА: %s не разбирается: %s' % (путь, e))
    os.makedirs(os.path.dirname(путь), exist_ok=True)
    io.open(путь, 'wb').write(текст.encode('utf-8'))


def прочитать(путь):
    return io.open(путь, 'rb').read().decode('utf-8')


def ид(ключ):
    """Устойчивый uuid: повторный запуск не плодит новые объекты."""
    return str(uuid.uuid5(uuid.NAMESPACE_OID, ИМЯ + ключ))


def описание_обработки():
    строки = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<mdclass:DataProcessor xmlns:mdclass='
        '"http://g5.1c.ru/v8/dt/metadata/mdclass" uuid="%s">' % ид('объект'),
        '  <producedTypes>',
        '    <objectType typeId="%s" valueTypeId="%s"/>'
        % (ид('объектТип'), ид('объектЗнач')),
        '    <managerType typeId="%s" valueTypeId="%s"/>'
        % (ид('менеджерТип'), ид('менеджерЗнач')),
        '  </producedTypes>',
        '  <name>%s</name>' % ИМЯ,
        '  <synonym>',
        '    <key>ru</key>',
        '    <value>%s</value>' % СИНОНИМ,
        '  </synonym>',
        '  <useStandardCommands>true</useStandardCommands>',
        '  <defaultForm>DataProcessor.%s.Form.%s</defaultForm>'
        % (ИМЯ, 'ПробаПК' if С_ФОРМОЙ_ПК else 'Проба1')]
    if С_ФОРМОЙ_ПК:
        строки += ['  <forms uuid="%s">' % ид('ПробаПК'),
                   '    <name>ПробаПК</name>',
                   '    <synonym>',
                   '      <key>ru</key>',
                   '      <value>ПробаПК — компьютерная форма с таблицами</value>',
                   '    </synonym>',
                   '    <usePurposes>PersonalComputer</usePurposes>',
                   '  </forms>']
    for проба in ПРОБЫ:
        строки += ['  <forms uuid="%s">' % ид(проба),
                   '    <name>%s</name>' % проба,
                   '    <synonym>',
                   '      <key>ru</key>',
                   '      <value>%s — %s</value>' % (проба, ЧТО_ПРОВЕРЯЕТ[проба]),
                   '    </synonym>',
                   '    <usePurposes>MobileDevice</usePurposes>',
                   '  </forms>']
    строки += ['</mdclass:DataProcessor>', '']
    return СТР.join(строки)


def реквизит_пробы(имя, подпись, тип, номер, отступ=2):
    """Реквизит формы: номера продолжают общий ряд, как это делает EDT."""
    о = ' ' * отступ
    строки = ['%s<attributes>' % о,
              '%s  <name>%s</name>' % (о, имя),
              '%s  <title>' % о,
              '%s    <key>ru</key>' % о,
              '%s    <value>%s</value>' % (о, подпись),
              '%s  </title>' % о,
              '%s  <id>%d</id>' % (о, номер),
              '%s  <valueType>' % о,
              '%s    <types>%s</types>' % (о, тип)]
    if тип == 'Number':
        строки += ['%s    <numberQualifiers>' % о,
                   '%s      <precision>5</precision>' % о,
                   '%s    </numberQualifiers>' % о]
    строки += ['%s  </valueType>' % о,
               '%s  <view>' % о,
               '%s    <common>true</common>' % о,
               '%s  </view>' % о,
               '%s  <edit>' % о,
               '%s    <common>true</common>' % о,
               '%s  </edit>' % о,
               '%s</attributes>' % о]
    return строки


def хвост_формы(строки, сч, проба, полный=False):
    """Общая часть: панель, обработчик, свойства, реквизиты, команды."""
    строки += ['  <autoCommandBar>',
               '    <name>ФормаКоманднаяПанель</name>',
               '    <id>%d</id>' % сч(),
               '  </autoCommandBar>',
               '  <handlers>',
               '    <event>OnCreateAtServer</event>',
               '    <name>ПриСозданииНаСервере</name>',
               '  </handlers>',
               '  <saveWindowSettings>true</saveWindowSettings>',
               '  <autoTitle>false</autoTitle>',
               '  <autoUrl>true</autoUrl>',
               '  <group>Vertical</group>',
               '  <autoFillCheck>true</autoFillCheck>',
               '  <allowFormCustomize>true</allowFormCustomize>',
               '  <enabled>true</enabled>',
               '  <showTitle>true</showTitle>',
               '  <showCloseButton>true</showCloseButton>',
               '  <attributes>',
               '    <name>Объект</name>',
               '    <id>1</id>',
               '    <valueType>',
               '      <types>DataProcessorObject.%s</types>' % ИМЯ,
               '    </valueType>',
               '    <view>',
               '      <common>true</common>',
               '    </view>',
               '    <edit>',
               '      <common>true</common>',
               '    </edit>',
               '    <main>true</main>',
               '  </attributes>']
    поля = (('Водитель', 'Водитель', 'CatalogRef.ФизическиеЛица'),
            ('МояМашина', 'Машина', 'CatalogRef.уатТС'),
            ('ЧтоДелаю', 'Сейчас', 'String'),
            ('КудаЕду', 'Куда', 'CatalogRef.уатПунктыНазначения'),
            ('НормативТекст', 'Норматив стоянки', 'String'),
            ('ПораЗакончить', 'Пора заканчивать', 'Boolean'),
            ('РейсовВсего', 'Рейсов у меня', 'Number'),
            ('ТекущийРейс', 'Текущий рейс', 'DocumentRef.уатМаршрутныйЛист'))
    for номер, (имя_р, подпись_р, тип_р) in enumerate(поля, 2):
        строки += реквизит_пробы(имя_р, подпись_р, тип_р, номер)
    for номер, имя_кн in enumerate(('Дальше', 'СледующийРейс', 'Обновить'), 1):
        строки += ['  <formCommands>',
                   '    <name>%s</name>' % имя_кн,
                   '    <title>',
                   '      <key>ru</key>',
                   '      <value>%s</value>' % имя_кн,
                   '    </title>',
                   '    <id>%d</id>' % номер,
                   '    <use>',
                   '      <common>true</common>',
                   '    </use>',
                   '    <action xsi:type="form:FormCommandHandlerContainer">',
                   '      <handler>',
                   '        <name>%s</name>' % имя_кн,
                   '      </handler>',
                   '    </action>',
                   '    <currentRowUse>Auto</currentRowUse>',
                   '  </formCommands>']
    строки += ['  <commandInterface>',
               '    <navigationPanel/>',
               '    <commandBar/>',
               '  </commandInterface>',
               '  <extInfo xsi:type="form:ObjectFormExtInfo"/>',
               '</form:Form>',
               '']
    return СТР.join(строки)


def форма_пк():
    """Компьютерная форма с двумя таблицами — как основная форма АРМ."""
    сч = образец.Счётчик()
    строки = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<form:Form xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
              ' xmlns:core="http://g5.1c.ru/v8/dt/mcore"'
              ' xmlns:form="http://g5.1c.ru/v8/dt/form">']
    строки += образец.поле(сч, 'Текст', 'Текст', 2, 'InputField', 'Текст')
    строки += ['  <autoCommandBar>',
               '    <name>ФормаКоманднаяПанель</name>',
               '    <id>%d</id>' % сч(),
               '  </autoCommandBar>',
               '  <saveWindowSettings>true</saveWindowSettings>',
               '  <autoTitle>true</autoTitle>',
               '  <autoUrl>true</autoUrl>',
               '  <group>Vertical</group>',
               '  <autoFillCheck>true</autoFillCheck>',
               '  <allowFormCustomize>true</allowFormCustomize>',
               '  <enabled>true</enabled>',
               '  <showTitle>true</showTitle>',
               '  <showCloseButton>true</showCloseButton>',
               '  <attributes>',
               '    <name>Объект</name>',
               '    <id>1</id>',
               '    <valueType>',
               '      <types>DataProcessorObject.%s</types>' % ИМЯ,
               '    </valueType>',
               '    <view>',
               '      <common>true</common>',
               '    </view>',
               '    <edit>',
               '      <common>true</common>',
               '    </edit>',
               '    <main>true</main>',
               '  </attributes>']
    строки += реквизит_пробы('Текст', 'Текст', 'String', 2)
    строки += ['  <commandInterface>',
               '    <navigationPanel/>',
               '    <commandBar/>',
               '  </commandInterface>',
               '  <extInfo xsi:type="form:ObjectFormExtInfo"/>',
               '</form:Form>',
               '']
    return СТР.join(строки)


def форма(проба):
    """Каждая проба добавляет к предыдущей ровно одно отличие."""
    сч = образец.Счётчик()
    ступень = int(проба.replace('Проба', ''))
    заголовок = ступень >= 2
    обработчик = ступень >= 3
    кнопка = ступень >= 4
    только_чтение = ступень >= 5
    флажок = ступень >= 6
    число = ступень >= 7
    документ = ступень >= 8
    полный = ступень >= 9

    строки = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<form:Form xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
              ' xmlns:core="http://g5.1c.ru/v8/dt/mcore"'
              ' xmlns:form="http://g5.1c.ru/v8/dt/form">']
    if заголовок:
        строки += ['  <title>',
                   '    <key>ru</key>',
                   '    <value>%s</value>' % проба,
                   '  </title>']

    if кнопка:
        строки += ['  <items xsi:type="form:FormGroup">',
                   '    <name>КоманднаяПанель</name>',
                   '    <id>%d</id>' % сч()]
        if полный:
            for имя_кн in ('Дальше', 'СледующийРейс', 'Обновить'):
                строки += образец.кнопка(сч, имя_кн, 4, имя_кн == 'Дальше')
        else:
            строки += образец.кнопка(сч, 'Проверить', 4, True)
        строки += ['    <visible>true</visible>',
                   '    <enabled>true</enabled>',
                   '    <userVisible>',
                   '      <common>true</common>',
                   '    </userVisible>']
        строки += образец.подсказка('КоманднаяПанель', сч(), 4)
        строки += ['    <type>CommandBar</type>',
                   '    <extInfo xsi:type="form:CommandBarExtInfo">',
                   '      <horizontalAlign>Left</horizontalAlign>',
                   '    </extInfo>',
                   '  </items>']

    if полный:
        # Ровно те поля, что стоят в нашей карточке водителя.
        for имя_п, подпись_п, вид_п in (
                ('Водитель', 'Водитель', 'InputField'),
                ('МояМашина', 'Машина', 'InputField'),
                ('ЧтоДелаю', 'Сейчас', 'InputField'),
                ('КудаЕду', 'Куда', 'InputField'),
                ('НормативТекст', 'Норматив стоянки', 'InputField'),
                ('ПораЗакончить', 'Пора заканчивать', 'CheckBoxField'),
                ('РейсовВсего', 'Рейсов у меня', 'InputField')):
            строки += образец.поле(сч, имя_п, имя_п, 2, вид_п, подпись_п, True)
        return хвост_формы(строки, сч, проба, полный=True)

    строки += образец.поле(сч, 'Текст', 'Текст', 2, 'InputField', 'Текст')
    if только_чтение:
        строки += образец.поле(сч, 'Машина', 'Машина', 2, 'InputField',
                               'Машина', True)
    if флажок:
        строки += образец.поле(сч, 'Готово', 'Готово', 2, 'CheckBoxField',
                               'Готово', True)
    if число:
        строки += образец.поле(сч, 'Сколько', 'Сколько', 2, 'InputField',
                               'Сколько', True)

    строки += ['  <autoCommandBar>',
               '    <name>ФормаКоманднаяПанель</name>',
               '    <id>%d</id>' % сч(),
               '  </autoCommandBar>']
    if обработчик:
        строки += ['  <handlers>',
                   '    <event>OnCreateAtServer</event>',
                   '    <name>ПриСозданииНаСервере</name>',
                   '  </handlers>']
    строки += ['  <saveWindowSettings>true</saveWindowSettings>',
               '  <autoTitle>%s</autoTitle>' % ('false' if заголовок else 'true'),
               '  <autoUrl>true</autoUrl>',
               '  <group>Vertical</group>',
               '  <autoFillCheck>true</autoFillCheck>',
               '  <allowFormCustomize>true</allowFormCustomize>',
               '  <enabled>true</enabled>',
               '  <showTitle>true</showTitle>',
               '  <showCloseButton>true</showCloseButton>',
               '  <attributes>',
               '    <name>Объект</name>',
               '    <id>1</id>',
               '    <valueType>',
               '      <types>DataProcessorObject.%s</types>' % ИМЯ,
               '    </valueType>',
               '    <view>',
               '      <common>true</common>',
               '    </view>',
               '    <edit>',
               '      <common>true</common>',
               '    </edit>',
               '    <main>true</main>',
               '  </attributes>',
               '  <attributes>',
               '    <name>Текст</name>',
               '    <title>',
               '      <key>ru</key>',
               '      <value>Текст</value>',
               '    </title>',
               '    <id>2</id>',
               '    <valueType>',
               '      <types>String</types>',
               '      <stringQualifiers/>',
               '    </valueType>',
               '    <view>',
               '      <common>true</common>',
               '    </view>',
               '    <edit>',
               '      <common>true</common>',
               '    </edit>',
               '  </attributes>']
    if флажок:
        строки += реквизит_пробы('Готово', 'Готово', 'Boolean', 4)
    if число:
        строки += реквизит_пробы('Сколько', 'Сколько', 'Number', 5)
    if документ:
        # Реквизит есть, на форму НЕ выведен — так у нас лежит «ТекущийРейс».
        строки += реквизит_пробы('Рейс', 'Рейс',
                                 'DocumentRef.уатМаршрутныйЛист', 6)
    if только_чтение:
        строки += ['  <attributes>',
                   '    <name>Машина</name>',
                   '    <title>',
                   '      <key>ru</key>',
                   '      <value>Машина</value>',
                   '    </title>',
                   '    <id>3</id>',
                   '    <valueType>',
                   '      <types>CatalogRef.уатТС</types>',
                   '    </valueType>',
                   '    <view>',
                   '      <common>true</common>',
                   '    </view>',
                   '    <edit>',
                   '      <common>true</common>',
                   '    </edit>',
                   '  </attributes>']
    if кнопка:
        строки += ['  <formCommands>',
                   '    <name>Проверить</name>',
                   '    <title>',
                   '      <key>ru</key>',
                   '      <value>Проверить</value>',
                   '    </title>',
                   '    <id>1</id>',
                   '    <use>',
                   '      <common>true</common>',
                   '    </use>',
                   '    <action xsi:type="form:FormCommandHandlerContainer">',
                   '      <handler>',
                   '        <name>Проверить</name>',
                   '      </handler>',
                   '    </action>',
                   '    <currentRowUse>Auto</currentRowUse>',
                   '  </formCommands>']
    строки += ['  <commandInterface>',
               '    <navigationPanel/>',
               '    <commandBar/>',
               '  </commandInterface>',
               '  <extInfo xsi:type="form:ObjectFormExtInfo"/>',
               '</form:Form>',
               '']
    return СТР.join(строки)


def модуль(проба):
    куски = ['// Модуль пробной формы «%s»: %s.' % (проба, ЧТО_ПРОВЕРЯЕТ[проба]),
             '//',
             '// Форма временная — собирается'
             ' инструменты/проба_мобильной_формы.py.',
             '']
    if проба in ('Проба3', 'Проба4', 'Проба5'):
        куски += ['&НаСервере',
                  'Процедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)',
                  '',
                  '\tТекст = "форма открылась";',
                  '',
                  'КонецПроцедуры',
                  '']
    if проба == 'Проба10':
        # Ровно то, что делает наша форма: спрашивает общий модуль.
        куски += ['&НаСервере',
                  'Процедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)',
                  '',
                  '\tВодитель = мвмРейсыВодителя.Физлицо();',
                  '\tЧтоДелаю = "форма открылась";',
                  '',
                  'КонецПроцедуры',
                  '']
        for имя_кн in ('Дальше', 'СледующийРейс', 'Обновить'):
            куски += ['&НаКлиенте',
                      'Процедура %s(Команда)' % имя_кн,
                      '',
                      '\tПоказатьПредупреждение(, "%s");' % имя_кн,
                      '',
                      'КонецПроцедуры',
                      '']
        return СТР.join(куски)

    if проба == 'Проба9':
        for имя_кн in ('Дальше', 'СледующийРейс', 'Обновить'):
            куски += ['&НаКлиенте',
                      'Процедура %s(Команда)' % имя_кн,
                      '',
                      '\tПоказатьПредупреждение(, "%s");' % имя_кн,
                      '',
                      'КонецПроцедуры',
                      '']
        return СТР.join(куски)

    if проба in ('Проба4', 'Проба5'):
        куски += ['&НаКлиенте',
                  'Процедура Проверить(Команда)',
                  '',
                  '\tПоказатьПредупреждение(, "Кнопка работает.");',
                  '',
                  'КонецПроцедуры',
                  '']
    return СТР.join(куски)


def зарегистрировать(убрать=False):
    путь = os.path.join(ИСХ, 'Configuration', 'Configuration.mdo')
    т = прочитать(путь)
    строка = '  <dataProcessors>DataProcessor.%s</dataProcessors>' % ИМЯ
    есть = (строка + СТР) in т
    if убрать:
        if есть:
            io.open(путь, 'wb').write(т.replace(строка + СТР, '').encode('utf-8'))
        return есть
    if есть:
        return False
    последняя = т.rfind('  <dataProcessors>')
    конец = т.index(СТР, последняя) + len(СТР)
    io.open(путь, 'wb').write((т[:конец] + строка + СТР + т[конец:])
                              .encode('utf-8'))
    return True


def main():
    if УБРАТЬ:
        было = зарегистрировать(убрать=True)
        if os.path.isdir(ПАПКА):
            shutil.rmtree(ПАПКА)
        print('Пробная обработка убрана%s'
              % ('' if было else ' (её и не было в конфигурации)'))
        return

    записать(os.path.join(ПАПКА, ИМЯ + '.mdo'), описание_обработки())
    if С_ФОРМОЙ_ПК:
        папка = os.path.join(ПАПКА, 'Forms', 'ПробаПК')
        записать(os.path.join(папка, 'Form.form'), форма_пк())
        записать(os.path.join(папка, 'Module.bsl'),
                 '// Компьютерная проба: пусто, важна только сама форма.' + СТР)
    for проба in ПРОБЫ:
        папка = os.path.join(ПАПКА, 'Forms', проба)
        записать(os.path.join(папка, 'Form.form'), форма(проба))
        записать(os.path.join(папка, 'Module.bsl'), модуль(проба))
    новая = зарегистрировать()

    print('Пробная обработка «%s»%s\n'
          % (СИНОНИМ, ' — зарегистрирована' if новая else ''))
    print('  Открывайте формы по порядку. Первая, которая НЕ нарисуется,')
    print('  и называет виноватого:\n')
    for проба in ПРОБЫ:
        print('    %-8s + %s' % (проба, ЧТО_ПРОВЕРЯЕТ[проба]))
    print('\n  Убрать потом: python инструменты/проба_мобильной_формы.py'
          ' --убрать')


if __name__ == '__main__':
    main()
