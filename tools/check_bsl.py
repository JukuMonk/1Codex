# -*- coding: utf-8 -*-
"""check_bsl — претензии к модулю BSL, которые компилятор пропускает,
а платформа показывает в бою.

  python tools/check_bsl.py <Module.bsl> [--common] [--hier Справочник1,Справочник2]

  --common   модуль общий (не формы): не требует директив и не ловит
             занятые имена «Параметры/Объект/Элементы»;
  --hier     иерархические справочники конфигурации — для проверки, что
             запросы к ним отсекают группы (case 017). Список можно снять
             с проекта: grep -l "<hierarchical>true" src/Catalogs/*/*.mdo

Что ловит (номера — cases/):
  001..   форм не касается; здесь только код:
  010  присваивание «Параметры = …» в модуле формы;
  011  клиентский метод в серверной / бездирективной процедуре;
  012  функция модуля формы без директивы (вставка разорвала объявление);
  014  «ОбменДаннымиЗагрузка» вместо «ОбменДанными.Загрузка»;
  015  одиночная кавычка внутри текста запроса;
  016  псевдоним «КАК По» — ключевое слово запроса;
  017  запрос к иерархическому справочнику без «НЕ X.ЭтоГруппа»;
  031  МАКСИМУМ/МИНИМУМ по строковому полю без ВЫРАЗИТЬ (предупреждение);
  032  «ПустаяСсылка» без скобок;
  033  &НаКлиентеНаСервере (предупреждение);
  047  имя процедуры/функции совпадает с глобальным методом платформы;
  057  имя процедуры — ключевое слово BSL (команда формы «Прервать»);
  058  «Число + "строка"» — тип задаёт левый операнд;
  два «;» подряд в пакете запросов.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edt_lib as lib  # noqa: E402


def main():
    hier = ()
    skip = set()
    for i, a in enumerate(sys.argv):
        if a == '--hier' and i + 1 < len(sys.argv):
            hier = tuple(x.strip() for x in sys.argv[i + 1].split(','))
            skip.add(i + 1)
    args = [a for i, a in enumerate(sys.argv) if i > 0 and not a.startswith('--') and i not in skip]
    if not args:
        sys.exit(__doc__)
    is_form = '--common' not in sys.argv
    total = 0
    for path in args:
        text = lib.read_text(path)
        problems = lib.check_bsl(text, is_form_module=is_form, hierarchical_catalogs=hier)
        print('%s: %s' % (path, 'замечаний нет' if not problems else ''))
        for p in problems:
            print('  ' + p)
        total += len([p for p in problems if not p.startswith('предупреждение')])
    sys.exit(1 if total else 0)


if __name__ == '__main__':
    main()
