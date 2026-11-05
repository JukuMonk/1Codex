import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import sync_skill as sync

class SkillSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.a=self.root/'source';self.b=self.root/'target'
        self.a.mkdir();self.b.mkdir();(self.a/'SKILL.md').write_text('new')
    def plan(self):return sync.make_plan(self.a,self.b,['SKILL.md'])
    def test_create_and_verify(self):
        result=sync.apply_plan(self.plan())
        self.assertEqual(result['updated'],1);self.assertEqual((self.b/'SKILL.md').read_text(),'new')
    def test_idempotent(self):
        sync.apply_plan(self.plan());self.assertEqual(sync.apply_plan(self.plan())['updated'],0)
    def test_stale_source(self):
        p=self.plan();(self.a/'SKILL.md').write_text('changed')
        with self.assertRaises(ValueError):sync.apply_plan(p)
        self.assertFalse((self.b/'SKILL.md').exists())
    def test_preserve_concurrent_destination(self):
        p=self.plan();(self.b/'SKILL.md').write_text('my edit')
        with self.assertRaises(ValueError):sync.apply_plan(p)
        self.assertEqual((self.b/'SKILL.md').read_text(),'my edit')
    def test_shared_preserves_entrypoint(self):
        with self.assertRaises(ValueError):sync.make_plan(self.a,self.b,['SKILL.md'],'shared')
    def test_shared_does_not_merge_independent_case_numbering(self):
        self.assertFalse(sync.shared('cases/099-another-history/lessons.md'))
    def test_traversal_and_git(self):
        for name in ['../outside','.git/config','C:/outside','tools/../../outside','a\\b']:
            with self.subTest(name=name),self.assertRaises(ValueError):sync.inside(self.b,name)
    def test_nested_roots(self):
        with self.assertRaises(ValueError):sync.make_plan(self.a,self.a/'nested',['SKILL.md'])
    def test_rollback_failed_publish(self):
        (self.a/'other').write_text('more');(self.b/'SKILL.md').write_text('old')
        p=sync.make_plan(self.a,self.b,['SKILL.md','other'])
        replace=sync.os.replace;calls=0
        def fail(src,dst):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('injected publish error')
            return replace(src,dst)
        with patch.object(sync.os,'replace',side_effect=fail),self.assertRaises(OSError):sync.apply_plan(p)
        self.assertEqual((self.b/'SKILL.md').read_text(),'old');self.assertFalse((self.b/'other').exists())
        self.assertFalse(list(self.b.glob('.1codex-*')))

if __name__=='__main__': unittest.main()
