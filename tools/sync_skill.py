"""Plan and apply a reviewed skill update; preserve profiles and concurrent edits."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
from workflow.resource_lock import base_lease

SHARED=('reference/probes/',
        'tools/workflow/task_plan.py','tools/workflow/form_contract.py','tools/workflow/ui_contract.py',
        'tools/workflow/api_index.py','tools/workflow/hbk_source.py','tools/workflow/verification.py',
        'tools/workflow/watchdog.py','tools/workflow/source_guard.py','tools/workflow/ui_batch.py',
        'tools/workflow/reference/manager.bsl',
        'knowledge/task-plan.md','knowledge/contracts-and-api.md','knowledge/incremental-execution.md',
        'knowledge/optimization-workflow.md')
SHARED+=tuple('tools/workflow/tests/test_'+name+'.py' for name in (
    'task_plan','form_contract','ui_contract','api_index','hbk_source',
    'verification','watchdog','source_guard_progress','ui_batch'))
IGNORED={'.git','.platform','__pycache__'}

def digest(path):
    path=Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def link(path):
    return path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction())

def inside(root,relative):
    name=PurePosixPath(relative)
    if name.is_absolute() or not name.parts or any(p in ('..','.') or ':' in p or '\\' in p for p in name.parts):
        raise ValueError('Unsafe relative path')
    if any(p in IGNORED for p in name.parts): raise ValueError('Forbidden metadata path')
    root=Path(root).absolute()
    if link(root): raise ValueError('Skill root must not be a link')
    result=root
    for part in name.parts:
        result=result/part
        if link(result): raise ValueError('Links are not deployable')
    if not result.resolve().is_relative_to(root.resolve()): raise ValueError('Path escapes skill')
    return result

def tracked_files(source,profile):
    if profile not in ('codex','shared'): raise ValueError('Unknown skill profile')
    result=subprocess.run(['git','-C',str(source),'ls-files','-z'],capture_output=True,check=True)
    names=result.stdout.decode('utf-8').split('\0')
    return sorted(n for n in names if n and (profile=='codex' or shared(n)))

def shared(name):
    return any(name.startswith(p) if p.endswith('/') else name==p for p in SHARED)

def inventory(root,names):
    return {n:digest(inside(root,n)) for n in names}

def make_plan(source,target,names,profile='codex'):
    if profile not in ('codex','shared'): raise ValueError('Unknown skill profile')
    source=Path(source).resolve();target=Path(target).absolute()
    if source==target.resolve() or source.is_relative_to(target.resolve()) or target.resolve().is_relative_to(source):
        raise ValueError('Source and destination must be separate trees')
    names=sorted(set(names))
    for name in names:
        if profile=='shared' and not shared(name): raise ValueError('Profile-specific file in shared update')
        if not inside(source,name).is_file(): raise ValueError('Missing source file: '+name)
    return {'schema_version':1,'profile':profile,'source':str(source),'target':str(target),
            'files':{n:{'source':digest(inside(source,n)),'before':digest(inside(target,n))} for n in names}}

def apply_plan(plan):
    if plan.get('schema_version')!=1 or plan.get('profile') not in ('codex','shared'): raise ValueError('Unknown sync plan')
    source=Path(plan['source']);target=Path(plan['target'])
    # Validate all boundaries again; serialized plans are untrusted input.
    expected=make_plan(source,target,list(plan['files']),plan['profile'])
    if expected!=plan: raise ValueError('Source or target changed after the update was planned')
    lock_root=target.parent/'.1codex-sync-locks'
    key=hashlib.sha256(str(target.resolve()).casefold().encode()).hexdigest()
    backups={};written={}
    with base_lease(lock_root,key):
        if make_plan(source,target,list(plan['files']),plan['profile'])!=plan: raise ValueError('Stale sync plan')
        try:
            for name,entry in plan['files'].items():
                if entry['source']==entry['before']: continue
                src=inside(source,name);dst=inside(target,name)
                if digest(src)!=entry['source'] or digest(dst)!=entry['before']: raise ValueError('Concurrent skill edit')
                backups[name]=dst.read_bytes() if dst.is_file() else None
                dst.parent.mkdir(parents=True,exist_ok=True)
                data=src.read_bytes()
                if hashlib.sha256(data).hexdigest()!=entry['source']: raise ValueError('Source changed while reading')
                with tempfile.NamedTemporaryFile(dir=dst.parent,prefix='.1codex-',delete=False) as stream:
                    pending=Path(stream.name);stream.write(data)
                try:
                    if digest(dst)!=entry['before']: raise ValueError('Destination changed while staging')
                    os.replace(pending,dst);written[name]=entry['source']
                finally: pending.unlink(missing_ok=True)
            if inventory(source,plan['files'])!={n:e['source'] for n,e in plan['files'].items()}:
                raise ValueError('Source changed before synchronization completed')
            if inventory(target,plan['files'])!={n:e['source'] for n,e in plan['files'].items()}:
                raise ValueError('Target changed before synchronization completed')
            return {'status':'verified','profile':plan['profile'],'updated':len(written),
                    'files':inventory(target,plan['files'])}
        except BaseException:
            for name in reversed(list(written)):
                dst=inside(target,name)
                if digest(dst)!=written[name]: continue # Preserve an external concurrent edit.
                data=backups[name]
                if data is None: dst.unlink()
                else: dst.write_bytes(data)
            raise

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('plan');p.add_argument('--source',required=True);p.add_argument('--target',required=True)
    p.add_argument('--profile',choices=('codex','shared'),default='codex');p.add_argument('--output',required=True)
    p=sub.add_parser('apply');p.add_argument('plan');p.add_argument('--result',required=True)
    args=parser.parse_args()
    if args.command=='plan':
        result=make_plan(args.source,args.target,tracked_files(args.source,args.profile),args.profile)
        output=Path(args.output)
    else:
        result=apply_plan(json.loads(Path(args.plan).read_text(encoding='utf-8')));output=Path(args.result)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Sync '+args.command+' completed:',output)

if __name__=='__main__': main()
