"""Conservative form-command preflight for the verified 8.5.1 profile.

Unknown platform profiles and commands require a probe, never a guessed rejection.
This checks bindings and exclusions, not BSL execution or effective permissions.
"""
from pathlib import Path
import argparse
import json
import xml.etree.ElementTree as ET

PROFILE = '8.5.1.1529'
SAVED = {'Write', 'WriteAndClose', 'Post', 'PostAndClose', 'UndoPosting'}


def local(tag):
    return tag.rsplit('}', 1)[-1]


def child_text(node, name, default=''):
    return next((c.text or '' for c in node if local(c.tag) == name), default)


def inspect_form(form_path, metadata_path=None, platform_version=PROFILE):
    path = Path(form_path)
    root = ET.parse(path).getroot()
    if local(root.tag) != 'Form':
        raise ValueError('Expected a managed Form XML')
    main_types = []
    for attr in root.iter():
        if local(attr.tag) == 'Attribute' and child_text(attr, 'MainAttribute') == 'true':
            main_types.extend(n.text or '' for n in attr.iter() if local(n.tag) == 'Type' and not list(n))
    main = main_types[0] if len(main_types) == 1 else None
    kind = 'catalog' if main and main.startswith('cfg:CatalogObject.') else (
        'document' if main and main.startswith('cfg:DocumentObject.') else 'other')
    commands = set()
    for node in root.iter():
        tag, text = local(node.tag), (node.text or '').strip()
        if tag == 'CommandName' and text.startswith('Form.StandardCommand.'):
            commands.add(text.rsplit('.', 1)[-1])
        elif tag == 'ExcludedCommand':
            commands.add(text)
    if metadata_path is None:
        # Catalogs/Name/Forms/Form/Ext/Form.xml -> Catalogs/Name.xml.
        if len(path.parents) >= 4:
            candidate = path.parents[3].with_suffix('.xml')
            if candidate.is_file(): metadata_path = candidate
    posting = None
    if metadata_path:
        md = ET.parse(metadata_path).getroot()
        posting = next((n.text for n in md.iter() if local(n.tag) == 'Posting'), None)
    errors, probes = [], []
    if platform_version != PROFILE:
        probes.append({'code': 'unverified_platform', 'platform': platform_version})
    for command in sorted(commands):
        if command not in SAVED:
            # Other platform extensions expose many legitimate standard commands.
            probes.append({'code': 'command_not_profiled', 'command': command})
            continue
        if platform_version != PROFILE:
            continue
        if command == 'WriteAndClose' and kind == 'document':
            errors.append({'code': 'catalog_command_on_document', 'command': command})
        elif command in {'Post', 'PostAndClose', 'UndoPosting'}:
            if kind == 'catalog':
                errors.append({'code': 'document_command_on_catalog', 'command': command})
            elif kind == 'document' and posting == 'Deny':
                errors.append({'code': 'posting_disabled', 'command': command})
            elif kind != 'document' or posting not in {'Allow', 'Deny'}:
                probes.append({'code': 'posting_metadata_required', 'command': command})
        elif kind == 'other':
            probes.append({'code': 'unprofiled_main_attribute', 'command': command})
    return {'schema_version': 1, 'platform_version': platform_version, 'main_type': main,
            'main_kind': kind, 'posting': posting, 'commands': sorted(commands),
            'errors': errors, 'probes': probes,
            'status': 'blocked' if errors else ('needs_probe' if probes else 'ready')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('form', type=Path)
    parser.add_argument('--metadata', type=Path)
    parser.add_argument('--platform', default=PROFILE)
    args = parser.parse_args()
    result = inspect_form(args.form, args.metadata, args.platform)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result['errors'] else (2 if result['probes'] else 0)


if __name__ == '__main__':
    raise SystemExit(main())
