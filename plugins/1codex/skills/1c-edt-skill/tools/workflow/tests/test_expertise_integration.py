import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.workflow import expertise as ex, expertise_cli as cli, task_plan, timing, pipeline


class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root/'source';self.source.mkdir()
        (self.source/'Module.bsl').write_text('Первая строка\nВторая строка\n',encoding='utf-8')
        self.plan = self.root/'task-plan.json'
        task_plan.create(self.plan,'Test',[{'id':p,'requirement':'Требование '+p,'acceptance':['Результат']} for p in ['P1','P2']],'r1',self.root)
        self.journal = timing.create(self.root,'Expertise')
        self.work = self.root/'.platform/expertise/test'
        ex.initialize(self.work,self.source,'Test profile',task_plan=self.plan,journal=self.journal)
        task_plan.attach_expertise(self.plan,self.work)
        self.review = {'mode':'quick','summary':'Требования согласованы','findings':[], 'questions':[],
            'points':[{'id':p,'next_action':'Выполнить доработку'} for p in ['P1','P2']],
            'checked_sources':[{'path':'source/Module.bsl','first':1,'last':1}],
            'limitations':['COM и UI ещё не выполнялись']}

    def prepare(self):
        cli.start(self.work);cli.read(self.work,'source/Module.bsl',1,1)

    def test_plan_gate_requires_actual_review_and_preserves_legacy(self):
        with self.assertRaises(ValueError):
            task_plan.begin_stage(self.plan,self.journal,'P1','implementation')
        analysis=task_plan.begin_stage(self.plan,self.journal,'P1','analysis')
        task_plan.end_stage(self.plan,self.journal,analysis)
        self.prepare();cli.submit(self.work,self.review)
        stage=task_plan.begin_stage(self.plan,self.journal,'P1','implementation')
        task_plan.end_stage(self.plan,self.journal,stage)
        data=ex.load(self.plan);data['points'][0]['requirement']='Изменённое требование';ex.save(self.plan,data)
        with self.assertRaises(ValueError):
            task_plan.begin_stage(self.plan,self.journal,'P1','implementation')
        independent=task_plan.begin_stage(self.plan,self.journal,'P2','implementation')
        task_plan.end_stage(self.plan,self.journal,independent)
        with self.assertRaises(ValueError):
            task_plan.begin_stage(self.plan,self.journal,'__shared__','implementation')

    def test_reads_live_source_changes_and_refuses_stale_submission(self):
        self.prepare()
        (self.source/'Module.bsl').write_text('Изменено',encoding='utf-8')
        with self.assertRaises(ValueError):cli.submit(self.work,self.review)
        self.assertFalse(list((self.work/'.review').glob('review-*.json')))
        self.prepare();cli.submit(self.work,self.review)
        self.assertEqual(ex.readiness(self.work,ex.latest(self.work))['P1'],'ready')

    def test_partial_reads_repeats_and_evidence_validation(self):
        self.prepare();cli.read(self.work,'source/Module.bsl',1,1)
        totals=ex.load(self.work/'session.json')['read_totals']
        self.assertEqual(totals['repeat_lines'],1)
        self.assertEqual(totals['repeat_bytes'],len('Первая строка\n'.encode()))
        self.review['checked_sources'][0]['last']=2
        with self.assertRaises(ValueError):cli.submit(self.work,self.review)
        cli.read(self.work,'source/Module.bsl',2,2);cli.submit(self.work,self.review)
        data=ex.load(self.journal)
        self.assertEqual(sum(s['status']=='failed' for s in data['stages']),1)
        self.assertFalse(any(s['status']=='running' for s in data['stages']))

    def test_search_is_bounded_and_cannot_escape(self):
        (self.source/'Module.bsl').write_text('Найти\n'*200,encoding='utf-8')
        self.prepare()
        with self.assertRaises(ValueError):cli.read(self.work,'source/Module.bsl',1,200)
        with self.assertRaises(ValueError):cli.read(self.work,'source/../../task-plan.json')
        result=cli.search(self.work,'Найти')
        self.assertTrue(0<len(result['matches'])<=20)

    def test_restart_closes_old_attempt_and_monitor_exports_new_graph(self):
        self.prepare();self.prepare();cli.submit(self.work,self.review)
        data=ex.load(self.journal)
        self.assertEqual(sum(s['status']=='interrupted' for s in data['stages']),1)
        self.assertFalse(any(s['status']=='running' for s in data['stages']))
        timing.finish(self.journal)
        html=pipeline.page(pipeline.read_state(self.journal),False)
        self.assertIn('Экспертиза задачи',html)
        self.assertIn('expertise.review',html)

    def test_wrong_plan_binding_rejected(self):
        self.prepare();cli.submit(self.work,self.review)
        other=self.root/'other.json'
        task_plan.create(other,'Other',[{'id':'P1','requirement':'Иное','acceptance':['Иное']}],'r1',self.root)
        b=ex.load(self.work/'binding.json');b['task_plan']=str(other);ex.save(self.work/'binding.json',b)
        with self.assertRaises(ValueError):task_plan.begin_stage(self.plan,self.journal,'P1','implementation')

    def test_shape_rejects_bool_integer_unknown_fields_empty_options(self):
        self.prepare()
        for update in [{'extra':1},{'mode':'other'},{'summary':''}]:
            review=copy.deepcopy(self.review);review.update(update)
            with self.assertRaises(ValueError):cli.submit(self.work,review)
        self.review['checked_sources'][0]['first']=True
        with self.assertRaises(ValueError):cli.submit(self.work,self.review)

    def test_cli_full_roundtrip_returns_status_and_records_timings(self):
        script=Path(cli.__file__)
        def run(*args,success=True):
            p=subprocess.run([sys.executable,str(script),*map(str,args)],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(p.returncode,0 if success else 1,p.stderr+p.stdout)
            return json.loads(p.stdout)
        run('check',self.work,'--point','P1',success=False)
        run('start',self.work)
        run('read',self.work,'source/Module.bsl','--first',1,'--last',1)
        reviewfile=self.root/'review.json';ex.save(reviewfile,self.review)
        result=run('submit',self.work,'--review',reviewfile)
        self.assertEqual(result['states'],{'P1':'ready','P2':'ready'})
        run('check',self.work,'--point','P1')
        self.assertEqual(run('show',self.work)['review'],self.review)
        calls=[json.loads(x) for x in (self.work/'calls.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(calls),6);self.assertTrue(all(c['seconds']>=0 for c in calls))


if __name__=='__main__':unittest.main()
