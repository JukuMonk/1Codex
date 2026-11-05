from pathlib import Path
import hashlib
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from api_index import build_index, search_index


class ApiIndex(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'html';self.root.mkdir()
        self.cache=Path(self.temp.name)/'api.sqlite'
        self.page=self.root/'Open.html'
        self.page.write_text('<title>Открыть Open</title><h1>ТестируемоеПолеФормы.Открыть()</h1><p>Эмулирует кнопку открытия поля</p><script>HiddenFakeMethod</script>',encoding='utf-8')
        (self.root/'Save.html').write_text('<title>Записать</title><p>Метод формы Записать() context клиент</p>',encoding='utf-8')

    def build(self):return build_index(self.root,self.cache,'8.5.1.1529')
    def search(self,query,**kwargs):return search_index(self.cache,query,'8.5.1.1529',**kwargs)

    def test_indexed_russian_context_and_source_evidence(self):
        self.assertEqual(self.build()['parsed'],2)
        results=self.search('ТестируемоеПолеФормы Открыть')['matches']
        self.assertEqual(len(results),1)
        self.assertEqual(results[0]['path'],'Open.html')
        self.assertEqual(results[0]['source_sha256'],hashlib.sha256(self.page.read_bytes()).hexdigest())
        self.assertIn('Эмулирует',results[0]['excerpt'])
        self.assertFalse(self.search('HiddenFakeMethod')['matches'])

    def test_reuse_and_incremental_rebuild(self):
        self.build()
        self.assertEqual(self.build()['parsed'],0)
        self.page.write_text('<title>New</title><p>Changed method signature</p>',encoding='utf-8')
        self.assertEqual(self.build()['parsed'],1)
        self.assertTrue(self.search('Changed')['matches'])

    def test_source_change_rejected_before_search(self):
        self.build();self.page.write_text('Changed source',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Stale'):self.search('Открыть')

    def test_platform_change_rebuilds_docs(self):
        self.build()
        result=build_index(self.root,self.cache,'8.3')
        self.assertEqual(result['parsed'],2)
        self.assertEqual(search_index(self.cache,'Открыть','8.3')['platform_version'],'8.3')

    def test_declared_windows_charset_and_utf16_bom(self):
        self.page.write_bytes('<meta charset="windows-1251"><title>Открыть</title><p>ТестируемоеПолеФормы</p>'.encode('cp1251'))
        (self.root/'Save.html').write_bytes('<title>Записать</title><p>Сервер</p>'.encode('utf-16'))
        self.build()
        self.assertTrue(self.search('Открыть ТестируемоеПолеФормы')['matches'])
        self.assertTrue(self.search('Записать Сервер')['matches'])

    def test_undecodable_help_keeps_previous_index(self):
        self.build();before=self.cache.read_bytes()
        self.page.write_bytes(b'<meta charset="not-a-codec">bad')
        with self.assertRaisesRegex(ValueError,'charset'):self.build()
        self.assertEqual(self.cache.read_bytes(),before)

    def test_escaping_source_symlink_rejected(self):
        outside=Path(self.temp.name)/'outside.html';outside.write_text('outside')
        target=self.root/'link.html'
        try: target.symlink_to(outside)
        except (OSError,NotImplementedError):self.skipTest('Symlink permission unavailable')
        with self.assertRaisesRegex(ValueError,'escape'):self.build()

    def test_platform_identity_required(self):
        self.build()
        with self.assertRaisesRegex(ValueError,'platform'):search_index(self.cache,'Открыть','8.3')

    def test_source_content_with_preserved_timestamp_rejected(self):
        self.build();stat=self.page.stat();raw=self.page.read_bytes()
        self.page.write_bytes(raw.replace(b'Open',b'Gone'));os.utime(self.page,ns=(stat.st_atime_ns,stat.st_mtime_ns))
        with self.assertRaisesRegex(ValueError,'content changed'):self.search('Открыть')

    def test_original_archive_invalidates_cache(self):
        archive=Path(self.temp.name)/'help.hbk';archive.write_bytes(b'archive1')
        build_index(self.root,self.cache,'8.5.1.1529',archive)
        archive.write_bytes(b'archive2')
        with self.assertRaisesRegex(ValueError,'Stale'):self.search('Открыть')

    def test_deleted_documents_removed(self):
        self.build();self.page.unlink();self.build()
        self.assertFalse(self.search('Открыть')['matches'])

    def test_results_are_bounded(self):
        self.build()
        with self.assertRaises(ValueError):self.search('a',limit=51)
        with self.assertRaises(ValueError):self.search('')
        result=self.search('метод',limit=1,max_excerpt=80)
        self.assertLessEqual(len(result['matches']),1)
        for row in result['matches']:self.assertLessEqual(len(row['excerpt']),80)

    def test_interrupted_build_retains_old_index(self):
        self.build();before=self.cache.read_bytes()
        def interrupt(value):raise RuntimeError('stop')
        with self.assertRaises(RuntimeError):build_index(self.root,self.cache,'8.5.1.1529',progress=interrupt)
        self.assertEqual(self.cache.read_bytes(),before)
        self.assertFalse(list(self.cache.parent.glob('*.pending')))

    def test_unsafe_cache_path_rejected(self):
        self.build()
        with closing(sqlite3.connect(self.cache)) as db:
            db.execute('INSERT INTO documents VALUES (?,?,?,?,?)',('../outside.html','Unsafe','unsafe','[]','digest'))
            db.execute('INSERT INTO tokens VALUES (?,?)',('unsafe','../outside.html'))
            db.commit()
        with self.assertRaisesRegex(ValueError,'Unsafe'):self.search('unsafe')


if __name__=='__main__':unittest.main()
