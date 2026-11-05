"""Content-bound local verification evidence and resumable callback execution.

This module never executes shell commands or publishes an artifact. The adapter
must provide fresh, non-secret database/schema/data attestations from its target.
"""
from dataclasses import dataclass
import fnmatch
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import time


class VerificationError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def relative(value):
    value = str(value).replace('\\', '/')
    path = PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or ':' in value:
        raise VerificationError('Only project-relative paths are accepted')
    return path.as_posix()


def contained(root, value):
    root = Path(root).resolve()
    path = root / relative(value)
    if not path.resolve().is_relative_to(root):
        raise VerificationError('Path leaves the project')
    current = path
    while current != root:
        if current.is_symlink() or (hasattr(current, 'is_junction') and current.is_junction()):
            raise VerificationError('Links are not valid verification inputs')
        current = current.parent
    return path


def matches(path, patterns):
    return any(fnmatch.fnmatchcase(path, p) or path == p.rstrip('/') or
               (p.endswith('/') and path.startswith(p)) for p in patterns)


@dataclass(frozen=True)
class TestSpec:
    id: str
    script: str
    dependencies: tuple | None

    def __post_init__(self):
        if not self.id or not self.id.replace('-', '').replace('_', '').isalnum():
            raise VerificationError('Invalid test ID')
        relative(self.script)
        if self.dependencies is not None:
            for item in self.dependencies: relative(item)


def select_tests(changed, specs, ignored_patterns=()):
    """Unknown ownership/dependencies select all; ignored docs remain explicit."""
    specs = list(specs)
    if len({s.id for s in specs}) != len(specs): raise VerificationError('Duplicate test ID')
    changes = [relative(p) for p in changed]
    changes = [p for p in changes if not matches(p, ignored_patterns)]
    if not changes: return []
    if any(s.dependencies is None for s in specs): return specs
    covered = lambda p: any(p == s.script or matches(p, s.dependencies) for s in specs)
    if any(not covered(p) for p in changes): return specs
    return [s for s in specs if any(p == s.script or matches(p, s.dependencies) for p in changes)]


REQUIRED_CONTEXT = ('source', 'environment', 'database', 'configuration', 'schema', 'data', 'revision', 'dataset')


def valid_context(context):
    if not isinstance(context, dict) or any(not context.get(k) for k in REQUIRED_CONTEXT):
        raise VerificationError('Fresh environment/database/schema/data/revision/dataset attestations are required')
    # Adapter supplies IDs/digests, never connection strings or arbitrary objects.
    if any(not isinstance(v, str) or len(v) > 512 for v in context.values()):
        raise VerificationError('Context values must be short non-secret identifiers')
    return dict(context)


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def input_manifest(project, spec):
    if spec.dependencies is None: raise VerificationError('Unknown dependencies cannot be cached')
    root = Path(project).resolve()
    result = {}
    script = contained(root, spec.script)
    if not script.is_file(): raise VerificationError('Missing test script')
    result[spec.script] = file_hash(script)
    for pattern in spec.dependencies:
        found = set()
        # Path.glob('directory/**') yields directories, not files. Expand them
        # explicitly so the documented subtree dependency is actually cacheable.
        for item in root.glob(pattern):
            contained(root, item.relative_to(root).as_posix())
            if item.is_file(): found.add(item)
            elif item.is_dir(): found.update(p for p in item.rglob('*') if p.is_file())
        if not found: raise VerificationError('Dependency pattern matched no files: ' + pattern)
        for p in found:
            name = p.relative_to(root).as_posix()
            result[name] = file_hash(contained(root, name))
    return result


class SignedStore:
    """Accidental/foreign record edits are rejected using a workspace-local key.

    The key is not protection against an actor controlling the whole workspace.
    Do not copy it to Git or use this cache as an authorization boundary.
    """
    def __init__(self, project, name):
        self.project = Path(project).resolve()
        self.folder = contained(self.project, '.platform/verification')
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = contained(self.project, '.platform/verification/' + name)
        self.key_path = contained(self.project, '.platform/verification/local.key')
        try:
            fd = os.open(self.key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, 'wb') as stream: stream.write(secrets.token_bytes(32))
        self.key = self.key_path.read_bytes()
        if len(self.key) != 32: raise VerificationError('Invalid local evidence key')

    def read(self):
        if not self.path.exists(): return {}
        try:
            envelope = json.loads(self.path.read_text(encoding='utf-8'))
            data = envelope['data']
            signature = hmac.new(self.key, digest(data).encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, envelope['signature']):
                raise VerificationError('Evidence record was modified')
            return data
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise VerificationError('Invalid evidence record') from exc

    def write(self, data):
        envelope = {'data': data, 'signature': hmac.new(self.key, digest(data).encode(), hashlib.sha256).hexdigest()}
        pending = self.path.with_suffix('.pending')
        pending.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding='utf-8')
        pending.replace(self.path)


class VerificationCache:
    def __init__(self, project):
        self.store = SignedStore(project, 'tests.json')
        self.project = self.store.project

    def key(self, spec, context):
        return digest({'spec': {'id': spec.id, 'script': spec.script, 'dependencies': spec.dependencies},
                       'context': valid_context(context), 'inputs': input_manifest(self.project, spec)})

    def record(self, spec, context, evidence, status='succeeded'):
        if status not in ('succeeded', 'failed'): raise VerificationError('Invalid status')
        evidence = [relative(p) for p in evidence]
        if status == 'succeeded' and not evidence: raise VerificationError('Successful test requires evidence')
        hashes = {}
        for p in evidence:
            path = contained(self.project, p)
            if not path.is_file(): raise VerificationError('Missing evidence file')
            hashes[p] = file_hash(path)
        data = self.store.read()
        data[spec.id] = {'key': self.key(spec, context), 'status': status, 'evidence': hashes}
        self.store.write(data)

    def can_reuse(self, spec, context):
        try:
            row = self.store.read().get(spec.id)
            return bool(row and row['status'] == 'succeeded' and row['key'] == self.key(spec, context)
                        and row['evidence'] and all(contained(self.project, p).is_file() and
                        file_hash(contained(self.project, p)) == sha for p, sha in row['evidence'].items()))
        except (VerificationError, KeyError, OSError):
            return False


class ReleaseSession:
    """Resume only an unbroken, verified prefix; publication remains FrozenRun's job.

    Context provider must attest *current* state before every callback and after
    every reused checkpoint. A legitimate state-changing callback declares an
    expected post-context in advance; otherwise any mutation rejects its result.
    Final integrity is mandatory even when every earlier stage is reused.
    """
    def __init__(self, project, release_id, context_provider, *, max_backup_age=3600, clock=time.time):
        if not release_id or not release_id.replace('-', '').replace('_', '').isalnum():
            raise VerificationError('Invalid release ID')
        self.store = SignedStore(project, 'release-' + release_id + '.json')
        self.provider = context_provider
        self.clock = clock
        self.max_backup_age = max_backup_age
        if max_backup_age <= 0: raise VerificationError('Backup freshness window must be positive')
        self.context = valid_context(context_provider())
        self.data = self.store.read()
        self.fresh = not self.data
        self.position = 0
        self.prefix_valid = not self.data or self.data.get('context') == self.context
        self.observed_context = self.context
        self.completed = []

    def _current(self): return valid_context(self.provider())

    def _evidence(self, evidence):
        result = {}
        for name in evidence:
            name = relative(name); path = contained(self.store.project, name)
            if not path.is_file(): raise VerificationError('Missing checkpoint evidence')
            result[name] = file_hash(path)
        if not result: raise VerificationError('Checkpoint requires evidence')
        return result

    def _backup_fresh(self, row):
        now = self.clock()
        return row.get('backup_at') is not None and 0 <= now-row['backup_at'] <= self.max_backup_age

    def run(self, name, callback, *, evidence, backup=False, expected_after=None):
        if name == 'final_integrity': raise VerificationError('Use finish() for mandatory integrity')
        before = self._current()
        if before != self.observed_context:
            raise VerificationError('Context changed between release stages')
        after_expected = valid_context(expected_after) if expected_after is not None else before
        old = self.data.get('stages', [])
        row = old[self.position] if self.position < len(old) else None
        try: existing_evidence = self._evidence(evidence)
        except VerificationError: existing_evidence = None
        can_reuse = bool(self.prefix_valid and row and row['name'] == name and
                         row['status'] == 'succeeded' and self.data.get('context') == before and
                         row.get('evidence') == existing_evidence and existing_evidence and
                         (expected_after is None or row['after'] == after_expected) and
                         (not backup or self._backup_fresh(row)))
        if can_reuse:
            if self._current() != before: raise VerificationError('Context changed while resuming')
            self.completed.append(row); self.position += 1
            return 'reused'
        self.prefix_valid = False
        # Persist in-progress before executing user code. A crash, failed evidence
        # hash, or exception must never leave the former successful row reusable.
        self.store.write({'context': before, 'stages': self.completed + [
            {'name': name, 'status': 'running', 'before': before, 'after': before,
             'evidence': {}, 'backup_at': None}]})
        try:
            result = callback()
        except BaseException:
            self.completed.append({'name': name, 'status': 'failed', 'before': before,
                                   'after': self._current(), 'evidence': {}, 'backup_at': None})
            self.store.write({'context': self._current(), 'stages': self.completed})
            raise
        after = self._current()
        row = {'name': name, 'status': 'succeeded' if result in (None, 0) and after == after_expected else 'failed',
               'before': before, 'after': after, 'evidence': self._evidence(evidence),
               'backup_at': self.clock() if backup else None}
        self.completed.append(row); self.position += 1
        self.observed_context = after
        self.data = {'context': after, 'stages': self.completed}
        self.store.write(self.data)
        if row['status'] != 'succeeded': raise VerificationError('Release callback failed or changed unattested state')
        return 'executed'

    def finish(self, final_integrity):
        before = self._current()
        if not self.completed or self.observed_context != before or any(r['status'] != 'succeeded' for r in self.completed):
            raise VerificationError('Release state is stale')
        if not any(self._backup_fresh(r) for r in self.completed if r.get('backup_at') is not None):
            raise VerificationError('A fresh verified backup is required')
        def verify_evidence():
            if any(self._evidence(row['evidence']) != row['evidence'] for row in self.completed):
                raise VerificationError('Release evidence changed after its checkpoint')
        verify_evidence()
        result = final_integrity()
        if result not in (None, 0) or self._current() != before:
            raise VerificationError('Final integrity failed')
        verify_evidence()
        # Adapter may now call existing FrozenRun.publish(), which independently
        # rechecks the frozen source before/after atomic artifact replacement.
        return {'status': 'verified', 'stages': len(self.completed), 'final_integrity': 'executed'}
