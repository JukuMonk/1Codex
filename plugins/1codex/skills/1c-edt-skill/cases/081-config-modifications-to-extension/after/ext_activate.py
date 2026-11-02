# -*- coding: utf-8 -*-
"""Расширение НПЦАП_Доработки в базе: первое обновление ИБ без расширения, затем включение без безопасного режима.

БСП обновляет права ролей конфигурации только в сеансе без расширений, изменяющих роли (РегистрСведений.ПраваРолей),
поэтому: выключить расширение → ВыполнитьОбновлениеИнформационнойБазы → включить. Безопасный режим снимается:
интеграции Kafka (внешняя компонента, каталог сертификатов) и Winnum (HTTP) в безопасном режиме не работают.

  python tools/ext_activate.py [ext_base]
"""
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import com  # noqa: E402

EXT = 'НПЦАП_Доработки'


def найти(cn):
    for e in cn.РасширенияКонфигурации.Получить():
        if e.Имя == EXT:
            return e
    raise SystemExit('нет расширения ' + EXT)


def без_предупреждений(cn):
    """Без этого Записать() расширения через COM падает на «Предупреждение безопасности … Подключить?»."""
    защита = cn.NewObject('ОписаниеЗащитыОтОпасныхДействий')
    защита.ПредупреждатьОбОпасныхДействиях = False
    return защита


def main(base='ext_base'):
    cn = com.connect(base)
    e = найти(cn)
    e.ЗащитаОтОпасныхДействий = без_предупреждений(cn)
    e.Активно = False
    e.Записать()
    del e, cn
    import pythoncom
    pythoncom.CoFreeUnusedLibraries()
    rc = com.обновить(base)
    if rc:
        return rc
    cn = com.connect(base)
    e = найти(cn)
    e.Активно = True
    e.БезопасныйРежим = False
    e.ЗащитаОтОпасныхДействий = без_предупреждений(cn)
    e.Записать()
    cn = com.connect(base)
    e = найти(cn)
    print('%s %s: активно %s, безопасный режим %s' % (e.Имя, e.Версия, e.Активно, e.БезопасныйРежим))
    return 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))
