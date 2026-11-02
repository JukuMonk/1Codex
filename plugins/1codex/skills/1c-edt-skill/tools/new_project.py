# -*- coding: utf-8 -*-
"""Prepare a 1C project: Codex and Designer XML by default.

  python tools/new_project.py <dump> <tools-dir> --prefix <prefix> [--name <name>]
  Optional connection hints: --v8 <1cv8.exe> --ib <test-infobase-folder>.

Creates AGENTS.md, a configuration map, ignore files and platform.json with
unset runtime paths unless explicitly supplied. Never loads or creates a base,
registers COM, configures Claude hooks or publishes to GitHub by default.
Existing instructions and settings are preserved.

Legacy EDT/Claude setup: --format edt --agent claude.
Legacy hook only: --hook <project-folder> --agent claude.
"""
import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)

KINDS = [
    ('Catalogs', 'Справочники', 'Справочник'),
    ('Documents', 'Документы', 'Документ'),
    ('InformationRegisters', 'Регистры сведений', 'РегистрСведений'),
    ('AccumulationRegisters', 'Регистры накопления', 'РегистрНакопления'),
    ('ChartsOfCharacteristicTypes', 'Планы видов характеристик', 'ПланВидовХарактеристик'),
    ('Enums', 'Перечисления', 'Перечисление'),
    ('Constants', 'Константы', 'Константа'),
    ('DataProcessors', 'Обработки', 'Обработка'),
    ('Reports', 'Отчёты', 'Отчёт'),
    ('CommonModules', 'Общие модули', 'ОбщийМодуль'),
    ('Subsystems', 'Подсистемы', 'Подсистема'),
]
TYPE_RU = {'String': 'Строка', 'Number': 'Число', 'Boolean': 'Булево', 'Date': 'Дата',
           'CatalogRef': 'Справочник', 'DocumentRef': 'Документ', 'EnumRef': 'Перечисление',
           'ChartOfCharacteristicTypesRef': 'ПВХ', 'DefinedType': 'ОпределяемыйТип'}


def read(path):
    return io.open(path, encoding='utf-8', newline='').read()


def synonym(block):
    m = re.search(r'<synonym>\s*<key>ru</key>\s*<value>([^<]*)</value>', block)
    return m.group(1).strip() if m else ''


def types(block):
    out = []
    for t in re.findall(r'<types>([^<]+)</types>', block):
        if '.' in t:
            k, n = t.split('.', 1)
            out.append('%s.%s' % (TYPE_RU.get(k, k), n))
        else:
            out.append(TYPE_RU.get(t, t))
    return '|'.join(out)


def fields(block, tag):
    """Реквизиты/измерения/ресурсы первого уровня блока: (имя, синоним, тип)."""
    res = []
    for m in re.finditer(r'<%s uuid="[^"]+">(.*?)</%s>' % (tag, tag), block, re.S):
        b = m.group(1)
        name = re.search(r'<name>([^<]+)</name>', b)
        if name:
            res.append((name.group(1), synonym(b), types(b)))
    return res


def build_reference(src, out_dir, prefix):
    os.makedirs(out_dir, exist_ok=True)
    md = ['# Метаданные конфигурации', '',
          'Сгенерировано `tools/new_project.py` из проекта EDT. Пересобрать после обновления',
          'конфигурации поставщика. Свои объекты (префикс `%s`) помечены `*`.' % prefix, '']
    rows = []
    total = 0
    for folder, title, kind in KINDS:
        d = os.path.join(src, folder)
        if not os.path.isdir(d):
            continue
        names = sorted(n for n in os.listdir(d) if os.path.isfile(os.path.join(d, n, n + '.mdo')))
        if not names:
            continue
        md += ['## %s (%d)' % (title, len(names)), '']
        for n in names:
            text = read(os.path.join(d, n, n + '.mdo'))
            head = text.split('<attributes', 1)[0].split('<tabularSections', 1)[0]
            md.append('- %s`%s` — %s' % ('*' if prefix and n.startswith(prefix) else '', n, synonym(head)))
            total += 1
            if kind in ('Обработка', 'Отчёт', 'ОбщийМодуль', 'Подсистема', 'Константа'):
                continue
            # шапка: реквизиты, измерения, ресурсы; ТЧ отдельно
            body_wo_ts = re.sub(r'<tabularSections uuid="[^"]+">.*?</tabularSections>', '', text, flags=re.S)
            for tag, section in (('attributes', ''), ('dimensions', 'измерение'), ('resources', 'ресурс'),
                                 ('enumValues', 'значение')):
                for fname, fsyn, ftype in fields(body_wo_ts, tag):
                    rows.append((kind, n, section, fname, fsyn, ftype))
            for ts in re.finditer(r'<tabularSections uuid="[^"]+">(.*?)</tabularSections>', text, re.S):
                tsname = re.search(r'<name>([^<]+)</name>', ts.group(1))
                if not tsname:
                    continue
                rows.append((kind, n, 'ТЧ', tsname.group(1), synonym(ts.group(1)), ''))
                for fname, fsyn, ftype in fields(ts.group(1), 'attributes'):
                    rows.append((kind, n, 'ТЧ.' + tsname.group(1), fname, fsyn, ftype))
        md.append('')
    io.open(os.path.join(out_dir, 'объекты.md'), 'w', encoding='utf-8', newline='').write('\n'.join(md))
    with io.open(os.path.join(out_dir, 'реквизиты.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['Вид', 'Объект', 'Раздел', 'Имя', 'Синоним', 'Тип'])
        w.writerows(rows)
    return total, len(rows)


def write_once(path, text):
    if os.path.exists(path):
        print('  есть   %s' % path)
        return False
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    io.open(path, 'w', encoding='utf-8', newline='').write(text)
    print('  создан %s' % path)
    return True


def claude_settings(project_dir):
    """Хуки Claude Code проекта (.claude/settings.json); существующий файл не трогать — дописать руками."""
    hook = os.path.join(HERE, 'hook_heredoc.py').replace('\\', '/')
    settings = {'hooks': {'PreToolUse': [{'matcher': 'Bash', 'hooks': [
        {'type': 'command', 'command': 'python "%s"' % hook, 'timeout': 10}]}]}}
    if not write_once(os.path.join(project_dir, '.claude', 'settings.json'),
                      json.dumps(settings, ensure_ascii=False, indent=2) + '\n'):
        print('  (хук heredoc — добавить в существующий .claude/settings.json: %s)' % hook)


def legacy_main():
    if '--hook' in sys.argv:
        dirs = [a for a in sys.argv[1:] if not a.startswith('--')]
        if not dirs:
            sys.exit(__doc__)
        claude_settings(os.path.abspath(dirs[0]))
        return
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) < 2:
        sys.exit(__doc__)
    root, tools_dir = os.path.abspath(args[0]), os.path.abspath(args[1])
    src = os.path.join(root, 'src') if os.path.isdir(os.path.join(root, 'src')) else root
    prefix, name = '', os.path.basename(tools_dir)
    for i, a in enumerate(sys.argv):
        if a == '--prefix' and i + 1 < len(sys.argv):
            prefix = sys.argv[i + 1]
        if a == '--name' and i + 1 < len(sys.argv):
            name = sys.argv[i + 1]
    if not prefix:
        sys.exit('ОШИБКА: укажите --prefix — префикс имён своих объектов (например, мвм)')
    config = os.path.join(src, 'Configuration', 'Configuration.mdo')
    if not os.path.exists(config):
        sys.exit('ОШИБКА: %s не похож на проект EDT (нет Configuration.mdo)' % root)
    cfg = read(config)
    cfg_name = re.search(r'<name>([^<]+)</name>', cfg).group(1)
    cfg_ver = re.search(r'<version>([^<]+)</version>', cfg)
    cfg_ver = cfg_ver.group(1) if cfg_ver else '?'
    print('Новый проект «%s»: конфигурация %s %s, префикс %s\n' % (name, cfg_name, cfg_ver, prefix))

    objs, rows = build_reference(src, os.path.join(tools_dir, 'метаданные'), prefix)
    print('  справочник метаданных: объектов %d, полей %d' % (objs, rows))

    tpl = read(os.path.join(PACK, 'bootstrap', 'CLAUDE.md.template'))
    tpl = (tpl.replace('{{ИМЯ}}', name).replace('{{ПРЕФИКС}}', prefix)
              .replace('{{КОНФИГУРАЦИЯ}}', '%s %s' % (cfg_name, cfg_ver))
              .replace('{{ПРОЕКТ_EDT}}', root).replace('{{ИНСТРУМЕНТЫ}}', tools_dir)
              .replace('{{SKILL}}', PACK))
    write_once(os.path.join(tools_dir, 'CLAUDE.md'), tpl)
    write_once(os.path.join(tools_dir, '.gitignore'), read(os.path.join(PACK, 'bootstrap', 'gitignore.tools')))
    write_once(os.path.join(root, '.gitignore'), read(os.path.join(PACK, 'bootstrap', 'gitignore.edt')))
    write_once(os.path.join(tools_dir, 'инструменты', 'отправить_всё.py'),
               read(os.path.join(PACK, 'bootstrap', 'отправить_всё.py.template'))
               .replace('{{ИНСТРУМЕНТЫ}}', tools_dir).replace('{{ПРОЕКТ_EDT}}', root))   # подстановка в r'…'
    claude_settings(tools_dir)

    print('\nПроверка объектов с префиксом %s:' % prefix)
    r = subprocess.run([sys.executable, os.path.join(HERE, 'check_project.py'), root, '--prefix', prefix, '--quiet'],
                       capture_output=True, text=True, encoding='utf-8')
    print('  ' + (r.stdout.strip().splitlines() or ['(пусто)'])[-1])
    print('\nДальше — knowledge/new-project.md: git init, remote, первый объект через scaffold.py.')


def designer_main(root, tools_dir, prefix, name=None, v8=None, ib=None):
    """Prepare Codex instructions for an existing Designer dump, without touching a base."""
    root, tools_dir = os.path.abspath(root), os.path.abspath(tools_dir)
    config = os.path.join(root, 'Configuration.xml')
    if not os.path.isfile(config):
        raise ValueError('нет Configuration.xml: укажите XML-выгрузку Конфигуратора')
    tree = ET.parse(config)
    configuration = tree.getroot().find('{*}Configuration')
    if configuration is None:
        raise ValueError('Configuration.xml не содержит объект Configuration')
    props = configuration.find('{*}Properties')
    cfg_name = props.findtext('{*}Name') if props is not None else None
    if not cfg_name:
        raise ValueError('в Configuration.xml отсутствует имя конфигурации')
    name = name or cfg_name
    version = tree.getroot().get('version', '')
    os.makedirs(tools_dir, exist_ok=True)
    map_path = os.path.join(tools_dir, 'КАРТА.md')
    run = subprocess.run([sys.executable, os.path.join(HERE, 'config_map.py'), root,
                          '--итог', map_path], capture_output=True, text=True,
                         encoding='utf-8', errors='replace',
                         env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    if run.returncode:
        raise ValueError('не удалось построить карту: ' + run.stdout + run.stderr)
    print(run.stdout.strip())
    tpl = read(os.path.join(PACK, 'bootstrap', 'AGENTS.md.template'))
    for marker, value in {'ИМЯ': name, 'КОНФИГУРАЦИЯ': cfg_name, 'ПРЕФИКС': prefix,
                          'ВЫГРУЗКА': root, 'ИНСТРУМЕНТЫ': tools_dir, 'SKILL': PACK}.items():
        tpl = tpl.replace('{{' + marker + '}}', value)
    write_once(os.path.join(tools_dir, 'AGENTS.md'), tpl)
    if root != tools_dir:
        write_once(os.path.join(root, 'AGENTS.md'), tpl)
    ignore = read(os.path.join(PACK, 'bootstrap', 'gitignore.designer'))
    for folder in dict.fromkeys([root, tools_dir]):
        write_once(os.path.join(folder, '.gitignore'), ignore)
    settings = {'format': 'designer', 'agent': 'codex', 'project_name': name,
                'configuration_name': cfg_name, 'metadata_version': version,
                'compatibility_mode': props.findtext('{*}CompatibilityMode'),
                'v8': os.path.abspath(v8) if v8 else None, 'dump': root,
                'work': os.path.join(tools_dir, '.platform'), 'prefix': prefix,
                'test_ib': os.path.abspath(ib) if ib else None,
                'ib': 'File="%s";' % os.path.abspath(ib) if ib else None,
                'configuration_kind': None, 'com': None,
                'test_usr': '', 'ui_port': 48123}
    write_once(os.path.join(tools_dir, 'platform.json'),
               json.dumps(settings, ensure_ascii=False, indent=2) + '\n')
    print('Codex / Конфигуратор: база не изменялась; заполните настройки перед запуском платформы.')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Подготовка проекта 1С: по умолчанию Codex, без EDT.')
    parser.add_argument('root', nargs='?', help='XML-выгрузка Конфигуратора')
    parser.add_argument('tools_dir', nargs='?', help='папка инструментов и карты')
    parser.add_argument('--prefix')
    parser.add_argument('--name')
    parser.add_argument('--v8', help='путь к 1cv8.exe выбранной версии')
    parser.add_argument('--ib', help='отдельная файловая тестовая база')
    parser.add_argument('--format', choices=['designer', 'edt'], default='designer')
    parser.add_argument('--agent', choices=['codex', 'claude'], default='codex')
    parser.add_argument('--hook', action='store_true', help='исторический хук только Claude Code')
    args = parser.parse_args()
    if args.hook:
        if args.agent != 'claude' or not args.root:
            parser.error('--hook предназначен только для явно выбранного --agent claude и папки root')
        claude_settings(os.path.abspath(args.root))
        return 0
    if not args.root or not args.tools_dir or not args.prefix:
        parser.error('нужны root, tools_dir и --prefix')
    if args.format == 'edt':
        if args.agent != 'claude':
            parser.error('исторический режим EDT доступен только с --agent claude; Codex работает без EDT')
        sys.argv = [sys.argv[0], args.root, args.tools_dir, '--prefix', args.prefix]
        if args.name:
            sys.argv += ['--name', args.name]
        legacy_main()
        return 0
    if args.agent != 'codex':
        parser.error('режим designer в этом стартовом наборе предназначен для Codex')
    try:
        designer_main(args.root, args.tools_dir, args.prefix, args.name, args.v8, args.ib)
    except (ValueError, OSError, ET.ParseError) as error:
        parser.exit(1, 'ОШИБКА: %s\n' % error)
    return 0


if __name__ == '__main__':
    sys.exit(main())
