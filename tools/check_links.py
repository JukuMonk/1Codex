# -*- coding: utf-8 -*-
"""Самопроверка skill pack: ссылки между файлами и поиск чувствительных данных.

  python tools/check_links.py              # пути в `…` и [](…) внутри *.md ведут к существующим файлам
  python tools/check_links.py --sensitive  # + адреса, учётные данные, домены во всех текстовых файлах

Ссылка считается путём, если начинается с одной из папок набора
(knowledge/, examples/, cases/, reference/, tools/, tests/, index/) или с
CLAUDE.md / README.md. Хвост после «:» (`tools/edt_lib.py:make_picture`),
после «.» у имени функции (`tools/edt_lib.stable_uid`) и шаблоны с «*»/«…»
или номером-заготовкой `NNN`/`MMM` (`cases/NNN-slug/`) разрешаются по правилам ниже.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPS = ('knowledge/', 'examples/', 'cases/', 'reference/', 'tools/', 'tests/', 'index/',
        'CLAUDE.md', 'README.md')
LINK = re.compile(r'`([^`\n]+)`|\]\(([^)\n]+)\)')
SENSITIVE = [
    (re.compile(r'https?://(?!localhost|g5\.1c\.ru|v8\.1c\.ru|www\.w3\.org|<)[^\s`"\'>)]+'), 'адрес'),
    # номера версий вида 1.1.36.1 (ТЛЭиУА) и 8.3.24.x — не адреса
    (re.compile(r'(?<![\w.])(?!1\.1\.36\.|8\.3\.)(?:\d{1,3}\.){3}\d{1,3}\b'), 'ip-адрес'),
    (re.compile(r'/N"[^<"][^"]*"'), 'имя пользователя в командной строке'),
    (re.compile(r'(?i)(password|пароль)\s*[:=]\s*\S+'), 'пароль'),
    (re.compile(r'(?i)(token|api[_-]?key|secret)\s*[:=]\s*\S+'), 'токен'),
    (re.compile(r'\bWIN-[A-Z0-9]{6,}\b'), 'имя хоста'),
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+'), 'e-mail'),
]
TEXT_EXT = ('.md', '.py', '.bsl', '.txt', '.mdo', '.form', '.dcs', '.cmi', '.rights', '.xml')


def files(exts):
    for d, _dirs, names in os.walk(ROOT):
        if os.sep + '.git' in d:
            continue
        for n in names:
            if n.lower().endswith(exts):
                yield os.path.join(d, n)


def resolve(link, base_dir):
    """Существует ли то, на что указывает ссылка. Возвращает None (ок) или причину."""
    link = link.strip()
    # tools/edt_lib.py:make_picture, tools/edt_lib.stable_uid, tools/edt_lib.dcs_schema(groups=…)
    link = link.split('(')[0]
    if link.startswith('tools/') and not link.endswith('.py') and '.' in os.path.basename(link):
        link = link.rsplit('.', 1)[0] + '.py'
    link = link.split(':')[0]
    link = link.split('#')[0]
    if not link:
        return None
    # cases/NNN-slug/ — заготовка номера кейса в правилах набора, а не ссылка на кейс
    link = re.sub(r'(?<![A-Za-z])(?:NNN|MMM)(?![A-Za-z])', '*', link)
    if '…' in link or '*' in link:
        # шаблон: проверяем существование части до первого шаблона
        head = re.split(r'[…*]', link)[0].rstrip('/')
        head = head.rsplit('/', 1)[0] if not os.path.exists(os.path.join(ROOT, head)) else head
        return None if os.path.exists(os.path.join(ROOT, head)) else 'нет ' + head
    cand = [os.path.join(ROOT, link), os.path.join(base_dir, link)]
    for c in cand:
        if os.path.exists(c):
            return None
    # cases/024 — префикс папки кейса
    if link.startswith('cases/'):
        parts = link.split('/')
        if len(parts) >= 2 and os.path.isdir(os.path.join(ROOT, 'cases')):
            for n in os.listdir(os.path.join(ROOT, 'cases')):
                if n.startswith(parts[1]):
                    return None
    return 'нет файла'


def check_links():
    bad = 0
    for path in files(('.md',)):
        text = io.open(path, encoding='utf-8').read()
        base_dir = os.path.dirname(path)
        rel = os.path.relpath(path, ROOT).replace(os.sep, '/')
        for m in LINK.finditer(text):
            link = (m.group(1) or m.group(2) or '').strip()
            if not link.startswith(TOPS):
                continue
            why = resolve(link, base_dir)
            if why:
                bad += 1
                line = text[:m.start()].count('\n') + 1
                print('%s:%d: `%s` — %s' % (rel, line, link, why))
    return bad


def check_sensitive():
    hits = 0
    for path in files(TEXT_EXT):
        rel = os.path.relpath(path, ROOT).replace(os.sep, '/')
        if rel == 'tools/check_links.py':
            continue
        try:
            text = io.open(path, encoding='utf-8').read()
        except UnicodeDecodeError:
            continue
        for rx, kind in SENSITIVE:
            for m in rx.finditer(text):
                hits += 1
                line = text[:m.start()].count('\n') + 1
                print('%s:%d: %s: %s' % (rel, line, kind, m.group(0)[:80]))
    return hits


def main():
    bad = check_links()
    print('ссылки: %s' % ('ok' if not bad else '%d битых' % bad))
    if '--sensitive' in sys.argv:
        hits = check_sensitive()
        print('чувствительные данные: %s' % ('не найдены' if not hits else '%d совпадений' % hits))
        bad += hits
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
