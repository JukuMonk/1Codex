# -*- coding: utf-8 -*-
"""Сверка расширения с ПРОД без платформы.

1. Каждый перехватчик &ИзменениеИКонтроль: тело без #Удаление-блоков и маркеров = метод ПРОД;
   тело без #Вставка-блоков и маркеров = метод поставщика. Расхождения допустимы только в методах из
   METHOD_PATCHES (регистры-спутники) — печатаются отдельно.
2. Каждый новый метод ПРОД есть в модуле расширения дословно.
3. Каждый новый объект/реквизит/макет ПРОД есть в расширении (кроме перенесённых в регистры-спутники).
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsl_methods as bm  # noqa: E402
import build_ext as be  # noqa: E402

ROOT = be.ROOT
EXT = be.OUT


def strip_markers(lines, keep):
    """keep='prod' — убрать #Удаление-блоки; keep='vendor' — убрать #Вставка-блоки."""
    out, skip = [], False
    drop_open, drop_close = ('#Удаление', '#КонецУдаления') if keep == 'prod' else ('#Вставка', '#КонецВставки')
    for l in lines:
        s = l.strip()
        if s.startswith(drop_open):
            skip = True
            continue
        if s.startswith(drop_close):
            skip = False
            continue
        if s.startswith(('#Вставка', '#КонецВставки', '#Удаление', '#КонецУдаления')):
            continue
        if not skip:
            out.append(l)
    return out


def main():
    diff = json.load(open(os.path.join(ROOT, 'logs', 'diff.json'), encoding='utf-8'))
    errors, patched, n_int, n_new = [], [], 0, 0
    for p in diff['changed']:
        if not p.endswith('.bsl'):
            continue
        r = bm.compare(os.path.join(be.VENDOR, p), os.path.join(be.PROD, p))
        if not r['changed'] and not r['added']:
            continue
        ext_path = os.path.join(EXT, p.replace('/', os.sep))
        if not os.path.exists(ext_path):
            errors.append('нет модуля в расширении: ' + p)
            continue
        em, _ = bm.parse(bm.read(ext_path))
        ext_methods = {m.name.lower(): m for m in em}
        by_target = {}
        for m in em:
            for a in m.ann:
                mm = re.match(r'\s*&ИзменениеИКонтроль\("([^"]+)"\)', a)
                if mm:
                    by_target[mm.group(1).lower()] = m
        for a, b in r['changed']:
            n_int += 1
            m = by_target.get(a.name.lower())
            if m is None:
                errors.append('%s: нет перехватчика %s' % (p, a.name))
                continue
            hl = be.header_len(a.lines)
            body = m.lines[be.header_len(m.lines):-1]
            prod_body = [x.rstrip() for x in strip_markers(body, 'prod')]
            vend_body = [x.rstrip() for x in strip_markers(body, 'vendor')]
            ok_v = vend_body == [x.rstrip() for x in a.lines[hl:-1]]
            ok_p = prod_body == [x.rstrip() for x in b.lines[hl:-1]]
            if not ok_v:
                errors.append('%s: %s — тело поставщика не совпадает (контроль не пройдёт)' % (p, a.name))
            if not ok_p:
                (patched if (p, a.name) in be.METHOD_PATCHES else errors).append(
                    '%s: %s — отличается от ПРОД%s' % (p, a.name, ' (правка под регистр-спутник)' if (p, a.name) in be.METHOD_PATCHES else ''))
        for m in r['added']:
            n_new += 1
            x = ext_methods.get(m.name.lower())
            if x is None or [l.rstrip() for l in x.lines] != [l.rstrip() for l in m.lines]:
                errors.append('%s: новый метод %s перенесён не дословно' % (p, m.name))
    print('перехватчиков проверено %d, новых методов %d' % (n_int, n_new))
    for e in patched:
        print('  ожидаемо:', e)
    # объекты
    for o in diff['new_objects']:
        d, name = o.split('.', 1)
        if not os.path.exists(os.path.join(EXT, d, name + '.xml')):
            errors.append('нет нового объекта ' + o)
    for e in errors:
        print('ОШИБКА', e)
    print('ошибок:', len(errors))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
