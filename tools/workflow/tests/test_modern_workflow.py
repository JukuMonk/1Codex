import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(TOOLS))
import project_cli as cli
import edt_lib
import bsl_checks
import skd_builder
import release_policy
import case_catalog
sys.path.insert(0,str(TOOLS.parent/'tests/designer'))
import skd_samples
import shutil
import new_project
from workflow import timing
from workflow.analyze_timing import analyze, exclusive_stages
from workflow.learning import compare_runs


class ModernTests(unittest.TestCase):
    def test_case_evidence_hash_is_checkout_portable(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'lesson.md'
            path.write_bytes('Урок\nСтрока\n'.encode('utf-8'))
            expected=case_catalog.evidence_digest(path)
            path.write_bytes('Урок\r\nСтрока\r\n'.encode('utf-8-sig'))
            self.assertEqual(case_catalog.evidence_digest(path),expected)
            path.write_bytes('Урок\r\nДругая строка\r\n'.encode('utf-8-sig'))
            self.assertNotEqual(case_catalog.evidence_digest(path),expected)

    def test_bootstrap_is_relocatable_preserves_settings_and_compares_deployment(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';project=root/'project'
            fixture=TOOLS.parent/'tests/designer/fixtures/configuration'
            shutil.copytree(fixture,source)
            new_project.designer_main(str(source),str(project),'тст','Проверка',None,None)
            instructions=(project/'AGENTS.md').read_text(encoding='utf-8')
            self.assertNotIn(str(TOOLS.parent),instructions)
            self.assertNotIn('{{',instructions)
            self.assertFalse(cli.compare(source,fixture)['errors'])
            settings=project/'platform.json';settings.write_text('{"keep":true}',encoding='utf-8')
            new_project.designer_main(str(source),str(project),'тст','Проверка',None,None)
            self.assertEqual(json.loads(settings.read_text(encoding='utf-8')),{'keep':True})

    def test_skd_byte_parity_with_recorded_pre_refactor_baseline(self):
        baseline=json.loads((TOOLS.parent/'tests/designer/fixtures/skd-baseline.json').read_text(encoding='utf-8'))
        actual={k:hashlib.sha256(v.encode('utf-8')).hexdigest() for k,v in skd_samples.outputs(skd_builder).items()}
        self.assertEqual(actual,baseline['sha256'])

    def test_stable_version_must_increase(self):
        self.assertEqual(release_policy.validate('1.10.0','1.9.9'),(1,10,0))
        for candidate in ('1.9.9','1.8.0','01.10.0','1.10','main','1.10.0-beta'):
            with self.assertRaises(ValueError):release_policy.validate(candidate,'1.9.9')

    def test_catalog_keeps_reviewed_metadata_and_detects_evidence_change(self):
        data=case_catalog.build();row=data['cases'][0]
        row.update(platform_build='8.3.27.2325',regression_tests=['manual-example'],format='shared',classification_reviewed=True)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'catalog.json';path.write_text(json.dumps(data),encoding='utf-8')
            with patch.object(case_catalog,'CATALOG',path):rebuilt=case_catalog.build()
        self.assertEqual(rebuilt['cases'][0]['platform_build'],'8.3.27.2325')
        self.assertEqual(rebuilt['cases'][0]['format'],'shared')
        self.assertEqual(rebuilt['cases'][0]['regression_tests'],['manual-example'])
        rebuilt['cases'][0]['evidence'][0]['sha256']='0'*64
        self.assertTrue(any('Evidence changed' in s for s in case_catalog.validate(rebuilt)))

    def test_timing_dispersion_is_robust_to_outlier(self):
        with tempfile.TemporaryDirectory() as temp:
            paths=[]
            for seconds in (1,2,3,4,100):
                path=timing.create(temp,'spread',scenario='s',environment='e',dataset='d',revision='r')
                timing.finish(path)
                with timing.journal(path) as data:data['elapsed_seconds']=seconds
                paths.append(path)
            stats=analyze(paths)['groups'][0]['revisions']['r']
            self.assertEqual(stats['median_seconds'],3)
            self.assertEqual(stats['mad_seconds'],1)
            self.assertEqual(stats['max_seconds'],100)

    def test_shared_api_aliases_preserve_identity(self):
        self.assertIs(edt_lib.check_bsl,bsl_checks.check_bsl)
        self.assertIs(edt_lib.dcs_schema,skd_builder.dcs_schema)
        self.assertIs(edt_lib.dcs_schema_ex,skd_builder.dcs_schema_ex)
        self.assertTrue(bsl_checks.check_bsl('А=Справочники.X.ПустаяСсылка;',False))

    def test_platform_import_exposes_stdlib_without_cli_side_effects(self):
        result=subprocess.run([sys.executable,'-c',"import sys;sys.path.insert(0,sys.argv[1]);import platform,uuid;assert platform.system();print(uuid.uuid4())",str(TOOLS)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_doctor_readonly_missing_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(cli,'doctor',wraps=cli.doctor):
                data=cli.doctor({'dump':str(Path(temp)/'absent')})
            self.assertFalse(data['ready_for_platform'])
            self.assertFalse((Path(temp)/'absent').exists())

    def test_settings_refuse_production_and_vendor_full_load(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';source.mkdir();base=root/'base';base.mkdir()
            (base/'1Cv8.1CD').write_bytes(b'fixture');v8=root/'1cv8.exe';v8.write_bytes(b'fixture')
            cfg={'dump':str(source),'work':str(root/'work'),'v8':str(v8),'test_ib':str(base),
                 'configuration_kind':'vendor','metadata_version':'2.20'}
            with self.assertRaisesRegex(ValueError,'delta'):cli.validate_settings(cfg)
            cfg.update(configuration_kind='own',production_ib=str(base))
            with self.assertRaisesRegex(ValueError,'production'):cli.validate_settings(cfg)

    def test_compare_detects_file_loss_and_content_change(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=Path(temp)/'a',Path(temp)/'b';a.mkdir();b.mkdir()
            (a/'Module.bsl').write_text('old');(b/'Module.bsl').write_text('new')
            (a/'needed.xml').write_text('<r/>')
            self.assertEqual(len(cli.compare(a,b)['errors']),2)

    def test_clock_backwards_marks_invalid(self):
        with tempfile.TemporaryDirectory() as temp:
            path=timing.create(temp,'clock',scenario='s',environment='e',dataset='d')
            with patch.object(timing,'stamp',return_value='2026-11-02T10:00:00+00:00'): phase=timing.begin(path,'x')
            with patch.object(timing,'stamp',return_value='2026-11-02T09:00:00+00:00'):timing.end(path,phase)
            timing.finish(path)
            result=analyze([path]);self.assertEqual(len(result['invalid_runs']),1)

    def test_exclusive_intervals_subtract_child_union(self):
        def row(id,parent,start,end):return {'stage_id':id,'parent_id':parent,'name':id,'status':'ok',
            'started_at':f'2026-11-02T00:00:{start:02d}+00:00','ended_at':f'2026-11-02T00:00:{end:02d}+00:00'}
        data={'stages':[row('p',None,0,20),row('a','p',2,10),row('b','p',5,15)]}
        self.assertEqual(exclusive_stages(data)[0]['exclusive_seconds'],7)

    def test_learning_keeps_failures_and_does_not_mix_datasets(self):
        with tempfile.TemporaryDirectory() as temp:
            paths=[]
            for revision,seconds,status in [('old',10,'ok')]*5+[('new',8,'ok')]*5+[('new',1,'failed')]:
                path=timing.create(temp,'benchmark',scenario='s',environment='e',dataset='d',revision=revision)
                data=json.loads(path.read_text(encoding='utf-8'))
                data.update(status=status,elapsed_seconds=seconds)
                path.write_text(json.dumps(data),encoding='utf-8');paths.append(path)
            comparison=compare_runs(paths,'old','new')['comparisons'][0]
            self.assertEqual(comparison['decision'],'quality_regression')
            extra=timing.create(temp,'another',scenario='s',environment='e',dataset='other',revision='new')
            timing.finish(extra);paths.append(extra)
            self.assertEqual(len(analyze(paths)['groups']),2)

    def test_learning_insufficient_samples(self):
        with tempfile.TemporaryDirectory() as temp:
            paths=[]
            for revision in ('old','new'):
                path=timing.create(temp,'b',scenario='s',environment='e',dataset='d',revision=revision)
                timing.finish(path);paths.append(path)
            self.assertEqual(compare_runs(paths,'old','new')['comparisons'][0]['decision'],'insufficient_samples')
