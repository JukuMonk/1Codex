"""Structural checks for Designer dumps. Does not compile 1C modules or XDTO schemas."""
import argparse
from pathlib import Path
import sys
import uuid
import xml.etree.ElementTree as ET


def local(tag):
    return tag.rsplit('}', 1)[-1]


def check(path, require_root=True):
    root = Path(path)
    if not root.is_dir(): return ['Input directory does not exist: ' + str(root)]
    files = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in ('.xml', '.bsl'))
    if not files: return ['No XML or BSL files in input']
    problems, parsed = [], {}
    for file in files:
        if file.suffix.lower() != '.xml': continue
        relative = file.relative_to(root).as_posix()
        try:
            raw = file.read_bytes()
            if b'<!DOCTYPE' in raw.upper(): raise ValueError('DTD is not supported')
            element = ET.fromstring(raw)
            parsed[file] = element
        except (ValueError, ET.ParseError) as exc:
            problems.append(f'{relative}: invalid XML: {exc}')
            continue
        if local(element.tag) == 'Form':
            for scope in ('ChildItems', 'Attributes', 'Commands'):
                section = element.find('{*}' + scope)
                if section is None: continue
                ids = [n.get('id') for n in section.iter() if n.get('id') is not None]
                if len(ids) != len(set(ids)): problems.append(f'{relative}: duplicate IDs in {scope}')
            for node in element.iter():
                if sum(local(n.tag) == 'Visible' for n in node) > 1:
                    problems.append(f'{relative}: duplicate Visible on {node.get("name", local(node.tag))}')
        for node in element.iter():
            if node.get('uuid'):
                try: uuid.UUID(node.get('uuid'))
                except ValueError: problems.append(f'{relative}: malformed UUID')
    roots = [(p, e) for p, e in parsed.items() if p.parent == root and
             local(e.tag) == 'MetaDataObject' and any(local(c.tag) in
             ('Configuration', 'ExternalDataProcessor', 'ExternalReport') for c in e)]
    if require_root and len(roots) != 1: problems.append('Expected exactly one configuration or external processor/report root')
    for file, element in roots:
        obj = next(c for c in element if local(c.tag) in ('Configuration', 'ExternalDataProcessor', 'ExternalReport'))
        children = obj.find('{*}ChildObjects')
        if children is None: continue
        from designer_lib import KIND_DIRS
        for child in children:
            kind, name = local(child.tag), (child.text or '').strip()
            if kind in KIND_DIRS and name:
                target = root / KIND_DIRS[kind] / (name + '.xml')
                if not target.is_file(): problems.append(f'{file.name}: missing {kind}.{name}: {target.relative_to(root)}')
        # Check form metadata and payload for external objects too.
        name = obj.findtext('{*}Properties/{*}Name')
        if local(obj.tag).startswith('External') and name:
            for child in children:
                if local(child.tag) == 'Form' and child.text:
                    for relative in (f'{name}/Forms/{child.text}.xml', f'{name}/Forms/{child.text}/Ext/Form.xml'):
                        if not (root/relative).is_file(): problems.append('Missing external form resource: ' + relative)
    return problems


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('dump')
    p.add_argument('--fragment', action='store_true')
    args = p.parse_args()
    errors = check(args.dump, not args.fragment)
    for error in errors: print(error)
    print(f'Designer structure: {len(errors)} error(s); platform compilation not performed')
    return bool(errors)


if __name__ == '__main__': sys.exit(main())
