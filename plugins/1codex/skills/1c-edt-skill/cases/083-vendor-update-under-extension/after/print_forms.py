# -*- coding: utf-8 -*-
"""Печатные формы доработок через COM (БСП УправлениеПечатью.СформироватьПечатныеФормыДляБыстройПечати).

  python tools/print_forms.py <база>        # по каждой команде печати Деснол: документ-образец, строк результата / ошибка
Команды — добавленные доработкой в ДобавитьКомандыПечати (идентификаторы из diff поставка 3.0.8.1 → ПРОД).
"""
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import com  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RU = {'Documents': 'Документ', 'DataProcessors': 'Обработка'}


def команды():
    d = json.load(open(os.path.join(ROOT, 'logs', 'diff.json'), encoding='utf-8'))
    out = []
    for p in d['changed']:
        if not p.endswith('ManagerModule.bsl'):
            continue
        r = subprocess.run(['git', 'diff', '--no-index', '-U0', 'src/vendor/' + p, 'src/cf/' + p], cwd=ROOT,
                           capture_output=True, text=True, encoding='utf-8')
        for m in re.finditer(r'^\+.*\.Идентификатор\s*=\s*"([^"]+)"', r.stdout, re.M):
            out.append((p.split('/')[0], p.split('/')[1], m.group(1)))
    return out


def main(base):
    cn = com.connect(base)
    итог = {}
    for d, obj, ид in команды():
        if d not in RU:
            continue
        з = cn.NewObject('Запрос')
        з.Текст = 'ВЫБРАТЬ ПЕРВЫЕ 1 Т.Ссылка КАК С ИЗ %s.%s КАК Т ГДЕ Т.Проведен УПОРЯДОЧИТЬ ПО Т.Дата УБЫВ' % (RU[d], obj)
        в = з.Выполнить().Выбрать()
        if not в.Следующий():
            итог[ид] = 'нет документов'
            continue
        м = cn.NewObject('Массив')
        м.Добавить(в.С)
        try:
            р = cn.УправлениеПечатью.СформироватьПечатныеФормыДляБыстройПечати('%s.%s' % (RU[d], obj), ид, м, cn.NewObject('Структура'))
            if р.Отказ:
                итог[ид] = 'ОТКАЗ'
            else:
                тд = р.ТабличныеДокументы
                n = 0
                for i in range(тд.Количество()):
                    x = тд.Получить(i)
                    x = getattr(x, 'Значение', x)
                    n += x.ВысотаТаблицы
                итог[ид] = 'строк %d' % n
        except Exception as e:
            итог[ид] = 'ОШИБКА ' + com.ошибка(e).replace('\n', ' ').replace('{НПЦАП_Доработки ', '{')[:300]
        print('  %-50s %-45s %s' % (obj, ид, итог[ид]))
    return итог


if __name__ == '__main__':
    main(*sys.argv[1:])
