"""Produce a Git-ready marketplace tree from the single source skill."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--version', required=True)
args = parser.parse_args()
target = args.output.resolve()
if target.exists() and any(target.iterdir()):
    parser.error('Publication directory must be empty')
target.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='1codex-release-') as temp:
    subprocess.run([sys.executable, str(ROOT/'packaging/build_plugin.py'),
                    '--output', temp, '--version', args.version], check=True)
    with zipfile.ZipFile(Path(temp)/f'1Codex-local-{args.version}.zip') as archive:
        archive.extractall(target)
    (target/'validation.json').write_bytes((Path(temp)/'validation.json').read_bytes())
for name in ('Install-1Codex.ps1', 'Update-1Codex.ps1'):
    (target/name).write_bytes((ROOT/'distribution'/name).read_bytes())
(target/'README.md').write_bytes((ROOT/'docs/INSTALL.md').read_bytes())
(target/'OWNER.md').write_bytes((ROOT/'docs/UPDATES.md').read_bytes())
print(json.dumps({'output': str(target), 'version': args.version}))
