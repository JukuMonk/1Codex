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
from collections import Counter
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import designer_lib as dl  # noqa: E402
import bsl_checks as edt_lib  # noqa: E402


def problems(dump):
    from check_designer import check
    structural = check(dump, require_root=False)
    if structural:
        raise ValueError('\n'.join(structural))
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
    try:
        все = problems(dump)
    except (OSError, ValueError) as exc:
        print('линт: некорректный вход: ' + str(exc))
        return 2
    def identity(problem):
        stable = key(problem).replace('\\', '/')
        match = re.search(r'строка (\d+): ', problem)
        context = ''
        if match:
            relative = problem.split(' — ', 1)[0]
            lines = (Path(dump)/relative).read_text(encoding='utf-8-sig').splitlines()
            n = int(match[1]) - 1
            if n < len(lines): context = hashlib.sha256(lines[n].strip().encode('utf-8')).hexdigest()
        return stable, context
    if remember:
        with io.open(baseline, 'w', encoding='utf-8') as f:
            entries = [{'key': k, 'context': c, 'count': count} for (k, c), count in sorted(Counter(map(identity, все)).items())]
            json.dump({'schema_version': 2, 'entries': entries}, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print('линт: в базовый список записано %d замечаний → %s' % (len(все), baseline))
        return 0
    известные = Counter()
    legacy = False
    if os.path.exists(baseline):
        with io.open(baseline, encoding='utf-8') as f:
            raw = f.read()
        if raw.lstrip().startswith('{'):
            try:
                data = json.loads(raw)
                if data['schema_version'] != 2: raise ValueError('Unsupported baseline schema')
                for row in data['entries']:
                    if type(row['count']) is not int or row['count'] < 1: raise ValueError('Invalid baseline count')
                    известные[(row['key'], row['context'])] += row['count']
            except (ValueError, KeyError, TypeError) as exc:
                print('линт: некорректный baseline: ' + str(exc))
                return 2
        else:
            legacy = True
            известные.update((s.replace('\\', '/'), '') for s in raw.splitlines() if s)
    новые = []
    for problem in все:
        k = (key(problem).replace('\\', '/'), '') if legacy else identity(problem)
        if известные[k] > 0: известные[k] -= 1
        else: новые.append(problem)
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
