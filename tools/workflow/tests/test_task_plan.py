import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys

from tools.workflow import task_plan as plan, timing


def card(id='OP01', **kwargs):
    value = dict(id=id, requirement='Requirement '+str(id), objects=['Forms/A.xml'],
                 acceptance=['Observable result'], uncertainties=[], tests=['unit'], limitations=[])
    value.update(kwargs)
    return value


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # Windows runners may expose TEMP as RUNNER~1 while timing resolves
        # the full path. Compare the same canonical directory in either case.
        self.root = Path(self.temp.name).resolve()
        self.path = self.root/'task.json'
        plan.create(self.path,'Task',[card(),card('OP02')],'rev1',self.root)
        self.journal = timing.create(self.root,'test')
        self.artifact = self.root/'proof.json'
        self.artifact.write_text('{"passed":true}',encoding='utf-8')

    def data(self):
        return json.loads(self.path.read_text(encoding='utf-8'))

    def evidence(self,point='OP01',status='passed',**kwargs):
        return plan.record_evidence(self.path,point,'unit','static',status,self.artifact,**kwargs)

    def point(self,id='OP01'):
        return next(row for row in plan.report(self.path)['points'] if row['id']==id)

    def test_cards_validate_ids_and_required_fields(self):
        for invalid in ('../OP1','OP 1','', '__shared__', 1, None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                plan.create(self.root/'other.json','Task',[card(invalid)],'r')
        for values in ([card(),card()], [card(acceptance=[])], [card(objects=['x','x'])], [card(password='secret')]):
            with self.subTest(values=values),self.assertRaises(ValueError):
                plan.create(self.root/'other.json','Task',values,'r')

    def test_create_is_exclusive_and_bounded(self):
        with self.assertRaises(FileExistsError):
            plan.create(self.path,'Task',[card()],'r',self.root)
        with self.assertRaises(ValueError):
            plan.create(self.root.parent/'escape.json','Task',[card()],'r',self.root)

    def test_timing_compatibility_and_explicit_failure_kind(self):
        legacy = timing.begin(self.journal,'legacy')
        timing.end(self.journal,legacy)
        stage = plan.begin_stage(self.path,self.journal,'OP01','ui')
        with self.assertRaises(ValueError):
            plan.end_stage(self.path,self.journal,stage,'failed')
        plan.end_stage(self.path,self.journal,stage,'failed','tool')
        record = plan.report(self.path)['timing']
        self.assertEqual(record['failures'][0]['kind'],'tool')
        self.assertEqual(record['failures'][0]['point_id'],'OP01')
        timing.finish(self.journal)

    def test_unknown_and_closed_stage_rejected(self):
        with self.assertRaises(ValueError):
            plan.begin_stage(self.path,self.journal,'UNKNOWN','analysis')
        with self.assertRaises(ValueError):
            plan.begin_stage(self.path,self.journal,'OP01','invented')
        with self.assertRaises(ValueError):
            plan.end_stage(self.path,self.journal,'UNKNOWN')
        stage = plan.begin_stage(self.path,self.journal,'OP01','analysis')
        plan.end_stage(self.path,self.journal,stage)
        with self.assertRaises(ValueError):
            plan.end_stage(self.path,self.journal,stage)
        timing.finish(self.journal)
        with self.assertRaises(ValueError):
            plan.begin_stage(self.path,self.journal,'OP01','analysis')

    def test_parent_must_be_running_and_same_task(self):
        parent = plan.begin_stage(self.path,self.journal,'__shared__','implementation')
        child = plan.begin_stage(self.path,self.journal,'OP01','static',parent=parent)
        with self.assertRaises(ValueError):
            plan.end_stage(self.path,self.journal,parent)
        plan.end_stage(self.path,self.journal,child)
        plan.end_stage(self.path,self.journal,parent)
        with self.assertRaises(ValueError):
            plan.begin_stage(self.path,self.journal,'OP01','ui',parent=parent)
        other = self.root/'other.json'
        plan.create(other,'Other',[card()],'r',self.root)
        foreign = plan.begin_stage(other,self.journal,'OP01','analysis')
        with self.assertRaises(ValueError):
            plan.end_stage(self.path,self.journal,foreign)
        with self.assertRaises(ValueError):
            plan.begin_stage(self.path,self.journal,'OP01','ui',parent=foreign)

    def test_research_checkpoint_is_not_cancellation(self):
        stage=plan.begin_stage(self.path,self.journal,'OP01','research',budget_seconds=60)
        record=json.loads(self.journal.read_text(encoding='utf-8'))
        item=record['stages'][0]
        item['started_at']='2026-01-01T00:00:00+00:00'
        self.journal.write_text(json.dumps(record),encoding='utf-8')
        self.assertEqual(plan.research_checkpoint(self.path,self.journal,stage,now='2026-01-01T00:00:30+00:00')['action'],'within_budget')
        self.assertEqual(plan.research_checkpoint(self.path,self.journal,stage,now='2026-01-01T00:01:00+00:00')['action'],'needs_probe')
        self.assertEqual(plan.research_checkpoint(self.path,self.journal,stage,'Minimal probe in progress',now='2026-01-01T00:01:01+00:00')['action'],'continue_with_reason')
        self.assertEqual(json.loads(self.journal.read_text())['stages'][0]['status'],'running')
        with self.assertRaises(ValueError):
            plan.research_checkpoint(self.path,self.journal,stage,now='2025-01-01T00:00:00+00:00')

    def test_research_limits_validated(self):
        for phase,budget in [('analysis',60),('research',0),('research',True),('research',float('nan')),('research',float('inf'))]:
            with self.subTest(phase=phase,budget=budget),self.assertRaises(ValueError):
                plan.begin_stage(self.path,self.journal,'OP01',phase,budget_seconds=budget)
        stage=plan.begin_stage(self.path,self.journal,'OP01','research')
        with self.assertRaises(ValueError):
            plan.research_checkpoint(self.path,self.journal,stage)
        plan.end_stage(self.path,self.journal,stage)
        with self.assertRaises(ValueError):
            plan.research_checkpoint(self.path,self.journal,stage)

    def test_no_proof_does_not_complete_point(self):
        self.assertEqual(self.point()['status'],'unverified')
        with timing.journal(self.path) as data:
            data['points'][0]['tests']=[]
        self.assertEqual(self.point()['status'],'unverified')

    def test_evidence_is_assigned_and_project_bounded(self):
        for point,test in [('NO','unit'),('OP01','other'),('__shared__','unit')]:
            with self.subTest(point=point,test=test),self.assertRaises(ValueError):
                plan.record_evidence(self.path,point,test,'static','passed',self.artifact)
        with self.assertRaises(ValueError):
            plan.record_evidence(self.path,'OP01','unit','static','passed',self.root.parent/'outside.log')
        with self.assertRaises(ValueError):
            plan.record_evidence(self.path,'OP01','unit','static','passed',self.root/'missing.log')
        with self.assertRaises(ValueError):
            plan.record_evidence(self.path,'OP01','unit','static','passed',self.root)
        with self.assertRaises(ValueError):
            plan.record_evidence(self.path,'OP01','unit','static','passed',self.path)

    def test_manifest_cannot_be_timing_journal(self):
        with self.assertRaises(ValueError):
            plan.begin_stage(self.path,self.path,'OP01','analysis')

    def test_pass_failure_and_recovery_are_preserved(self):
        self.evidence()
        self.assertEqual(self.point()['status'],'verified')
        self.evidence(status='failed')
        self.assertEqual(self.point()['status'],'failed')
        self.evidence()
        self.assertEqual(self.point()['status'],'verified')
        self.assertEqual(len(self.data()['evidence']),3)

    def test_artifact_changes_invalidate_old_proof(self):
        self.evidence()
        self.artifact.write_text('changed',encoding='utf-8')
        self.assertEqual(self.point()['status'],'unverified')
        self.assertIn('changed artifact',self.point()['evidence_problems'][0])
        self.artifact.unlink()
        self.assertIn('missing artifact',self.point()['evidence_problems'][0])

    def test_revision_changes_invalidate_old_proof(self):
        self.evidence()
        plan.set_revision(self.path,'rev2')
        self.assertEqual(self.point()['status'],'unverified')
        self.assertIn('stale revision',self.point()['evidence_problems'][0])
        self.evidence()
        self.assertEqual(self.point()['status'],'verified')

    def test_limitations_are_explicit_in_status(self):
        self.evidence(limitations=['Native keys not tested'])
        self.assertEqual(self.point()['status'],'limited')
        self.assertEqual(self.point()['effective_limitations'],['Native keys not tested'])

    def test_closed_manifest_cannot_accept_more_results(self):
        with timing.journal(self.path) as data:
            data['status']='closed'
        with self.assertRaises(ValueError):self.evidence()
        with self.assertRaises(ValueError):plan.set_revision(self.path,'rev2')
        with self.assertRaises(ValueError):plan.begin_stage(self.path,self.journal,'OP01','analysis')

    def test_nested_parallel_timing_and_shared_costs(self):
        task=self.data()
        def stage(id,point,a,b,parent=None):
            return dict(stage_id=id,parent_id=parent,task_id=task['task_id'],point_id=point,phase='implementation',
                status='ok',started_at=f'2026-01-01T00:00:{a:02d}+00:00',ended_at=f'2026-01-01T00:00:{b:02d}+00:00')
        with timing.journal(self.path) as data:
            data['journals']=[self.journal.relative_to(self.root).as_posix()]
        record=json.loads(self.journal.read_text())
        record['stages']=[stage('shared','__shared__',0,20),stage('a','OP01',2,8,'shared'),stage('b','OP02',6,12,'shared')]
        self.journal.write_text(json.dumps(record),encoding='utf-8')
        result=plan.report(self.path)['timing']
        self.assertEqual(result['covered_seconds'],20)
        self.assertEqual(result['shared_seconds'],10)
        self.assertEqual(result['by_point_seconds']['OP01'],6)
        self.assertEqual(result['by_point_seconds']['OP02'],6)
        # Point totals overlap. Never report their sum (22) as elapsed (20).
        record['stages'][2]['point_id']='OP01'
        self.journal.write_text(json.dumps(record),encoding='utf-8')
        self.assertEqual(plan.report(self.path)['timing']['by_point_seconds']['OP01'],10)

    def test_unknown_timing_point_and_clock_rejected(self):
        stage=plan.begin_stage(self.path,self.journal,'OP01','analysis')
        self.assertEqual(plan.report(self.path)['timing']['unfinished_stages'],[stage])
        plan.end_stage(self.path,self.journal,stage)
        record=json.loads(self.journal.read_text())
        record['stages'][0]['clock_valid']=False
        self.journal.write_text(json.dumps(record),encoding='utf-8')
        with self.assertRaises(ValueError):plan.report(self.path)

    def test_reports_escape_inputs_and_share_derived_status(self):
        with timing.journal(self.path) as data:
            data['title']='<script>alert(1)</script>'
            data['points'][0]['requirement']='A | <img src=x onerror=alert(1)>'
        self.evidence()
        for format,suffix in [('json','json'),('html','html'),('markdown','md')]:
            out=plan.render_report(self.path,self.root/('report.'+suffix),format)
            text=out.read_text(encoding='utf-8')
            self.assertIn('verified',text)
            self.assertIn('unverified',text)
            if format!='json':
                self.assertNotIn('<script>',text)
                self.assertNotIn('<img src=x',text)
                self.assertIn('&lt;',text)

    def test_reports_cannot_overwrite_source_proof_or_escape(self):
        self.evidence()
        plan.begin_stage(self.path,self.journal,'OP01','analysis')
        for target in (self.path,self.journal,self.artifact,self.root.parent/'outside.html'):
            with self.subTest(target=target),self.assertRaises(ValueError):
                plan.render_report(self.path,target,'html')

    def test_cli_creates_times_records_and_renders_same_task(self):
        manifest=self.root/'cli.json'
        cards=self.root/'cards.json'
        cards.write_text(json.dumps([card()]),encoding='utf-8')
        script=str(Path(plan.__file__))
        def run(*args):
            result=subprocess.run([sys.executable,script,*map(str,args)],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stderr)
            return result.stdout.strip()
        run('create',manifest,'--title','CLI task','--points',cards,'--revision','r','--project',self.root)
        stage=run('begin',manifest,self.journal,'--point','OP01','--phase','implementation')
        run('end',manifest,self.journal,stage)
        run('evidence',manifest,'--point','OP01','--test','unit','--level','static','--status','passed','--artifact',self.artifact)
        target=self.root/'cli-report.json'
        run('report',manifest,'--output',target)
        result=json.loads(target.read_text(encoding='utf-8'))
        self.assertEqual(result['counts']['verified'],1)
        self.assertIn('OP01',result['timing']['by_point_seconds'])


if __name__=='__main__':unittest.main()
