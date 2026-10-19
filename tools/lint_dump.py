# -*- coding: utf-8 -*-
"""Линт XML-выгрузки Конфигуратора без платформы (за секунды, до минутной загрузки; case 092).

Модули `.bsl` — edt_lib.check_bsl (директивы, клиентские методы на сервере, кавычки и ключевые слова в запросах…),
тексты запросов динамических списков форм (`<QueryText>` в Form.xml) — designer_lib.check_query, не ключевые
параметры формы в клиентском коде — designer_lib.check_form_params. Замечания к
унаследованному коду, который компилируется и работает, кладутся в базовый список (без номеров строк — они плывут
при правках) — показываются только НОВЫЕ. Код 1 — есть новые замечания.

  python tools/lint_dump.py <каталог выгрузки> [--baseline <файл>] [--remember]
  --baseline  файл известных замечаний (по умолчанию <каталог выгрузки>/../lint_baseline.txt)
  --remember  записать текущие замечания в базовый список (один раз на унаследованную конфигурацию)

Встраивать первым шагом команды загрузки проекта: ошибка запроса видна за секунду, а не после загрузки в базу.
"""
import argparse
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import designer_lib as dl  # noqa: E402
import edt_lib  # noqa: E402


def problems(dump):
    out = []
    for корень, _, имена in os.walk(dump):
        for и in имена:
            п = os.path.join(корень, и)
            отн = os.path.relpath(п, dump)
            if и.endswith('.bsl'):
                формы = os.sep + 'Forms' + os.sep in п
                out += ['%s — %s' % (отн, з) for з in edt_lib.check_bsl(dl.read(п), is_form_module=формы)
                        if not str(з).startswith('предупреждение')]
                xml = os.path.join(os.path.dirname(корень), 'Form.xml')  # …/Ext/Form/Module.bsl → …/Ext/Form.xml
                if формы and и == 'Module.bsl' and os.path.exists(xml):
                    out += ['%s — %s' % (отн, з) for з in dl.check_form_params(dl.read(п), dl.read(xml))]
            elif и == 'Form.xml':
                for м in re.finditer(r'<QueryText>(.*?)</QueryText>', dl.read(п), re.S):
                    текст = м.group(1).replace('&amp;', '&').replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>')
                    out += ['%s — %s' % (отн, з) for з in dl.check_query(текст)]
    return out


def key(problem):
    return re.sub(r'строка \d+: ', '', problem)


def lint(dump, baseline=None, remember=False):
    baseline = baseline or os.path.join(os.path.dirname(os.path.abspath(dump)), 'lint_baseline.txt')
    все = problems(dump)
    if remember:
        with io.open(baseline, 'w', encoding='utf-8') as f:
            f.write('\n'.join(sorted(set(map(key, все)))) + '\n')
        print('линт: в базовый список записано %d замечаний → %s' % (len(все), baseline))
        return 0
    известные = set()
    if os.path.exists(baseline):
        with io.open(baseline, encoding='utf-8') as f:
            известные = set(f.read().splitlines())
    новые = [п for п in все if key(п) not in известные]
    for п in новые:
        print(п)
    print('линт: новых замечаний %d (известных: %d)' % (len(новые), len(все) - len(новые)))
    return 1 if новые else 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('dump')
    a.add_argument('--baseline')
    a.add_argument('--remember', action='store_true')
    о = a.parse_args()
    sys.exit(lint(о.dump, о.baseline, о.remember))
