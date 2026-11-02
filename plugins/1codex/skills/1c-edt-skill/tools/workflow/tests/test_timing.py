import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import timing


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = timing.create(self.temp.name, 'test')

    def test_nested_failure_and_completion(self):
        with timing.stage(self.path, 'parent') as parent:
            with self.assertRaises(RuntimeError):
                with timing.stage(self.path, 'child', parent):
                    raise RuntimeError('secret-not-for-journal')
        timing.finish(self.path)
        text = self.path.read_text(encoding='utf-8')
        self.assertNotIn('secret-not-for-journal', text)
        data = json.loads(text)
        self.assertEqual([s['status'] for s in data['stages']], ['ok', 'failed'])
        self.assertGreaterEqual(data['stages'][0]['monotonic_seconds'], 0)
        with self.assertRaises(ValueError): timing.begin(self.path, 'late')

    def test_unfinished_stage_blocks_finish_and_parent_end(self):
        parent = timing.begin(self.path, 'parent')
        child = timing.begin(self.path, 'child', parent)
        with self.assertRaises(ValueError): timing.finish(self.path)
        with self.assertRaises(ValueError): timing.end(self.path, parent)
        timing.end(self.path, child, 'interrupted')
        timing.end(self.path, parent)
        with self.assertRaises(ValueError): timing.end(self.path, parent)
        timing.finish(self.path, 'interrupted')

    def test_overlap_union_and_gap(self):
        data = json.loads(self.path.read_text(encoding='utf-8'))
        data.update(elapsed_seconds=30, stages=[
            dict(started_at='2026-10-31T00:00:00+00:00', ended_at='2026-10-31T00:00:10+00:00'),
            dict(started_at='2026-10-31T00:00:05+00:00', ended_at='2026-10-31T00:00:15+00:00'),
            dict(started_at='2026-10-31T00:00:06+00:00', ended_at='2026-10-31T00:00:07+00:00')])
        self.path.write_text(json.dumps(data), encoding='utf-8')
        report = timing.summary(self.path)
        self.assertEqual(report['covered_seconds'], 15)
        self.assertEqual(report['unclassified_seconds'], 15)

    def test_cross_process_cli(self):
        tool = str(Path(timing.__file__))
        def run(*args):
            return subprocess.check_output([sys.executable, tool, *map(str, args)], text=True).strip()
        phase = run('begin', self.path, 'analysis')
        run('end', self.path, phase, '--status', 'failed')
        run('finish', self.path, '--status', 'failed')
        self.assertEqual(json.loads(run('show', self.path))['task']['status'], 'failed')

    def test_failed_atomic_write_keeps_previous_journal(self):
        original = self.path.read_bytes()
        with patch.object(Path, 'replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): timing.begin(self.path, 'lost')
        self.assertEqual(self.path.read_bytes(), original)
        phase = timing.begin(self.path, 'retry')
        timing.end(self.path, phase)
        timing.finish(self.path)
