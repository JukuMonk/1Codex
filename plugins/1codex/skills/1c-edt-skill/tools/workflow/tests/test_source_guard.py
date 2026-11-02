"""No 1C or UI: real filesystem/OS-lock tests and mocked deployment failures."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import source_guard as guard


class SourceFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'конфигурация'
        self.source.mkdir()
        (self.source / 'Configuration.xml').write_text('<root><value>old</value></root>', encoding='utf-8')
        (self.source / 'Module.bsl').write_bytes('Процедура Тест()\nКонецПроцедуры\n'.encode('utf-8'))
        self.original = guard.manifest(self.source)
        self.runs = []

    def tearDown(self):
        for run in self.runs: run.close()
        self.temp.cleanup()

    def session(self):
        run = guard.FrozenRun(self.root, self.source, 'test')
        self.runs.append(run)
        return run

    def edit(self):
        (self.source / 'Configuration.xml').write_text('<root>concurrent</root>', encoding='utf-8')


class FrozenSourceTests(SourceFixture, unittest.TestCase):

    def test_copy_is_independent_and_normalizes_only_private_bsl(self):
        run = self.session()
        self.assertEqual(guard.manifest(self.source), self.original)
        self.assertTrue((run.snapshot / 'Module.bsl').read_bytes().startswith(b'\xef\xbb\xbf'))
        self.edit()
        self.assertEqual((run.snapshot / 'Configuration.xml').read_text(encoding='utf-8'), '<root><value>old</value></root>')
        with self.assertRaises(guard.GuardError): run.check()

    def test_copy_race_is_rejected(self):
        original = guard.shutil.copytree
        def racing(*args, **kwargs):
            result = original(*args, **kwargs); self.edit(); return result
        with patch.object(guard.shutil, 'copytree', side_effect=racing):
            with self.assertRaises(guard.GuardError): self.session()

    def test_snapshot_mutation_is_rejected(self):
        run = self.session()
        if os.name == 'nt':
            with self.assertRaises(PermissionError):
                (run.snapshot / 'Configuration.xml').write_text('tampered', encoding='utf-8')
            with self.assertRaises(PermissionError): (run.snapshot / 'Configuration.xml').unlink()
            run.check()
        else:
            (run.snapshot / 'Configuration.xml').write_text('tampered', encoding='utf-8')
            with self.assertRaises(guard.GuardError): run.check()

    def test_before_and_after_long_stage_and_private_journal(self):
        run = self.session()
        with self.assertRaises(guard.GuardError): run.stage('long test', lambda: self.edit() or 0)
        run.finish('failed')
        journal = json.loads((run.folder / 'run.json').read_text(encoding='utf-8'))
        self.assertEqual(journal['status'], 'failed')
        self.assertEqual(journal['stages'][0]['status'], 'failed')
        self.assertIn('duration_seconds', journal['stages'][0])
        self.assertIn('source_fingerprint', journal)
        self.assertNotIn('exception', journal)

    def test_journal_preserves_stage_parent_and_depth(self):
        run = self.session()
        run.stage('outer', lambda: run.stage('inner', lambda: 0))
        outer, inner = run.record['stages']
        self.assertEqual(outer['depth'], 0)
        self.assertEqual(inner['depth'], 1)
        self.assertEqual(inner['parent_stage_id'], outer['stage_id'])

    def test_canonical_output_does_not_overwrite_live(self):
        run = self.session(); exported = self.root / 'export'; exported.mkdir()
        (exported / 'Configuration.xml').write_text('<root>\n <value>old</value>\n</root>', encoding='utf-8')
        result = run.canonical_copy(exported, ['Configuration.xml'])
        self.assertEqual(guard.manifest(self.source), self.original)
        self.assertTrue(guard.cosmetic_equivalent(self.source / 'Configuration.xml', Path(result) / 'Configuration.xml'))
        self.edit()
        with self.assertRaises(guard.GuardError): run.canonical_copy(exported, ['Configuration.xml'])

    def test_semantic_xml_and_bsl_changes_are_not_cosmetic(self):
        other = self.root / 'other.xml'; other.write_text('<root><value>changed</value></root>', encoding='utf-8')
        self.assertFalse(guard.cosmetic_equivalent(self.source / 'Configuration.xml', other))
        other.write_text('<root><value>old</value><default>false</default></root>', encoding='utf-8')
        self.assertFalse(guard.cosmetic_equivalent(self.source / 'Configuration.xml', other))
        other.write_text('Процедура Тест()\nСообщить("changed");\nКонецПроцедуры', encoding='utf-8')
        self.assertFalse(guard.cosmetic_equivalent(self.source / 'Module.bsl', other))

    def test_os_lock_blocks_another_process_and_releases_after_crash(self):
        script = ('import sys,time;sys.path.insert(0,sys.argv[1]);from source_guard import project_lock;'
                  '\nwith project_lock(sys.argv[2]):\n print("ready",flush=True);time.sleep(30)')
        child = subprocess.Popen([sys.executable, '-c', script, str(Path(guard.__file__).parent), str(self.root)], stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), 'ready')
            with self.assertRaises(guard.GuardError):
                with guard.project_lock(self.root): pass
        finally:
            child.terminate(); child.wait(timeout=10); child.stdout.close()
        with guard.project_lock(self.root): pass

    def test_publish_rolls_back_if_source_changes_during_commit(self):
        run = self.session(); staged = run.folder / 'staged.cf'; staged.write_bytes(b'new')
        target = self.root / 'release.cf'; target.write_bytes(b'old')
        run.pending.append((str(staged), str(target)))
        original = guard.os.replace
        def racing(src, dst):
            result = original(src, dst)
            if Path(dst) == target: self.edit()
            return result
        with patch.object(guard.os, 'replace', side_effect=racing):
            with self.assertRaises(guard.GuardError): run.publish()
        self.assertEqual(target.read_bytes(), b'old')


