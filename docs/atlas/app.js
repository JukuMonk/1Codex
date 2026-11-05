(()=>{
'use strict';
const nodes=JSON.parse(document.getElementById('node-data').textContent);
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const types={step:'Действие',decision:'Развилка',check:'Проверка',artifact:'Результат',external:'Настройка проекта',error:'Ошибка / возврат'};
const dialog=$('#node-dialog'),search=$('#search-dialog'),full=$('#graph-dialog');
function showNode(id){
 const n=nodes[id];if(!n)return;
 $$('.node.selected').forEach(e=>e.classList.remove('selected'));$$('.edge.related').forEach(e=>e.classList.remove('related'));
 $$(`[data-node="${id}"]`).forEach(e=>e.classList.add('selected'));
 $$(`.edge[data-from="${id}"],.edge[data-to="${id}"]`).forEach(e=>e.classList.add('related'));
 $('#detail-context').textContent=n.chapter;$('#detail-kind').textContent=types[n.kind];$('#detail-title').textContent=n.title;$('#detail-sub').textContent=n.sub;$('#detail-body').textContent=n.detail;
 $('#detail-artifact-wrap').hidden=!n.artifact;$('#detail-artifact').textContent=n.artifact;$('#detail-source').href=n.source_url;
 const related=$('#detail-related>div');related.replaceChildren();
 const ids=[...new Set($$(`main .edge[data-from="${id}"]`).map(e=>e.dataset.to))];
 $('#detail-related').hidden=!ids.length;
 ids.forEach(next=>{const b=document.createElement('button');b.type='button';b.textContent=nodes[next].title+' →';b.onclick=()=>showNode(next);related.append(b)});
 if(!dialog.open)dialog.showModal();
}
document.addEventListener('click',e=>{const n=e.target.closest('[data-node]');if(n)showNode(n.dataset.node)});
document.addEventListener('keydown',e=>{const n=e.target.closest('[data-node]');if(n&&(e.key==='Enter'||e.key===' ')){e.preventDefault();showNode(n.dataset.node)}});
for(const d of [dialog,search])d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close()}});
function openSearch(){search.showModal();$('#search-input').focus();renderSearch()}
$('#search-open').onclick=openSearch;
document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA'].includes(e.target.tagName)&&!dialog.open&&!search.open&&!full.open){e.preventDefault();openSearch()}});
function renderSearch(){const q=$('#search-input').value.trim().toLocaleLowerCase('ru');const result=$('#search-results');result.replaceChildren();if(!q){$('#search-status').textContent='Поиск по названиям, пояснениям и инструментам всех узлов';return}
 const matches=Object.entries(nodes).filter(([id,n])=>[n.title,n.sub,n.detail,n.artifact,n.source].join(' ').toLocaleLowerCase('ru').includes(q));
 $('#search-status').textContent=`Найдено: ${matches.length}`;
 for(const [id,n] of matches){const b=document.createElement('button'),small=document.createElement('small'),title=document.createElement('span');b.type='button';small.textContent=n.chapter;title.textContent=n.title;b.append(small,title);b.onclick=()=>{search.close();location.hash=n.section;showNode(id)};result.append(b)}
}
$('#search-input').addEventListener('input',renderSearch);
let graphWidth=1000,zoom=1;
function scaleGraph(v){zoom=Math.max(.25,Math.min(2.5,v));$('#graph-canvas svg').style.width=`${graphWidth*zoom}px`;$('#graph-scale').textContent=Math.round(zoom*100)+'%'}
function openGraph(container){const original=container.querySelector('svg');const clone=original.cloneNode(true);graphWidth=Number(original.dataset.width);
 // Unique identifiers keep marker and title references valid while the original is visible behind the dialog.
 const ids=new Map([...clone.querySelectorAll('[id]')].map(e=>[e.id,e.id+'-expanded']));
 clone.querySelectorAll('*').forEach(e=>{if(e.id)e.id=ids.get(e.id);for(const a of ['marker-end','aria-labelledby']){const value=e.getAttribute(a);if(value){let updated=value;for(const [oldId,newId] of ids){updated=updated.replace(`url(#${oldId})`,`url(#${newId})`);if(updated===oldId)updated=newId}e.setAttribute(a,updated)}}});
 if(clone.hasAttribute('aria-labelledby'))clone.setAttribute('aria-labelledby',clone.getAttribute('aria-labelledby')+'-expanded');
 $('#graph-title').textContent=container.closest('section').querySelector('h2').textContent;$('#graph-canvas').replaceChildren(clone);full.showModal();scaleGraph(Math.min(1,($('#graph-canvas').clientWidth-24)/graphWidth));$('#graph-canvas').scrollTo(0,0);
}
$$('.diagram button').forEach(b=>b.onclick=()=>{const container=b.closest('.diagram');if(b.dataset.action==='expand')openGraph(container);else container.querySelector('.graph-scroll').classList.toggle('actual',b.dataset.action==='actual')});
$('#graph-zoom-in').onclick=()=>scaleGraph(zoom+.15);$('#graph-zoom-out').onclick=()=>scaleGraph(zoom-.15);$('#graph-fit').onclick=()=>scaleGraph(($('#graph-canvas').clientWidth-24)/graphWidth);$('#graph-close').onclick=()=>full.close();
$('#print').onclick=()=>window.print();
function theme(dark){document.body.classList.toggle('dark',dark);$('#theme-toggle').textContent=dark?'Светлая тема':'Тёмная тема';$('#theme-toggle').setAttribute('aria-pressed',String(dark))}
try{theme(localStorage.getItem('1codex-atlas-terminal-theme')!=='light')}catch{theme(true)}
$('#theme-toggle').onclick=()=>{const d=!document.body.classList.contains('dark');theme(d);try{localStorage.setItem('1codex-atlas-terminal-theme',d?'dark':'light')}catch{}};
const links=$$('.rail nav a'),sections=$$('main>section');
let pendingScroll=false;
function markSection(){pendingScroll=false;let current=sections[0];for(const s of sections){if(s.getBoundingClientRect().top<=innerHeight*.3)current=s;else break}links.forEach(a=>a.classList.toggle('active',a.hash==='#'+current.id))}
window.addEventListener('scroll',()=>{if(!pendingScroll){pendingScroll=true;requestAnimationFrame(markSection)}},{passive:true});markSection();
// Preserve incoming links to the previous edition of the atlas.
const aliases={atlas:'overview',route:'analysis','minus-demo':'com','capabilities-map':'library',concept:'library',inventory:'library',architecture:'library',composition:'library',workflow:'analysis','manual-book':'analysis','updates-map':'delivery',updates:'delivery',environments:'library',formats:'implementation',tools:'implementation',validation:'evidence',reliability:'release',timing:'learning',start:'analysis',cases:'knowledge',handbook:'knowledge',limits:'library',sources:'library',testing:'evidence','negative-stock':'com'};
function resolveAlias(){const target=aliases[location.hash.slice(1)];if(target){history.replaceState(null,'','#'+target);document.getElementById(target).scrollIntoView()}}
window.addEventListener('hashchange',resolveAlias);resolveAlias();
let lastWidth=innerWidth;
function centerMobileGraphs(){if(innerWidth>900)return;$$('.graph-scroll').forEach(scroller=>{const first=scroller.querySelector('.node'),r=first.getBoundingClientRect(),box=scroller.getBoundingClientRect();scroller.scrollLeft+=r.left+r.width/2-box.left-scroller.clientWidth/2})}
requestAnimationFrame(centerMobileGraphs);
window.addEventListener('resize',()=>{if(lastWidth!==innerWidth){lastWidth=innerWidth;requestAnimationFrame(centerMobileGraphs)}});
const exampleButtons=$$('[data-stock-delta]');
function stockExample(button){const delta=Number(button.dataset.stockDelta),values=[20,0,10].map(v=>v+delta),xs=[80,440,800],ys=values.map(v=>180-v*5),bad=Math.min(...values)<0;
 $('#stock-candidate').setAttribute('points',xs.map((x,i)=>`${x},${ys[i]}`).join(' '));
 $$('.stock-dot').forEach((dot,i)=>{dot.setAttribute('cy',ys[i]);dot.setAttribute('fill',bad?'var(--danger)':'var(--accent)')});
 $$('.stock-value').forEach((label,i)=>{label.setAttribute('y',ys[i]-16);label.textContent=values[i]});
 $('#stock-candidate').setAttribute('stroke',bad?'var(--danger)':'var(--accent)');
 $('#stock-result').textContent=bad?`Операция должна быть отклонена: минимум внутри периода ${Math.min(...values)}. Проверка только начала (${values[0]}) и конца (${values[2]}) пропустила бы дефект.`:`Исходная история допустима: минимум ${Math.min(...values)}, конечный остаток ${values[2]}.`;
 $('#stock-result').classList.toggle('negative',bad);exampleButtons.forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
}
exampleButtons.forEach(b=>b.onclick=()=>stockExample(b));if(exampleButtons.length)stockExample(exampleButtons[1]);
})();
