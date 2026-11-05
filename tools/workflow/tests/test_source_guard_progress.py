from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from source_guard import FrozenRun, manifest


class PreparationTests(unittest.TestCase):
    def test_phase_timings_and_real_file_checkpoints_are_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';source.mkdir()
            for i in range(130):(source/('f'+str(i)+'.bsl')).write_text('test')
            original=manifest(source);events=[]
            with_run=FrozenRun(root,source,'test',progress=events.append)
            try:
                names=[s['name'] for s in with_run.record['preparation_stages']]
                self.assertEqual(names,['hash_live','copy','verify_live','verify_copy','normalize_bsl',
                                        'hash_normalized','read_leases','verify_leases'])
                self.assertTrue(all(s['status']=='succeeded' and s['duration_seconds']>=0
                                    for s in with_run.record['preparation_stages']))
                self.assertTrue(any(e['phase']=='copy' and e['processed_files']==64 for e in events))
                self.assertTrue(any(e['phase']=='copy' and e['processed_files']==130 for e in events))
                self.assertEqual(manifest(source),original)
                record=json.loads((with_run.folder/'run.json').read_text(encoding='utf-8'))
                self.assertEqual(record['preparation_progress']['phase'],'verify_leases')
            finally:with_run.close()

    def test_failed_phase_is_recorded_without_sensitive_error_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';source.mkdir();(source/'test.bsl').write_text('x')
            with patch('source_guard.shutil.copytree',side_effect=OSError('secret connection')):
                with self.assertRaises(OSError):FrozenRun(root,source,'test')
            path=next((root/'.platform/runs').glob('*/run.json'))
            raw=path.read_text(encoding='utf-8');record=json.loads(raw)
            self.assertEqual(record['status'],'failed_preparing')
            self.assertEqual(record['preparation_stages'][-1]['name'],'copy')
            self.assertEqual(record['preparation_stages'][-1]['status'],'failed')
            self.assertNotIn('secret connection',raw)


if __name__=='__main__':unittest.main()
