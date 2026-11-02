# -*- coding: utf-8 -*-
"""Что добавлено в метаданные изменённых типовых объектов: реквизиты, ТЧ, измерения, формы, макеты, команды,
и какие свойства самого объекта изменены (по выгрузкам src/vendor и src/cf)."""
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = '{http://v8.1c.ru/8.3/MDClasses}'


def children(path):
    """{путь элемента: текст свойств} для дочерних объектов (рекурсивно, с ТЧ)."""
    root = ET.parse(path).getroot()
    obj = list(root)[0]
    out, props = {}, {}
    pr = obj.find(NS + 'Properties')
    if pr is not None:
        for p in pr:
            props[p.tag.replace(NS, '')] = ET.tostring(p, encoding='unicode')

    def walk(node, prefix):
        co = node.find(NS + 'ChildObjects')
        if co is None:
            return
        for ch in co:
            kind = ch.tag.replace(NS, '')
            if len(ch) == 0:            # Form/Template/… ссылкой по имени
                out[prefix + kind + '.' + (ch.text or '')] = ''
                continue
            p = ch.find(NS + 'Properties')
            name = p.find(NS + 'Name').text
            key = prefix + kind + '.' + name
            out[key] = ET.tostring(p, encoding='unicode')
            walk(ch, key + '.')
    walk(obj, '')
    return out, props


def main():
    d = json.load(open(os.path.join(ROOT, 'logs', 'diff.json'), encoding='utf-8'))
    res = {}
    for p in d['changed']:
        parts = p.split('/')
        if not p.endswith('.xml') or len(parts) != 2:
            continue
        a, ap = children(os.path.join(ROOT, 'src', 'vendor', p))
        b, bp = children(os.path.join(ROOT, 'src', 'cf', p))
        r = {'added': sorted(set(b) - set(a)), 'removed': sorted(set(a) - set(b)),
             'changed': sorted(k for k in set(a) & set(b) if a[k] != b[k]),
             'props': sorted(k for k in set(ap) | set(bp) if ap.get(k) != bp.get(k))}
        res[p] = r
        print('==', p)
        for k, v in r.items():
            if v:
                print('  %s: %s' % (k, ', '.join(v)))
    json.dump(res, open(os.path.join(ROOT, 'logs', 'diff_meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
