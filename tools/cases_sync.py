# -*- coding: utf-8 -*-
"""Согласованность кейсов набора при правках из разных проектов (правила текущей редакции — knowledge/codex.md).

  python tools/cases_sync.py проверить                     # папки cases/ ↔ строки index/cases.md ↔ счётчики; дубли номеров
  python tools/cases_sync.py следующий                     # свободный номер: максимум из своих папок, origin/main и указателя + 1
  python tools/cases_sync.py счётчики                      # счётчики кейсов в README/CLAUDE/SKILL/указателе = число папок
  python tools/cases_sync.py перенумеровать 080 081        # просмотр: папка и ссылки на кейс 080 → 081
  python tools/cases_sync.py перенумеровать 080 081 --применить

Конфликт номеров — главный при слиянии: два проекта взяли один «следующий» номер. Уже отправленный в GitHub кейс
номер сохраняет, свой (ещё не отправленный) перенумеровывается. Ссылки ищутся по формам, которые встречаются в
наборе: `cases/080-…`, строка `| 080 |` указателя, «кейс(а|е|у|ом|ы|ах|ов) 080», «Case/case 080», списки после них
(«кейсы 074, 076 и 080») и номера в скобках «(030, 080)». Просмотр показывает каждую замену — проверить глазами.
"""
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(ROOT, 'cases')
INDEX = os.path.join(ROOT, 'index', 'cases.md')
DIR = re.compile(r'^(\d{3})-(.+)$')
ROW = re.compile(r'^\| (\d{3}) \| ([^|]+?) \|', re.M)
# счётчики кейсов: (файл, шаблон с одной группой — число)
COUNTERS = [
    ('CLAUDE.md', r'— (\d+) разобранных ошибок'),
    ('CLAUDE.md', r'`cases/` — (\d+) кейсов'),
    ('README.md', r'cases/NNN-slug/\s+(\d+) кейсов'),
    ('SKILL.md', r'(\d+) разобранных кейсов'),
    ('SKILL.md', r'`cases/` — (\d+) кейсов'),
    ('index/cases.md', r'^# index/cases — (\d+) кейсов'),
]
if os.path.isfile(os.path.join(ROOT, 'knowledge', 'codex.md')):
    # Codex entrypoints intentionally do not duplicate counters in CLAUDE.md.
    COUNTERS = [
        ('README.md', r'(\d+) кейсов'),
        ('SKILL.md', r'Набор содержит (\d+) кейсов'),
        ('index/cases.md', r'^# index/cases — (\d+) кейсов'),
    ]
TEXT = ('.md', '.py', '.txt', '.bsl', '.json')


def read(path):
    with io.open(path, encoding='utf-8', newline='') as f:
        return f.read()


def write(path, text):
    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def local_dirs():
    """[(номер, слаг)] папок cases/ на диске."""
    out = []
    for name in sorted(os.listdir(CASES)):
        m = DIR.match(name)
        if m and os.path.isdir(os.path.join(CASES, name)):
            out.append((m.group(1), m.group(2)))
    return out


def remote_dirs(ref='origin/main'):
    """[(номер, слаг)] папок cases/ в ref (после git fetch); пусто, если ref нет."""
    r = subprocess.run(['git', '-C', ROOT, 'ls-tree', '--name-only', ref, 'cases/'], capture_output=True)
    if r.returncode:
        return []
    out = []
    for line in r.stdout.decode('utf-8', 'replace').splitlines():
        m = DIR.match(line.split('/', 1)[-1])
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def index_rows():
    return [(m.group(1), m.group(2).strip()) for m in ROW.finditer(read(INDEX))]


def check():
    dirs, rows = local_dirs(), index_rows()
    problems = []
    seen = {}
    for num, slug in dirs:
        seen.setdefault(num, []).append(slug)
    for num, slugs in sorted(seen.items()):
        if len(slugs) > 1:
            problems.append('номер %s у нескольких кейсов: %s — перенумеровать свой (перенумеровать %s <следующий>)'
                            % (num, ', '.join(slugs), num))
    by_row = {}
    for num, slug in rows:
        by_row.setdefault(num, []).append(slug)
    for num, slug in dirs:
        if slug not in by_row.get(num, []):
            problems.append('нет строки в index/cases.md: %s-%s' % (num, slug))
    names = {(n, s) for n, s in dirs}
    for num, slug in rows:
        if (num, slug) not in names:
            problems.append('строка index/cases.md без папки: %s | %s' % (num, slug))
    for num, slugs in sorted(by_row.items()):
        if len(slugs) > 1:
            problems.append('в index/cases.md номер %s несколько раз: %s' % (num, ', '.join(slugs)))
    total = len(dirs)
    for name, pattern in COUNTERS:
        text = read(os.path.join(ROOT, name))
        m = re.search(pattern, text, re.M)
        if not m:
            problems.append('%s: счётчик не найден (%s)' % (name, pattern))
        elif int(m.group(1)) != total:
            problems.append('%s: счётчик %s, папок %d — python tools/cases_sync.py счётчики' % (name, m.group(1), total))
    for p in problems:
        print('!', p)
    print('кейсов %d, строк указателя %d; %s' % (total, len(rows), 'расхождений нет' if not problems else
                                                   'расхождений %d' % len(problems)))
    return 1 if problems else 0


def next_number():
    nums = [int(n) for n, _ in local_dirs() + remote_dirs() + index_rows()]
    return '%03d' % (max(nums) + 1 if nums else 1)


def recount():
    total = len(local_dirs())
    for name, pattern in COUNTERS:
        path = os.path.join(ROOT, name)
        text = read(path)
        m = re.search(pattern, text, re.M)
        if m and int(m.group(1)) != total:
            text = text[:m.start(1)] + str(total) + text[m.end(1):]
            write(path, text)
            print('%s: %s → %d' % (name, m.group(1), total))
    print('кейсов', total)


def _list_sub(old, new):
    """Замена номера внутри списка «074, 076 и 080» / «(030, 080)»."""
    return lambda m: m.group(0)[:m.start(2) - m.start(0)] + re.sub(r'\b%s\b' % old, new, m.group(2)) + \
        m.group(0)[m.end(2) - m.start(0):]


def renumber(old, new, apply=False):
    src = [d for d in os.listdir(CASES) if d.startswith(old + '-')]
    if len(src) != 1:
        sys.exit('папка cases/%s-… не найдена или не одна: %s' % (old, src))
    if any(d.startswith(new + '-') for d in os.listdir(CASES)) and new != old:
        sys.exit('номер %s уже занят — возьмите: %s' % (new, next_number()))
    slug = src[0][len(old) + 1:]
    nums = r'(\d{3}(?:\s*(?:,|и|–|-)\s*\d{3})*)'
    rules = [
        (re.compile(r'cases/%s-' % old), 'cases/%s-' % new),
        (re.compile(r'^\| %s \|' % old, re.M), '| %s |' % new),
        (re.compile(r'(?i)\b(case|кейс(?:а|е|у|ом|ы|ах|ов)?)\s+' + nums), None),
        (re.compile(r'^(- [^\n:]+:\s+)' + nums, re.M), None),          # списки по темам в index/cases.md
        (re.compile(r'\(' + nums + r'\)'), None),
    ]
    changes = 0
    for top, _, files in os.walk(ROOT):
        if '.git' in top.split(os.sep):
            continue
        for f in files:
            if not f.endswith(TEXT):
                continue
            path = os.path.join(top, f)
            try:
                text = read(path)
            except UnicodeDecodeError:
                continue
            result = text
            for rx, repl in rules:
                if repl is not None:
                    result = rx.sub(repl, result)
                elif rx.groups == 2:
                    result = rx.sub(_list_sub(old, new), result)
                else:
                    result = rx.sub(lambda m: '(' + re.sub(r'\b%s\b' % old, new, m.group(1)) + ')', result)
            if result != text:
                rel = os.path.relpath(path, ROOT)
                a, b = text.splitlines(), result.splitlines()
                for i, (x, y) in enumerate(zip(a, b)):
                    if x != y:
                        changes += 1
                        print('%s:%d\n  - %s\n  + %s' % (rel, i + 1, x.strip()[:150], y.strip()[:150]))
                if apply:
                    write(path, result)
    print('папка: cases/%s-%s → cases/%s-%s; строк к замене: %d' % (old, slug, new, slug, changes))
    if apply:
        r = subprocess.run(['git', '-C', ROOT, 'mv', os.path.join('cases', old + '-' + slug),
                            os.path.join('cases', new + '-' + slug)], capture_output=True)
        if r.returncode:   # папка ещё не в git — переименовать на диске
            os.rename(os.path.join(CASES, old + '-' + slug), os.path.join(CASES, new + '-' + slug))
        print('применено; дальше: python tools/cases_sync.py проверить')
    else:
        print('просмотр; применить — тот же вызов с --применить')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == 'проверить':
        return check()
    if a[0] == 'следующий':
        print(next_number())
        return 0
    if a[0] == 'счётчики':
        recount()
        return 0
    if a[0] == 'перенумеровать' and len(a) >= 3:
        renumber(a[1], a[2], '--применить' in a)
        return 0
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main())
