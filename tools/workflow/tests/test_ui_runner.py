import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ui_test


class UiRunnerTests(unittest.TestCase):
    def test_old_path_cleanup_is_disabled(self):
        with self.assertRaises(RuntimeError): ui_test.close_clients('unused')

    def test_busy_port_is_rejected(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0));listener.listen()
            with self.assertRaises(OSError): ui_test.port_available(listener.getsockname()[1])

    def exercise(self, failure=None):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);scenario=root/'scenario.txt';scenario.write_text('форма | Example', encoding='utf-8')
            foreign=Mock();client=Mock(pid=11);manager=Mock(pid=12)
            client.poll.return_value=None; manager.poll.return_value=None
            work=root/'work';work.mkdir();(work/'ТестUIМенеджер.epf').write_bytes(b'fake')
            def launch(command):
                if '/TESTMANAGER' in command:
                    if failure == 'start': raise OSError('start failed')
                    manifests=list((work/'ui-runs').glob('*/manifest.json'))
                    data=json.loads(manifests[0].read_text(encoding='utf-8'))
                    Path(data['journal']).write_text('ОШИБКА controlled' if failure=='scenario' else 'OK',encoding='utf-8')
                    return manager
                return client
            with patch.object(ui_test,'port_available'), patch.object(ui_test,'manager_outdated',return_value=False), \
                 patch.object(ui_test.subprocess,'Popen',side_effect=launch), patch.object(ui_test.time,'sleep'), \
                 patch.object(ui_test,'capture',return_value=(False,'headless')):
                if failure=='start':
                    with self.assertRaises(OSError): ui_test.run(str(scenario),'test-base','bin',work=str(work))
                else:
                    self.assertEqual(ui_test.run(str(scenario),'test-base','bin',work=str(work)),1 if failure else 0)
            client.terminate.assert_called_once()
            if failure!='start': manager.terminate.assert_called_once()
            foreign.terminate.assert_not_called()
            data=json.loads((work/'ui-last.json').read_text(encoding='utf-8'))
            self.assertEqual(data['status'],'failed' if failure else 'succeeded')
            self.assertEqual(data['frames'],[])

    def test_success_owns_only_started_processes(self): self.exercise()
    def test_failed_scenario_cleans_both_processes(self): self.exercise('scenario')
    def test_manager_start_failure_cleans_client(self): self.exercise('start')
