# -*- coding: utf-8 -*-
"""scaffold — новый объект в проект EDT из примера skill pack.

Копирует папку примера (examples/metadata/<вид>/<Имя>/) в src/<Папка>/<НовоеИмя>/,
переименовывает объект во всех файлах, выдаёт СВЕЖИЕ uuid всем uuid="…"
(включая typeId/valueTypeId) и прописывает объект в Configuration.mdo.
Формы из примера едут вместе с объектом (ссылки Catalog.Имя.Form.X
переименовываются). uuid устойчивые: повторный запуск с тем же именем даёт
те же uuid, а значит база не увидит «новый» объект дважды (case 020).

  python tools/scaffold.py <корень проекта EDT> <вид> <ИмяВПримере> <НовоеИмя> [--synonym "Синоним"]
  вид: catalog | enum | constant | information-register | accumulation-register |
       document | common-module | data-processor | report | role | subsystem |
       mobile (examples/mobile/mobile-form) | html (examples/forms/html-field-form)

После скаффолдинга:
  1. python tools/check_project.py <корень> --prefix <НовоеИмя>
  2. если объект должен быть в интерфейсе — добавить его в состав подсистемы
     (см. examples/metadata/subsystem/) и, если нужно, в роль;
  3. НОВЫЙ объект база принимает только ПОЛНЫМ обновлением конфигурации (case 020).
"""
import io
import os
import re
import shutil
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edt_lib as lib  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIND_OF = {'catalog': 'Catalog', 'enum': 'Enum', 'constant': 'Constant',
           'information-register': 'InformationRegister', 'accumulation-register': 'AccumulationRegister',
           'document': 'Document', 'common-module': 'CommonModule', 'data-processor': 'DataProcessor',
           'report': 'Report', 'role': 'Role', 'subsystem': 'Subsystem',
           # обработки с особыми формами лежат вне examples/metadata
           'mobile': 'DataProcessor', 'html': 'DataProcessor'}
SOURCE_DIR = {'mobile': ('examples', 'mobile', 'mobile-form'),
              'html': ('examples', 'forms', 'html-field-form')}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) < 4:
        sys.exit(__doc__)
    root, kind_key, old, new = args[:4]
    synonym = None
    for i, a in enumerate(sys.argv):
        if a == '--synonym' and i + 1 < len(sys.argv):
            synonym = sys.argv[i + 1]
    kind = KIND_OF[kind_key]
    src = os.path.join(root, 'src')
    source = os.path.join(HERE, *SOURCE_DIR.get(kind_key, ('examples', 'metadata', kind_key)), old)
    if not os.path.isdir(source):
        sys.exit('нет примера %s' % source)
    target = os.path.join(src, lib.FOLDERS[kind], new)
    if os.path.exists(target):
        sys.exit('уже есть %s — скаффолдинг не перезаписывает объекты' % target)

    uuid_map = {}

    def fresh(match):
        old_u = match.group(1)
        if old_u not in uuid_map:
            uuid_map[old_u] = str(uuid.uuid5(uuid.NAMESPACE_URL, 'scaffold/%s/%s/%s' % (kind, new, old_u)))
        return 'uuid="%s"' % uuid_map[old_u]

    for dirpath, _dirs, files in os.walk(source):
        rel = os.path.relpath(dirpath, source)
        out_dir = os.path.join(target, rel) if rel != '.' else target
        os.makedirs(out_dir, exist_ok=True)
        for f in files:
            if f == 'README.md':
                continue
            data = io.open(os.path.join(dirpath, f), 'rb').read()
            name_out = f.replace(old, new)
            if f.endswith(('.mdo', '.form', '.bsl', '.dcs', '.cmi', '.rights')):
                text = data.decode('utf-8')
                text = text.replace(old, new)
                text = re.sub(r'uuid="([0-9a-f-]{36})"', fresh, text)
                text = re.sub(r'(typeId|valueTypeId)="([0-9a-f-]{36})"',
                              lambda m: '%s="%s"' % (m.group(1), fresh_type(m.group(2), uuid_map, kind, new)), text)
                if synonym and f.endswith('.mdo') and rel == '.':
                    text = re.sub(r'(<name>%s</name>\s*<synonym>\s*<key>ru</key>\s*<value>)[^<]*(</value>)' % re.escape(new),
                                  lambda m: m.group(1) + lib.esc(synonym) + m.group(2), text, count=1)
                data = text.encode('utf-8')
            io.open(os.path.join(out_dir, name_out), 'wb').write(data)

    config_path = os.path.join(src, 'Configuration', 'Configuration.mdo')
    config = lib.read_text(config_path)
    if kind != 'Subsystem':
        config, added = lib.register_in_configuration(config, kind, new)
    else:
        config, added = lib.register_in_configuration(config, kind, new)
    lib.write_text(config_path, config)
    print('создан %s.%s из примера %s' % (kind, new, old))
    print('  папка: %s' % target)
    print('  Configuration.mdo: %s' % ('прописан' if added else 'уже был'))
    print('  uuid заменено: %d' % len(uuid_map))
    print('Дальше: python tools/check_project.py "%s" --prefix %s' % (root, new))


def fresh_type(old_u, uuid_map, kind, new):
    if old_u not in uuid_map:
        uuid_map[old_u] = str(uuid.uuid5(uuid.NAMESPACE_URL, 'scaffold/%s/%s/%s' % (kind, new, old_u)))
    return uuid_map[old_u]


if __name__ == '__main__':
    main()
