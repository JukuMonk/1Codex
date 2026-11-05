"""Build the single-file offline atlas: python docs/atlas/build.py [--node /path/node]."""
import argparse, collections, hashlib, html, json, re, shutil, subprocess, sys, textwrap
from pathlib import Path
from content import GRAPHS

HERE=Path(__file__).resolve().parent
REPO=HERE.parent.parent
H=lambda s:html.escape(str(s),quote=True)
TYPES={'step':'Действие','decision':'Развилка','check':'Проверка','artifact':'Результат','external':'Настройка проекта','error':'Ошибка / возврат'}
BASE='https://github.com/JukuMonk/1Codex/blob/v1.1.0/'

def lines(value,width):
    return textwrap.wrap(value,width=width,break_long_words=False,break_on_hyphens=False)

def svg(g):
    gid=g['id']; w=g['layout']['width']; h=g['layout']['height']
    out=[f'<svg class="flow-svg" xmlns="http://www.w3.org/2000/svg" role="group" aria-labelledby="svg-title-{gid}" viewBox="0 0 {w:.1f} {h:.1f}" style="--native-width:{w:.1f}px" data-width="{w:.1f}"><title id="svg-title-{gid}">{H(g["title"])}</title><defs>']
    for typ,color in [('normal','var(--edge)'),('error','var(--danger)'),('back','var(--edge-return)')]:
        out.append(f'<marker id="arrow-{gid}-{typ}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{color}"/></marker>')
    out.append('</defs>')
    for e in g['edges']:
        typ=e['kind']; pts=e['points']; route=[pts[0]]
        for a,b in zip(pts,pts[1:]):
            if abs(a['x']-b['x'])>.1 and abs(a['y']-b['y'])>.1:
                mid=(a['y']+b['y'])/2
                route.extend([{'x':a['x'],'y':mid},{'x':b['x'],'y':mid}])
            route.append(b)
        d='M '+' L '.join(f'{p["x"]:.1f},{p["y"]:.1f}' for p in route)
        out.append(f'<path class="edge {typ}" data-from="{gid}-{e["a"]}" data-to="{gid}-{e["b"]}" d="{d}" marker-end="url(#arrow-{gid}-{typ})"/>')
        if e['label']:
            out.append(f'<g class="edge-label"><rect x="{e["x"]-e["width"]/2-4:.1f}" y="{e["y"]-10:.1f}" width="{e["width"]+8:.1f}" height="20" rx="3"/><text x="{e["x"]:.1f}" y="{e["y"]+4:.1f}" text-anchor="middle">{H(e["label"])}</text></g>')
    for n in g['nodes']:
        uid=gid+'-'+n['id']; x=n['x']-112; y=n['y']-58; title=lines(n['title'],21); sub=lines(n['sub'],29)
        out.append(f'<g class="node {n["kind"]}" id="node-{uid}" data-node="{uid}" tabindex="0" role="button" aria-label="{H(n["title"]+". "+n["sub"]+". Открыть пояснение")}" transform="translate({x:.1f} {y:.1f})"><title>{H(n["detail"])}</title>')
        out.append('<rect class="node-box" width="224" height="116" rx="6"/><path class="node-mark" d="M 0 14 V 102"/>')
        out.append(f'<text class="node-type" x="16" y="22">{H(TYPES[n["kind"]])}</text>')
        for i,line in enumerate(title):out.append(f'<text class="node-title" x="16" y="{45+i*21}">{H(line)}</text>')
        for i,line in enumerate(sub):out.append(f'<text class="node-sub" x="16" y="{78+i*16 if len(title)==1 else 91+i*16}">{H(line)}</text>')
        out.append('<text class="node-plus" x="205" y="23" aria-hidden="true">+</text></g>')
    out.append('</svg>');return ''.join(out)

def overview():
    boxes=[('analysis','01','Задача','критерии и среда',20,30),('metadata','02','Метаданные','карта и область правки',265,30),('knowledge','03','Знания','правило и рабочий аналог',510,30),('implementation','04','Изменение','XML · BSL · формы · СКД',755,30),('platform','05','Платформа','загрузка и сверка',755,155),('data','06','Данные','посев и сценарии',510,155),('com','07','COM','логика и числа',265,155),('ui','08','Интерфейс','Vanessa / TestManager',20,155),('evidence','09','Приёмка','свести результаты',20,280),('release','10','Выпуск','файл и отчёт',265,280),('learning','11','Улучшение','замеры и регрессия',510,280),('delivery','12','Обновление','стабильная версия',755,280)]
    s=['<svg xmlns="http://www.w3.org/2000/svg" class="overview-svg" viewBox="0 0 1000 406" role="group" aria-label="Общий маршрут 1Codex: двенадцать этапов"><defs><marker id="overview-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10Z" fill="var(--overview-line)"/></marker></defs>']
    # Layout is a folded route. COM and UI are complementary branches of platform checks.
    for d in ['M240 72H265','M485 72H510','M730 72H755','M865 114V155','M755 197H730','M510 197H485','M620 239V260H130V239','M375 239V260H130V280','M130 239V280','M240 322H265','M485 322H510','M730 322H755']:
        s.append(f'<path d="{d}" fill="none" stroke="var(--overview-line)" stroke-width="2" marker-end="url(#overview-arrow)"/>')
    for key,no,title,sub,x,y in boxes:
        s.append(f'<a href="#{key}" aria-label="{no}. {title}"><rect x="{x}" y="{y}" width="220" height="84" rx="5"/><text class="overview-no" x="{x+15}" y="{y+25}">{no}</text><text class="overview-title" x="{x+47}" y="{y+26}">{title}</text><text class="overview-sub" x="{x+15}" y="{y+58}">{sub}</text></a>')
    s.append('<text x="20" y="393" class="overview-foot">При ошибке: сохранить свидетельства → исправить → повторить затронутые проверки</text></svg>')
    return ''.join(s)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--node',default=shutil.which('node'));args=parser.parse_args()
    if not args.node:parser.error('Node.js is required for the build; the HTML itself needs no runtime.')
    p=subprocess.run([args.node,str(HERE/'layout.cjs')],input=json.dumps(GRAPHS,ensure_ascii=False),capture_output=True,text=True,encoding='utf-8')
    if p.returncode:
        sys.stderr.write(p.stderr[-4000:]);raise SystemExit(p.returncode)
    graphs=json.loads(p.stdout)
    catalog=json.loads((REPO/'index/catalog.json').read_text(encoding='utf-8-sig'));counts=collections.Counter(c['format'] for c in catalog['cases'])
    stats=dict(cases=len(catalog['cases']),knowledge=len(list((REPO/'knowledge').glob('*.md'))),tools=len(list((REPO/'tools').rglob('*.py'))),nodes=sum(len(g['nodes']) for g in graphs),edges=sum(len(g['edges']) for g in graphs),maps=len(graphs))
    source_sha=subprocess.check_output(['git','rev-parse','v1.1.0^{commit}'],cwd=REPO,text=True).strip()
    labels=['Разбор задачи','Поиск метаданных','Выбор знаний','Изменение исходников','Проверка платформой','Демо-данные','COM-соединение','Интерфейс и Vanessa','Приёмка','Выпуск и отчёт','Замеры и улучшения','Обновления']
    nav=''.join(f'<a href="#{g["id"]}"><span>{i:02}</span>{H(labels[i-1])}</a>' for i,g in enumerate(graphs,1))
    sections=[];node_data={}
    for i,g in enumerate(graphs,1):
        for n in g['nodes']:node_data[g['id']+'-'+n['id']]={**n,'chapter':g['title'],'section':g['id'],'source_url':BASE+n['source']}
        extra=''
        if g['id']=='com':extra=(HERE/'stock-example.html').read_text(encoding='utf-8')
        if g['id']=='metadata':extra='<div class="micro-diagram"><span>Название в задаче</span><b>→</b><span>Раздел КАРТА.md</span><b>→</b><span>XML + обработчик</span><b>→</b><span>Связанные сценарии</span></div>'
        if g['id']=='ui':extra='<div class="route-note"><b>Два запускателя, общий механизм TestClient</b><span><code>project_cli → ui_test.py</code>: встроенный запуск UI-тестов</span><span><code>vanessa.py → EPF → .feature</code>: отдельный запуск Vanessa</span></div>'
        if g['id']=='evidence':extra='''<div class="coverage-wrap"><table class="coverage"><caption>Какой уровень подтверждает требование</caption><thead><tr><th>Что проверяем</th><th>XML / lint</th><th>Платформа</th><th>COM</th><th>UI / Vanessa</th></tr></thead><tbody><tr><th>Структура и синтаксис</th><td>частично</td><td>загрузка / компиляция</td><td>при исполнении</td><td>при исполнении</td></tr><tr><th>Движения и значения отчёта</th><td>не проверяет</td><td>не проверяет</td><td class="yes">утверждения</td><td>с проверкой данных</td></tr><tr><th>Кнопки, поля, клиентские события</th><td>не проверяет</td><td>не проверяет</td><td>не проверяет</td><td class="yes">действия и состояния</td></tr><tr><th>Скрытый минус внутри периода</th><td>не проверяет</td><td>не проверяет</td><td class="yes">история движений</td><td>отказ в интерфейсе</td></tr></tbody></table></div>'''
        sections.append(f'''<section class="chapter" id="{g['id']}" aria-labelledby="heading-{g['id']}">
<header class="chapter-head"><div class="chapter-no">{i:02}</div><div><p class="section-kicker">Этап {i} из {len(graphs)}</p><h2 id="heading-{g['id']}">{H(g['title'])}</h2><p>{H(g['intro'])}</p></div></header>
{extra}<div class="diagram" data-graph="{g['id']}"><div class="diagram-bar"><span>{len(g['nodes'])} узлов · {len(g['edges'])} связей</span><div><button type="button" data-action="fit">По ширине</button><button type="button" data-action="actual">100%</button><button type="button" data-action="expand" aria-label="Развернуть схему: {H(g['title'])}">Развернуть ↗</button></div></div><div class="graph-scroll" tabindex="0" aria-label="Схема. При увеличении прокручивайте горизонтально">{svg(g)}</div></div>
<div class="chapter-result"><span>На выходе</span><p>{H(g['outcome'])}</p><a href="{BASE+g['source']}" target="_blank" rel="noopener">Источник ↗</a></div></section>''')
    metrics=''.join(f'<div><strong>{stats[k]}</strong><span>{label}</span></div>' for k,label in [('cases','разобранных кейсов'),('knowledge','раздела знаний'),('tools','Python-файлов в tools'),('maps','подробных схем')])
    bars=''.join(f'<div class="catalog-row"><span>{name}</span><div><i style="width:{counts[key]/stats["cases"]*100:.3f}%"></i></div><b>{counts[key]}</b></div>' for key,name in [('designer','Конфигуратор'),('shared','Общие приёмы'),('legacy-edt','Архив EDT')])
    data=json.dumps(node_data,ensure_ascii=False).replace('<','\\u003c')
    values={'CSS':(HERE/'style.css').read_text(encoding='utf-8')+'\n'+(HERE/'terminal.css').read_text(encoding='utf-8'),'JS':(HERE/'app.js').read_text(encoding='utf-8'),'NAV':nav,'SECTIONS':'\n'.join(sections),'OVERVIEW':overview(),'METRICS':metrics,'BARS':bars,'NODE_DATA':data,'NODE_COUNT':str(stats['nodes']),'EDGE_COUNT':str(stats['edges']),'SOURCE_SHA':source_sha,'LICENSE':H((HERE/'vendor/DAGRE-LICENSE.txt').read_text(encoding='utf-8')+'\n'+(HERE/'vendor/DAGRE-BUNDLE-LICENSE.txt').read_text(encoding='utf-8'))}
    result=(HERE/'template.html').read_text(encoding='utf-8')
    for k,v in values.items():result=result.replace('{{'+k+'}}',v)
    if re.search(r'\{\{[A-Z_]+\}\}',result):raise ValueError('Unresolved template slot')
    (HERE.parent/'index.html').write_text(result,encoding='utf-8',newline='\n')
    (HERE/'graph-layout.json').write_text(json.dumps(graphs,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    manifest={'version':'1.1.0','source_commit':source_sha,'snapshot_date':'2026-11-02',**stats,'case_formats':dict(counts),'dagre_version':'3.1.3','html_sha256':hashlib.sha256(result.encode()).hexdigest()}
    (HERE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
