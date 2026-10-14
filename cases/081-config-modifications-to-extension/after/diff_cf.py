# -*- coding: utf-8 -*-
"""Сравнение выгрузки ПРОД с выгрузкой поставщика: что добавлено, изменено, удалено (по объектам)."""
import os, sys, io, hashlib, collections, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, 'src', 'vendor')
B = os.path.join(ROOT, 'src', 'cf')
SKIP = {'ConfigDumpInfo.xml'}


def files(root):
    out = {}
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.relpath(os.path.join(d, f), root).replace(os.sep, '/')
            if p in SKIP or p.startswith('Ext/ParentConfigurations'):
                continue
            out[p] = os.path.join(d, f)
    return out


def h(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def obj(p):
    parts = p.split('/')
    if len(parts) == 1 or parts[0] == 'Ext':
        return 'Configuration'
    return parts[0] + '.' + parts[1].replace('.xml', '')


fa, fb = files(A), files(B)
added = sorted(set(fb) - set(fa))
removed = sorted(set(fa) - set(fb))
changed = sorted(p for p in set(fa) & set(fb)
                 if os.path.getsize(fa[p]) != os.path.getsize(fb[p]) or h(fa[p]) != h(fb[p]))
res = collections.OrderedDict()
for kind, lst in (('added', added), ('changed', changed), ('removed', removed)):
    g = collections.defaultdict(list)
    for p in lst:
        g[obj(p)].append(p)
    res[kind] = g
newobjs = [o for o in res['added'] if '/'.join(o.split('.', 1)) + '.xml' in added]
json.dump({'added': added, 'changed': changed, 'removed': removed, 'new_objects': newobjs},
          open(os.path.join(ROOT, 'logs', 'diff.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('файлов: добавлено %d, изменено %d, удалено %d' % (len(added), len(changed), len(removed)))
print('\nНОВЫЕ ОБЪЕКТЫ (%d):' % len(newobjs))
for o in newobjs:
    print('  ', o)
print('\nИЗМЕНЁННЫЕ ТИПОВЫЕ ОБЪЕКТЫ:')
for o in sorted(set(res['changed']) | set(k for k in res['added'] if k not in newobjs)):
    items = [p.split('/', 2)[-1] for p in res['changed'].get(o, [])] + ['+' + p.split('/', 2)[-1] for p in res['added'].get(o, [])]
    print('  ', o, '|', ', '.join(items)[:400])
print('\nУДАЛЁННЫЕ:')
for o, l in res['removed'].items():
    print('  ', o, l[:5])
