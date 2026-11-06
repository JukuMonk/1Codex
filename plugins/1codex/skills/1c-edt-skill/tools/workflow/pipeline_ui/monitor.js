'use strict';
const bundle = JSON.parse(document.getElementById('bundle').textContent);
const graphs = new Map(bundle.graphs.map(graph => [graph.id, graph]));
const titles = new Map(Object.entries(bundle.chapters));
const $ = id => document.getElementById(id);
const words = {begin:'Начало',running:'В работе',ok:'Готово',failed:'Ошибка',interrupted:'Прервано',
  quiet:'Без событий',idle:'Не запускался',waiting:'Ожидание',warning:'Предупреждение',
  stalled:'Остановка прогресса',progress:'Прогресс'};
const signs = {running:'›',ok:'✓',failed:'!',interrupted:'×',quiet:'·',idle:'',waiting:'Ⅱ',warning:'!',stalled:'!'};
const failureKinds = {product:'продукт',tool:'инструмент',infrastructure:'окружение'};
const openBranches = new Set(), openNodes = new Set(), showUnused = new Set(), manual = new Set(), manualNodes = new Set();
let state = bundle.state, receivedAt = Date.now(), lost = false, selected = '', selectedNode = '', point = '';
let stages = [], byId = new Map(), groups = new Map(), endpoints = new Map(), anchors = new Map(), attention = new Map();
let scheduled = 0, previousSignature = '', pausedClock = 0;
let timeRange = 'auto', chains = [];
let initialRoutePosition = false;
const clockTime = value => new Date(value).toLocaleTimeString('ru-RU');
const dateTime = value => new Date(value).toLocaleString('ru-RU',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
const keyOf = s => graphs.has((s.node||'').split('.')[0]) ? s.node.split('.')[0] : 'unmapped';
const leafOf = s => keyOf(s)==='unmapped' ? 'unmapped:'+s.name : s.node.includes('.') ? s.node : s.node+':general';
const identity = s => JSON.stringify([s.task,s.point,s.node||s.name]);

function clock() {
  if (state.end) return Date.parse(state.end);
  if (lost) return pausedClock;
  return Date.parse(state.sampled)+(bundle.live ? Date.now()-receivedAt : 0);
}
function duration(ms) {
  const n=Math.max(0,Math.floor(ms/1000));
  return (n>=3600?Math.floor(n/3600)+' ч ':'')+(n>=60?Math.floor(n/60)%60+' мин ':'')+n%60+' с';
}

function instant(iso) {
  const fraction=/\.(\d+)(?:Z|[+-]\d{2}:\d{2})$/.exec(iso);
  return Date.parse(iso)+(fraction && fraction[1].length>3 ? Number('0.'+fraction[1].slice(3)) : 0);
}
function shortTime(ms) {
  ms=Math.max(0,ms);
  if(ms<1000) return Math.round(ms)+' мс';
  if(ms<60000) return (ms/1000).toLocaleString('ru-RU',{maximumFractionDigits:2})+' с';
  return duration(ms);
}
function elapsed(s,now=clock()) {
  return Math.max(0,(s.end?instant(s.end):now)-instant(s.start));
}
function el(tag,text,cls) {
  const e=document.createElement(tag);
  if (text!=null) e.textContent=text;
  if (cls) e.className=cls;
  return e;
}
function button(text,key,action,cls) {
  const b=el('button',text,cls);
  b.type='button'; b.dataset.focus=key; b.onclick=action;
  return b;
}
function svg(tag,attrs) {
  const e=document.createElementNS('http://www.w3.org/2000/svg',tag);
  for(const [k,v] of Object.entries(attrs)) e.setAttribute(k,v);
  return e;
}
function tone(s) {
  if(s.status!=='running') return s.status;
  const last=s.signals.at(-1);
  if(last && ['waiting','warning','stalled'].includes(last.kind)) return last.kind;
  if(s.phase==='waiting' && !last) return 'waiting';
  return clock()-Date.parse(s.last_activity||s.start)>=60000 ? 'quiet':'running';
}
function aggregate(items) {
  if(!items.length) return 'idle';
  const running=items.filter(s=>s.status==='running').map(tone);
  if(running.length) return ['stalled','warning','quiet','waiting','running'].find(k=>running.includes(k));
  const latest=new Map();
  for(const s of items) {
    const k=identity(s), prev=latest.get(k);
    if(!prev || prev.attempt<s.attempt) latest.set(k,{attempt:s.attempt,states:[]});
    if(latest.get(k).attempt===s.attempt) latest.get(k).states.push(s.status);
  }
  return ['failed','interrupted','ok'].find(k=>[...latest.values()].some(v=>v.states.includes(k)))||'idle';
}
function displayName(s) {
  const leaf=groups.get(keyOf(s))?.leaves.get(leafOf(s));
  if(!leaf || (!/^[a-z-]+$/.test(s.name) && s.name!==s.point+':'+s.phase)) return s.name;
  return leaf.title;
}
function makeGroups() {
  stages=state.stages.filter(s=>!point || s.point===point);
  byId=new Map(stages.map(s=>[s.id,s]));
  attention=new Map();
  for(const event of state.events) {
    if(byId.has(event.id) && ['stalled','warning','quiet','waiting'].includes(event.kind)) attention.set(event.id,event.kind);
  }
  groups=new Map();
  for(const [key,title] of titles) {
    const leaves=new Map();
    for(const node of graphs.get(key).nodes) leaves.set(key+'.'+node.id,{key:key+'.'+node.id,title:node.title,ref:node,items:[]});
    groups.set(key,{key,title,items:[],leaves});
  }
  for(const s of stages) {
    const key=keyOf(s), leaf=leafOf(s);
    if(!groups.has(key)) groups.set(key,{key,title:'Без привязки',items:[],leaves:new Map()});
    const g=groups.get(key);
    if(!g.leaves.has(leaf)) g.leaves.set(leaf,{key:leaf,title:key==='unmapped'?s.name:'Работа этапа',items:[]});
    g.items.push(s); g.leaves.get(leaf).items.push(s);
  }
}
const isFailure = s => s.status==='failed' || s.status==='interrupted';
const isProblem = s => isFailure(s) || s.attempt>1 || ['stalled','warning','quiet','waiting'].includes(tone(s));
function autoOpen(initial=false) {
  for(const g of groups.values()) {
    if(!manual.has(g.key) && g.items.some(s=>isProblem(s)||s.status==='running')) openBranches.add(g.key);
    if(openBranches.has(g.key)) {
      for(const leaf of g.leaves.values()) {
        if(!manualNodes.has(leaf.key) && leaf.items.some(isFailure)) openNodes.add(leaf.key);
      }
    }
  }
  if(initial && state.end && !openBranches.size) {
    const busiest=[...groups.values()].sort((a,b)=>b.items.length-a.items.length)[0];
    if(busiest?.items.length>1) openBranches.add(busiest.key);
  }
}
function glyph(value) {
  const g=el('span',signs[value],'glyph');
  g.dataset.tone=value; g.setAttribute('aria-hidden','true');
  return g;
}
function statusTag(value) {
  const tag=el('span',words[value],'status');tag.dataset.tone=value;return tag;
}
function flags(items) {
  const box=el('span',null,'row-end'), failures=items.filter(isFailure).length, repeats=items.filter(s=>s.attempt>1).length;
  if(failures) {
    const f=el('span','! '+failures,'flag fault');f.title='Ошибок и прерываний: '+failures;f.setAttribute('aria-label',f.title);box.append(f);
  }
  if(repeats) {
    const f=el('span','↶ '+repeats,'flag retry');f.title='Повторных попыток: '+repeats;f.setAttribute('aria-label',f.title);box.append(f);
  }
  const signals=items.filter(s=>attention.has(s.id));
  if(signals.length && !failures && !repeats) {
    const f=el('span','Ⅱ '+signals.length,'flag notice');
    f.title='Узлов с предупреждением или ожиданием: '+signals.length; f.setAttribute('aria-label',f.title);box.append(f);
  }
  box.append(statusTag(aggregate(items)));
  return box;
}
// Only an explicit wait or watchdog stop changes the meaning of an interval.
// Warnings and a silent journal are observations, not queue/backoff timestamps.
function timeParts(s) {
  let from=instant(s.start), mode=s.phase==='waiting'?'wait':'work';
  const result=[];
  for(const signal of s.signals) {
    const next={waiting:'wait',stalled:'stop',progress:'work'}[signal.kind];
    if(!next || next===mode) continue;
    const at=Math.max(from,instant(signal.at));
    if(at>from) result.push({from,to:at,mode});
    from=at;mode=next;
  }
  result.push({from,to:s.end?instant(s.end):null,mode});
  return result;
}
function taggedTime(s,mode,now=clock()) {
  return timeParts(s).filter(p=>p.mode===mode).reduce((ms,p)=>ms+Math.max(0,(p.to??now)-p.from),0);
}
function relationKind(prev,s,link) {
  if(link==='parent')return 'parent';
  if(isFailure(prev) && identity(prev)!==identity(s))return 'fault';
  return s.attempt>1?'retry':isFailure(prev)?'fault':link;
}
function track(items) {
  const bar=el('span',null,'track');
  bar.setAttribute('aria-hidden','true');
  const lanes=[];
  for(const s of items) {
    const start=instant(s.start);
    let lane=lanes.findIndex(end=>end<=start);
    if(lane===-1) lane=lanes.length;
    lanes[lane]=s.end?instant(s.end):Infinity;
    for(const part of timeParts(s)) {
      const mark=el('i');mark.dataset.tone=tone(s);mark.dataset.stage=s.id;
      mark.dataset.from=part.from;
      if(part.to!==null) mark.dataset.to=part.to;
      mark.dataset.mode=part.mode;
      mark.style.setProperty('--lane',lane);
      if(s.attempt>1) mark.classList.add('repeat');
      const meaning={wait:'Ожидание',stop:'Остановка',work:words[tone(s)]}[part.mode];
      mark.title=displayName(s)+' · '+meaning+' · '+shortTime((part.to??clock())-part.from);
      bar.append(mark);
    }
  }
  bar.style.setProperty('--lanes',Math.max(lanes.length,1));
  return bar;
}
function pin(b,key,items) {
  const p=el('span',null,'pin');b.prepend(p);anchors.set(key,p);
  for(const s of items) endpoints.set(s.id,key);
}
function disclosure(key,title,items,expanded,cls,act) {
  const b=button(null,key,act,cls), value=aggregate(items);
  b.dataset.tone=value;
  b.setAttribute('aria-expanded',String(expanded));
  const chev=el('span',expanded?'▾':'▸','chev');chev.setAttribute('aria-hidden','true');
  b.append(chev,glyph(value),el('span',title,'row-title'),flags(items));
  return b;
}
function toggle(set,key) {
  if(set.has(key)) set.delete(key); else set.add(key);
}
function focusButton(key,scroll) {
  const b=[...document.querySelectorAll('button[data-focus]')].find(e=>e.dataset.focus===key);
  if(b){if(scroll) b.scrollIntoView({block:'nearest'}); b.focus({preventScroll:true});}
}
function jump(s) {
  const key=keyOf(s), leaf=leafOf(s);
  openBranches.add(key);openNodes.add(leaf);selected=s.id;selectedNode=leaf;
  render(false);focusButton('attempt:'+s.id,true);
}
function jumpNode(key,node) {
  openBranches.add(key);openNodes.add(node);showUnused.add(key);selectedNode=node;selected='';
  render(false);focusButton('leaf:'+node,true);
}
function jumpBranch(key) {
  if(!groups.get(key).items.length) $('used').checked=false;
  openBranches.add(key);manual.add(key);render(false);focusButton('branch:'+key,true);
}
function attemptRow(s) {
  const box=el('div',null,'attempt'), opened=selected===s.id;
  const b=button(null,'attempt:'+s.id,()=>{
    selected=opened?'':s.id;selectedNode=leafOf(s);render();
  },'attempt-head');
  b.setAttribute('aria-expanded',String(opened));b.dataset.tone=tone(s);
  const measured=el('span',shortTime(elapsed(s)),'attempt-duration');
  measured.dataset.stage=s.id;
  b.append(glyph(tone(s)),el('span','Попытка '+s.attempt,'row-title'),statusTag(tone(s)),
    el('time',clockTime(s.start)),measured,track([s]));
  pin(b,'attempt:'+s.id,[s]);box.append(b);
  if(!opened) return box;
  const detail=el('div',null,'attempt-detail');detail.dataset.tone=tone(s);
  detail.append(el('h3',s.name));
  const info=[words[tone(s)],s.point?'Пункт '+s.point:'',s.failure?failureKinds[s.failure]:'',
              shortTime(elapsed(s))].filter(Boolean);
  detail.append(el('p',info.join(' · ')));
  for(const [mode,label] of [['wait','Записанное ожидание'],['stop','Подтверждённая остановка']]) {
    const ms=taggedTime(s,mode);
    if(ms>0)detail.append(el('p',label+' · '+shortTime(ms),'interval-detail'));
  }
  for(const [id,label] of [[s.after,s.link==='explicit'?'После':'Следом по времени'],[s.parent,'В составе']]) {
    const prev=byId.get(id);
    if(prev) detail.append(button(label+' → '+displayName(prev),'relation:'+s.id+':'+label,()=>jump(prev),'relation'));
  }
  const observations=state.events.filter(e=>e.id===s.id && ['progress','quiet','warning','waiting','stalled'].includes(e.kind));
  if(observations.length){
    const ul=el('ul');
    for(const n of observations) {
      const note=n.message ? ' · '+n.message : '';
      ul.append(el('li',clockTime(n.at)+' · '+words[n.kind]+note));
    }
    detail.append(ul);
  }
  box.append(detail);return box;
}
function leafRow(group,leaf) {
  const wrap=el('div',null,'leaf'), opened=openNodes.has(leaf.key);
  const b=disclosure('leaf:'+leaf.key,leaf.title,leaf.items,opened,'leaf-head',()=>{
    manualNodes.add(leaf.key);toggle(openNodes,leaf.key);selected='';selectedNode=openNodes.has(leaf.key)?leaf.key:'';render();
  });
  b.append(track(leaf.items));pin(b,'leaf:'+leaf.key,leaf.items);wrap.append(b);
  if(!opened) return wrap;
  const body=el('div',null,'leaf-body');
  if(leaf.ref) body.append(el('p',leaf.ref.detail));
  for(const s of leaf.items) body.append(attemptRow(s));
  if(!leaf.items.length) body.append(el('small','Узел пока не запускался','subtle'));
  if(leaf.ref) {
    const graph=graphs.get(group.key), next=graph.edges.filter(e=>e.a===leaf.ref.id);
    if(next.length) {
      const links=el('div','По атласу ','node-links');
      for(const e of next) {
        const target=group.key+'.'+e.b, title=group.leaves.get(target).title;
        links.append(button((e.label?e.label+' · ':'')+'→ '+title,'plan:'+leaf.key+'>'+target,()=>jumpNode(group.key,target)));
      }
      body.append(links);
    }
  }
  wrap.append(body);return wrap;
}
function branchRow(g) {
  const row=el('section',null,'branch'), opened=openBranches.has(g.key);
  const b=disclosure('branch:'+g.key,g.title,g.items,opened,'branch-head',()=>{
    manual.add(g.key);toggle(openBranches,g.key);render();
  });
  if(!opened && g.items.length) {
    const names=[...new Set(g.items.map(displayName))];
    const preview=el('span',names.slice(0,2).join(' · ')+(names.length>2?' +'+(names.length-2):''),'preview');
    b.insertBefore(preview,b.querySelector('.row-end'));
  }
  b.append(track(g.items));pin(b,'branch:'+g.key,g.items);row.append(b);
  if(!opened) return row;
  const children=el('div');children.setAttribute('role','group');children.setAttribute('aria-label',g.title);
  const unvisited=[...g.leaves.values()].filter(n=>!n.items.length);
  for(const leaf of g.leaves.values()){
    if(leaf.items.length || !g.items.length || showUnused.has(g.key)) children.append(leafRow(g,leaf));
  }
  if(g.items.length && unvisited.length) children.append(button(showUnused.has(g.key)?'Скрыть незадействованные узлы':'Ещё узлы атласа ('+unvisited.length+')','more:'+g.key,()=>{
    toggle(showUnused,g.key);render();
  },'muted-button'));
  row.append(children);return row;
}
function scheduleWires() {
  cancelAnimationFrame(scheduled);scheduled=requestAnimationFrame(drawWires);
}
function drawWires() {
  const paper=$('wires'), origin=$('tree').getBoundingClientRect();
  if(!origin.width) return;
  const colors={explicit:'#8eac85',sequence:'#8eac85',retry:'#edc27d',fault:'#ef9f8c',parent:'#879183',plan:'#788375'};
  const defs=svg('defs',{});
  for(const [key,color] of Object.entries(colors)) {
    const m=svg('marker',{id:'end-'+key,viewBox:'0 0 8 8',refX:7,refY:4,markerWidth:5,markerHeight:5,orient:'auto'});
    m.append(svg('path',{d:'M0 0L8 4L0 8Z',fill:color}));defs.append(m);
  }
  const positions=new Map();
  for(const [key,pin] of anchors) {
    const r=pin.getBoundingClientRect();positions.set(key,{x:r.left-origin.left,y:r.top-origin.top+1});
  }
  const paths=new Map();
  function add(a,b,kind,relation,caption) {
    if(!a||!b||(!positions.has(a)||!positions.has(b))||(a===b && kind!=='retry')) return;
    const key=JSON.stringify([a,b,kind,relation]);
    if(paths.has(key)){paths.get(key).count++;return;}
    paths.set(key,{a,b,kind,relation,caption,count:1});
  }
  for(const s of stages) {
    const prev=byId.get(s.after), parent=byId.get(s.parent), target=endpoints.get(s.id);
    if(prev) {
      const kind=relationKind(prev,s,s.link);
      add(endpoints.get(prev.id),target,kind,s.link,displayName(prev)+' → '+displayName(s));
    } else if(s.attempt>1) {
      const old=stages.filter(p=>identity(p)===identity(s)&&p.attempt===s.attempt-1&&p.end&&p.end<=s.start);
      if(old.length===1) add(endpoints.get(old[0].id),target,'retry','repeat','Повтор того же узла');
    }
    if(parent && parent!==prev) add(endpoints.get(parent.id),target,'parent','parent','Вложенный этап');
  }
  const group=graphs.get(selectedNode.split('.')[0]);
  if(group && openNodes.has(selectedNode)) {
    for(const e of group.edges) {
      const a=group.id+'.'+e.a, b=group.id+'.'+e.b;
      if(selectedNode===a || selectedNode===b) add('leaf:'+a,'leaf:'+b,'plan','plan',e.label||'Возможный переход атласа');
    }
  }
  // Each overlapping vertical interval gets a separate track in the left gutter.
  const wires=[...paths.values()].map(e=>{
    const a=positions.get(e.a),b=positions.get(e.b);
    return {...e,fromKey:e.a,toKey:e.b,a,b,start:Math.min(a.y,b.y)-5,end:Math.max(a.y,b.y)+5};
  }).sort((a,b)=>a.start-b.start || b.end-a.end);
  const tracks=[];
  for(const wire of wires) {
    let lane=tracks.findIndex(end=>end<wire.start);
    if(lane===-1) lane=tracks.length;
    tracks[lane]=wire.end;wire.lane=lane;
  }
  const rail=parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--rail'))||62;
  const fragment=document.createDocumentFragment();fragment.append(defs);
  const root=positions.get('root');
  if(root) {
    const spineX=root.x-4;
    const branches=[...positions].filter(([key])=>key.startsWith('branch:')).map(([,p])=>p);
    if(branches.length){
      fragment.append(svg('path',{d:'M '+spineX+' '+root.y+' V '+branches.at(-1).y,
        fill:'none',stroke:'#455245','stroke-width':1,'stroke-dasharray':'2 4'}));
      for(const p of branches) fragment.append(svg('path',{d:'M '+spineX+' '+p.y+' H '+p.x,
        fill:'none',stroke:'#455245','stroke-width':1,'stroke-dasharray':'2 4'}));
    }
  }
  const layers={plan:0,parent:1,sequence:2,explicit:3,fault:4,retry:5};
  wires.sort((a,b)=>layers[a.kind]-layers[b.kind]);
  for(const w of wires) {
    const x=rail-9-(w.lane+1)*(rail-14)/Math.max(2,tracks.length+1);
    const same=w.a===w.b, y1=w.a.y-(same?5:0),y2=w.b.y+(same?5:0);
    const sign=y2>=y1?1:-1, rad=Math.min(5,Math.abs(y2-y1)/3);
    const d='M '+w.a.x+' '+y1+' H '+(x+rad)+' Q '+x+' '+y1+' '+x+' '+(y1+sign*rad)+
      ' V '+(y2-sign*rad)+' Q '+x+' '+y2+' '+(x+rad)+' '+y2+' H '+(w.b.x-2);
    const line=svg('path',{d,fill:'none',stroke:colors[w.kind],'stroke-width':w.kind==='retry'||w.kind==='fault'?2.4:1.3,
      'data-kind':w.kind,'data-link':w.relation,'data-from':w.fromKey,'data-to':w.toKey,'marker-end':'url(#end-'+w.kind+')'});
    if(w.kind==='retry') line.setAttribute('stroke-dasharray','6 3');
    else if(w.relation==='sequence' || w.kind==='parent' || w.kind==='plan') line.setAttribute('stroke-dasharray','2 3');
    const title=svg('title',{});title.textContent=w.caption+(w.count>1?' ×'+w.count:'');line.append(title);fragment.append(line);
  }
  paper.replaceChildren(fragment);
  for(const label of document.querySelectorAll('[data-legend]')) label.hidden=!wires.some(w=>w.kind===label.dataset.legend);
}
function renderNavigator() {
  const root=$('navigator'), buttons=[];
  for(const [key,g] of groups) {
    const b=button(null,'nav:'+key,()=>jumpBranch(key),'nav-step');
    b.dataset.tone=aggregate(g.items);b.append(el('span',g.title));
    if(g.items.some(isFailure)) b.classList.add('has-issue');
    b.title=g.title+' · '+words[b.dataset.tone];b.setAttribute('aria-label',b.title);
    buttons.push(b);
  }
  root.replaceChildren(...buttons);
}
function metric(label,value,toneKey) {
  const box=el('div',null,'metric');if(toneKey)box.dataset.tone=toneKey;
  box.append(el('strong',String(value)),el('small',label));return box;
}
// Only show a corrective chain if the explicit predecessors actually reach the failed attempt.
function recoveryChains() {
  const chains=[];
  for(const s of stages.filter(t=>t.attempt>1)) {
    const chain=[s],seen=new Set([s.id]);let cursor=s;
    while(cursor.link==='explicit') {
      cursor=byId.get(cursor.after);
      if(!cursor||seen.has(cursor.id))break;
      chain.push(cursor);seen.add(cursor.id);
      if(identity(cursor)===identity(s) && isFailure(cursor)) {chains.push(chain.reverse());break;}
    }
  }
  return chains;
}

// Expand attempts along the recorded predecessor (or, in its absence, parent).
// The longest continuation stays on the same rail; each sibling gets its own lane.
function routeLayout(items) {
  const placed=new Map(), roots=[];
  for(const s of items) {
    const previous=placed.get(s.after), parent=placed.get(s.parent);
    const from=previous || parent;
    const rank=1+Math.max(previous?.rank??-1,parent?.rank??-1);
    const n={s,from,parent,link:previous?s.link:parent?'parent':'',children:[],
      rank,depth:1,lanes:1,lane:0};
    placed.set(s.id,n);
    if(from)from.children.push(n);else roots.push(n);
  }
  for(const n of [...placed.values()].reverse()) {
    if(!n.children.length)continue;
    n.children.sort((a,b)=>b.depth-a.depth || instant(a.s.start)-instant(b.s.start));
    n.depth=1+n.children[0].depth;
    n.lanes=n.children.reduce((sum,c)=>sum+c.lanes,0);
  }
  let total=0;
  for(const n of roots){n.lane=total;total+=n.lanes;}
  for(const n of placed.values()){
    let lane=n.lane;
    for(const child of n.children){child.lane=lane;lane+=child.lanes;}
  }
  return {nodes:[...placed.values()],lanes:total};
}
function routeLabel(s) {
  const leaf=groups.get(keyOf(s))?.leaves.get(leafOf(s));
  // Reference names are stable for machine-generated stages; retain an author's repair label.
  return leaf?.ref && (s.name===s.point+':'+s.phase || /^[a-z-]+$/.test(s.name))?leaf.title:s.name;
}
function routeMap() {
  const board=$('route-board'), pane=$('route-window'), layout=routeLayout(stages);
  $('rail-count').textContent='Запусков · '+stages.length;
  $('rail-fail').hidden=!stages.some(isFailure);
  $('rail-retry').hidden=!stages.some(s=>s.attempt>1);
  if(!stages.length) {
    board.removeAttribute('style');board.replaceChildren(el('p','Здесь появится первая записанная попытка.','empty'));return;
  }
  const columns=layout.nodes.reduce((n,item)=>Math.max(n,item.rank+1),1);
  const width=Math.max(pane.clientWidth,columns*156+24);
  const cell=Math.min(205,(width-24)/columns);
  const left=(width-columns*cell)/2+cell/2;
  const row=88, height=layout.lanes*row+12, center=25, radius=12;
  board.style.width=width+'px';board.style.height=height+'px';
  const lines=svg('svg',{width,height,'aria-hidden':'true',class:'route-lines'});
  const boxes=[];
  const repeated=new Set(stages.filter(s=>s.attempt>1).map(identity));
  const scopes=new Set(stages.map(s=>s.parent).filter(Boolean));
  for(const n of layout.nodes) {
    n.x=left+n.rank*cell;n.y=center+n.lane*row;
    if(n.from) {
      const x1=n.from.x+radius, x2=n.x-radius, bend=(x1+x2)/2;
      const kind=relationKind(n.from.s,n.s,n.link);
      const path=svg('path',{d:'M '+x1+' '+n.from.y+' C '+bend+' '+n.from.y+' '+bend+' '+n.y+' '+x2+' '+n.y,
        'data-kind':kind,'data-link':n.link,'data-from':n.from.s.id,'data-to':n.s.id});
      lines.append(path);
      if(['retry','fault'].includes(kind)) {
        lines.append(svg('path',{d:'M '+(x2-5)+' '+(n.y-3)+' l 4 3 -4 3','data-kind':kind,class:'route-tip'}));
      }
    }
    if(n.parent && n.parent!==n.from) {
      // Cross long distances between rows, entering the child through the empty inter-column gap.
      const p=n.parent, start=p.x+radius, end=n.x-radius, viaY=p.y-18;
      const outX=p.x+cell*.42,inX=n.x-cell*.48;
      const d='M '+start+' '+p.y+' H '+(outX-4)+' Q '+outX+' '+p.y+' '+outX+' '+(p.y-4)+
        ' V '+viaY+' H '+inX+' V '+(n.y+4)+' H '+end;
      lines.prepend(svg('path',{d,'data-kind':'parent','data-link':'parent','data-from':p.s.id,'data-to':n.s.id}));
    }
    const s=n.s, b=button(null,'route:'+s.id,()=>jump(s),'route-stop');
    b.style.left=n.x+'px';b.style.top=(n.y-radius)+'px';b.style.width=Math.min(cell-9,165)+'px';
    b.dataset.tone=tone(s);b.dataset.id=s.id;b.dataset.lane=n.lane;
    b.setAttribute('aria-label',routeLabel(s)+', попытка '+s.attempt+', '+words[tone(s)]);
    const prefix=s.attempt>1?'↶ №'+s.attempt+' · ':repeated.has(identity(s))?'№1 · ':scopes.has(s.id)?'Группа · ':'';
    const caption=el('small',prefix+shortTime(elapsed(s)));
    caption.dataset.prefix=prefix;
    b.append(glyph(tone(s)),el('strong',routeLabel(s)),caption);
    if(s.id===selected)b.classList.add('chosen');
    b.title=displayName(s)+' · '+words[tone(s)]+' · '+clockTime(s.start);
    boxes.push(b);
  }
  board.replaceChildren(lines,...boxes);
  if(!initialRoutePosition && pane.clientWidth>0 && stages.length) {
    const issue=stages.find(isFailure);
    if(issue && pane.clientWidth<600)positionRoute(issue,false);
    initialRoutePosition=true;
  }
}
function positionRoute(s,focus=true) {
  if(!s)return;
  const pane=$('route-window');
  const stop=$('route-board').querySelector('[data-id="'+CSS.escape(s.id)+'"]');
  if(!stop)return;
  pane.scrollLeft=stop.offsetLeft-pane.clientWidth*.35;
  if(focus)stop.focus({preventScroll:true});
}
function timeWindows() {
  const select=$('time-window');
  const options=[new Option('Весь прогон','full')];
  for(const path of chains) {
    const last=path.at(-1);
    options.push(new Option('Повтор №'+last.attempt+' · '+routeLabel(last)+(last.point?' · '+last.point:''),last.id));
  }
  select.replaceChildren(...options);
  if(timeRange==='auto' && chains.length)timeRange=chains.at(-1).at(-1).id;
  if(timeRange!=='auto' && timeRange!=='full' && !chains.some(c=>c.at(-1).id===timeRange))timeRange='full';
  select.value=timeRange==='auto'?'full':timeRange;
}
function timeBounds(now) {
  const chain=chains.find(c=>c.at(-1).id===timeRange);
  if(chain) {
    const last=chain.at(-1),start=instant(chain[0].start),end=last.end?instant(last.end):now;
    return {start,end:Math.max(start+1,end)};
  }
  const start=instant(state.start);
  return {start,end:Math.max(start+1,now)};
}
function showRecovery(path) {
  const last=path.at(-1);
  timeRange=last.id;
  for(const s of path){openBranches.add(keyOf(s));openNodes.add(leafOf(s));}
  render(false);
  focusButton('attempt:'+path[0].id,true);
}
function summary() {
  const failures=stages.filter(isFailure), repeats=stages.filter(s=>s.attempt>1);
  const used=[...groups.values()].filter(g=>graphs.has(g.key)&&g.items.length).length;
  $('metrics').replaceChildren(metric('Этапов атласа',used+'/'+graphs.size),metric('Запусков',stages.length),
    metric('Сбоев',failures.length,failures.length?'failed':''),metric('Повторов',repeats.length,repeats.length?'running':''));
  const box=$('incidents');box.replaceChildren();
  const covered=new Set();
  function addCard(label,items,recovery=false) {
    const card=el('div',null,'incident');card.append(el('h3',label));
    for(const [i,s] of items.entries()) {
      const b=button(null,'incident:'+items.at(-1).id+':'+s.id,()=>jump(s),'incident-step');
      b.dataset.tone=tone(s);
      const role=recovery && i>0 && i<items.length-1 ? 'Между попытками' : 'Попытка '+s.attempt;
      b.append(el('small',role+' · '+shortTime(elapsed(s))),el('strong',displayName(s)),statusTag(tone(s)));
      const message=s.signals.at(-1)?.message;
      if(message)b.append(el('span',message,'incident-note'));
      const waiting=taggedTime(s,'wait');
      if(waiting>0)b.append(el('span','Ожидание по журналу · '+shortTime(waiting),'incident-note'));
      card.append(b);
    }
    if(recovery)card.append(button('Показать на шкале →','zoom:'+items.at(-1).id,()=>showRecovery(items),'zoom-link'));
    box.append(card);
  }
  for(const path of chains) {
    addCard(path.at(-1).status==='ok'?'Ошибка и успешный повтор':'Возврат к проверке',path,true);
    for(const s of path) covered.add(s.id);
  }
  for(const s of stages) {
    if(covered.has(s.id)) continue;
    if(isFailure(s) || ['stalled','warning','quiet','waiting'].includes(tone(s))) addCard(words[tone(s)],[s]);
    else if(attention.has(s.id)) addCard('В истории · '+words[attention.get(s.id)],[s]);
  }
}
function renderLog() {
  const mode=$('filter').value, rows=[];
  for(const e of [...state.events].reverse()) {
    const s=byId.get(e.id);if(!s)continue;
    if(mode==='failed' && !['failed','interrupted','stalled'].includes(e.kind))continue;
    if(mode==='repeat' && !(s.attempt>1 && e.kind==='begin'))continue;
    if(mode==='waiting' && !['waiting','warning','stalled','quiet'].includes(e.kind))continue;
    const row=el('li'),b=button(null,'event:'+s.id+':'+e.at+':'+e.kind,()=>jump(s),'event');
    const tag=el('span',words[e.kind]||e.kind,'tag');tag.dataset.tone=e.kind==='begin'?'running':e.kind;
    b.append(el('time',clockTime(e.at)),tag,el('strong',displayName(s)));
    const context=[s.point,s.attempt>1?'Попытка '+s.attempt:'',e.kind==='failed'?failureKinds[s.failure]:'',
      e.message].filter(Boolean);
    if(context.length) b.append(el('small',context.join(' · ')));
    row.append(b);rows.push(row);
  }
  $('total').textContent=String(rows.length);
  $('events').replaceChildren(...(rows.length?rows:[el('li','Событий пока нет','empty')]));
}
function render(keepFocus=true, keepPosition=false) {
  const focused=keepFocus?document.activeElement?.dataset.focus:null;
  let anchor=null, top=0;
  if(keepPosition) {
    const old=[...$('branches').querySelectorAll('[data-focus]')].find(n=>n.getBoundingClientRect().bottom>0);
    if(old){anchor=old.dataset.focus;top=old.getBoundingClientRect().top;}
  }
  endpoints=new Map();anchors=new Map();
  chains=recoveryChains();timeWindows();routeMap();
  const rows=[];
  for(const g of groups.values()){
    if(!$('used').checked || g.items.length) rows.push(branchRow(g));
  }
  const root=el('div',null,'tree-root');
  const origin=el('i');anchors.set('root',origin);
  root.append(origin,el('strong','Начало прогона'),el('time',clockTime(state.start)));
  $('branches').replaceChildren(root,...(rows.length?rows:[el('p','Задействованные этапы появятся здесь после первого запуска.','empty')]));
  renderNavigator();summary();renderLog();paintTime();scheduleWires();
  if(focused)focusButton(focused,false);
  if(anchor){
    const current=[...$('branches').querySelectorAll('[data-focus]')].find(b=>b.dataset.focus===anchor);
    if(current)window.scrollBy(0,current.getBoundingClientRect().top-top);
  }
}
function paintTime() {
  const now=clock(), {start,end}=timeBounds(now), span=end-start;
  $('duration').textContent=duration(now-instant(state.start));
  for(const s of stages.filter(s=>s.status==='running')) {
    const caption=$('route-board').querySelector('[data-id="'+CSS.escape(s.id)+'"] small');
    if(caption)caption.textContent=caption.dataset.prefix+shortTime(elapsed(s,now));
    const measured=$('tree').querySelector('.attempt-duration[data-stage="'+CSS.escape(s.id)+'"]');
    if(measured)measured.textContent=shortTime(elapsed(s,now));
  }
  const axis=$('scale');
  const ticks=[0,.5,1].map(f=>shortTime(span*f));
  if(axis.dataset.labels!==ticks.join('/')) {
    axis.dataset.labels=ticks.join('/');
    axis.replaceChildren(...ticks.map(t=>el('span',t)));
  }
  axis.title='От '+clockTime(start)+' до '+clockTime(end);
  for(const mark of document.querySelectorAll('.track i')) {
    const from=Number(mark.dataset.from), to=mark.hasAttribute('data-to')?Number(mark.dataset.to):now;
    mark.hidden=to<start || from>end;
    if(mark.hidden)continue;
    const x=Math.max(0,Math.min(100,100*(from-start)/span));
    const width=Math.max(0,100*(Math.min(to,end)-Math.max(from,start))/span);
    mark.style.left=x+'%';mark.style.width=width+'%';
  }
}
function syncControls() {
  const points=[...new Set(state.stages.map(s=>s.point).filter(Boolean))];
  $('points-wrap').hidden=!points.length;
  $('point').replaceChildren(new Option('Все пункты',''),...points.map(p=>new Option(p,p)));
  $('point').value=point;
  $('title').textContent=state.title;
  $('run-id').textContent='Прогон '+state.run.slice(0,8)+' / '+dateTime(state.start);
  $('job-status').textContent=words[state.status];
  $('source').textContent=bundle.live?'Локальный журнал':'Автономный снимок журнала';
}
function connection() {
  const text=!bundle.live?'Сохранённый снимок':lost?'Связь потеряна':state.end?'Журнал завершён':'● В эфире';
  $('connection').dataset.offline=String(lost);
  if($('connection').textContent!==text)$('connection').textContent=text;
}
function signature() {
  return JSON.stringify([state.status,state.stages,state.events.length,stages.map(tone)]);
}
async function poll() {
  try {
    const response=await fetch('state',{cache:'no-store',signal:AbortSignal.timeout(5000)});
    if(!response.ok)throw Error('journal unavailable');
    const fresh=await response.json();
    if(fresh.run!==state.run)throw Error('different journal');
    state=fresh;receivedAt=Date.now();lost=false;makeGroups();
    const next=signature();
    if(next!==previousSignature){
      previousSignature=next;autoOpen();syncControls();render(true,true);
    } else paintTime();
  } catch {
    if(!lost)pausedClock=clock();
    lost=true;
  }
  connection();
  if(!state.end)setTimeout(poll,1000);
}
$('expand').onclick=()=>{
  for(const g of groups.values())if(!$('used').checked||g.items.length){
    manual.add(g.key);openBranches.add(g.key);showUnused.add(g.key);
  }
  render();
};
$('collapse').onclick=()=>{
  for(const [key,g] of groups){manual.add(key);for(const n of g.leaves.keys())manualNodes.add(n);}
  openBranches.clear();openNodes.clear();showUnused.clear();selected='';selectedNode='';render();
};
$('used').onchange=()=>render();
$('point').onchange=()=>{point=$('point').value;selected='';selectedNode='';makeGroups();autoOpen();render();};
$('filter').onchange=renderLog;
$('rail-fail').onclick=()=>positionRoute(stages.find(isFailure));
$('rail-retry').onclick=()=>positionRoute(chains.at(-1)?.at(-1) || stages.filter(s=>s.attempt>1).at(-1));
$('time-window').onchange=()=>{timeRange=$('time-window').value;paintTime();};
window.addEventListener('resize',scheduleWires);
let routeWidth=0;
new ResizeObserver(entries=>{
  const width=entries[0].contentRect.width;
  if(width===routeWidth)return;
  routeWidth=width;
  const key=document.activeElement?.closest('#route-board')?document.activeElement.dataset.focus:null;
  routeMap();
  if(key)focusButton(key,false);
}).observe($('route-window'));
new ResizeObserver(scheduleWires).observe($('tree'));
makeGroups();autoOpen(true);syncControls();render();previousSignature=signature();connection();
if(bundle.live && !state.end)poll();
