"""Build and verify portable and local-marketplace 1Codex packages."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'packaging'


def json_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(args, cwd):
    result = subprocess.run(args, cwd=cwd, capture_output=True, encoding='utf-8',
                            errors='strict', env={**os.environ, 'PYTHONUTF8': '1'})
    if result.returncode:
        raise RuntimeError(f'{args}:\n{result.stdout}\n{result.stderr}')
    return result.stdout.strip()


def zip_tree(root, target):
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                entry = zipfile.ZipInfo(path.relative_to(root).as_posix(), (2026, 11, 2, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, path.read_bytes())


def extract_checked(archive, destination):
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        assert len(names) == len(set(names)), 'Duplicate archive entries'
        assert source.testzip() is None, 'ZIP CRC failure'
        for name in names:
            path = PurePosixPath(name)
            assert not path.is_absolute() and '..' not in path.parts and '\\' not in name
            assert not {'.git', '__pycache__'}.intersection(path.parts)
            assert path.suffix not in {'.pyc', '.1CD', '.dt'}, name
        source.extractall(destination)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--version', help='Override package version for a CI release')
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error('Output must be outside the skill repository')
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((TEMPLATES / 'plugin.json').read_text(encoding='utf-8'))
    if args.version:
        manifest['version'] = args.version
    case_count = sum(1 for path in (ROOT / 'cases').iterdir() if path.is_dir() and re.match(r'^\d{3}-', path.name))
    manifest['description'] = re.sub(r'\d+ кейс', f'{case_count} кейс', manifest['description'])
    version = manifest['version']
    assert re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', manifest['name'])
    assert re.fullmatch(r'\d+\.\d+\.\d+', version)
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    resource_dirs = {'bootstrap', 'cases', 'examples', 'index', 'knowledge', 'reference', 'tests', 'tools'}
    tracked = [name for name in tracked if name and
               (PurePosixPath(name).parts[0] in resource_dirs or
                name in {'SKILL.md', 'AGENTS.md', 'CLAUDE.md', 'README.md'})]
    report = {'plugin': manifest['name'], 'version': version,
              'source_commit': run(['git', 'rev-parse', 'HEAD'], ROOT),
              'checks': {}, 'host_installation_tested': False,
              'note': 'Archive and bundled-tool checks only; target ChatGPT installation still requires acceptance tests.'}
    with tempfile.TemporaryDirectory(prefix='1codex-package-') as temp:
        stage = Path(temp)
        kit = stage / 'local'
        plugin = kit / 'plugins' / manifest['name']
        skill = plugin / 'skills' / '1c-edt-skill'
        for name in tracked:
            src = ROOT / name
            if not src.is_file() or src.is_symlink():
                raise RuntimeError(f'Unsupported tracked file: {name}')
            dst = skill / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
        entry = skill / 'SKILL.md'
        body = entry.read_text(encoding='utf-8-sig')
        marker = '# Разработка 1С в Codex без EDT'
        assert marker in body
        body = body.replace(marker, '# Разработка 1С в ChatGPT и Codex без EDT\n\n'
            'Сначала прочитать [правила среды ChatGPT](knowledge/chatgpt.md). '
            'Они уточняют доступность инструментов в текущем чате; затем применять '
            'рабочий цикл и материалы ниже.', 1)
        entry.write_text(body, encoding='utf-8', newline='\n')
        readme = skill / 'README.md'
        readme.write_text(f'# Навык 1Codex\n\nНабор содержит {case_count} кейсов.\n\nИнструкция установки — [README пакета](../../README.md).\n'
                          'Начало работы — [SKILL.md](SKILL.md).\n', encoding='utf-8', newline='\n')
        (skill / 'knowledge' / 'chatgpt.md').write_bytes((TEMPLATES / 'chatgpt.md').read_bytes())
        setup = plugin / 'skills' / 'setup' / 'SKILL.md'
        setup.parent.mkdir(parents=True)
        setup.write_bytes((TEMPLATES / 'setup' / 'SKILL.md').read_bytes())
        json_write(plugin / 'plugin.json', manifest)
        extension = manifest['extensions']['com.openai']
        compat = {key: value for key, value in manifest.items() if key not in {'$schema', 'extensions'}}
        compat.update({'skills': './skills/', 'interface': extension['interface'],
                       'extensions': {'com.openai': {'onboardingSkill': extension['onboardingSkill']}}})
        json_write(plugin / '.codex-plugin' / 'plugin.json', compat)
        for target in (plugin / 'README.md', kit / 'README.md'):
            target.write_bytes((TEMPLATES / 'README.md').read_bytes())
        marketplace = {'name': '1codex', 'interface': {'displayName': '1Codex'},
                       'plugins': [{'name': manifest['name'],
                           'source': {'source': 'local', 'path': './plugins/1codex'},
                           'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'},
                           'category': 'Productivity'}]}
        json_write(kit / '.agents' / 'plugins' / 'marketplace.json', marketplace)
        config = kit / '.codex' / 'config.toml'
        config.parent.mkdir(parents=True)
        config.write_text('[plugins."1codex@1codex"]\nenabled = true\n', encoding='utf-8')
        portable_zip = output / f'1Codex-{version}.zip'
        local_zip = output / f'1Codex-local-{version}.zip'
        zip_tree(plugin, portable_zip)
        zip_tree(kit, local_zip)
        restored = stage / 'restored'
        extract_checked(portable_zip, restored)
        restored_kit = stage / 'restored-kit'
        extract_checked(local_zip, restored_kit)
        report['checks']['zip_integrity_and_safe_paths'] = 'PASS'
        assert json.loads((restored / 'plugin.json').read_text(encoding='utf-8')) == manifest
        assert (restored / extension['onboardingSkill']).is_file()
        assert len(list((restored / 'skills').glob('*/SKILL.md'))) == 2
        for skill_entry in (restored / 'skills').glob('*/SKILL.md'):
            text = skill_entry.read_text(encoding='utf-8')
            header = text.split('---', 2)[1]
            assert re.search(r'^name: [a-z0-9-]+$', header, re.M)
            assert re.search(r'^description: .+', header, re.M)
            assert skill_entry.parent.name == re.search(r'^name: (.+)$', header, re.M)[1]
        report['checks']['skill_frontmatter'] = 'PASS'
        for name in tracked:
            if name not in {'SKILL.md', 'README.md'}:
                assert (restored / 'skills' / '1c-edt-skill' / name).read_bytes() == (ROOT / name).read_bytes(), name
        report['checks']['source_resources_preserved'] = len(tracked) - 2
        report['checks']['adapted_entrypoints'] = ['SKILL.md', 'README.md']
        for file in restored.rglob('*.py'):
            compile(file.read_bytes(), str(file), 'exec')
        report['checks']['python_syntax'] = 'PASS'
        import tomllib
        enabled = tomllib.loads((restored_kit / '.codex' / 'config.toml').read_text(encoding='utf-8'))
        assert enabled['plugins']['1codex@1codex']['enabled'] is True
        market = json.loads((restored_kit / '.agents/plugins/marketplace.json').read_text(encoding='utf-8'))
        path = restored_kit / market['plugins'][0]['source']['path']
        assert (path / 'plugin.json').read_bytes() == (restored / 'plugin.json').read_bytes()
        report['checks']['marketplace_resolution_and_enable_config'] = 'PASS'
        installed_skill = restored / 'skills' / '1c-edt-skill'
        for label, cmd in (
            ('links', ['tools/check_links.py']),
            ('cases', ['tools/cases_sync.py', 'проверить']),
            ('sandbox', ['tools/check_project.py', 'tests/sandbox'])):
            report['checks'][label] = run([sys.executable, *cmd], installed_skill)
        report['archives'] = {}
        for archive in (portable_zip, local_zip):
            report['archives'][archive.name] = {'bytes': archive.stat().st_size,
                'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
    json_write(output / 'validation.json', report)
    (output / 'Инструкция.md').write_bytes((TEMPLATES / 'README.md').read_bytes())
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
