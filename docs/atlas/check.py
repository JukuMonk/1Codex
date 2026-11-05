"""Content/graph integrity checks; no 1C instance is needed for this HTML-only change."""
from pathlib import Path
import collections, hashlib, json, re, sys
from content import GRAPHS

HERE=Path(__file__).resolve().parent; ROOT=HERE.parent.parent

def reachable(g,start):
    adj=collections.defaultdict(list)
    for e in g['edges']:adj[e['a']].append(e['b'])
    seen=set();todo=[start]
    while todo:
        n=todo.pop()
        if n not in seen:seen.add(n);todo.extend(adj[n])
    return seen

def main():
    tests=[]
    def check(condition,name):
        if not condition:raise AssertionError(name)
        tests.append(name)
    layouts=json.loads((HERE/'graph-layout.json').read_text(encoding='utf-8'))
    for g in GRAPHS:
        ids=[n['id'] for n in g['nodes']]
        check(len(ids)==len(set(ids)),g['id']+': unique node IDs')
        check(all(e['a'] in ids and e['b'] in ids for e in g['edges']),g['id']+': edge endpoints')
        check(reachable(g,ids[0])==set(ids),g['id']+': all nodes reachable from entry')
        check(all((ROOT/n['source']).is_file() for n in g['nodes']),g['id']+': local source evidence exists')
        check(all(n['detail'] and n['sub'] and n['title'] for n in g['nodes']),g['id']+': every node explained')
    for g in layouts:
        nodes=g['nodes']
        overlap=[]
        for i,a in enumerate(nodes):
            for b in nodes[i+1:]:
                if abs(a['x']-b['x'])<(a['width']+b['width'])/2 and abs(a['y']-b['y'])<(a['height']+b['height'])/2:overlap.append((a['id'],b['id']))
        check(not overlap,g['id']+': no overlapping node boxes')
    text=(ROOT/'docs/index.html').read_text(encoding='utf-8')
    manifest=json.loads((HERE/'manifest.json').read_text(encoding='utf-8'))
    check(hashlib.sha256(text.encode()).hexdigest()==manifest['html_sha256'],'built artifact matches manifest')
    check(len(layouts)==manifest['maps']==12,'twelve complete process maps')
    check(sum(len(g['nodes']) for g in GRAPHS)==manifest['nodes'],'node count from source')
    check('Подробности для пользователей и инженеров' not in text,'no separate technical appendix')
    check(not re.search(r'<script[^>]+src=|<link[^>]+rel=["\']stylesheet',text),'no external JS or CSS dependencies')
    check(not re.search(r'url\(["\']?https?://',text),'no external font or image dependencies')
    check('TestManager' in text and 'Vanessa Automation' in text and 'COMConnector' in text,'all actual test routes present')
    catalog=json.loads((ROOT/'index/catalog.json').read_text(encoding='utf-8-sig'))
    check(manifest['case_formats']==dict(collections.Counter(c['format'] for c in catalog['cases'])),'case distribution matches catalog')
    report={'status':'passed','checks':len(tests),'details':tests}
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':sys.stdout.reconfigure(encoding='utf-8');main()
