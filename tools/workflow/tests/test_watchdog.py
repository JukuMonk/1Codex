import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from watchdog import Watchdog, Phase, RetryGate, run_monitored, StalledOperation


class Clock:
    def __init__(self):self.now=0
    def __call__(self):return self.now
    def sleep(self,seconds):self.now+=seconds


class WatchdogTests(unittest.TestCase):
    def setUp(self):self.clock=Clock()

    def test_unchanged_token_does_not_reset_deadline(self):
        monitor=Watchdog(Phase('copy'),clock=self.clock)
        monitor.progress(('files',1));self.clock.now=60;monitor.progress(('files',1))
        self.assertEqual(monitor.check()['kind'],'no_progress_warning')
        self.clock.now=120;self.assertEqual(monitor.check()['kind'],'stalled_unsafe')

    def test_real_checkpoint_extends_deadline_and_double_duration_warns(self):
        monitor=Watchdog(Phase('copy',expected_seconds=20),clock=self.clock)
        self.clock.now=39;monitor.progress(64)
        self.assertIsNone(monitor.check())
        self.clock.now=40;self.assertEqual(monitor.check()['kind'],'duration_warning')
        self.clock.now=90;monitor.progress(128);self.assertIsNone(monitor.check())

    def child(self):
        child=Mock(spec=subprocess.Popen);child.poll.return_value=None;return child

    def test_safe_cancel_only_own_child_handle(self):
        child=self.child();events=[]
        with self.assertRaises(StalledOperation):
            run_monitored(child,lambda:None,Phase('read',warn_seconds=1,stop_seconds=2,cancel_safe=True),
                          on_event=events.append,clock=self.clock,sleep=self.clock.sleep)
        child.terminate.assert_called_once();child.wait.assert_called_once()
        self.assertEqual([e['kind'] for e in events],['no_progress_warning','stalled_cancel_safe'])

    def test_unsafe_write_not_terminated(self):
        child=self.child()
        with self.assertRaises(StalledOperation) as failure:
            run_monitored(child,lambda:None,Phase('UpdateDBCfg',warn_seconds=1,stop_seconds=2),
                          clock=self.clock,sleep=self.clock.sleep)
        self.assertEqual(failure.exception.event['kind'],'stalled_unsafe')
        child.terminate.assert_not_called();child.kill.assert_not_called()

    def test_foreign_pid_never_accepted(self):
        with self.assertRaises(TypeError):run_monitored(1234,lambda:None,Phase('read'))

    def test_access_denied_immediate_and_not_serializing_private_command(self):
        child=self.child();events=[]
        with self.assertRaises(StalledOperation):
            run_monitored(child,lambda:None,Phase('read'),access_denied_provider=lambda:True,on_event=events.append)
        self.assertEqual(events[0]['kind'],'access_denied')
        child.terminate.assert_not_called()
        self.assertNotIn('args',events[0])

    def test_normal_exit_and_changed_conditions_retry(self):
        child=self.child();child.poll.return_value=0;child.returncode=0
        self.assertEqual(run_monitored(child,lambda:None,Phase('read')),0)
        gate=RetryGate();gate.failed('access_denied','same-role')
        with self.assertRaises(ValueError):gate.check('access_denied','same-role')
        self.assertTrue(gate.check('access_denied','fixed-role'))


if __name__=='__main__':unittest.main()
