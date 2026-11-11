"""Read bounded task materials, save expertise and check per-point readiness."""
import argparse
import json
from pathlib import Path
import sys
import time

try:
    from . import expertise as ex, timing, task_plan
except ImportError:
    import expertise as ex, timing, task_plan


def _session(project):
    return Path(project)/'session.json'


def _begin(project, name, node, parent=None):
    journal = ex.binding(project).get('journal')
    return timing.begin(journal, name, parent, node=node) if journal else None


def _end(project, stage, status='ok'):
    if stage:
        timing.end(ex.binding(project)['journal'], stage, status)


def _read(project, session, name, first=1, last=None):
    lines = ex.material(project, name).splitlines()
    if first < 1 or first > max(1, len(lines)):
        raise ValueError('Invalid first line')
    last = min(last if last is not None else first+79, len(lines))
    if last-first >= 160 or last < first-1:
        raise ValueError('Read at most 160 lines')
    rows = [[i, lines[i-1]] for i in range(first, last+1)]
    seen = session.setdefault('seen_lines', {})
    totals = session.setdefault('read_totals', {'lines':0,'bytes':0,'repeat_lines':0,'repeat_bytes':0})
    for i, text in rows:
        key = ex.digest([name,i,text]);size = len((text+'\n').encode('utf-8'))
        totals['lines'] += 1;totals['bytes'] += size
        if key in seen:
            totals['repeat_lines'] += 1;totals['repeat_bytes'] += size
        seen[key] = True
    session['reads'][name] = sorted(set(session['reads'].get(name, [])) | {r[0] for r in rows})
    return {'path':name, 'rows':rows, 'total':len(lines)}


def start(project):
    """Begin a fresh review; an unfinished previous attempt remains interrupted."""
    with ex.base_lease(project, _session(project)):
        inputs = ex.input_fingerprints(project)
        if _session(project).exists():
            old = ex.load(_session(project))
            if not old['closed']:
                _end(project, old.get('stage'), 'interrupted')
                old['closed'] = True
                ex.save(_session(project), old)
        stage = _begin(project, 'Архитектурно-методологическая экспертиза', 'expertise.review')
        session = {'inputs':inputs, 'reads':{}, 'closed':False,
                   'stage':stage, 'started_at':timing.stamp()}
        context = _begin(project, 'Постановка, решения и индекс исходников', 'expertise.context', stage)
        try:
            result = [_read(project, session, p, 1, 160)
                      for p in ['project.txt','task.json','decisions.json','index.txt']]
            ex.save(_session(project), session)
        except Exception:
            _end(project, context, 'failed');_end(project, stage, 'failed')
            raise
        _end(project, context)
        return result


def read(project, name, first=1, last=None):
    with ex.base_lease(project, _session(project)):
        session = ex.load(_session(project))
        if session['closed']:
            raise ValueError('Review is closed; start a new one')
        result = _read(project, session, name, first, last)
        ex.save(_session(project), session)
        if session['stage']:
            timing.signal(ex.binding(project)['journal'],session['stage'],'progress',
                          ('Прочитано '+name+', с строки '+str(first))[:240])
        return result


def search(project, text, path_contains=''):
    if len(text) < 2:
        raise ValueError('Search requires at least two characters')
    result = []
    with ex.base_lease(project, _session(project)):
        session = ex.load(_session(project))
        if session['closed']:
            raise ValueError('Review is closed; start a new one')
        for p in sorted(ex.source_root(project).rglob('*')):
            if not p.is_file():
                continue
            name = 'source/'+p.relative_to(ex.source_root(project)).as_posix()
            if path_contains not in name:
                continue
            try:
                lines = ex.material(project, name).splitlines()
            except UnicodeError:
                continue
            hits = [i for i, line in enumerate(lines, 1) if text.casefold() in line.casefold()]
            for i in hits[:5]:
                result.append(_read(project, session, name, max(1,i-1), min(len(lines),i+1)))
                if len(result) == 20:
                    break
            if len(result) == 20:
                break
        ex.save(_session(project), session)
        if session['stage']:
            timing.signal(ex.binding(project)['journal'],session['stage'],'progress',
                          'Поиск по исходникам: возвращено фрагментов '+str(len(result)))
    return {'matches':result, 'limit':20, 'may_be_truncated':len(result)==20}


def submit(project, review):
    with ex.base_lease(project, _session(project)):
        session = ex.load(_session(project))
        if session['closed']:
            raise ValueError('Review is closed')
        stage = _begin(project, 'Проверить заключение и сохранить версию', 'expertise.contract', session['stage'])
        try:
            path = ex.record(project, review, session['reads'], session['inputs'])
            states = ex.readiness(project, path)
        except Exception:
            _end(project, stage, 'failed')
            raise
        _end(project, stage)
        if review['questions']:
            qstage = _begin(project, 'Подготовить вопросы владельцу решения', 'expertise.decision', session['stage'])
            if qstage:
                timing.signal(ex.binding(project)['journal'], qstage, 'progress',
                              '; '.join(q['question'] for q in review['questions'])[:240])
            _end(project, qstage)
        handoff = _begin(project, 'Готовые пункты и открытые решения', 'expertise.handoff', session['stage'])
        if handoff:
            timing.signal(ex.binding(project)['journal'], handoff, 'progress',
                          ', '.join(k+': '+v for k,v in states.items())[:240])
        _end(project, handoff);_end(project, session['stage'])
        session['closed'] = True
        session['ended_at'] = timing.stamp()
        session['review'] = str(path)
        ex.save(_session(project), session)
        return {'review':str(path), 'states':states, 'questions':review['questions']}


def dispatch(args):
    p = args.workspace.resolve()
    if args.action == 'init':
        ex.initialize(p, args.source, args.profile.read_text(encoding='utf-8-sig'),
                      ex.load(args.task) if args.task else None,
                      ex.load(args.decisions) if args.decisions else None,
                      args.task_plan, args.journal)
        if args.task_plan:
            task_plan.attach_expertise(args.task_plan, p)
        return {'workspace':str(p)}
    if args.action == 'schema':
        return ex.SCHEMA
    if args.action == 'start':
        return start(p)
    if args.action == 'read':
        return read(p, args.path, args.first, args.last)
    if args.action == 'search':
        return search(p, args.text, args.path_contains)
    if args.action == 'submit':
        return submit(p, ex.load(args.review))
    if args.action == 'check':
        states = ex.readiness(p, ex.latest(p))
        if args.point and states.get(args.point) != 'ready':
            raise ValueError(args.point+': '+states.get(args.point,'unreviewed'))
        return states
    if args.action == 'show':
        path = ex.latest(p)
        return {'states':ex.readiness(p,path), 'review':ex.load(path)['payload']['review']}
    raise ValueError('Unknown action')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ['init','start','read','search','submit','check','show','schema']:
        p = sub.add_parser(name)
        p.add_argument('workspace', type=Path)
        if name == 'init':
            p.add_argument('--source', required=True, type=Path)
            p.add_argument('--profile', required=True, type=Path)
            choice = p.add_mutually_exclusive_group(required=True)
            choice.add_argument('--task', type=Path)
            choice.add_argument('--task-plan', type=Path)
            p.add_argument('--decisions', type=Path)
            p.add_argument('--journal', type=Path)
        elif name == 'read':
            p.add_argument('path');p.add_argument('--first',type=int,default=1);p.add_argument('--last',type=int)
        elif name == 'search':
            p.add_argument('text');p.add_argument('--path-contains',default='')
        elif name == 'submit':
            p.add_argument('--review',type=Path,required=True)
        elif name == 'check':
            p.add_argument('--point')
    args = parser.parse_args();started = time.perf_counter();error = None
    try:
        result = dispatch(args)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        error = str(exc);result = {'error':error}
    encoded = json.dumps(result, ensure_ascii=False)
    if args.workspace.is_dir():
        with ex.base_lease(args.workspace, args.workspace/'calls.jsonl'):
            with (args.workspace/'calls.jsonl').open('a',encoding='utf-8') as f:
                f.write(json.dumps({'at':timing.stamp(),'operation':args.action,
                    'seconds':time.perf_counter()-started,'response_bytes':len(encoded.encode()),
                    'error':error},ensure_ascii=False)+'\n')
    print(encoded)
    return 1 if error else 0


if __name__ == '__main__':
    sys.exit(main())
