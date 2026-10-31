import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from resource_lock import base_lease, BaseBusy
import ui_error_log
import source_guard as guard


class ResourceTests(unittest.TestCase):
    def test_base_lease_reentrant_independent_and_cross_process(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp)/'db'
            code = "import sys;sys.path.insert(0,sys.argv[1]);from resource_lock import base_lease;\nwith base_lease(sys.argv[2],sys.argv[3]): print('acquired')"
            with base_lease(temp, db), base_lease(temp, db), base_lease(temp, Path(temp)/'other'):
                blocked = subprocess.run([sys.executable, '-c', code, str(TOOLS), temp, str(db)], capture_output=True)
                self.assertNotEqual(blocked.returncode, 0)
            acquired = subprocess.run([sys.executable, '-c', code, str(TOOLS), temp, str(db)], capture_output=True)
            self.assertEqual(acquired.returncode, 0)


    def test_handles_close_even_if_journal_disk_write_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            live = Path(temp)/'live'; live.mkdir(); (live/'a.bsl').write_text('text', encoding='utf-8')
            run = guard.FrozenRun(temp, live, 'test')
            with patch.object(run, 'save', side_effect=OSError('disk full')):
                with self.assertRaises(OSError): run.finish('failed')
            self.assertEqual(run.leases, [])
            (run.snapshot/'a.bsl').write_bytes(b'write allowed after close')


    def test_lgp_new_error_only_bounded_and_redacted(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'1Cv8Log'; folder.mkdir(); path = folder/'log.lgp'
            path.write_text('{20261030120000,N,\n{0,0},1,E,"old error",0}\n', encoding='utf-8')
            before = ui_error_log.cursor(temp)
            with path.open('a', encoding='utf-8') as log:
                log.write('{20261030120100,N,\n{0,0},1,1,2,1,20,E,"ERROR\n{Module(12)}: throw ""SECRET"";",0}\n')
            result = ui_error_log.collect(temp, before, 'ERROR', ['SECRET'])
            self.assertEqual(len(result), 1)
            self.assertIn('Module(12)', result[0]); self.assertNotIn('SECRET', result[0])
            self.assertEqual(ui_error_log.collect(temp, before, 'old error'), [])
            self.assertEqual(ui_error_log.collect(temp, before, 'ERROR', limit=5), [])


    def test_lgp_incomplete_record_is_not_reported(self):
        self.assertIsNone(ui_error_log.quoted('no closing quote', 0))


    def test_profiler_does_not_double_count_nested_stage(self):
        import profile_runs
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'runs/id'; path.mkdir(parents=True)
            (path/'run.json').write_text(json.dumps({'run_id':'id','operation':'test','status':'succeeded','duration_seconds':10,
                'stages':[{'name':'test','depth':0,'duration_seconds':9,'status':'succeeded'},
                          {'name':'load','depth':1,'duration_seconds':5,'status':'succeeded'},
                          {'name':'nested','depth':2,'duration_seconds':4,'status':'succeeded'}]}), encoding='utf-8')
            rows = profile_runs.read_runs(Path(temp))
            self.assertEqual(rows[0]['seconds'], 10)
            self.assertEqual([s['name'] for s in rows[0]['stages']], ['load'])


