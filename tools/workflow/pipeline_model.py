"""Map observed timing stages onto the published atlas. No 1C runtime needed."""
import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path


GRAPH_FILE = Path(__file__).resolve().parents[2] / 'docs' / 'atlas' / 'graph-layout.json'
CHAPTERS = {
    'analysis': 'Задача', 'expertise': 'Экспертиза задачи', 'metadata': 'Метаданные', 'knowledge': 'Правила',
    'implementation': 'Исходники', 'platform': 'Платформа', 'data': 'Демо-данные',
    'com': 'COM', 'ui': 'Интерфейс', 'evidence': 'Приёмка', 'release': 'Выпуск',
    'learning': 'Замеры', 'delivery': 'Обновление',
}
RUNNER_NODES = {
    'doctor': 'analysis.doctor', 'structure': 'platform.xml', 'lint': 'platform.lint',
    'backup': 'platform.backup', 'load': 'platform.load', 'update': 'platform.update',
    'modules': 'platform.compile', 'build': 'platform.build_epf', 'dump': 'platform.dump',
    'compare': 'platform.compare', 'com': 'com.hook', 'ui': 'ui.own',
    'export': 'release.artifact', 'publish-local': 'release.handoff',
}
PLAN_PHASES = {
    'analysis': 'analysis', 'implementation': 'implementation', 'static': 'platform',
    'sandbox': 'data.base', 'load': 'platform.load', 'compile': 'platform.compile',
    'com': 'com', 'ui': 'ui', 'visual': 'evidence.ui', 'repair': 'implementation',
    'research': 'knowledge', 'release': 'release', 'report': 'release.report',
}


@lru_cache(maxsize=1)
def atlas():
    graphs = json.loads(GRAPH_FILE.read_text(encoding='utf-8'))
    expert = json.loads(Path(__file__).with_name('expertise_graph.json').read_text(encoding='utf-8'))
    return graphs[:1] + [expert] + graphs[1:]


@lru_cache(maxsize=1)
def node_keys():
    return set(CHAPTERS) | {g['id'] + '.' + n['id'] for g in atlas() for n in g['nodes']}


def bindings(record, node=None, after=None):
    fields = {}
    if node:
        if node not in node_keys():
            raise ValueError(f'Unknown atlas node: {node}')
        fields['node'] = node
    if after:
        if not any(s['stage_id'] == after and s['status'] != 'running' for s in record['stages']):
            raise ValueError('Predecessor must be a finished stage in this journal')
        fields['after'] = after
    return fields


def silence_events(stages, sampled):
    """Mark observed gaps, also counting activity of nested operations for their parents."""
    activity = {s['id']: [] for s in stages}
    parent_ids = {s['id']: s['parent'] for s in stages}
    for s in stages:
        stamps = [s['start'], *(n['at'] for n in s['signals'])]
        if s['end']:
            stamps.append(s['end'])
        parent = s['parent']
        visited = set()
        while parent in activity and parent not in visited:
            visited.add(parent)
            activity[parent].extend(stamps)
            parent = parent_ids[parent]
    quiet = []
    for s in stages:
        ticks = [(s['start'], 'waiting' if s['phase']=='waiting' else 'progress')]
        ticks.extend((n['at'], n['kind']) for n in s['signals'])
        ticks.extend((t,'child') for t in activity[s['id']])
        ticks.sort(key=lambda t:t[0])
        ticks.append((s['end'] or sampled, 'stop'))
        mode = 'progress'
        for (start,kind),(end,_) in zip(ticks,ticks[1:]):
            if kind != 'child':
                mode = kind
            threshold = datetime.fromisoformat(start) + timedelta(seconds=60)
            if mode=='progress' and threshold <= datetime.fromisoformat(end):
                quiet.append(dict(id=s['id'],kind='quiet',at=threshold.isoformat(),
                                  message='60 секунд без записи о ходе этапа'))
        s['last_activity'] = ticks[-2][0]
    return quiet


def snapshot(record, now=None):
    if record.get('status') not in ('running', 'ok', 'failed', 'interrupted') or not record.get('run_id'):
        raise ValueError('Expected a timing journal')
    stages, events, seen, siblings, attempts = [], [], {}, {}, {}
    for entry in record['stages']:
        sid = entry['stage_id']
        parent = seen.get(entry.get('parent_id'), {})
        point = entry.get('point_id') or parent.get('point', '')
        task = entry.get('task_id') or parent.get('task', '')
        node = entry.get('node') or PLAN_PHASES.get(entry.get('phase')) or RUNNER_NODES.get(entry['name'])
        identity = (task, point, node or entry['name'])
        history = attempts.setdefault(identity, [])
        attempt = 1 + max((n for end,n in history if end and end <= entry['started_at']), default=0)
        history.append((entry.get('ended_at'), attempt))
        lane = (task, point, entry.get('parent_id'))
        previous = siblings.get(lane)
        after = entry.get('after')
        link = 'explicit' if after else None
        if not after and previous and previous['end'] and previous['end'] <= entry['started_at']:
            # Only consecutive, non-overlapping siblings. Temporal order is not a dependency.
            after, link = previous['id'], 'sequence'
        notes = entry.get('signals', [])
        stage = dict(id=sid, name=entry['name'], node=node, point=point, task=task,
                     parent=entry.get('parent_id'), after=after, link=link, attempt=attempt,
                     start=entry['started_at'], end=entry.get('ended_at'), status=entry['status'],
                     phase=entry.get('phase'), failure=entry.get('failure_kind'),
                     signals=[{k: n[k] for k in ('at', 'kind', 'message')} for n in notes])
        seen[sid] = siblings[lane] = stage
        stages.append(stage)
        events.append(dict(at=stage['start'], id=sid, kind='begin'))
        events.extend(dict(at=n['at'], id=sid, kind=n['kind'], message=n['message']) for n in stage['signals'])
        if stage['end']:
            events.append(dict(at=stage['end'], id=sid, kind=stage['status']))
    sampled = now or datetime.now(timezone.utc).isoformat()
    events.extend(silence_events(stages, sampled))
    events.sort(key=lambda e: e['at'])
    return dict(run=record['run_id'], title=record['label'], status=record['status'],
                start=record['started_at'], end=record.get('ended_at'), stages=stages,
                events=events, sampled=sampled)
