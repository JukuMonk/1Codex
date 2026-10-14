# -*- coding: utf-8 -*-
"""Прогон перехода «ПРОД → поставка 3.0.8.1 + расширение» на КОПИИ демобазы и сверка.

  python tools/test_migration.py [шаги…]     # по умолчанию все: copy export reports_before switch import compare

  copy            base\\1Cv8.1CD → mig_base (базу base не трогаем)
  export          migrate.py выгрузить mig_base → logs/mig_data.json (снимок «до»)
  reports_before  отчёты на mig_base до перехода → logs/reports_before
  switch          LoadCfg поставки + UpdateDBCfg; расширение .cfe + UpdateDBCfg; ext_activate (ИБ без расширения, включить)
  import          migrate.py загрузить mig_base ← logs/mig_data.json
  compare         снимок «после» (режим расширения) == «до»; отчёты после == до; итог в logs/migration_report.txt
"""
import json
import os
import shutil
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v8  # noqa: E402

ROOT = v8.ROOT
TARGET = os.environ.get('NPCAP_TARGET', '3.0.8.1')
CF = {'3.0.8.1': 'vendor_3.0.8.1.cf', '3.0.25.3': os.path.join('updates', '1Cv8.cf')}[TARGET]
CFE = {'3.0.8.1': os.path.join('dist', 'НПЦАП_Доработки.cfe'), '3.0.25.3': os.path.join('dist', '3.0.25.3', 'НПЦАП_Доработки.cfe')}[TARGET]
MIG = 'mig_base' if TARGET == '3.0.8.1' else 'mig_base_new'
IB = os.path.join(ROOT, MIG)
LOGS = os.path.join(ROOT, 'logs')
DATA_BEFORE = os.path.join(LOGS, 'mig_data.json')
DATA_AFTER = os.path.join(LOGS, 'mig_data_after_%s.json' % os.environ.get('NPCAP_TARGET', '3.0.8.1'))
EXT = 'НПЦАП_Доработки'


def шаг(имя):
    print('\n=== %s  (%s)' % (имя, time.strftime('%H:%M:%S')))


def copy():
    шаг('копия base → mig_base')
    if os.path.isdir(IB):
        shutil.rmtree(IB)
    os.makedirs(IB)
    shutil.copy2(os.environ.get('MIG_SRC') or os.path.join(ROOT, 'base', '1Cv8.1CD'), os.path.join(IB, '1Cv8.1CD'))


def export():
    шаг('выгрузка данных доработок (ПРОД)')
    import migrate
    return migrate.выгрузить(MIG, DATA_BEFORE)


def reports(tag):
    шаг('отчёты ' + tag)
    import reports as r
    r.main('base' if tag == 'before' else MIG, os.path.join(LOGS, 'reports_%s_%s' % (TARGET, tag)))  # до = исходная base (те же данные)
    return 0


def switch():
    шаг('замена конфигурации на поставку %s + расширение' % TARGET)
    import migrate
    migrate.подготовить(MIG)
    if v8.run('DESIGNER', r'/LoadCfg "%s"' % os.path.join(ROOT, CF), 'mig_loadcfg.log', ib=IB):
        return 1
    if v8.run('DESIGNER', '/UpdateDBCfg', 'mig_update.log', ib=IB):
        return 1
    if v8.run('DESIGNER', r'/LoadCfg "%s" -Extension "%s"' % (os.path.join(ROOT, CFE), EXT), 'mig_loadcfe.log', ib=IB):
        return 1
    if v8.run('DESIGNER', '/UpdateDBCfg -Extension "%s"' % EXT, 'mig_update_ext.log', ib=IB):
        return 1
    import ext_activate
    if TARGET != '3.0.8.1':
        # прямой скачок 3.0.8.1 → 3.0.25.3: обработчики старых версий ссылаются на переименованные объекты —
        # временное расширение-исправление на время обновления ИБ (tools/update_fix_ext.py)
        import update_fix_ext
        if update_fix_ext.install(MIG):
            return 1
    rc = ext_activate.main(MIG)
    if TARGET != '3.0.8.1':
        update_fix_ext.remove(MIG)
    return rc


def import_():
    шаг('загрузка данных доработок в расширение')
    import migrate
    return migrate.загрузить(MIG, DATA_BEFORE)


def compare():
    шаг('сверка')
    import migrate
    migrate.выгрузить(MIG, DATA_AFTER, 'расширение')
    до = json.load(open(DATA_BEFORE, encoding='utf-8'))
    после = json.load(open(DATA_AFTER, encoding='utf-8'))
    out, ошибок = [], 0
    for раздел in ('свои', 'поля', 'спутники'):
        for ключ in sorted(set(до[раздел]) | set(после[раздел])):
            a, b = до[раздел].get(ключ), после[раздел].get(ключ)
            if раздел == 'поля' and a is not None and b is not None:
                # порядок выборки без сортировки после реструктуризации другой — сравнение по ссылкам
                a = sorted(a, key=lambda x: x['ref'])
                b = sorted(b, key=lambda x: x['ref'])
            n = len(a) if a is not None else 0
            if a == b:
                out.append('ОК       %-9s %-70s %d' % (раздел, ключ, n))
            else:
                ошибок += 1
                out.append('РАЗЛИЧИЕ %-9s %-70s до %s, после %s' % (раздел, ключ, n, len(b) if b is not None else '—'))
    рд, рп = os.path.join(LOGS, 'reports_%s_before' % TARGET), os.path.join(LOGS, 'reports_%s_after' % TARGET)
    for f in sorted(os.listdir(рд)):
        a = open(os.path.join(рд, f), encoding='utf-8').read()
        b = open(os.path.join(рп, f), encoding='utf-8').read() if os.path.exists(os.path.join(рп, f)) else None
        строк = len([l for l in a.splitlines() if l.strip()])
        if a == b:
            out.append('ОК       отчёт     %-70s строк %d%s' % (f[:-4], строк, ' (ошибка в обеих)' if a.startswith('ОШИБКА') else ''))
        else:
            ошибок += 1
            out.append('РАЗЛИЧИЕ отчёт     %-70s' % f[:-4])
    out.append('различий: %d' % ошибок)
    txt = '\n'.join(out)
    print(txt)
    with open(os.path.join(LOGS, 'migration_report.txt'), 'w', encoding='utf-8') as f:
        f.write(txt)
    return 1 if ошибок else 0


STEPS = {'copy': copy, 'export': export, 'reports_before': lambda: reports('before'), 'switch': switch,
         'import': import_, 'reports_after': lambda: reports('after'), 'compare': compare}

if __name__ == '__main__':
    steps = sys.argv[1:] or ['copy', 'export', 'reports_before', 'switch', 'import', 'reports_after', 'compare']
    for s in steps:
        rc = STEPS[s]()
        if rc:
            print('шаг %s: код %s — остановка' % (s, rc))
            sys.exit(rc)
