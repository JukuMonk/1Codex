"""Preflight actual UI DSL names, element types and table-edit preconditions.

Inventory can combine source XML and a captured runtime JSON/tree. Unknown
forms/actions are reported as needs_probe; they are never treated as tested.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET

FIELD_TYPES = {'InputField', 'CheckBoxField', 'LabelField', 'TextDocumentField', 'HTMLDocumentField'}
TABLE_ACTIONS = {'строка', 'текущая', 'текущаястрока', 'выделить', 'открыть', 'завершить'}
PASS_ACTIONS = {'ждать', 'снимок', 'сообщения', 'контекст', 'дамп', 'закрыть', 'закрыть-форму', 'вопрос', 'раздел'}
RUNTIME_TYPES = {'кнопка': 'Button', 'поле': 'InputField', 'таблица': 'Table', 'группа': 'UsualGroup', 'декорация': 'LabelDecoration'}


def local(tag): return tag.rsplit('}', 1)[-1]


def title(node):
    for child in node:
        if local(child.tag) == 'Title':
            return next((n.text or '' for n in child.iter() if local(n.tag) == 'content'), '')
    return ''


def text(node, key): return next((c.text or '' for c in node if local(c.tag) == key), '')


def load_inventory(xml_paths=(), runtime=None):
    forms, sources = {}, {}
    for path in map(Path, xml_paths):
        form = ET.parse(path).getroot()
        if local(form.tag) != 'Form': raise ValueError('Expected managed Form XML: ' + str(path))
        form_id = str(path.resolve())
        elements = {}
        def walk(node, table=None):
            kind, name = local(node.tag), node.get('name')
            if kind == 'Table': table = name
            if name and kind not in {'Attribute', 'Command', 'Parameter', 'Event'}:
                if name in elements: raise ValueError('Duplicate element: ' + name)
                elements[name] = {'name': name, 'kind': kind, 'title': title(node),
                                  'table': table if kind != 'Table' else None,
                                  'read_only': text(node, 'ReadOnly') == 'true', 'source': 'xml'}
            for child in node:
                if local(child.tag) not in {'Attributes', 'Commands', 'Parameters'}: walk(child, table)
        walk(form)
        forms[form_id] = {'id': form_id, 'title': title(form), 'elements': elements}
        sources[form_id] = hashlib.sha256(path.read_bytes()).hexdigest()
    if runtime:
        if isinstance(runtime, (str, Path)):
            raw = Path(runtime).read_text(encoding='utf-8-sig')
            data = json.loads(raw) if raw.lstrip().startswith('{') else parse_runtime_tree(raw)
        else: data = runtime
        for entry in data.get('forms', []):
            form_id = entry.get('id') or entry.get('title')
            if not form_id: raise ValueError('Runtime form needs id or title')
            merged = forms.setdefault(form_id, {'id': form_id, 'title': entry.get('title', ''), 'elements': {}})
            merged['title'] = entry.get('title', merged['title'])
            for element in entry.get('elements', []):
                item = dict(element)
                if not item.get('name') or not item.get('kind'): raise ValueError('Runtime element needs name and kind')
                item['source'] = 'runtime'
                # Text trees do not expose ReadOnly; do not erase an XML fact
                # with an unknown runtime property.
                previous = merged['elements'].get(item['name'], {})
                merged['elements'][item['name']] = dict(previous, **{key:value for key,value in item.items() if value is not None})
    return {'schema_version': 1, 'forms': forms, 'sources': sources}


def parse_runtime_tree(raw, form_id=None):
    """Parse the bounded text tree emitted by the supplied TestManager diagnostic."""
    found = re.search(r'активная форма:\s*(.+)', raw)
    heading = form_id or (found.group(1).strip() if found else 'runtime')
    elements, stack = [], []
    pattern = re.compile(r'^(\s*)Тестируем(?:ая|ое) (кнопка|поле|таблица|группа|декорация) формы (\S+) «(.*)»\s*$')
    for line in raw.splitlines():
        match = pattern.match(line)
        if not match: continue
        indent, kind, name, label = match.groups()
        depth = len(indent.expandtabs(4))
        while stack and stack[-1][0] >= depth: stack.pop()
        table = next((n for _, k, n in reversed(stack) if k == 'Table'), None)
        actual_kind = RUNTIME_TYPES[kind]
        elements.append({'name': name, 'kind': actual_kind, 'title': label, 'table': table,
                         'read_only': None})
        stack.append((depth, actual_kind, name))
    return {'forms': [{'id': heading, 'title': heading, 'elements': elements}]}


def validate_scenario(lines, inventory, strict=True):
    forms = inventory.get('forms', {})
    current = next(iter(forms)) if len(forms) == 1 else None
    editing = {}
    errors, probes = [], []
    def issue(collection, line, code, **details): collection.append(dict(line=line, code=code, **details))
    # Stale XML must never certify a scenario against previous UI names.
    for source, digest in inventory.get('sources', {}).items():
        path = Path(source)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            issue(errors, 0, 'stale_inventory', source=source)
    for number, raw in enumerate(lines, 1):
        raw = raw.strip()
        if not raw or raw.startswith('#'): continue
        args = [part.strip() for part in raw.split('|')]
        action, args = args[0].casefold(), args[1:]
        if action in {'форма', 'окно'}:
            wanted = args[0] if args else ''
            matches = [key for key, form in forms.items() if wanted and (key == wanted or wanted in form.get('title', ''))]
            if len(matches) == 1: current = matches[0]
            else:
                current = None
                issue(probes, number, 'form_not_in_inventory' if not matches else 'ambiguous_form', target=wanted)
            continue
        if action == 'команда': continue
        if action in PASS_ACTIONS: continue
        if current is None:
            issue(probes, number, 'active_form_unknown', action=action)
            continue
        elements = forms[current]['elements']
        def get(name, kinds=None, allow_title=False):
            candidates = [v for k, v in elements.items() if k == name or (allow_title and v.get('title') == name)]
            if kinds: candidates = [v for v in candidates if v['kind'] in kinds]
            if len(candidates) != 1:
                issue(errors if strict else probes, number, 'element_missing' if not candidates else 'ambiguous_element', target=name)
                return None
            return candidates[0]
        def column(table_name, column_name):
            item = get(column_name, FIELD_TYPES)
            if item and item.get('table') != table_name:
                issue(errors, number, 'column_wrong_table', target=column_name, table=table_name)
                return None
            return item
        first = args[0] if args else ''
        if action in {'кнопка-точно', 'кнопка'}:
            get(first, {'Button'}, allow_title=action == 'кнопка')
        elif action in {'поле', 'ссылка', 'значение', 'выбор', 'флажок', 'открыть-поле', 'фокус-поле'}:
            item = get(first, FIELD_TYPES)
            if item and action in {'поле', 'ссылка', 'флажок'}:
                if item.get('read_only'):
                    issue(errors, number, 'read_only_field', target=first)
                elif item.get('table') and editing.get(current) != (item['table'], first):
                    issue(errors, number, 'table_not_editing_column', target=first, table=item['table'])
        elif action in TABLE_ACTIONS:
            get(first, {'Table'})
            if action in {'завершить', 'строка'}: editing.pop(current, None)
        elif action in {'изменить', 'редактировать-выбор', 'ячейка', 'видимыйпорядок'}:
            table = get(first, {'Table'})
            item = column(first, args[1]) if len(args) > 1 and args[1] else None
            if action in {'изменить', 'редактировать-выбор'}:
                if (table and table.get('read_only')) or (item and item.get('read_only')):
                    issue(errors, number, 'read_only_edit', target=first)
                elif table and item: editing[current] = (first, item['name'])
                elif table: issue(probes, number, 'edit_column_required', target=first)
        elif action in {'добавить-строку', 'скопировать-строку'}:
            table = get(first, {'Table'})
            if len(args) < 2: issue(errors, number, 'exact_button_required', target=first)
            else: get(args[1], {'Button'})
            if table and table.get('read_only'): issue(errors, number, 'read_only_edit', target=first)
        elif action == 'сортировать':
            get(first, {'Table'})
            label = args[1] if len(args) > 1 else ''
            matches = [v for v in elements.values() if v.get('table') == first and v.get('title') == label]
            if len(matches) != 1: issue(errors, number, 'column_title_required', target=label, table=first)
        elif action == 'страница': get(first, {'UsualPage', 'Page'})
        elif action in {'надпись', 'заголовок'}: get(first, allow_title=True)
        else: issue(probes, number, 'unsupported_action', action=action)
    return {'schema_version': 1, 'errors': errors, 'probes': probes,
            'status': 'blocked' if errors else ('needs_probe' if probes else 'ready')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scenario', type=Path)
    parser.add_argument('--form', type=Path, action='append', default=[])
    parser.add_argument('--runtime', type=Path)
    args = parser.parse_args()
    result = validate_scenario(args.scenario.read_text(encoding='utf-8-sig').splitlines(), load_inventory(args.form, args.runtime))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result['errors'] else (2 if result['probes'] else 0)


if __name__ == '__main__': raise SystemExit(main())
