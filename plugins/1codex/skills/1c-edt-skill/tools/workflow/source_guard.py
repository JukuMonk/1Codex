"""Frozen inputs and crash-released project locks; never writes to the live source.

The lock coordinates platform commands, not arbitrary editors. Fingerprints detect
external edits at checkpoints. Snapshots are private copies (never hard links),
verified against manifests before use. Canonical output remains a separate artifact.
"""
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid


class GuardError(RuntimeError):
    pass


class ReadLease:
    """Windows denies opening frozen files for write/delete until all leases close.

    On non-Windows hosts only manifest verification is available. This project
    deploys from Windows; callers can inspect ``os_protected`` in the journal.
    """
    def __init__(self, root, files):
        self.handles = []
        if os.name != 'nt': return
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                           wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        create.restype = wintypes.HANDLE
        self.close_handle = kernel.CloseHandle
        self.close_handle.argtypes = [wintypes.HANDLE]
        self.close_handle.restype = wintypes.BOOL
        try:
            for relative in files:
                # GENERIC_READ, FILE_SHARE_READ only, OPEN_EXISTING.
                handle = create(str(Path(root) / relative), 0x80000000, 1, None, 3, 0x80, None)
                if handle == ctypes.c_void_p(-1).value:
                    raise GuardError('Не удалось защитить frozen-файл от записи: ' + relative)
                self.handles.append(handle)
        except BaseException:
            self.close(); raise

    def close(self):
        for handle in self.handles: self.close_handle(handle)
        self.handles.clear()


def manifest(directory):
    root = Path(directory)
    result = {}
    if not root.is_dir():
        raise GuardError('Нет каталога исходников')
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise GuardError('Ссылки и junction в исходнике запрещены: ' + str(path.relative_to(root)))
        if path.is_file():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def fingerprint(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


@contextlib.contextmanager
def project_lock(project, platform=None):
    """Nonblocking OS byte/flock lock. A crashed process releases it automatically."""
    path = Path(platform or Path(project) / '.platform') / 'platform-project.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise GuardError('Другой процесс выполняет цикл/выпуск/операцию платформы этого проекта') from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def cosmetic_equivalent(left, right):
    """Conservative comparison: line endings/BOM or XML formatting only.

    No default-property removal, changed attributes, reordered children or arbitrary
    BSL whitespace changes are accepted automatically.
    """
    a, b = Path(left).read_bytes(), Path(right).read_bytes()
    if a == b:
        return True
    if Path(left).suffix.lower() == '.xml':
        import xml.etree.ElementTree as ET
        def signature(raw):
            import io
            # Keep prefix bindings too: QName values in 1C XML are text.
            namespaces = []
            for event, value in ET.iterparse(io.BytesIO(raw), events=('start-ns',)):
                namespaces.append(value)
            def tree(node, inherited=False):
                space = node.get('{http://www.w3.org/XML/1998/namespace}space')
                preserve = inherited if space is None else space == 'preserve'
                def layout(value):
                    return None if value is None or (not preserve and not value.strip()) else value
                text = layout(node.text) if len(node) else node.text
                return (node.tag, tuple(sorted(node.attrib.items())), text,
                        tuple((tree(child, preserve), layout(child.tail)) for child in node))
            return (tuple(namespaces), tree(ET.fromstring(raw)))
        try:
            return signature(a) == signature(b)
        except ET.ParseError:
            return False
    try:
        return a.decode('utf-8-sig').replace('\r\n', '\n').rstrip('\n') == b.decode('utf-8-sig').replace('\r\n', '\n').rstrip('\n')
    except UnicodeDecodeError:
        return False


class FrozenRun:
    def __init__(self, project, live, operation, platform=None):
        self.live = Path(live).resolve()
        self.id = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex[:10]
        self.folder = Path(platform or Path(project) / '.platform') / 'runs' / self.id
        self.folder.mkdir(parents=True)
        self.snapshot = self.folder / 'source'
        self.started = time.monotonic()
        self.record = dict(run_id=self.id, operation=operation, started_at=utc_now(), status='preparing', stages=[])
        self.frozen = {}
        self.pending = []
        self.leases = []
        self.stage_stack = []
        self.baseline = manifest(self.live)
        self.record['source_fingerprint'] = fingerprint(self.baseline)
        self.save()
        try:
            shutil.copytree(self.live, self.snapshot)
            self.assert_live()
            if manifest(self.snapshot) != self.baseline:
                raise GuardError('Исходник изменился во время создания snapshot')
            # Normalize only the private copy, never files being edited by other agents.
            for p in self.snapshot.rglob('*.bsl'):
                data = p.read_bytes().decode('utf-8-sig').replace('\r\n', '\n')
                p.write_bytes(b'\xef\xbb\xbf' + data.replace('\n', '\r\n').encode('utf-8'))
            self.seal(self.snapshot)
            self.record['snapshot_fingerprint'] = fingerprint(self.frozen[str(self.snapshot)])
            self.record['os_protected'] = os.name == 'nt'
            (self.folder / 'source-manifest.json').write_text(json.dumps(self.baseline, ensure_ascii=False, indent=2), encoding='utf-8')
            (self.folder / 'snapshot-manifest.json').write_text(json.dumps(self.frozen[str(self.snapshot)], ensure_ascii=False, indent=2), encoding='utf-8')
            self.record['status'] = 'running'
            self.record['preparation_seconds'] = round(time.monotonic()-self.started, 3)
            self.save()
        except BaseException:
            self.finish('failed_preparing')
            raise

    def save(self):
        target = self.folder / 'run.json'
        temp = self.folder / 'run.json.tmp'
        temp.write_text(json.dumps(self.record, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, target)

    def seal(self, path):
        files = manifest(path)
        lease = ReadLease(path, files)
        try:
            if manifest(path) != files:
                raise GuardError('Snapshot изменился во время установки запрета записи')
            self.leases.append(lease)
            self.frozen[str(path)] = files
        except BaseException:
            lease.close(); raise

    def assert_live(self):
        if manifest(self.live) != self.baseline:
            raise GuardError('Исходник изменился после начала операции; принятие выгрузки и выпуск CF запрещены')

    def check(self):
        began = time.monotonic()
        try:
            self.assert_live()
            for folder, expected in self.frozen.items():
                if manifest(folder) != expected:
                    raise GuardError('Frozen snapshot изменён; операция остановлена')
        finally:
            self.record['source_check_count'] = self.record.get('source_check_count', 0) + 1
            self.record['source_check_seconds'] = round(self.record.get('source_check_seconds', 0) + time.monotonic()-began, 3)

    def stage(self, name, function):
        self.check()
        entry = dict(stage_id=uuid.uuid4().hex, parent_stage_id=self.stage_stack[-1] if self.stage_stack else None,
                     depth=len(self.stage_stack), name=name, started_at=utc_now(), status='running')
        self.record['stages'].append(entry); self.save()
        self.stage_stack.append(entry['stage_id'])
        began = time.monotonic()
        try:
            code = function()
            self.check()
            entry.update(status='succeeded' if not code else 'failed', exit_code=code)
            return code
        except BaseException:
            # Do not serialize exception messages or command lines: they can contain passwords.
            entry['status'] = 'failed'
            raise
        finally:
            self.stage_stack.pop()
            entry.update(finished_at=utc_now(), duration_seconds=round(time.monotonic()-began, 3))
            self.save()

    def finish(self, status):
        self.record.update(status=status, finished_at=utc_now(), duration_seconds=round(time.monotonic()-self.started, 3))
        try:
            self.save()
        finally:
            self.close()

    def close(self):
        for lease in self.leases: lease.close()
        self.leases.clear()

    def publish(self):
        """Final commit point; roll back output replacement if a source check fails."""
        self.check()
        committed = []
        try:
            for temporary, destination in self.pending:
                destination = Path(destination)
                previous = self.folder / ('previous-' + uuid.uuid4().hex)
                existed = destination.exists()
                if existed:
                    shutil.copy2(destination, previous)
                self.check()
                os.replace(temporary, destination)
                committed.append((destination, previous if existed else None))
                self.check()
        except BaseException:
            for destination, previous in reversed(committed):
                if previous:
                    os.replace(previous, destination)
                elif destination.exists():
                    destination.unlink()
            raise
        finally:
            self.discard_pending()

    def discard_pending(self):
        for temporary, _ in self.pending:
            if Path(temporary).exists():
                Path(temporary).unlink()
        self.pending.clear()

    def canonical_copy(self, exported, replacements):
        """Materialize canonical files without touching live or the loaded snapshot."""
        self.check()
        target = self.folder / ('canonical-' + uuid.uuid4().hex[:8])
        shutil.copytree(self.snapshot, target)
        for relative in replacements:
            src = Path(exported) / relative
            dst = target / relative
            # Paths come from comparison; still ensure they cannot escape the output tree.
            if not dst.resolve().is_relative_to(target.resolve()):
                raise GuardError('Путь выгрузки выходит за snapshot')
            if not src.is_file():
                raise GuardError('В канонической выгрузке нет файла: ' + relative)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        self.check()
        self.seal(target)
        return str(target)
