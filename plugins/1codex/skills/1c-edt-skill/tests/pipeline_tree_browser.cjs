// NODE_PATH must contain Playwright. Run from the skill root.
// node tests/pipeline_tree_browser.cjs OUTPUT [BROWSER_EXECUTABLE]
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {spawn, spawnSync} = require('node:child_process');
const {chromium} = require('playwright');

const out = path.resolve(process.argv[2]);
fs.mkdirSync(out,{recursive:true});
const project = fs.mkdtempSync(path.join(out,'tree-run-'));
const python = process.env.PYTHON || 'python';
const env = {...process.env,PYTHONUTF8:'1'};
const tool = name => path.resolve('tools/workflow',name+'.py');
const run = (name,...args) => {
  const result=spawnSync(python,[tool(name),...args],{encoding:'utf8',env});
  if(result.status!==0) throw Error(result.stdout+result.stderr);
  return result.stdout.trim();
};
const journal=run('timing','start','--project',project,'--label','Проверка дерева');
const start=(name,node,...args)=>run('timing','begin',journal,name,'--node',node,...args);
const end=(id,status='ok')=>run('timing','end',journal,id,'--status',status);
const readURL=async file=>{
  const deadline=Date.now()+10000;
  while(Date.now()<deadline){
    if(fs.existsSync(file))return fs.readFileSync(file,'utf8');
    await new Promise(resolve=>setTimeout(resolve,50));
  }
  throw Error('Monitor did not start');
};

(async()=>{
  const checks=[],errors=[];
  const ready=path.join(project,'ready.url');
  const server=spawn(python,[tool('pipeline'),'serve',journal,'--ready',ready],{env,stdio:'ignore'});
  let browser;
  try {
    browser=await chromium.launch({headless:true,...(process.argv[3]?{executablePath:process.argv[3]}:{})});
    const p=await browser.newPage({viewport:{width:1440,height:960}});
    p.on('pageerror',e=>errors.push(e.message));
    await p.goto(await readURL(ready));
    const head=key=>p.locator('[data-focus="branch:'+key+'"]');
    const leaf=key=>p.locator('[data-focus="leaf:'+key+'"]');
    const attempt=id=>p.locator('[data-focus="attempt:'+id+'"]');
    const liveUntil=fn=>p.waitForFunction(fn);
    assert.equal(await p.locator('.branch').count(),12);
    assert.equal(await p.locator('.route-stop').count(),0);
    assert.equal(await p.title(),'Монитор 1Codex');
    assert.match(await p.locator('.mast .brand').innerText(), /Монитор 1Codex$/);
    checks.push('all chapters and the monitor name visible before work');
    const check=start('Проверка','platform.lint');
    await liveUntil(()=>document.querySelector('[data-focus="branch:platform"]').dataset.tone==='running');
    await head('platform').click();
    run('timing','signal',journal,check,'progress','Контрольная точка');
    await liveUntil(()=>document.querySelector('#events').textContent.includes('Контрольная точка'));
    assert.equal(await head('platform').getAttribute('aria-expanded'),'false');
    checks.push('manual collapse survives live event');
    end(check,'failed');
    const fix=start('Исправление','implementation.xml','--after',check);
    run('timing','signal',journal,fix,'waiting','Ожидание подтверждения тестового стенда');
    await p.waitForFunction(()=>document.querySelector('.track [data-mode="wait"]'));
    run('timing','signal',journal,fix,'warning','Предупреждение во время ожидания');
    run('timing','signal',journal,fix,'progress','Исправление проверено');
    end(fix);
    const retry=start('Повторная проверка','platform.lint','--after',fix);end(retry);
    await liveUntil(()=>document.getElementById('incidents').textContent.includes('Ошибка и успешный повтор'));
    await p.locator('#incidents button').first().click();
    assert.equal(await attempt(check).getAttribute('aria-expanded'),'true');
    assert.equal(await attempt(retry).count(),1);
    if(await head('implementation').getAttribute('aria-expanded')==='false')await head('implementation').click();
    assert.equal(await head('platform').getAttribute('aria-expanded'),'true');
    await p.waitForFunction(()=>document.querySelector('#wires [data-kind="retry"]'));
    checks.push('correction chain opens exact failed attempt, other branches stay visible');
    const routeLeg=(from,to)=>p.locator('#route-board path[data-from="'+from+'"][data-to="'+to+'"]');
    assert.equal(await routeLeg(check,fix).getAttribute('data-kind'),'fault');
    assert.equal(await routeLeg(fix,retry).getAttribute('data-kind'),'retry');
    assert.equal(await p.locator('#time-window').inputValue(),retry);
    await p.locator('#time-window').selectOption('full');
    await p.locator('#incidents .zoom-link').click();
    assert.equal(await p.locator('#time-window').inputValue(),retry);
    assert.equal(await attempt(check).locator('.track i[data-tone="failed"]').count(),1);
    const waiting=attempt(fix).locator('.track i[data-mode="wait"]');
    assert.equal(await waiting.count(),1);
    assert.ok(await waiting.evaluate(e=>Number(e.dataset.to)>Number(e.dataset.from) && e.offsetWidth>0));
    await p.locator('[data-focus="route:'+retry+'"]').click();
    assert.equal(await attempt(retry).getAttribute('aria-expanded'),'true');
    checks.push('route distinguishes repair and retry, waterfall zoom uses recorded wait, route click selects the right attempt');
    await p.locator('#collapse').click();
    await p.waitForFunction(()=>document.querySelector('#wires [data-from="branch:implementation"][data-to="branch:platform"][data-kind="retry"]'));
    assert.match(await head('platform').innerText(),/! 1/);
    checks.push('collapsed parents retain error count and retry arrow');

    const parent=start('Приёмка','evidence.decision');
    const com=start('COM','com.assert','--parent',parent);
    const ui=start('Форма','ui.actions','--parent',parent);
    await liveUntil(()=>document.querySelector('[data-focus="branch:ui"]').dataset.tone==='running');
    const cross='#wires [data-from="branch:com"][data-to="branch:ui"]';
    assert.equal(await p.locator(cross).count(),0);
    await p.waitForFunction(()=>document.querySelectorAll('#wires [data-kind="parent"]').length>=2);
    assert.notEqual(await p.locator('[data-focus="route:'+com+'"]').getAttribute('data-lane'),
                    await p.locator('[data-focus="route:'+ui+'"]').getAttribute('data-lane'));
    assert.equal(await routeLeg(com,ui).count(),0);
    assert.equal(await routeLeg(parent,com).getAttribute('data-link'),'parent');
    run('timing','signal',journal,ui,'stalled','Подтверждена остановка');
    await liveUntil(()=>document.querySelector('[data-focus="branch:ui"]').dataset.tone==='stalled');
    end(com);end(ui,'interrupted');end(parent,'failed');
    const legacy=run('timing','begin',journal,'Операция без привязки');
    end(legacy);
    run('timing','finish',journal,'--status','failed');
    await liveUntil(()=>document.getElementById('connection').textContent==='Журнал завершён');
    checks.push('parallel children have parent links and no invented dependency; stall and interruption persist');
    await p.locator('#filter').selectOption('failed');
    const errorCount=await p.locator('#events .event').count();assert.ok(errorCount>=3);
    await p.locator('#filter').selectOption('repeat');
    assert.equal(await p.locator('#events .event').count(),1);
    await p.locator('#events .event').click();
    assert.equal(await attempt(retry).getAttribute('aria-expanded'),'true');
    checks.push('event filters and jump to exact attempt');
    await p.locator('[data-focus="more:platform"]').click();
    assert.equal(await p.locator('[data-focus^="leaf:platform."]').count(),13);
    await leaf('platform.input').click();
    const plan=p.locator('[data-focus^="plan:platform.input>"]').first();
    await plan.click();
    assert.equal(await head('platform').getAttribute('aria-expanded'),'true');
    assert.equal(await p.locator('.branch').count(),13); // the extra branch is the unmapped stage
    checks.push('atlas links expand inline without leaving the tree');
    const portable=path.join(project,'tree.html');run('pipeline','export',journal,portable);
    const mobile=await browser.newPage({viewport:{width:390,height:844}});
    await mobile.route(/^https?:/,r=>r.abort());
    await mobile.goto(pathToFileURL(portable).href);
    await mobile.locator('#expand').click();
    assert.equal(await mobile.locator('.leaf-head').count(),140); // 139 atlas nodes + one legacy label
    await mobile.locator('#used').check();
    assert.ok(await mobile.locator('.branch').count()<12);
    assert.ok(await mobile.locator('.track').first().evaluate(e=>e.offsetWidth>0));
    assert.equal(await mobile.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    assert.equal(await mobile.locator('#connection').innerText(),'Сохранённый снимок');
    checks.push('offline export with expanded branches fits iPhone width');
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(out,'tree-checks.json'),JSON.stringify({checks,errors},null,2));
    console.log(checks.join('\n'));
  } finally {
    if(browser)await browser.close();
    server.kill();
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
