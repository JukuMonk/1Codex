"""Independent fixture preparation and one functional TestManager session."""
import hashlib
import json
from pathlib import Path
import re
import uuid

ID=re.compile(r'^[A-Za-z0-9_.-]{1,60}$')
TOKEN=re.compile(r'\$\{([A-Za-z0-9_]+)\}')

def prepare(cases,factory):
    ids=[c['id'] for c in cases]
    if not ids or len(ids)!=len(set(ids)) or any(not ID.fullmatch(n) for n in ids):
        raise ValueError('Unique case identifiers are required')
    batch_id=uuid.uuid4().hex;resources=set();lines=[]
    for case in cases:
        fixture=factory(case['fixture'],batch_id+'.'+case['id'])
        refs=fixture.get('resources',[])
        if not refs or len(set(refs))!=len(refs) or resources.intersection(refs):
            raise ValueError('Each case must own independent fixture resources')
        resources.update(refs)
        lines.append('этап | '+case['id']+'.begin')
        for template in case['steps']:
            if '\n' in template or '\r' in template or '\x00' in template:
                raise ValueError('One DSL operation per line')
            if template.split('|',1)[0].strip().casefold()=='этап':
                raise ValueError('Batch boundary markers are reserved')
            def replace(match):
                value=str(fixture[match.group(1)])
                if any(c in value for c in '|\r\n\x00'): raise ValueError('Unsafe fixture substitution')
                return value
            lines.append(TOKEN.sub(replace,template))
        lines.append('этап | '+case['id']+'.end')
    return {'id':batch_id,'cases':ids,'scenario':'\n'.join(lines)+'\n'}

def outcomes(batch,journal,exit_code):
    result={i:'not_run' for i in batch['cases']}
    for line in journal.splitlines():
        marker=re.match(r'^ОК\s+этап\s*\|\s*([A-Za-z0-9_.-]+)\.(begin|end)(?:\s|$)',line)
        if marker and marker[1] in result:
            result[marker[1]]='failed' if marker[2]=='begin' else 'passed'
    if exit_code and all(v=='passed' for v in result.values()):
        return {'cases':result,'status':'infrastructure_failed'}
    return {'cases':result,'status':'passed' if exit_code==0 and all(v=='passed' for v in result.values()) else 'failed'}

def run(cases,factory,runner,work):
    batch=prepare(cases,factory);folder=Path(work)/batch['id'];folder.mkdir(parents=True)
    path=folder/'scenario.txt';path.write_text(batch['scenario'],encoding='utf-8')
    result=runner(path)
    report=outcomes(batch,result['journal'],result['exit_code'])
    report.update(batch_id=batch['id'],scenario_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  exit_code=result['exit_code'],runner_id=result.get('run_id'))
    (folder/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report
