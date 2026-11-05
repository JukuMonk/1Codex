from pathlib import Path
import io
import json
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hbk_source import Container, PROFILE, SENTINEL, extract_hbk
from api_index import build_index, search_index


def block(data,following=SENTINEL,total=None):
    length=len(data)
    return ('\r\n%08x %08x %08x \r\n'%(length if total is None else total,length,following)).encode()+data


def archive(entries):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as package:
        for name,body in entries:package.writestr(name,body)
    header=bytes(20)+'FileStorage'.encode('utf-16le')
    head_offset=16+31+12
    body_offset=head_offset+31+len(header)
    index=struct.pack('<III',head_offset,body_offset,SENTINEL)
    return struct.pack('<IIII',SENTINEL,512,19,0)+block(index)+block(header)+block(stream.getvalue())


class HbkSources(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.hbk=self.root/'help.hbk';self.cache=self.root/'cache'
        self.hbk.write_bytes(archive([('objects/Open.html','<title>Открыть</title><p>ТестируемоеПолеФормы</p>'),
                                    ('objects/Save.html','<title>Записать</title>')]))

    def extract(self,**kwargs):return extract_hbk(self.hbk,self.cache,PROFILE,['*/Open.html'],**kwargs)

    def test_selected_extract_and_api_index(self):
        first=self.extract()
        self.assertFalse(first['cache_hit']);self.assertEqual(first['files'],1)
        html=Path(first['source_root'])/'objects/Open.html'
        self.assertIn('Открыть',html.read_text(encoding='utf-8'))
        index=self.root/'api.sqlite'
        build_index(first['source_root'],index,PROFILE,self.hbk)
        self.assertTrue(search_index(index,'Открыть ТестируемоеПолеФормы',PROFILE)['matches'])

    def test_cache_hit_never_parses_container_or_zip(self):
        first=self.extract()
        with patch.object(Container,'storage_zip',side_effect=AssertionError('must not parse')):
            second=self.extract()
        self.assertTrue(second['cache_hit']);self.assertFalse(second['archive_parsed'])
        self.assertEqual(first['source_root'],second['source_root'])

    def test_archive_change_creates_distinct_source(self):
        first=self.extract();self.hbk.write_bytes(archive([('objects/Open.html','<title>Changed</title>')]))
        second=self.extract()
        self.assertNotEqual(first['source_root'],second['source_root'])
        self.assertTrue((Path(first['source_root'])/'objects/Open.html').is_file())

    def test_corrupt_cached_file_requires_explicit_rebuild(self):
        first=self.extract();(Path(first['source_root'])/'objects/Open.html').write_text('changed')
        with self.assertRaisesRegex(ValueError,'Damaged'):self.extract()
        second=self.extract(rebuild=True)
        self.assertNotEqual(first['source_root'],second['source_root'])

    def test_zip_traversal_rejected_and_staging_removed(self):
        for name in ('../outside.html','/absolute.html','drive:bad.html','dir\\bad.html'):
            with self.subTest(name=name):
                self.hbk.write_bytes(archive([(name,'<title>bad</title>')]))
                with self.assertRaises(ValueError):self.extract()
                self.assertFalse(list(self.cache.glob('.hbk-stage-*')))
                self.assertFalse((self.root/'outside.html').exists())

    def test_member_bounds_checked_before_decompression(self):
        self.hbk.write_bytes(archive([('objects/Open.html','x'*10000)]))
        with self.assertRaisesRegex(ValueError,'page exceeds'):self.extract(max_file_bytes=10)
        self.assertFalse(list(self.cache.glob('.hbk-stage-*')))

    def test_file_count_and_total_bounds_are_explicit(self):
        for kwargs in ({'max_files':1},{'max_total_bytes':1}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(ValueError,'extraction bounds'):
                    extract_hbk(self.hbk,self.cache,PROFILE,['*.html'],**kwargs)

    def test_cancelled_progress_keeps_other_cache_content(self):
        self.cache.mkdir();keep=self.cache/'keep.txt';keep.write_text('keep')
        def cancel(progress):raise RuntimeError('cancelled own extraction')
        with self.assertRaisesRegex(RuntimeError,'cancelled'):self.extract(progress=cancel)
        self.assertEqual(keep.read_text(),'keep')
        self.assertFalse(list(self.cache.glob('.hbk-stage-*')))

    def test_duplicate_windows_paths_rejected(self):
        self.hbk.write_bytes(archive([('objects/Open.html','a'),('objects/OPEN.html','b')]))
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            extract_hbk(self.hbk,self.cache,PROFILE,['*.html'])

    def test_missing_selection_and_unknown_profile_rejected(self):
        with self.assertRaisesRegex(ValueError,'1..32'):extract_hbk(self.hbk,self.cache,PROFILE,[])
        with self.assertRaisesRegex(ValueError,'only'):extract_hbk(self.hbk,self.cache,'8.3',['*.html'])
        with self.assertRaisesRegex(ValueError,'No HTML'):extract_hbk(self.hbk,self.cache,PROFILE,['absent.html'])

    def test_cyclic_root_page_chain_is_bounded(self):
        self.hbk.write_bytes(struct.pack('<IIII',SENTINEL,512,19,0)+block(bytes(12),following=16,total=24))
        with self.assertRaisesRegex(ValueError,'Cyclic'):self.extract()

    def test_corrupt_directory_and_truncated_offset(self):
        self.hbk.write_bytes(struct.pack('<IIII',SENTINEL,512,19,0)+block(b'x'))
        with self.assertRaisesRegex(ValueError,'tuple'):self.extract()
        self.hbk.write_bytes(struct.pack('<IIII',SENTINEL,512,19,0)+block(struct.pack('<III',999999,999999,SENTINEL)))
        with self.assertRaisesRegex(ValueError,'offset'):self.extract()

    def test_corrupt_zip_rejected(self):
        data=bytearray(archive([('objects/Open.html','value')]))
        position=data.index(b'PK\x03\x04');data[position:position+2]=b'NO'
        self.hbk.write_bytes(data)
        with self.assertRaisesRegex(ValueError,'corrupt'):self.extract()

    def test_manifest_cannot_escape_cache(self):
        first=self.extract();manifest=Path(first['manifest']);data=json.loads(manifest.read_text())
        data['location']='../escape';manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'escape'):self.extract()


if __name__=='__main__':unittest.main()
