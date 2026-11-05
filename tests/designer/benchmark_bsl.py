"""Alternate baseline/candidate fresh-process BSL checks and retain timing + correctness."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from workflow import timing
from workflow.learning import compare_runs

WORKER=r'''
import hashlib,importlib.util,json,sys
spec=importlib.util.spec_from_file_location('measured_checks',sys.argv[1])
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
texts=['А = Справочники.Товары.ПустаяСсылка;',
       'Функция Значение() Экспорт\n Возврат 42;\nКонецФункции',
       'Процедура Проверка()\n А = Истина;\nКонецПроцедуры']
values=[]
for i in range(200):
    for text in texts:values.append(module.check_bsl(text,False))
print(hashlib.sha256(json.dumps(values,ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest())
'''


def run(baseline_file,output,samples):
    baseline_file=Path(baseline_file).resolve();output=Path(output).resolve()
    if output.exists() and any(output.iterdir()):raise ValueError('Use a new benchmark output directory')
    output.mkdir(parents=True,exist_ok=True)
    candidate=ROOT/'tools/bsl_checks.py'
    revisions={'baseline':hashlib.sha256(baseline_file.read_bytes()).hexdigest(),
               'candidate':hashlib.sha256(candidate.read_bytes()).hexdigest()}
    environment=os.name+'-python-'+sys.version.split()[0]
    dataset=hashlib.sha256(WORKER.encode()).hexdigest()
    paths=[];outputs=[]
    for i in range(samples):
        for label,file in [('baseline',baseline_file),('candidate',candidate)] if i%2==0 else [('candidate',candidate),('baseline',baseline_file)]:
            path=timing.create(output,'fresh process and 600 BSL checks',scenario='bsl-shared-import-v1',
                environment=environment,dataset=dataset,revision=label)
            status='failed';code=None
            try:
                with timing.stage(path,'process-import-and-check'):
                    r=subprocess.run([sys.executable,'-c',WORKER,str(file)],capture_output=True,text=True,
                        encoding='utf-8',env={**os.environ,'PYTHONUTF8':'1'},timeout=30)
                    code=r.returncode
                    outputs.append({'sample':i,'revision':label,'exit_code':code,'digest':r.stdout.strip(),'stderr':r.stderr})
                    if code:raise RuntimeError(r.stderr)
                status='ok'
            finally:
                timing.finish(path,status);paths.append(path)
    result=compare_runs(paths,'baseline','candidate')
    result.update(hypothesis='Separating shared BSL checks reduces fresh-process import cost while preserving diagnostics.',
                  source_sha256=revisions,outputs=outputs,correctness_equal=len({r['digest'] for r in outputs})==1,
                  method='Alternating fresh processes; 600 identical checks each; warm OS cache, no LLM, no 1C/UI. Includes process startup and timing journal overhead.')
    (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    assert result['correctness_equal'],'Diagnostics changed'
    return result


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline-file',required=True)
    p.add_argument('--output',required=True);p.add_argument('--samples',type=int,default=5)
    a=p.parse_args()
    if a.samples<5:p.error('At least five samples per revision are required')
    print(json.dumps(run(a.baseline_file,a.output,a.samples),ensure_ascii=False,indent=2))
