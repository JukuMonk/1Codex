"""Autonomous orchestration infrastructure tests: no 1C/UI processes."""
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui_session import ProjectLock, BusyError, RunArtifacts, safe_frame_name, scenario_prefix, stop_owned


class SessionTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(safe_frame_name('ФМ01_кадр-1'), 'ФМ01_кадр-1')
        for name in ('../escape', 'a/b', 'a\\b', '.', '', 'CON', 'C:evil', 'x\n'):
            with self.assertRaises(ValueError): safe_frame_name(name)

    def test_lock_contention_and_crash_release(self):
        with tempfile.TemporaryDirectory() as temp:
            code = "import sys,time;sys.path.insert(0,sys.argv[1]);from ui_session import ProjectLock;lock=ProjectLock(sys.argv[2]);lock.__enter__();print('locked',flush=True);time.sleep(30)"
            child = subprocess.Popen([sys.executable, '-c', code, str(Path(__file__).resolve().parents[1]), temp], stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), 'locked')
                with self.assertRaises(BusyError):
                    with ProjectLock(temp): pass
            finally:
                child.kill(); child.wait(); child.stdout.close()
            with ProjectLock(temp): pass

    def test_runs_unique_and_no_stale_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            a = RunArtifacts(temp, 'sandbox', 1, 'functional')
            b = RunArtifacts(temp, 'sandbox', 2, 'report-frame')
            self.assertNotEqual(a.root, b.root)
            a.manifest['frames'] = ['missing']
            a.save(); a.publish()
            self.assertFalse((Path(temp)/'снимки/ui_missing.png').exists())
            self.assertTrue((Path(temp)/'ui-last.json').exists())

    def test_scenario_prefix(self):
        text = 'команда | a\nснимок | first\nполе | a | b\nснимок | last\nзакрыть\n'
        self.assertEqual(scenario_prefix(text, 'last'), 'команда | a\nполе | a | b\n')
        self.assertEqual(scenario_prefix(text, 'поле | a | b', True), 'команда | a\nполе | a | b\n')
        with self.assertRaises(ValueError): scenario_prefix(text, 'missing')

    def test_cleanup_owned_only(self):
        class Process:
            def __init__(self, done=False): self.done=done; self.stopped=False
            def poll(self): return 0 if self.done else None
            def terminate(self): self.stopped=True
            def wait(self, timeout): pass
        ours, ended, foreign = Process(), Process(True), Process()
        stop_owned([ours, ended])
        self.assertTrue(ours.stopped)
        self.assertFalse(ended.stopped)
        self.assertFalse(foreign.stopped)

