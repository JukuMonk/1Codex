"""Compare measured runs with identical scenario/environment/data; retain failures and gaps."""
import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import statistics
import sys
try:
    from . import timing
except ImportError:
    import timing


def union(intervals):
    total, right = 0.0, float('-inf')
    for a,b in sorted(intervals):
        if b < a: raise ValueError('Clock moved backwards')
        total += max(0,b-max(a,right));right=max(right,b)
    return total


def exclusive_stages(task):
    """Subtract child interval union, never sum nested durations as task elapsed."""
    rows=[]
    for s in task['stages']:
        if 'ended_at' not in s: continue
        a,b=(datetime.fromisoformat(s[k]).timestamp() for k in ('started_at','ended_at'))
        children=[]
        for c in task['stages']:
            if c.get('parent_id')==s.get('stage_id') and 'ended_at' in c:
                ca,cb=(datetime.fromisoformat(c[k]).timestamp() for k in ('started_at','ended_at'))
                children.append((max(a,ca),min(b,cb)))
        rows.append({'name':s['name'],'status':s['status'],'inclusive_seconds':max(0,b-a),
                     'exclusive_seconds':max(0,b-a-union(children)), 'parent_id':s.get('parent_id')})
    return rows


def analyze(paths):
    groups=defaultdict(list); incomplete=[]; invalid=[]
    for path in paths:
        try:
            summary=timing.summary(path); data=summary['task']
            if data['status']=='running' or any(s['status']=='running' for s in data['stages']):
                incomplete.append(data['run_id']);continue
            if not data.get('clock_valid',True) or any(not s.get('clock_valid',True) for s in data['stages']):
                invalid.append(data['run_id']);continue
            key=tuple(data.get(k) for k in ('scenario','environment','dataset'))
            if any(v is None for v in key):
                key=('unclassified:' + data['run_id'],None,None)
            groups[key].append({'run_id':data['run_id'],'revision':data.get('revision'),
                'status':data['status'],'seconds':data['elapsed_seconds'],
                'unclassified_seconds':summary['unclassified_seconds'], 'stages':exclusive_stages(data)})
        except (OSError,ValueError,KeyError) as exc:
            invalid.append(str(path))
    output=[]
    for key,runs in groups.items():
        successful=[r['seconds'] for r in runs if r['status']=='ok']
        revisions={}
        for revision in dict.fromkeys(r['revision'] for r in runs):
            values=[r['seconds'] for r in runs if r['revision']==revision and r['status']=='ok']
            median=statistics.median(values) if values else None
            revisions[str(revision)]={'samples':len(values),'median_seconds':median,
                'min_seconds':min(values) if values else None,'max_seconds':max(values) if values else None,
                'mad_seconds':statistics.median(abs(v-median) for v in values) if values else None}
        output.append({'scenario':key[0],'environment':key[1],'dataset':key[2],
            'runs':runs,'attempts':len(runs),'failed_attempts':sum(r['status']!='ok' for r in runs),
            'median_success_seconds':statistics.median(successful) if successful else None,
            'revisions':revisions,'enough_samples_per_revision':all(v['samples']>=5 for v in revisions.values())})
    return {'groups':output,'incomplete_runs':incomplete,'invalid_runs':invalid,
        'interpretation':'Compare identical scenario/environment/dataset; report failures and gaps. Five samples are a minimum descriptive sample, not statistical proof. Parallel exclusive stages can still overlap.'}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,required=True);p.add_argument('--output',type=Path)
    args=p.parse_args()
    report=analyze(sorted((args.project/'.platform/task-timings').glob('*.json')))
    text=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text,encoding='utf-8')
    print(text)
if __name__=='__main__':main()
