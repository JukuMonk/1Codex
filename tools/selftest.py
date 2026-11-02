"""Run the same offline acceptance checks in a checkout and an installed skill."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def run():
    checks=[]
    commands=[('regression',['-m','unittest','discover','-s','tools/workflow/tests','-v']),
        ('links',['tools/check_links.py']),('cases',['tools/cases_sync.py','проверить']),
        ('catalog',['tools/case_catalog.py','check']),('legacy-sandbox',['tools/check_project.py','tests/sandbox']),
        ('designer-fixture',['tools/check_designer.py','tests/designer/fixtures/configuration']),
        ('designer-lint',['tools/lint_dump.py','tests/designer/fixtures/configuration']),
        ('designer-221-fixture',['tools/check_designer.py','tests/designer/fixtures/configuration-221']),
        ('designer-221-lint',['tools/lint_dump.py','tests/designer/fixtures/configuration-221'])]
    for label,command in commands:
        began=time.perf_counter()
        r=subprocess.run([sys.executable,*command],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',
                         env={**os.environ,'PYTHONUTF8':'1'})
        checks.append({'name':label,'exit_code':r.returncode,'seconds':time.perf_counter()-began,'stdout':r.stdout,'stderr':r.stderr})
    return {'status':'PASS' if all(c['exit_code']==0 for c in checks) else 'FAIL','checks':checks,
            'scope':'Offline tests only; 1C/COM/UI acceptance is separate.'}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);args=p.parse_args()
    result=run()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    for row in result['checks']:
        print(f'{row["name"]}: exit {row["exit_code"]}, {row["seconds"]:.3f}s')
        if row['exit_code']:print(row['stdout'],row['stderr'])
    return result['status']!='PASS'
if __name__=='__main__':sys.exit(main())
