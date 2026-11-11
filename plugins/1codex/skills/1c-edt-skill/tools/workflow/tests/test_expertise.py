from pathlib import Path
from tools.workflow.expertise import *
import unittest,tempfile

class Contracts(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='expertise-unit-');self.p=Path(self.tmp.name)
  (self.p/'source').mkdir();(self.p/'source/module.bsl').write_text('Исходная строка\n',encoding='utf-8')
  (self.p/'project.txt').write_text('Учебный проект',encoding='utf-8')
  save(self.p/'task.json',{'version':1,'points':{'P1':'Правило','P2':'Подпись'}});save(self.p/'decisions.json',[])
  self.reads={'source/module.bsl':{1}};cite={'path':'source/module.bsl','first':1,'last':1}
  self.r={'mode':'standard','summary':'Результат экспертизы','findings':[{'id':'F1','kind':'missing_decision','confidence':'confirmed','points':['P1'],'evidence':[cite],'problem':'Не выбрано правило поведения.','counterexample':'Одинаковый ввод имеет два результата.','consequence':'Результат пока не определён.','proposal':'Выбрать единое правило по примеру.','tradeoff':'При выборе правила изменится пример.','alternative':'','acceptance':[{'given':'Исходные данные','when':'Выполнить действие','then':'Принятый результат','level':'com'}]}],'questions':[{'id':'Q1','finding':'F1','points':['P1'],'owner':'Методолог','question':'Какое правило принять?','options':[{'label':'Первое','consequence':'Первый результат'},{'label':'Второе','consequence':'Второй результат'}],'recommended':0,'reason_needed':'Два несовместимых условия.'}],'points':[{'id':'P1','next_action':'Дождаться решения'},{'id':'P2','next_action':'Изменить подпись'}],'checked_sources':[cite],'limitations':['Проверки только запланированы.']}
 def tearDown(self):self.tmp.cleanup()
 def record(self):return record(self.p,self.r,self.reads,input_fingerprints(self.p))
 def test_block_only_dependent_point(self):
  path=self.record();self.assertEqual(readiness(self.p,path),{'P1':'needs_decision','P2':'ready'})
  seen=[]
  with self.assertRaises(ValueError):gate(self.p,path,'P1',lambda:seen.append('bad'))
  gate(self.p,path,'P2',lambda:seen.append('ok'));self.assertEqual(seen,['ok'])
 def test_missing_proposal_rejected(self):
  self.r['findings'][0]['proposal']=''
  with self.assertRaises(ValueError):self.record()
 def test_missing_example_rejected(self):
  self.r['findings'][0]['acceptance']=[]
  with self.assertRaises(ValueError):self.record()
 def test_unread_citation_rejected(self):
  self.reads={}
  with self.assertRaises(ValueError):self.record()
 def test_path_escape_rejected(self):
  with self.assertRaises(ValueError):resolve(self.p,'../common.py')
 def test_private_path_rejected(self):
  (self.p/'private').mkdir();save(self.p/'private/key.json',{})
  with self.assertRaises(ValueError):resolve(self.p,'source/../private/key.json')
 def test_missing_point_rejected(self):
  self.r['points'].pop()
  with self.assertRaises(ValueError):self.record()
 def test_advice_cannot_block(self):
  self.r['findings'][0]['kind']='improvement'
  with self.assertRaises(ValueError):self.record()
 def test_changed_requirement_scoped(self):
  path=self.record();d=load(self.p/'task.json');d['points']['P1']='Новое правило';save(self.p/'task.json',d)
  self.assertEqual(readiness(self.p,path),{'P1':'needs_review','P2':'ready'})
 def test_new_decision_requires_review(self):
  path=self.record();save(self.p/'decisions.json',[{'id':'D1','points':['P1'],'text':'Выбрано первое правило'}])
  self.assertEqual(readiness(self.p,path),{'P1':'needs_review','P2':'ready'})
 def test_source_change_conservative(self):
  path=self.record();(self.p/'source/module.bsl').write_text('Изменено',encoding='utf-8')
  self.assertEqual(set(readiness(self.p,path).values()),{'needs_review'})
 def test_new_point_unreviewed(self):
  path=self.record();d=load(self.p/'task.json');d['points']['P3']='Новый пункт';save(self.p/'task.json',d)
  self.assertEqual(readiness(self.p,path)['P3'],'unreviewed')
 def test_tamper_rejected(self):
  path=self.record();e=load(path);e['payload']['review']['questions']=[];save(path,e)
  with self.assertRaises(ValueError):readiness(self.p,path)
 def test_materials_changed_during_review_rejected(self):
  before=input_fingerprints(self.p);(self.p/'project.txt').write_text('Новая среда',encoding='utf-8')
  with self.assertRaises(ValueError):record(self.p,self.r,self.reads,before)
 def test_superseded_review_rejected(self):
  first=self.record();second=self.record()
  with self.assertRaises(ValueError):readiness(self.p,first)
  self.assertEqual(readiness(self.p,second)['P2'],'ready')
 def test_no_findings_valid(self):
  self.r['findings']=[];self.r['questions']=[]
  self.assertEqual(set(readiness(self.p,self.record()).values()),{'ready'})
 def test_missing_decision_without_question_rejected(self):
  self.r['questions']=[]
  with self.assertRaises(ValueError):self.record()
 def test_foreign_project_rejected(self):
  path=self.record();self.assertRaises(ValueError,readiness,self.p.parent,path)
 def test_missing_decision_all_affected_points_covered(self):
  self.r['findings'][0]['points'].append('P2')
  with self.assertRaises(ValueError):self.record()
 def test_decision_review_and_resume_preserve_history(self):
  first=self.record();original=first.read_bytes()
  save(self.p/'decisions.json',[{'id':'D1','points':['P1'],'text':'Принять первое правило'}])
  seen=[]
  with self.assertRaises(ValueError):gate(self.p,first,'P1',lambda:seen.append('stale'))
  gate(self.p,first,'P2',lambda:seen.append('independent'))
  self.r['findings']=[];self.r['questions']=[]
  second=self.record();gate(self.p,second,'P1',lambda:seen.append('resumed'))
  self.assertEqual(seen,['independent','resumed']);self.assertEqual(first.read_bytes(),original)
  self.assertEqual(set(readiness(self.p,second).values()),{'ready'})

if __name__=='__main__':unittest.main()
