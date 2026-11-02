"""Prove that a real module error blocks release and preserves the previous artifact."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

from create_fixture import create, ROOT
sys.path.insert(0, str(ROOT/'tools'))
import project_cli


def run(v8, output, previous):
    output=Path(output).resolve()
    cfg=create(v8, output)
    module=Path(cfg['dump'])/'CommonModules/тстСервис/Ext/Module.bsl'
    text=module.read_text(encoding='utf-8-sig')
    # Legal BSL syntax, unresolved identifier: only the real platform compiler can validate this.
    module.write_text(text.replace('Возврат "1Codex OK";', 'Возврат НеопределеннаяПеременнаяПриемки;'), encoding='utf-8-sig')
    target=Path(cfg['release_target']);target.parent.mkdir(parents=True)
    shutil.copyfile(previous,target)
    before=hashlib.sha256(target.read_bytes()).hexdigest()
    error=None
    try:
        project_cli.execute(project_cli.read_config(output/'platform.json'),'release')
    except RuntimeError as exc:
        error=str(exc)
    runs=list((output/'.platform/runs').glob('*/run.json'))
    assert len(runs)==1, runs
    record=json.loads(runs[0].read_text(encoding='utf-8'))
    after=hashlib.sha256(target.read_bytes()).hexdigest()
    assert error=='Stage failed: modules', (error,record)
    assert before==after, 'Previous release was overwritten'
    assert not any(s['name']=='publish-local' for s in record['stages']), record
    result={'status':'PASS','expected_failure':error,'previous_artifact_preserved':before==after,
            'artifact_sha256':before,'run':str(runs[0]),'stages':record['stages']}
    (output/'acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--v8',required=True);p.add_argument('--output',required=True);p.add_argument('--previous',required=True)
    a=p.parse_args();print(json.dumps(run(a.v8,a.output,a.previous),ensure_ascii=False,indent=2))
