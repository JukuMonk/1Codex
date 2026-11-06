"""Persistent stage timing for 1C tasks; no command arguments or secrets logged."""
import argparse
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid

try:
    from .resource_lock import base_lease, BaseBusy
except ImportError:
    from resource_lock import base_lease, BaseBusy


def bindings(record, node, after):
    # A standalone legacy timing.py + resource_lock.py still works without atlas assets.
    if not node and not after:
        return {}
    try:
        from .pipeline_model import bindings as atlas_bindings
    except ImportError:
        from pipeline_model import bindings as atlas_bindings
    return atlas_bindings(record, node, after)


def stamp():
    return datetime.now(timezone.utc).isoformat()


def create(project, label, scenario=None, environment=None, dataset=None, revision=None):
    run_id = uuid.uuid4().hex
    path = Path(project).resolve() / '.platform' / 'task-timings' / (run_id + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(schema_version=2, run_id=run_id, label=label, started_at=stamp(),
                scenario=scenario, environment=environment, dataset=dataset, revision=revision,
                status='running', stages=[])
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


@contextmanager
def journal(path):
    path = Path(path).resolve()
    with ExitStack() as locks:
        deadline = time.monotonic() + 5
        while True:
            try:
                locks.enter_context(base_lease(path.parent, path))
                break
            except BaseBusy:
                if time.monotonic() >= deadline: raise
                time.sleep(0.02)
        data = json.loads(path.read_text(encoding='utf-8'))
        yield data
        pending = path.with_suffix('.pending')
        pending.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        # Windows scanners/readers may briefly hold a handle without FILE_SHARE_DELETE.
        # Keep the journal lock while retrying; never re-read or drop this update.
        replace_deadline = time.monotonic() + 2
        while True:
            try:
                pending.replace(path)
                break
            except PermissionError:
                if time.monotonic() >= replace_deadline: raise
                time.sleep(0.025)


def begin(path, name, parent=None, *, node=None, after=None):
    with journal(path) as data:
        if data['status'] != 'running':
            raise ValueError('Task is closed')
        if parent and not any(s['stage_id'] == parent and s['status'] == 'running' for s in data['stages']):
            raise ValueError('Parent stage must be running')
        stage_id = uuid.uuid4().hex
        data['stages'].append(dict(stage_id=stage_id, parent_id=parent, name=name,
                                   started_at=stamp(), status='running', **bindings(data, node, after)))
    return stage_id


SIGNALS = ('progress', 'waiting', 'warning', 'stalled')


def signal(path, stage_id, kind, message):
    if kind not in SIGNALS or not message.strip() or len(message) > 240:
        raise ValueError('Expected a signal kind and a short message (1..240 characters)')
    with journal(path) as data:
        stage = next((s for s in data['stages'] if s['stage_id'] == stage_id), None)
        if not stage or stage['status'] != 'running':
            raise ValueError('Signal requires an active stage')
        stage.setdefault('signals', []).append(dict(at=stamp(), kind=kind, message=message.strip()))


def end(path, stage_id, status='ok'):
    if status not in ('ok', 'failed', 'interrupted'):
        raise ValueError('Invalid terminal status')
    with journal(path) as data:
        stage = next(s for s in data['stages'] if s['stage_id'] == stage_id)
        if stage['status'] != 'running':
            raise ValueError('Stage is closed')
        if any(s['parent_id'] == stage_id and s['status'] == 'running' for s in data['stages']):
            raise ValueError('Close child stages first')
        stage.update(ended_at=stamp(), status=status)
        stage['seconds'] = max(0, (datetime.fromisoformat(stage['ended_at']) -
                                   datetime.fromisoformat(stage['started_at'])).total_seconds())
        stage['clock_valid'] = stage['ended_at'] >= stage['started_at']


def finish(path, status='ok'):
    if status not in ('ok', 'failed', 'interrupted'):
        raise ValueError('Invalid terminal status')
    with journal(path) as data:
        if data['status'] != 'running' or any(s['status'] == 'running' for s in data['stages']):
            raise ValueError('Task is closed or has unfinished stages')
        data.update(status=status, ended_at=stamp())
        data['elapsed_seconds'] = max(0, (datetime.fromisoformat(data['ended_at']) -
                                          datetime.fromisoformat(data['started_at'])).total_seconds())
        data['clock_valid'] = datetime.fromisoformat(data['ended_at']) >= datetime.fromisoformat(data['started_at'])


@contextmanager
def stage(path, name, parent=None, *, node=None, after=None):
    stage_id = begin(path, name, parent, node=node, after=after)
    started = time.perf_counter()
    try:
        yield stage_id
    except BaseException:
        end(path, stage_id, 'failed')
        raise
    else:
        end(path, stage_id)
    finally:
        # Same-process duration is monotonic; durable CLI intervals use UTC wall time.
        with journal(path) as data:
            item = next(s for s in data['stages'] if s['stage_id'] == stage_id)
            item['monotonic_seconds'] = time.perf_counter() - started
            item['clock_valid'] = item.get('clock_valid', True) and abs(item['seconds']-item['monotonic_seconds']) < 2


def summary(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    intervals = sorted((datetime.fromisoformat(s['started_at']).timestamp(),
                        datetime.fromisoformat(s['ended_at']).timestamp())
                       for s in data['stages'] if 'ended_at' in s)
    covered, right = 0.0, float('-inf')
    for left, stop in intervals:
        covered += max(0, stop - max(left, right))
        right = max(right, stop)
    return dict(task=data, covered_seconds=covered,
                unclassified_seconds=max(0, data.get('elapsed_seconds', 0) - covered),
                note='Wall time includes waits; overlapping/nested stages must not be summed.')


def main():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    start = commands.add_parser('start')
    start.add_argument('--project', type=Path, default=Path.cwd())
    start.add_argument('--label', required=True)
    for name in ('scenario', 'environment', 'dataset', 'revision'):
        start.add_argument('--' + name)
    for action in ('begin', 'end', 'finish', 'show', 'signal'):
        command = commands.add_parser(action)
        command.add_argument('journal', type=Path)
        if action == 'begin':
            command.add_argument('name')
            command.add_argument('--parent')
            command.add_argument('--node', help='Atlas chapter or chapter.node')
            command.add_argument('--after', help='Finished predecessor stage ID')
        if action == 'signal':
            command.add_argument('stage_id')
            command.add_argument('kind', choices=SIGNALS)
            command.add_argument('message')
        if action == 'end':
            command.add_argument('stage_id')
        if action in ('end', 'finish'):
            command.add_argument('--status', choices=['ok', 'failed', 'interrupted'], default='ok')
    args = parser.parse_args()
    if args.action == 'start': print(create(args.project, args.label, args.scenario, args.environment, args.dataset, args.revision))
    elif args.action == 'begin': print(begin(args.journal, args.name, args.parent, node=args.node, after=args.after))
    elif args.action == 'signal': signal(args.journal, args.stage_id, args.kind, args.message)
    elif args.action == 'end': end(args.journal, args.stage_id, args.status)
    elif args.action == 'finish': finish(args.journal, args.status)
    else: print(json.dumps(summary(args.journal), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
