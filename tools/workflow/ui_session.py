"""Isolated UI run artifacts and crash-safe OS locking; no 1C dependencies."""
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path


class BusyError(RuntimeError):
    pass


class ProjectLock:
    def __init__(self, platform):
        self.path = Path(platform) / 'ui-manager.lock'
        self.stream = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open('a+b')
        if self.path.stat().st_size == 0:
            self.stream.write(b'0'); self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close(); self.stream = None
            raise BusyError('Другой UI-прогон уже выполняется в этом проекте') from None
        return self

    def __exit__(self, *args):
        if self.stream:
            self.stream.close()  # OS releases the byte lock even if the process crashes.
            self.stream = None


def safe_frame_name(name):
    if not isinstance(name, str) or not re.fullmatch(r'[\w -]{1,100}', name, re.UNICODE):
        raise ValueError('Недопустимое имя снимка')
    if name.endswith(' ') or name.upper().split('.')[0] in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
        raise ValueError('Недопустимое имя снимка')
    return name


def atomic_copy(source, target):
    source, target = Path(source), Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


class RunArtifacts:
    def __init__(self, platform, base, port, mode):
        self.platform = Path(platform)
        self.id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:12]
        self.root = self.platform / 'ui-runs' / self.id
        self.root.mkdir(parents=True)
        self.journal = self.root / 'journal.txt'
        self.request = self.root / 'journal.txt.снимок'
        self.manifest = {'run_id': self.id, 'base': base, 'port': str(port), 'mode': mode,
                         'started_at': datetime.now(timezone.utc).isoformat(), 'stages': [],
                         'status': 'running', 'frames': [], 'owned_pids': [], 'journal': str(self.journal)}
        self.save()

    def frame(self, name):
        return self.root / ('ui_' + safe_frame_name(name) + '.png')

    def save(self):
        path = self.root / 'manifest.json'
        temp = self.root / 'manifest.tmp'
        temp.write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, path)

    def publish(self):
        # Caller owns the project lock. Never publish absent/stale frames.
        if self.journal.is_file():
            atomic_copy(self.journal, self.platform / 'логи' / 'ui_журнал.txt')
        for frame in self.manifest['frames']:
            path = self.frame(frame)
            if path.is_file():
                atomic_copy(path, self.platform / 'снимки' / path.name)
        atomic_copy(self.root / 'manifest.json', self.platform / 'ui-last.json')


def scenario_prefix(text, marker, step=False):
    lines = text.splitlines()
    target = marker.strip() if step else 'снимок | ' + safe_frame_name(marker)
    for i, line in enumerate(lines):
        if line.strip() == target:
            return '\n'.join(s for s in lines[:i + (1 if step else 0)]
                             if not s.lstrip().lstrip('?').startswith('снимок |')) + '\n'
    raise ValueError('Указанный шаг или снимок отсутствует в сценарии')


def stop_owned(processes):
    for process in reversed(processes):
        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill(); process.wait(timeout=5)
                except Exception:
                    pass
