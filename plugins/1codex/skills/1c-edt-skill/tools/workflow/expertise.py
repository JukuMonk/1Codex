"""Task expertise: portable contract, versioned reviews and per-point readiness.

No platform execution or model dependency. See knowledge/task-expertise.md.
"""
from pathlib import Path
import hashlib, json, os, tempfile
try:
    from . import timing
    from .resource_lock import base_lease
except ImportError:
    import timing
    from resource_lock import base_lease

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, pending = tempfile.mkstemp(dir=path.parent, prefix='.expertise-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
        os.replace(pending, path)
    finally:
        if os.path.exists(pending):
            os.unlink(pending)

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   separators=(',', ':')).encode()).hexdigest()

def binding(project):
    path = Path(project)/'binding.json'
    return load(path) if path.exists() else {}

def source_root(project):
    return Path(binding(project).get('source', Path(project)/'source')).resolve()

def manifest(root):
    root = Path(root).resolve()
    result = {}
    for path in sorted(root.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts:
            continue
        if not path.resolve().is_relative_to(root):
            raise ValueError('Source link leaves selected source root')
        result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result

def task(project):
    plan = binding(project).get('task_plan')
    if plan:
        data = load(plan)
        if data.get('schema_version') != 1:
            raise ValueError('Unsupported bound task plan')
        points = {p['id']: p for p in data['points']}
        if len(points) != len(data['points']):
            raise ValueError('Duplicate task point')
        return {'version': 1, 'points': points}
    return load(Path(project)/'task.json')

def material(project, name):
    if name == 'task.json' and binding(project).get('task_plan'):
        return json.dumps(task(project), ensure_ascii=False, indent=2)
    if name == 'index.txt':
        return '\n'.join('source/'+p for p in manifest(source_root(project)))+'\n'
    return resolve(project, name).read_text(encoding='utf-8-sig')

def _shape(value, schema, path='review'):
    # Only the vocabulary used by SCHEMA below; no external JSON Schema runtime.
    types = {'object': dict, 'array': list, 'string': str, 'integer': int}
    if type(value) is not types[schema['type']]:
        raise ValueError(path+': invalid type')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(path+': invalid value')
    if schema['type'] == 'object':
        expected = schema['properties']
        if set(value) != set(expected):
            raise ValueError(path+': missing or unknown fields')
        for key, spec in expected.items():
            _shape(value[key], spec, path+'.'+key)
    elif schema['type'] == 'array':
        for i, item in enumerate(value):
            _shape(item, schema['items'], path+'['+str(i)+']')


import copy,hmac,secrets

def obj(p):return {'type':'object','properties':p,'required':list(p),'additionalProperties':False}
S={'type':'string'}
def arr(x):return {'type':'array','items':x}
def enum(*x):return {'type':'string','enum':list(x)}
CITE=obj({'path':S,'first':{'type':'integer'},'last':{'type':'integer'}})
ACCEPT=obj({'given':S,'when':S,'then':S,'level':enum('static','com','ui','integration')})
FINDING=obj({'id':S,'kind':enum('contradiction','missing_decision','risk','improvement'),'confidence':enum('confirmed','conditional'),'points':arr(S),'evidence':arr(CITE),'problem':S,'counterexample':S,'consequence':S,'proposal':S,'tradeoff':S,'alternative':S,'acceptance':arr(ACCEPT)})
QUESTION=obj({'id':S,'finding':S,'points':arr(S),'owner':S,'question':S,'options':arr(obj({'label':S,'consequence':S})),'recommended':{'type':'integer'},'reason_needed':S})
SCHEMA=obj({'mode':enum('quick','standard','extended'),'summary':S,'findings':arr(FINDING),'questions':arr(QUESTION),'points':arr(obj({'id':S,'next_action':S})),'checked_sources':arr(CITE),'limitations':arr(S)})

def resolve(project,name):
 if not isinstance(name,str) or '\\' in name:raise ValueError('Use relative slash-separated material names')
 base=Path(project).resolve()
 if name.startswith('source/'):
  base=source_root(project);p=(base/name[7:]).resolve()
 elif name in ['task.json','decisions.json','project.txt','index.txt']:
  p=(base/name).resolve()
 else:raise ValueError('Outside allowed materials')
 if not p.is_relative_to(base) or not p.is_file():raise ValueError('Outside allowed materials')
 return p


def input_fingerprints(project):
 project=Path(project);current_task=task(project);decisions=load(project/'decisions.json')
 points=current_task.get('points')
 if not isinstance(points,dict) or not points or any(not isinstance(k,str) or not k.strip() for k in points):raise ValueError('Nonempty task points required')
 if not isinstance(decisions,list):raise ValueError('Decisions must be a list')
 ids=[]
 for d in decisions:
  if not isinstance(d,dict) or set(d)!={'id','points','text'} or not isinstance(d['id'],str) or not d['id'].strip() or not isinstance(d['text'],str) or not d['text'].strip():raise ValueError('Invalid decision')
  if not isinstance(d['points'],list) or not d['points'] or any(p not in points for p in d['points']):raise ValueError('Decision requires known points')
  ids.append(d['id'])
 if len(ids)!=len(set(ids)):raise ValueError('Duplicate decision ID')
 # Conservative for sources: unknown source dependencies invalidate all points.
 shared={'source':manifest(source_root(project)),'project':hashlib.sha256((project/'project.txt').read_bytes()).hexdigest()}
 return {id:digest({'point':p,'decisions':[d for d in decisions if id in d['points']],'shared':shared,'binding':binding(project)}) for id,p in current_task['points'].items()}

def validate(review,project,reads):
 _shape(review,SCHEMA)
 if not review['summary'].strip() or any(not p['next_action'].strip() for p in review['points']):raise ValueError('Summary and next actions required')
 ids=set(task(project)['points']);fids=[f['id'] for f in review['findings']];qids=[q['id'] for q in review['questions']]
 if len(fids)!=len(set(fids)) or len(qids)!=len(set(qids)):raise ValueError('Duplicate finding/question ID')
 if len(review['points'])!=len(ids) or {p['id'] for p in review['points']}!=ids:raise ValueError('Every task point required exactly once')
 def citations(cites):
  if not cites:raise ValueError('Evidence is required')
  for c in cites:
   lines=material(project,c['path']).splitlines()
   if not 1<=c['first']<=c['last']<=len(lines):raise ValueError('Invalid citation range')
   if not set(range(c['first'],c['last']+1))<=set(reads.get(c['path'],[])):raise ValueError('Citation has not been read')
 citations(review['checked_sources'])
 for f in review['findings']:
  if not f['points'] or not set(f['points'])<=ids:raise ValueError('Unknown affected point')
  citations(f['evidence'])
  for key in ['problem','counterexample','consequence','proposal','tradeoff']:
   if len(f[key].strip())<8:raise ValueError('Finding requires concrete '+key)
  if not f['acceptance'] or any(not all(x[k].strip() for k in ['given','when','then']) for x in f['acceptance']):raise ValueError('Acceptance example required')
 for q in review['questions']:
  if q['finding'] not in fids:raise ValueError('Question must link to finding')
  f=next(f for f in review['findings'] if f['id']==q['finding'])
  if f['kind']=='improvement':raise ValueError('Advice cannot block implementation')
  if not q['points'] or not set(q['points'])<=set(f['points']):raise ValueError('Question blocks wrong points')
  if not 2<=len(q['options'])<=3 or not 0<=q['recommended']<len(q['options']):raise ValueError('Question requires options and recommendation')
  if not all(q[k].strip() for k in ['owner','question','reason_needed']):raise ValueError('Incomplete question')
  if any(not option[k].strip() for option in q['options'] for k in ['label','consequence']):raise ValueError('Incomplete question option')
 for f in review['findings']:
  if f['kind']=='missing_decision':
   covered={p for q in review['questions'] if q['finding']==f['id'] for p in q['points']}
   if not set(f['points'])<=covered:raise ValueError('Missing decision requires questions for every affected point')
 return review

def _record(project,review,reads,expected_inputs):
 project=Path(project)
 if input_fingerprints(project)!=expected_inputs:raise ValueError('Materials changed during review')
 validate(review,project,reads)
 folder=project/'.review';folder.mkdir(exist_ok=True);keyfile=folder/'local.key'
 if not keyfile.exists():keyfile.write_bytes(secrets.token_bytes(32))
 previous=sorted(folder.glob('review-*.json'));seq=max([int(p.stem.split('-')[1]) for p in previous]+[0])+1
 payload={'schema':1,'inputs':expected_inputs,'review':copy.deepcopy(review),'sequence':seq,'saved_at':timing.stamp()}
 envelope={'payload':payload,'signature':hmac.new(keyfile.read_bytes(),digest(payload).encode(),'sha256').hexdigest()}
 path=folder/f'review-{seq:010}.json';save(path,envelope)
 return path

def readiness(project,path):
 project=Path(project);path=Path(path)
 current_reviews=sorted((project/'.review').glob('review-*.json'))
 if not current_reviews or path.resolve()!=current_reviews[-1].resolve():raise ValueError('Review is superseded or belongs to another project')
 e=load(path);key=(project/'.review/local.key').read_bytes();payload=e['payload']
 if not hmac.compare_digest(e['signature'],hmac.new(key,digest(payload).encode(),'sha256').hexdigest()):raise ValueError('Review integrity mismatch')
 current=input_fingerprints(project);review=payload['review'];blocked={p for q in review['questions'] for p in q['points']};result={}
 for id,fp in current.items():
  if id not in payload['inputs']:result[id]='unreviewed'
  elif payload['inputs'][id]!=fp:result[id]='needs_review'
  elif id in blocked:result[id]='needs_decision'
  else:result[id]='ready'
 return result

def gate(project,path,point,action):
 status=readiness(project,path).get(point,'unreviewed')
 if status!='ready':raise ValueError('Point '+point+' cannot proceed: '+status)
 return action()

def record(project, review, reads, expected_inputs):
    with base_lease(project, Path(project)/'.review'):
        return _record(project, review, reads, expected_inputs)

def latest(project):
    paths = sorted((Path(project)/'.review').glob('review-*.json'))
    if not paths:
        raise ValueError('No saved expertise review; start and submit a review first')
    return paths[-1]

def initialize(project, source, profile, requirements=None, decisions=None, task_plan=None, journal=None):
    project = Path(project).resolve()
    source = Path(source).resolve()
    if not source.is_dir() or project.is_relative_to(source):
        raise ValueError('Choose a source directory separate from the expertise workspace')
    if (requirements is None) == (task_plan is None):
        raise ValueError('Choose requirements or a task plan')
    profile = str(profile).strip()
    if not profile:
        raise ValueError('Project profile is required')
    plan = Path(task_plan).resolve() if task_plan else None
    if plan and not plan.is_file():
        raise ValueError('Task plan is missing')
    if requirements is not None and (not isinstance(requirements,dict) or not requirements.get('points')):
        raise ValueError('Nonempty task points are required')
    project.mkdir(parents=True, exist_ok=False)
    save(project/'binding.json', {'source':str(source), 'task_plan':str(plan) if plan else None,
                                 'journal':str(Path(journal).resolve()) if journal else None})
    if requirements is not None:
        save(project/'task.json', requirements)
    save(project/'decisions.json', decisions or [])
    (project/'project.txt').write_text(profile+'\n',encoding='utf-8')
    input_fingerprints(project)
    return project
