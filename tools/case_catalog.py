"""Build, validate and search case metadata without claiming new platform verification."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT/'index/catalog.json'
# Reviewed routing, not a claim that every technique applies to every format.
SHARED={10,11,12,13,14,15,16,17,18,24,26,29,31,32,33,34,35,36,37,39,42,43,44,45,46,47,48,49,50,51,52,53,55,58,59,60,62,64,65,68,71,72,73}
DESIGNER=set(range(74,110))


def evidence_digest(path):
    """Hash Markdown content independently of Git checkout EOL/BOM conversion."""
    text=Path(path).read_bytes().decode('utf-8-sig').replace('\r\n','\n')
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def source_rows():
    text=(ROOT/'index/cases.md').read_text(encoding='utf-8-sig')
    return {int(m[1]):m.groups()[1:] for m in re.finditer(r'^\| (\d{3}) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|',text,re.M)}


def build():
    rows=source_rows();result=[]
    previous={r['id']:r for r in json.loads(CATALOG.read_text(encoding='utf-8'))['cases']} if CATALOG.exists() else {}
    for path in sorted((ROOT/'cases').glob('[0-9][0-9][0-9]-*')):
        num=int(path.name[:3]);row=rows[num]
        evidence=[p for p in (path/'task.md',path/'lessons.md') if p.is_file()]
        if not evidence and (path/'README.md').is_file(): evidence=[path/'README.md']
        raw='\n'.join(p.read_text(encoding='utf-8-sig') for p in evidence)
        result.append({'id':f'{num:03d}','slug':path.name[4:],'topic':row[1].strip(),'symptom':row[2].strip(),
            'format':'shared' if num in SHARED else ('designer' if num in DESIGNER else 'legacy-edt'),
            'platform_build':None,'compatibility_mode':None,
            'platform_mentions':sorted(set(re.findall(r'\b8\.\d+(?:\.\d+){1,2}\b',raw))),
            'configuration_kind':None,'client':None,'applies_to':'See task.md and lessons.md for verified boundaries',
            'confidence':row[3].strip(),'verification_status':'historical-evidence','verified_at':None,
            'regression_tests':[],'supersedes':[],
            'evidence':[{'path':p.relative_to(ROOT).as_posix(),'sha256':evidence_digest(p)} for p in evidence]})
    for row in result:
        old=previous.get(row['id'],{})
        for key in ('platform_build','compatibility_mode','configuration_kind','client','applies_to','verified_at','regression_tests','supersedes'):
            if old.get(key) is not None:row[key]=old[key]
        if old.get('classification_reviewed'):
            row.update(format=old['format'],classification_reviewed=True)
    return {'schema_version':2,'evidence_hash_format':'utf8-no-bom-lf-v1','classification_note':'Format is a discovery route; platform mentions are not a compatibility guarantee. Null fields are unreviewed, not universal.', 'cases':result}


def validate(data):
    errors=[];rows=source_rows();ids=[x['id'] for x in data['cases']]
    if data.get('schema_version')!=2 or data.get('evidence_hash_format')!='utf8-no-bom-lf-v1':
        errors.append('Unsupported catalog schema/hash format; rebuild with case_catalog.py build')
    if len(ids)!=len(set(ids)) or set(ids)!={f'{n:03d}' for n in rows}:errors.append('Case IDs differ from index')
    for row in data['cases']:
        if row['format'] not in ('designer','shared','legacy-edt','unclassified'):errors.append('Unknown format: '+row['id'])
        if not row['evidence']:errors.append('No evidence: '+row['id'])
        for entry in row['evidence']:
            path=ROOT/entry['path']
            if not path.is_file() or evidence_digest(path)!=entry['sha256']:
                errors.append('Evidence changed: '+entry['path'])
    return errors


def search(data,query='',format=None):
    words=query.casefold().split()
    return [r for r in data['cases'] if (not format or r['format'] in (format,'shared')) and
            all(w in (' '.join([r['id'],r['slug'],r['topic'],r['symptom']])).casefold() for w in words)]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['build','check','search'])
    p.add_argument('--query',default='');p.add_argument('--format',choices=['designer','shared','legacy-edt','unclassified'])
    args=p.parse_args()
    if args.action=='build':
        CATALOG.write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return 0
    data=json.loads(CATALOG.read_text(encoding='utf-8'))
    if args.action=='check':
        errors=validate(data)
        for e in errors:print(e)
        print(f'Catalog: {len(data["cases"])} cases; {len(errors)} error(s)');return bool(errors)
    for r in search(data,args.query,args.format):print(f'{r["id"]} | {r["format"]} | {r["confidence"]} | {r["symptom"]}')
    return 0
if __name__=='__main__':sys.exit(main())
