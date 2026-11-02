"""Acceptance: a separately opened 1C client survives the UI runner."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import project_cli
import ui_test
from workflow.ui_session import stop_owned


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);args=p.parse_args()
    cfg=project_cli.read_config(args.config);project_cli.validate_settings(cfg)
    v8c=Path(cfg['v8']).parent/'1cv8c.exe'
    foreign=subprocess.Popen('"%s" ENTERPRISE /F"%s" /DisableStartupMessages' % (v8c,cfg['test_ib']))
    output=Path(cfg['work'])/'isolation'
    try:
        time.sleep(5)
        assert foreign.poll() is None,'Control client exited before the test'
        result=ui_test.run(cfg['ui_scenario'],cfg['test_ib'],str(v8c.parent),work=str(output),port=49184,printwindow=True)
        survived=foreign.poll() is None
        report={'runner_exit_code':result,'independent_client_survived':survived,'control_pid':foreign.pid,
                'control_cleanup':'stopped by this acceptance script after assertion, never by runner'}
        (output/'acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        assert result==0 and survived,report
        print(json.dumps(report,ensure_ascii=False))
    finally:stop_owned([foreign])
if __name__=='__main__':main()
