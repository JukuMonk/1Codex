import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verification import (TestSpec, select_tests, VerificationCache, VerificationError,
                          ReleaseSession, contained)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('tests/a.py', 'tests/b.py', 'source/a.bsl', 'source/b.bsl', 'source/common.bsl',
                     'reports/report.md', 'evidence/a.json', 'evidence/backup.bin'):
            p = self.root/name;p.parent.mkdir(parents=True, exist_ok=True);p.write_text(name,encoding='utf-8')
        self.spec = TestSpec('a','tests/a.py',('source/a.bsl','source/common.bsl'))
        self.other = TestSpec('b','tests/b.py',('source/b.bsl','source/common.bsl'))
        self.context = {k:k+'-1' for k in ('source','environment','database','configuration','schema','data','revision','dataset')}


class SelectionTests(Fixture):
    def test_report_change_selects_no_1c_checks(self):
        self.assertEqual(select_tests(['reports/report.md'],[self.spec,self.other],('reports/*',)),[])

    def test_shared_module_invalidates_both(self):
        self.assertEqual(select_tests(['source/common.bsl'],[self.spec,self.other]),[self.spec,self.other])

    def test_script_and_owned_source_select_target(self):
        for path in ('tests/a.py','source/a.bsl'):
            self.assertEqual(select_tests([path],[self.spec,self.other]),[self.spec])

    def test_unknown_change_or_dependencies_is_conservative(self):
        self.assertEqual(select_tests(['source/new.bsl'],[self.spec,self.other]),[self.spec,self.other])
        unknown=TestSpec('unknown','tests/b.py',None)
        self.assertEqual(select_tests(['source/a.bsl'],[self.spec,unknown]),[self.spec,unknown])

    def test_duplicate_or_unsafe_path_rejected(self):
        with self.assertRaises(VerificationError):select_tests(['source/a.bsl'],[self.spec,self.spec])
        for value in ('../a','C:/file','/file'):
            with self.assertRaises(VerificationError):TestSpec('a',value,())


class CacheTests(Fixture):
    def setUp(self):
        super().setUp();self.cache=VerificationCache(self.root)
        self.cache.record(self.spec,self.context,['evidence/a.json'])

    def test_success_reused_but_report_edit_does_not_invalidate(self):
        (self.root/'reports/report.md').write_text('changed')
        self.assertTrue(self.cache.can_reuse(self.spec,self.context))

    def test_directory_glob_tracks_all_files_and_new_files_invalidate(self):
        spec=TestSpec('subtree','tests/a.py',('source/**',))
        self.cache.record(spec,self.context,['evidence/a.json'])
        self.assertTrue(self.cache.can_reuse(spec,self.context))
        (self.root/'source/new.bsl').write_text('new')
        self.assertFalse(self.cache.can_reuse(spec,self.context))

    def test_each_context_field_invalidates(self):
        for key in self.context:
            changed=dict(self.context);changed[key]='changed'
            self.assertFalse(self.cache.can_reuse(self.spec,changed),key)

    def test_script_dependency_and_evidence_mutations_invalidate(self):
        for name in ('tests/a.py','source/common.bsl','evidence/a.json'):
            p=self.root/name;old=p.read_bytes();p.write_bytes(b'changed')
            self.assertFalse(self.cache.can_reuse(self.spec,self.context),name)
            p.write_bytes(old)

    def test_failed_result_never_reused(self):
        self.cache.record(self.spec,self.context,[],status='failed')
        self.assertFalse(self.cache.can_reuse(self.spec,self.context))

    def test_missing_context_evidence_or_dependency_is_not_reused(self):
        self.assertFalse(self.cache.can_reuse(self.spec,{}))
        (self.root/'source/a.bsl').unlink()
        self.assertFalse(self.cache.can_reuse(self.spec,self.context))
        with self.assertRaises(VerificationError):self.cache.record(self.other,self.context,[])

    def test_forged_record_and_evidence_path_rejected(self):
        envelope=json.loads(self.cache.store.path.read_text())
        envelope['data']['a']['status']='failed'
        self.cache.store.path.write_text(json.dumps(envelope))
        self.assertFalse(self.cache.can_reuse(self.spec,self.context))
        with self.assertRaises(VerificationError):self.cache.store.read()
        with self.assertRaises(VerificationError):contained(self.root,'../secret')


class ResumeTests(Fixture):
    def setUp(self):
        super().setUp();self.now=1000;self.calls=[]

    def session(self):return ReleaseSession(self.root,'release1',lambda:dict(self.context),clock=lambda:self.now,max_backup_age=100)

    def run_prefix(self, session):
        session.run('backup',lambda:self.calls.append('backup'),evidence=['evidence/backup.bin'],backup=True)
        session.run('check',lambda:self.calls.append('check'),evidence=['evidence/a.json'])

    def test_resume_reuses_prefix_but_always_checks_final_integrity(self):
        a=self.session();self.run_prefix(a);a.finish(lambda:self.calls.append('integrity'))
        b=self.session();self.run_prefix(b);b.finish(lambda:self.calls.append('integrity'))
        self.assertEqual(self.calls,['backup','check','integrity','integrity'])

    def test_legitimate_load_transition_requires_explicit_expected_context(self):
        a=self.session()
        a.run('backup',lambda:None,evidence=['evidence/backup.bin'],backup=True)
        expected=dict(self.context,schema='loaded')
        a.run('load',lambda:self.context.update(schema='loaded'),evidence=['evidence/a.json'],expected_after=expected)
        a.finish(lambda:None)
        b=self.session()
        self.assertEqual(b.run('backup',lambda:self.fail('backup must be reused'),evidence=['evidence/backup.bin'],backup=True),'reused')
        self.assertEqual(b.run('load',lambda:self.fail('load must be reused'),evidence=['evidence/a.json'],expected_after=expected),'reused')
        b.finish(lambda:None)

    def test_stale_source_environment_database_schema_data_rerun_prefix(self):
        for key in ('source','revision','environment','database','schema','data','configuration','dataset'):
            a=self.session();self.run_prefix(a)
            self.context[key]+='-changed'
            b=self.session();before=len(self.calls);self.run_prefix(b)
            self.assertEqual(len(self.calls)-before,2,key)

    def test_expired_or_mutated_backup_requires_new_backup(self):
        a=self.session();self.run_prefix(a)
        self.now+=101
        b=self.session();before=len(self.calls);self.run_prefix(b)
        self.assertEqual(len(self.calls)-before,2)
        (self.root/'evidence/backup.bin').write_bytes(b'changed')
        c=self.session();before=len(self.calls);self.run_prefix(c)
        self.assertEqual(len(self.calls)-before,2)

    def test_callback_mutation_and_exception_cannot_form_successful_checkpoint(self):
        a=self.session()
        with self.assertRaises(VerificationError):
            a.run('backup',lambda:self.context.update(data='surprise'),evidence=['evidence/backup.bin'],backup=True)
        with self.assertRaises(VerificationError):a.finish(lambda:None)
        b=self.session()
        def crash():raise RuntimeError('private command must not be serialized')
        with self.assertRaises(RuntimeError):b.run('backup',crash,evidence=['evidence/backup.bin'],backup=True)
        self.assertNotIn('private command',b.store.path.read_text())

    def test_changes_between_stages_and_final_integrity_rejected(self):
        a=self.session();self.run_prefix(a);self.context['data']='changed'
        with self.assertRaises(VerificationError):a.run('extra',lambda:None,evidence=['evidence/a.json'])
        with self.assertRaises(VerificationError):a.finish(lambda:None)

    def test_final_requires_fresh_backup_and_refuses_mutating_integrity(self):
        a=self.session();a.run('check',lambda:None,evidence=['evidence/a.json'])
        with self.assertRaises(VerificationError):a.finish(lambda:None)
        b=self.session();self.run_prefix(b)
        with self.assertRaises(VerificationError):b.finish(lambda:self.context.update(data='changed'))

    def test_missing_evidence_reruns_and_missing_result_is_not_successful(self):
        a=self.session();self.run_prefix(a)
        path=self.root/'evidence/a.json';path.unlink()
        b=self.session()
        self.assertEqual(b.run('backup',lambda:None,evidence=['evidence/backup.bin'],backup=True),'reused')
        def restore():path.write_text('new evidence')
        self.assertEqual(b.run('check',restore,evidence=['evidence/a.json']),'executed')
        c=self.session()
        c.run('backup',lambda:None,evidence=['evidence/backup.bin'],backup=True)
        path.write_text('force checkpoint refresh')
        with self.assertRaises(VerificationError):
            c.run('check',lambda:path.unlink(),evidence=['evidence/a.json'])
        self.assertEqual(c.store.read()['stages'][-1]['status'],'running')

    def test_backup_and_evidence_rechecked_before_and_after_integrity(self):
        a=self.session();self.run_prefix(a)
        path=self.root/'evidence/backup.bin';old=path.read_bytes();path.write_bytes(b'corrupt')
        with self.assertRaises(VerificationError):a.finish(lambda:None)
        path.write_bytes(old)
        with self.assertRaises(VerificationError):a.finish(lambda:path.unlink())

    def test_explicit_data_transition_and_resume_actual_physical_hash(self):
        a=self.session()
        a.run('backup',lambda:None,evidence=['evidence/backup.bin'],backup=True)
        old=dict(self.context)
        policy=Mock(return_value=True)
        a.run('compile',lambda:self.context.update(data='physical-cache-written'),
              evidence=['evidence/a.json'],transition=policy)
        self.assertEqual(policy.call_args.args,(old,self.context))
        self.assertEqual(a.store.read()['context']['data'],'physical-cache-written')
        a.finish(lambda:None)
        b=self.session()
        b.run('backup',lambda:self.fail('backup reused'),evidence=['evidence/backup.bin'],backup=True)
        self.assertEqual(b.run('compile',lambda:self.fail('compile reused'),
            evidence=['evidence/a.json'],transition=policy),'reused')
        b.finish(lambda:None)

    def test_data_policy_cannot_authorize_source_environment_or_schema_changes(self):
        for key in self.context:
            if key=='data':continue
            a=ReleaseSession(self.root,'reject-'+key,lambda:dict(self.context),clock=lambda:self.now)
            a.run('backup',lambda:None,evidence=['evidence/backup.bin'],backup=True)
            policy=Mock(return_value=True)
            with self.assertRaises(VerificationError):
                a.run('compile',lambda:self.context.update({key:key+'-changed'}),
                      evidence=['evidence/a.json'],transition=policy)
            policy.assert_not_called()
            self.assertEqual(a.store.read()['stages'][-1]['status'],'failed')

    def test_false_or_raising_policy_and_false_operation_are_failed(self):
        policies=[lambda before,after:False,lambda before,after:None]
        def crash(before,after):raise RuntimeError('private validator exception')
        policies.append(crash)
        for i,policy in enumerate(policies):
            a=ReleaseSession(self.root,'policy-'+str(i),lambda:dict(self.context),clock=lambda:self.now)
            with self.assertRaises((VerificationError,RuntimeError)):
                a.run('compile',lambda:self.context.update(data='cache-'+str(i)),
                      evidence=['evidence/a.json'],transition=policy)
            self.assertEqual(a.store.read()['stages'][-1]['status'],'failed')
            self.assertNotIn('private validator exception',a.store.path.read_text())
        a=self.session()
        with self.assertRaises(VerificationError):
            a.run('compile',lambda:False,evidence=['evidence/a.json'],transition=lambda b,a:True)
        with self.assertRaises(VerificationError):a.finish(lambda:None)

    def test_policy_mutation_cannot_forge_success_and_bad_arguments_do_not_run(self):
        a=self.session()
        def mutate(before,after):
            before['source']='forged';after['source']='forged'
            self.context['source']='also changed'
            return True
        with self.assertRaises(VerificationError):
            a.run('compile',lambda:self.context.update(data='cache'),
                  evidence=['evidence/a.json'],transition=mutate)
        self.assertNotEqual(a.store.read()['stages'][-1]['before']['source'],'forged')
        callback=Mock()
        for kwargs in ({'transition':True},{'transition':lambda b,a:True,'expected_after':self.context}):
            with self.assertRaises(VerificationError):a.run('compile',callback,evidence=['evidence/a.json'],**kwargs)
        callback.assert_not_called()


if __name__=='__main__':unittest.main()
