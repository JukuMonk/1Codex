from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from workflow import pipeline, pipeline_model, task_plan, timing, watchdog


class PipelineTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.journal = timing.create(self.folder, 'Проверка')

    def state(self):
        return pipeline.read_state(self.journal)

    def invoke_monitor(self, argv, *, browser_result=True, browser_error=None):
        url = 'http://127.0.0.1:43210/test-run/'
        stdout, stderr = StringIO(), StringIO()
        with patch.object(sys, 'argv', ['pipeline.py', *argv]), redirect_stdout(stdout), redirect_stderr(stderr), \
                patch.object(pipeline, 'open_monitor', return_value=url) as server, \
                patch.object(pipeline.webbrowser, 'open_new_tab', return_value=browser_result,
                             side_effect=browser_error) as browser:
            pipeline.main()
        journal_line, address = stdout.getvalue().splitlines()
        journal = Path(json.loads(journal_line)['journal'])
        server.assert_called_once_with(journal)
        self.assertEqual(address, url)
        self.assertTrue(journal.is_file())
        return journal, browser, stderr.getvalue(), url

    def test_new_task_opens_one_tab_and_panel_mode_only_returns_the_url(self):
        for options in ([], ['--no-browser']):
            with self.subTest(options=options):
                journal, browser, message, url = self.invoke_monitor(
                    ['start', '--project', str(self.folder), '--label', 'Новая задача', *options])
                self.assertNotEqual(journal, self.journal)
                self.assertEqual(message, '')
                if options:
                    browser.assert_not_called()
                else:
                    browser.assert_called_once_with(url)

    def test_reopen_keeps_the_journal_if_browser_is_unavailable(self):
        for error in (None, OSError('browser unavailable')):
            with self.subTest(error=error):
                before = self.journal.read_bytes()
                journal, browser, message, url = self.invoke_monitor(
                    ['open', str(self.journal)], browser_result=False, browser_error=error)
                self.assertEqual(journal, self.journal)
                self.assertEqual(before, journal.read_bytes())
                browser.assert_called_once_with(url)
                self.assertIn('ссылку', message)

    def test_restart_recovers_bookmark_or_uses_a_new_free_port(self):
        ready = self.folder/'monitor.url'
        original, prefix = pipeline.bind_monitor(BaseHTTPRequestHandler, 0, ready)
        with original:
            port = original.server_port
            ready.write_text(f'http://127.0.0.1:{port}{prefix}',encoding='ascii')
            replacement, fresh = pipeline.bind_monitor(BaseHTTPRequestHandler, 0, ready)
            with replacement:
                self.assertNotEqual(replacement.server_port, port)
                self.assertNotEqual(fresh, prefix)
        restored, path = pipeline.bind_monitor(BaseHTTPRequestHandler, 0, ready)
        with restored:
            self.assertEqual((restored.server_port, path), (port, prefix))

    def test_old_unknown_label_and_known_runner_names(self):
        with timing.stage(self.journal, 'Ручной этап'):
            pass
        with timing.stage(self.journal, 'com'):
            pass
        timing.finish(self.journal)
        s = self.state()
        self.assertEqual([None, 'com.hook'], [st['node'] for st in s['stages']])
        self.assertEqual(['begin', 'ok', 'begin', 'ok'], [e['kind'] for e in s['events']])

    def test_parallel_siblings_have_no_fabricated_dependency(self):
        a = timing.begin(self.journal, 'A', node='com')
        b = timing.begin(self.journal, 'B', node='com')
        timing.end(self.journal,b)
        timing.end(self.journal,a)
        self.assertIsNone(self.state()['stages'][1]['after'])
        self.assertEqual([1,1],[s['attempt'] for s in self.state()['stages']])

    def test_failed_repair_retry_and_interruption_keep_separate_attempts(self):
        a = timing.begin(self.journal,'Проверка',node='platform.lint')
        timing.end(self.journal,a,'failed')
        fix = timing.begin(self.journal,'Исправление',node='implementation.xml',after=a)
        timing.end(self.journal,fix)
        b = timing.begin(self.journal,'Проверка',node='platform.lint',after=fix)
        watchdog.journal_reporter(self.journal,b)({'kind':'stalled_unsafe'})
        timing.end(self.journal,b,'interrupted')
        timing.finish(self.journal,'interrupted')
        stages = self.state()['stages']
        self.assertEqual([1,1,2], [s['attempt'] for s in stages])
        self.assertEqual([None,a,fix], [s['after'] for s in stages])
        self.assertEqual('stalled', stages[-1]['signals'][0]['kind'])
        self.assertEqual(['failed','ok','interrupted'], [s['status'] for s in stages])

    def test_invalid_target_predecessor_and_late_signal_do_not_mutate_journal(self):
        a = timing.begin(self.journal, 'A', node='metadata')
        for kwargs in ({'node':'made-up.node'}, {'after':a}, {'after':'missing'}):
            with self.assertRaises(ValueError):
                timing.begin(self.journal, 'B', **kwargs)
        timing.end(self.journal,a)
        with self.assertRaises(ValueError):
            timing.signal(self.journal,a,'progress','Поздняя запись')
        self.assertEqual(1,len(self.state()['stages']))

    def test_points_and_parent_do_not_share_attempt_counters(self):
        plan = self.folder/'plan.json'
        cards = [dict(id=key,requirement='Проверка',acceptance=['Пройдено'],tests=['lint'])
                 for key in ('A','B')]
        task_plan.create(plan,'Два пункта',cards,'1',self.folder)
        for key in ('A','B'):
            parent = task_plan.begin_stage(plan,self.journal,key,'static')
            child = timing.begin(self.journal,'lint',parent)
            timing.end(self.journal,child)
            task_plan.end_stage(plan,self.journal,parent)
        items = [s for s in self.state()['stages'] if s['parent']]
        self.assertEqual(['A','B'],[s['point'] for s in items])
        self.assertEqual([1,1],[s['attempt'] for s in items])

    def test_silence_tracks_child_progress_and_excludes_explicit_waits(self):
        base = datetime(2026,1,1,tzinfo=timezone.utc)
        at = lambda s:(base+timedelta(seconds=s)).isoformat()
        parent = timing.begin(self.journal,'Parent',node='platform')
        child = timing.begin(self.journal,'Child',parent,node='platform.compile')
        with timing.journal(self.journal) as d:
            a,b = d['stages']
            a['started_at'], b['started_at'] = at(0),at(10)
            b['signals'] = [dict(at=at(55),kind='progress',message='Шаг выполнен'),
                            dict(at=at(125),kind='waiting',message='Ожидание ответа')]
            d['started_at']=at(0)
            state=pipeline_model.snapshot(d,now=at(230))
        gaps=[(e['id'],e['at']) for e in state['events'] if e['kind']=='quiet']
        self.assertIn((parent,at(115)),gaps)
        self.assertEqual([(child,at(115))],[e for e in gaps if e[0]==child])
        self.assertNotIn((parent,at(60)),gaps)

    def test_all_mappings_resolve_and_export_escapes_script_breakout(self):
        keys = pipeline_model.node_keys()
        self.assertEqual(12,len(pipeline_model.atlas()))
        self.assertTrue(set(pipeline_model.RUNNER_NODES.values()) <= keys)
        self.assertTrue(set(pipeline_model.PLAN_PHASES.values()) <= keys)
        with timing.stage(self.journal,'</script><script>alert(1)</script>'):
            pass
        html = pipeline.page(self.state(),False)
        self.assertNotIn('</script><script>alert',html)
        self.assertIn('"live":false',html)

    def test_external_command_keeps_exit_code_but_does_not_log_arguments(self):
        for expected in (7,0):
            code=pipeline.run_command(self.journal,'Сценарии','ui.vanessa',
                                      [sys.executable,'-c',f'raise SystemExit({expected})','private-marker'])
            self.assertEqual(expected,code)
        self.assertNotIn('private-marker',self.journal.read_text(encoding='utf-8'))
        stages=self.state()['stages']
        self.assertEqual(['failed','ok'],[s['status'] for s in stages])
        self.assertEqual(2,stages[-1]['attempt'])
