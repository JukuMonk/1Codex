"""Requirements, point-tagged timing and evidence reports for a development task.

Only explicit safe fields are stored. Commands, credentials and connection strings
must stay in the project adapter; this module does not execute platform operations.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import html
import json
import math
from pathlib import Path
import re
import uuid

try:
    from . import timing
except ImportError:
    import timing

POINT_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')
PHASES = {'analysis', 'implementation', 'static', 'sandbox', 'load', 'compile',
          'com', 'ui', 'visual', 'repair', 'research', 'release', 'report', 'waiting'}
FAILURES = {'product', 'tool', 'infrastructure'}
LEVELS = {'static', 'compile', 'com', 'ui', 'visual', 'integration'}
SHARED = '__shared__'


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(field + ' must be a nonempty string')
    return value


def _strings(value, field, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(field + ' must be a list')
    for item in value:
        _text(item, field)
    if len(set(value)) != len(value):
        raise ValueError(field + ' contains duplicates')
    return value


def _point(point):
    expected = {'id', 'requirement', 'objects', 'acceptance', 'uncertainties', 'tests', 'limitations'}
    if not isinstance(point, dict) or set(point) - expected:
        raise ValueError('Unknown point fields')
    if not isinstance(point.get('id'), str) or not POINT_ID.fullmatch(point['id']):
        raise ValueError('Invalid point ID')
    return dict(id=point['id'], requirement=_text(point.get('requirement'), 'requirement'),
                objects=_strings(point.get('objects', []), 'objects'),
                acceptance=_strings(point.get('acceptance', []), 'acceptance', True),
                uncertainties=_strings(point.get('uncertainties', []), 'uncertainties'),
                tests=_strings(point.get('tests', []), 'tests'),
                limitations=_strings(point.get('limitations', []), 'limitations'))


def _read(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported task plan schema')
    ids = [p['id'] for p in data['points']]
    for point in data['points']:
        _point(point)
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate point IDs')
    return data


def _inside(root, path):
    root = Path(root).resolve()
    path = Path(path)
    result = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not result.is_relative_to(root):
        raise ValueError('Path leaves project root')
    return result


def _known(data, point_id):
    if point_id == SHARED:
        return None
    for point in data['points']:
        if point['id'] == point_id:
            return point
    raise ValueError('Unknown point ID: ' + point_id)


def create(path, title, points, revision, project_root=None):
    path = Path(path).resolve()
    root = Path(project_root).resolve() if project_root else path.parent
    _inside(root, path)
    normalized = [_point(p) for p in points]
    if not normalized or len({p['id'] for p in normalized}) != len(normalized):
        raise ValueError('Points must be nonempty and IDs unique')
    data = dict(schema_version=1, task_id=uuid.uuid4().hex,
                title=_text(title, 'title'), revision=_text(revision, 'revision'),
                project_root=str(root), created_at=timing.stamp(), status='running',
                points=normalized, journals=[], evidence=[])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
    return path


def set_revision(path, revision):
    _read(path)
    with timing.journal(path) as data:
        if data['status'] != 'running':
            raise ValueError('Task plan is closed')
        data['revision'] = _text(revision, 'revision')


def begin_stage(path, journal, point_id, phase, parent=None, budget_seconds=None):
    """Create a stage in timing.py's journal, adding task/point/phase metadata."""
    _read(path)
    if phase not in PHASES:
        raise ValueError('Unknown phase')
    if budget_seconds is not None and (phase != 'research' or
            isinstance(budget_seconds, bool) or not isinstance(budget_seconds, (int, float)) or
            not math.isfinite(budget_seconds) or budget_seconds <= 0):
        raise ValueError('Positive budget is allowed only for research')
    with timing.journal(path) as data:
        if data['status'] != 'running':
            raise ValueError('Task plan is closed')
        _known(data, point_id)
        journal_path = _inside(data['project_root'], journal)
        if journal_path == Path(path).resolve():
            raise ValueError('Timing journal must differ from task manifest')
        relative = journal_path.relative_to(Path(data['project_root'])).as_posix()
        with timing.journal(journal_path) as record:
            if not isinstance(record.get('stages'), list):
                raise ValueError('Invalid timing journal')
            if record['status'] != 'running':
                raise ValueError('Timing journal is closed')
            if parent:
                previous = next((s for s in record['stages'] if s['stage_id'] == parent), None)
                if not previous or previous['status'] != 'running':
                    raise ValueError('Parent stage must be running')
                if previous.get('task_id') != data['task_id']:
                    raise ValueError('Parent belongs to another task')
            stage_id = uuid.uuid4().hex
            record['stages'].append(dict(stage_id=stage_id, parent_id=parent,
                name=point_id + ':' + phase, started_at=timing.stamp(), status='running',
                task_id=data['task_id'], point_id=point_id, phase=phase,
                budget_seconds=budget_seconds))
        if relative not in data['journals']:
            data['journals'].append(relative)
    return stage_id


def end_stage(path, journal, stage_id, status='ok', failure_kind=None):
    data = _read(path)
    if status not in {'ok', 'failed', 'interrupted'}:
        raise ValueError('Unknown terminal status')
    if failure_kind is not None and failure_kind not in FAILURES:
        raise ValueError('Unknown failure kind')
    if status == 'failed' and failure_kind is None:
        raise ValueError('Failed stage requires product/tool/infrastructure classification')
    if status == 'ok' and failure_kind is not None:
        raise ValueError('Successful stage cannot carry failure kind')
    journal_path = _inside(data['project_root'], journal)
    with timing.journal(journal_path) as record:
        stage = next((s for s in record['stages'] if s['stage_id'] == stage_id), None)
        if not stage or stage.get('task_id') != data['task_id']:
            raise ValueError('Unknown stage for this task')
        if stage['status'] != 'running':
            raise ValueError('Stage is closed')
        if any(s.get('parent_id') == stage_id and s['status'] == 'running' for s in record['stages']):
            raise ValueError('Close child stages first')
        ended = timing.stamp()
        seconds = (datetime.fromisoformat(ended) - datetime.fromisoformat(stage['started_at'])).total_seconds()
        stage.update(ended_at=ended, seconds=max(0, seconds), clock_valid=seconds >= 0,
                     status=status, failure_kind=failure_kind)


def research_checkpoint(path, journal, stage_id, reason=None, now=None):
    """Report a decision checkpoint; does not cancel work or grant approval."""
    data = _read(path)
    journal_path = _inside(data['project_root'], journal)
    with timing.journal(journal_path) as record:
        stage = next((s for s in record['stages'] if s['stage_id'] == stage_id), None)
        if not stage or stage.get('task_id') != data['task_id']:
            raise ValueError('Unknown stage for this task')
        if stage['status'] != 'running' or stage.get('phase') != 'research':
            raise ValueError('Checkpoint requires a running research stage')
        limit = stage.get('budget_seconds')
        if limit is None:
            raise ValueError('Research stage has no explicit budget')
        current = datetime.fromisoformat(now or timing.stamp())
        elapsed = (current - datetime.fromisoformat(stage['started_at'])).total_seconds()
        if elapsed < 0:
            raise ValueError('Clock moved backwards')
        if reason is not None:
            _text(reason, 'reason')
        action = 'within_budget' if elapsed < limit else ('continue_with_reason' if reason else 'needs_probe')
        result = dict(at=current.isoformat(), elapsed_seconds=elapsed,
                      budget_seconds=limit, action=action, reason=reason)
        stage.setdefault('checkpoints', []).append(result)
    return result


def record_evidence(path, point_id, test_id, level, status, artifact,
                    revision=None, limitations=None):
    _read(path)
    if level not in LEVELS or status not in {'passed', 'failed'}:
        raise ValueError('Invalid evidence level or status')
    with timing.journal(path) as data:
        if data['status'] != 'running':
            raise ValueError('Task plan is closed')
        point = _known(data, point_id)
        if not point or test_id not in point['tests']:
            raise ValueError('Test is not assigned to this point')
        artifact_path = _inside(data['project_root'], artifact)
        if artifact_path == Path(path).resolve():
            raise ValueError('Task manifest cannot be its own proof')
        if not artifact_path.is_file():
            raise ValueError('Evidence artifact must be a file')
        row = dict(id=uuid.uuid4().hex, point_id=point_id, test_id=test_id, level=level,
                   status=status, revision=_text(revision or data['revision'], 'revision'),
                   artifact=artifact_path.relative_to(Path(data['project_root'])).as_posix(),
                   sha256=hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                   recorded_at=timing.stamp(), limitations=_strings(limitations or [], 'limitations'))
        data['evidence'].append(row)
    return row['id']


def _union(intervals):
    total = 0.0
    right = float('-inf')
    for start, end in sorted(intervals):
        total += max(0, end - max(start, right))
        right = max(right, end)
    return total


def _time_report(data):
    stages = []
    unfinished = []
    for relative in data['journals']:
        journal = json.loads(_inside(data['project_root'], relative).read_text(encoding='utf-8'))
        for stage in journal['stages']:
            if stage.get('task_id') != data['task_id']:
                continue
            _known(data, stage['point_id'])
            if 'ended_at' not in stage:
                unfinished.append(stage['stage_id'])
                continue
            start, end = (datetime.fromisoformat(stage[k]).timestamp() for k in ('started_at', 'ended_at'))
            if end < start or stage.get('clock_valid') is False:
                raise ValueError('Invalid timing clock')
            stages.append((stage, start, end))
    # Exclusive segments remove every descendant interval from a parent.
    # Their union per point prevents counting overlapping agents twice.
    segments = {}
    for stage, start, end in stages:
        children = sorted((max(start, a), min(end, b)) for child, a, b in stages
                          if child.get('parent_id') == stage['stage_id'] and a < end and b > start)
        cursor = start
        pieces = []
        for a, b in children:
            if a > cursor:
                pieces.append((cursor, a))
            cursor = max(cursor, b)
        if cursor < end:
            pieces.append((cursor, end))
        segments.setdefault(stage['point_id'], []).extend(pieces)
    return dict(covered_seconds=_union([(a, b) for _, a, b in stages]),
                by_point_seconds={key: _union(value) for key, value in segments.items()},
                shared_seconds=_union(segments.get(SHARED, [])),
                unfinished_stages=unfinished,
                failures=[dict(point_id=s['point_id'], phase=s['phase'], kind=s.get('failure_kind'),
                               seconds=b-a) for s, a, b in stages if s['status'] == 'failed'],
                note='Wall time includes waits. Point totals can overlap and must not be summed as task elapsed.')


def report(path):
    data = _read(path)
    points = []
    for point in data['points']:
        latest = {}
        for row in data['evidence']:
            if row['point_id'] == point['id']:
                latest[row['test_id']] = row
        verified = []
        problems = []
        limitations = list(point['limitations'])
        failed = False
        for test in point['tests']:
            row = latest.get(test)
            if row is None:
                problems.append(test + ': missing evidence')
                continue
            artifact = _inside(data['project_root'], row['artifact'])
            if row['revision'] != data['revision']:
                problems.append(test + ': stale revision')
            elif not artifact.is_file():
                problems.append(test + ': missing artifact')
            elif hashlib.sha256(artifact.read_bytes()).hexdigest() != row['sha256']:
                problems.append(test + ': changed artifact')
            elif row['status'] != 'passed':
                failed = True
                problems.append(test + ': failed')
            else:
                verified.append(row)
                limitations.extend(row.get('limitations', []))
        if failed:
            status = 'failed'
        elif not point['tests'] or problems:
            status = 'unverified'
        elif limitations:
            status = 'limited'
        else:
            status = 'verified'
        points.append(dict(**point, status=status, evidence=verified,
                           evidence_problems=problems, effective_limitations=list(dict.fromkeys(limitations))))
    return dict(schema_version=1, task_id=data['task_id'], title=data['title'], revision=data['revision'],
                generated_at=timing.stamp(), points=points, timing=_time_report(data),
                counts={s: sum(p['status'] == s for p in points) for s in ('verified', 'limited', 'unverified', 'failed')})


def render_report(path, output, format='json'):
    data = report(path)
    if format not in {'json', 'html', 'markdown'}:
        raise ValueError('Unknown report format')
    if format == 'json':
        text = json.dumps(data, ensure_ascii=False, indent=2)
    elif format == 'html':
        esc = lambda value: html.escape(str(value), quote=True)
        rows = ''.join('<tr><td>'+esc(p['id'])+'</td><td>'+esc(p['requirement'])+
                       '<br><small>Acceptance: '+esc('; '.join(p['acceptance']))+'</small></td><td>'+esc(p['status'])+
                       '</td><td>'+esc('; '.join(r['test_id']+' ['+r['level']+']: '+r['artifact']+' SHA256 '+r['sha256'] for r in p['evidence']))+
                       '</td><td>'+esc('; '.join(p['effective_limitations']+p['evidence_problems']))+'</td></tr>' for p in data['points'])
        text = '<!doctype html><html lang="en"><meta charset="utf-8"><title>'+esc(data['title'])+'</title><body><h1>'+esc(data['title'])+'</h1><table><thead><tr><th>Point</th><th>Requirement</th><th>Status</th><th>Evidence</th><th>Limitations and missing evidence</th></tr></thead><tbody>'+rows+'</tbody></table><pre>'+esc(json.dumps(data['timing'], ensure_ascii=False, indent=2))+'</pre></body></html>'
    else:
        esc = lambda value: re.sub(r'([\\`*_{}\[\]()#+.!|])', r'\\\1', html.escape(str(value), quote=False).replace('\n', ' '))
        rows = ['# '+esc(data['title']), '', '| Point | Requirement | Status | Evidence | Limitations and missing evidence |', '|---|---|---|---|---|']
        rows += ['| '+' | '.join(esc(x) for x in (p['id'], p['requirement'], p['status'],
                 '; '.join(r['test_id']+' ['+r['level']+']: '+r['artifact'] for r in p['evidence']),
                 '; '.join(p['effective_limitations']+p['evidence_problems'])))+' |' for p in data['points']]
        rows += ['', 'Timing is wall time; overlapping point totals must not be summed.', '', '```json', json.dumps(data['timing'], ensure_ascii=False, indent=2), '```']
        text = '\n'.join(rows)
    data_plan = _read(path)
    output = _inside(data_plan['project_root'], output)
    protected = {Path(path).resolve()}
    protected.update(_inside(data_plan['project_root'], p) for p in data_plan['journals'])
    protected.update(_inside(data_plan['project_root'], row['artifact']) for row in data_plan['evidence'])
    if output in protected:
        raise ValueError('Report cannot overwrite task manifest, journal or evidence')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text+'\n', encoding='utf-8')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    new = sub.add_parser('create')
    new.add_argument('manifest', type=Path)
    new.add_argument('--title', required=True)
    new.add_argument('--points', required=True, type=Path, help='JSON array of requirement cards')
    new.add_argument('--revision', required=True)
    new.add_argument('--project', type=Path)
    begin = sub.add_parser('begin')
    begin.add_argument('manifest', type=Path); begin.add_argument('journal', type=Path)
    begin.add_argument('--point', required=True); begin.add_argument('--phase', required=True, choices=sorted(PHASES))
    begin.add_argument('--parent'); begin.add_argument('--budget-seconds', type=float)
    end = sub.add_parser('end')
    end.add_argument('manifest', type=Path); end.add_argument('journal', type=Path); end.add_argument('stage_id')
    end.add_argument('--status', choices=['ok','failed','interrupted'], default='ok'); end.add_argument('--failure-kind', choices=sorted(FAILURES))
    checkpoint = sub.add_parser('checkpoint')
    checkpoint.add_argument('manifest', type=Path); checkpoint.add_argument('journal', type=Path); checkpoint.add_argument('stage_id')
    checkpoint.add_argument('--reason')
    evidence = sub.add_parser('evidence')
    evidence.add_argument('manifest', type=Path); evidence.add_argument('--point', required=True); evidence.add_argument('--test', required=True)
    evidence.add_argument('--level', choices=sorted(LEVELS), required=True); evidence.add_argument('--status', choices=['passed','failed'], required=True)
    evidence.add_argument('--artifact', type=Path, required=True); evidence.add_argument('--revision'); evidence.add_argument('--limitation', action='append', default=[])
    render = sub.add_parser('report')
    render.add_argument('manifest', type=Path); render.add_argument('--output', type=Path, required=True)
    render.add_argument('--format', choices=['json','html','markdown'], default='json')
    args = parser.parse_args()
    if args.command == 'create':
        print(create(args.manifest, args.title, json.loads(args.points.read_text(encoding='utf-8')), args.revision, args.project))
    elif args.command == 'begin':
        print(begin_stage(args.manifest,args.journal,args.point,args.phase,args.parent,args.budget_seconds))
    elif args.command == 'end':
        end_stage(args.manifest,args.journal,args.stage_id,args.status,args.failure_kind)
    elif args.command == 'checkpoint':
        print(json.dumps(research_checkpoint(args.manifest,args.journal,args.stage_id,args.reason),ensure_ascii=False))
    elif args.command == 'evidence':
        print(record_evidence(args.manifest,args.point,args.test,args.level,args.status,args.artifact,args.revision,args.limitation))
    else:
        print(render_report(args.manifest,args.output,args.format))


if __name__ == '__main__':
    main()
