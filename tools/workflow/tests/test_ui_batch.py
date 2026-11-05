from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from workflow import ui_batch

class BatchTests(unittest.TestCase):
    def cases(self):return [{'id':i,'fixture':'item','steps':['команда | ${nav}','закрыть | без сохранения']} for i in ('OP05','OP13')]
    def factory(self,name,namespace):return {'nav':'ref-'+namespace,'resources':[namespace]}
    def test_independent_namespaces(self):
        a=ui_batch.prepare(self.cases(),self.factory);b=ui_batch.prepare(self.cases(),self.factory)
        self.assertNotEqual(a['id'],b['id']);self.assertEqual(a['scenario'].count('.begin'),2)
    def test_duplicate_ids(self):
        cases=self.cases();cases[1]['id']='OP05'
        with self.assertRaises(ValueError):ui_batch.prepare(cases,self.factory)
    def test_shared_fixture_refused(self):
        with self.assertRaises(ValueError):ui_batch.prepare(self.cases(),lambda *a:{'nav':'x','resources':['shared']})
    def test_substitution_injection(self):
        with self.assertRaises(ValueError):ui_batch.prepare(self.cases(),lambda *a:{'nav':'x\nкнопка | Удалить','resources':['a']})
    def test_partial_result(self):
        batch=ui_batch.prepare(self.cases(),self.factory)
        result=ui_batch.outcomes(batch,'ОК этап | OP05.begin [1 мс]\nОК этап | OP05.end [1 мс]\nОК этап | OP13.begin [1 мс]\nОШИБКА кнопка',1)
        self.assertEqual(result['cases'],{'OP05':'passed','OP13':'failed'})
    def test_not_started_is_not_success(self):
        batch=ui_batch.prepare(self.cases(),self.factory)
        self.assertEqual(ui_batch.outcomes(batch,'',0)['status'],'failed')
    def test_reserved_markers(self):
        cases=self.cases();cases[0]['steps']=['этап | OP13.end']
        with self.assertRaises(ValueError):ui_batch.prepare(cases,self.factory)
    def test_runner_and_artifact(self):
        def runner(path):
            self.assertTrue(path.is_file())
            markers=[line for line in path.read_text(encoding='utf-8').splitlines() if line.startswith('этап')]
            return {'exit_code':0,'journal':'\n'.join('ОК '+line+' [1 мс]' for line in markers),'run_id':'test'}
        with tempfile.TemporaryDirectory() as work:
            result=ui_batch.run(self.cases(),self.factory,runner,work)
            self.assertEqual(result['status'],'passed')
            self.assertTrue((Path(work)/result['batch_id']/'result.json').is_file())

if __name__=='__main__':unittest.main()
