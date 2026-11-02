// Usage: NODE_PATH=<directory containing playwright> node check_browser.cjs HTML OUTPUT [EDGE]
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url');
const input=path.resolve(process.argv[2]||path.join(__dirname,'../index.html'));
const out=path.resolve(process.argv[3]||'atlas-browser-check');fs.mkdirSync(out,{recursive:true});
const edge=process.argv[4]||'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const tests=[],errors=[],requests=[];
function ok(v,s){if(!v)throw Error(s);tests.push(s)}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:edge});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  await context.route(/^https?:/,r=>{requests.push(r.request().url());return r.abort()});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(input).href);await page.evaluate(()=>document.fonts.ready);
  const meta=await page.evaluate(()=>({nodes:document.querySelectorAll('main .node').length,graphs:document.querySelectorAll('main .flow-svg').length,overflow:document.documentElement.scrollWidth>innerWidth}));
  ok(meta.nodes===139&&meta.graphs===12,'all 139 nodes and 12 graphs rendered without network');ok(!meta.overflow,'desktop page has no horizontal overflow');
  const clipping=await page.evaluate(()=>[...document.querySelectorAll('main .node')].flatMap(n=>[...n.querySelectorAll('text')].filter(t=>{const b=t.getBBox();return b.x<0||b.x+b.width>222||b.y<0||b.y+b.height>116}).map(t=>({node:n.dataset.node,text:t.textContent,box:JSON.stringify(t.getBBox())}))));
  fs.writeFileSync(path.join(out,'label-check.json'),JSON.stringify(clipping,null,2));ok(!clipping.length,'SVG labels stay inside their node boxes');
  await page.screenshot({path:path.join(out,'01-desktop.png')});
  await page.locator('#ui').evaluate(e=>e.scrollIntoView({block:'start'}));await page.waitForFunction(()=>document.querySelector('.rail a[href="#ui"]').classList.contains('active'));await page.screenshot({path:path.join(out,'02-ui-branches.png')});
  await page.locator('#ui').screenshot({path:path.join(out,'02-ui-full.png')});
  await page.locator('#metadata').evaluate(e=>e.scrollIntoView({block:'start'}));await page.waitForFunction(()=>document.querySelector('.rail a[href="#metadata"]').classList.contains('active'));await page.screenshot({path:path.join(out,'03-metadata.png')});
  ok(true,'navigation follows the visible chapter');
  await page.locator('#node-com-connector').focus();await page.keyboard.press('Enter');
  ok(await page.locator('#node-dialog').evaluate(e=>e.open),'keyboard activates a COM node');
  ok((await page.locator('#detail-body').innerText()).includes('разрядность'),'COM explanation contains actual constraints');
  await page.screenshot({path:path.join(out,'04-node-detail.png')});await page.keyboard.press('Escape');
  ok(!(await page.locator('#node-dialog').evaluate(e=>e.open)),'Escape closes detail and restores navigation');
  await page.locator('#search-open').click();await page.locator('#search-input').fill('Vanessa');
  ok(await page.locator('#search-results button').count()>2,'search indexes detailed explanations');
  await page.locator('#search-results button').filter({hasText:'Vanessa Automation'}).first().click();
  ok((await page.locator('#detail-title').innerText())==='Vanessa Automation','search opens the intended node');await page.keyboard.press('Escape');
  await page.locator('#ui button[data-action="expand"]').click();
  ok(await page.locator('#graph-dialog').evaluate(e=>e.open),'full diagram opens');
  const before=await page.locator('#graph-canvas svg').evaluate(e=>e.getBoundingClientRect().width);await page.locator('#graph-zoom-in').click();
  ok(await page.locator('#graph-canvas svg').evaluate(e=>e.getBoundingClientRect().width)>before,'diagram zoom changes rendered size');
  const duplicateIds=await page.evaluate(()=>{const a=[...document.querySelectorAll('[id]')].map(e=>e.id);return a.filter((x,i)=>a.indexOf(x)!==i)});ok(!duplicateIds.length,'expanded SVG has unique IDs');
  await page.locator('#graph-canvas [data-node="ui-vanessa"]').click();ok(await page.locator('#node-dialog').evaluate(e=>e.open),'expanded graph nodes remain interactive');await page.keyboard.press('Escape');await page.locator('#graph-close').click();
  await page.locator('[data-stock-delta="0"]').click();ok((await page.locator('#stock-result').innerText()).includes('минимум 0'),'initial stock history passes the invariant');
  await page.locator('[data-stock-delta="-1"]').first().click();ok((await page.locator('#stock-result').innerText()).includes('минимум внутри периода -1'),'backdated write-off exposes a local negative balance');
  await page.locator('[data-stock-delta="-10"]').click();ok((await page.locator('#stock-result').innerText()).includes('минимум внутри периода -10'),'receipt cancellation recomputes the history');
  await page.locator('[data-stock-delta="-1"]').first().click();
  await page.locator('.stock-example').screenshot({path:path.join(out,'08-history-example.png')});
  ok(await page.locator('body').evaluate(e=>e.classList.contains('dark')),'terminal theme is dark by default');await page.locator('#theme-toggle').click();ok(await page.locator('body').evaluate(e=>!e.classList.contains('dark')),'light terminal theme works');await page.goto(pathToFileURL(input).href+'#overview');ok(await page.locator('body').evaluate(e=>!e.classList.contains('dark')),'theme survives page reload');await page.screenshot({path:path.join(out,'05-light.png')});await page.locator('#theme-toggle').click();
  await page.goto(pathToFileURL(input).href+'#manual-book');ok(await page.evaluate(()=>location.hash)==='#analysis','previous atlas link resolves to unified content');
  await page.setViewportSize({width:390,height:844});await page.goto(pathToFileURL(input).href+'#overview');
  ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile page has no horizontal overflow');await page.screenshot({path:path.join(out,'06-mobile.png')});
  await page.locator('#ui').evaluate(e=>e.scrollIntoView({block:'start'}));await page.screenshot({path:path.join(out,'07-mobile-ui.png')});
  ok(await page.locator('#ui .graph-scroll').evaluate(e=>{const n=e.querySelector('.node').getBoundingClientRect(),r=e.getBoundingClientRect();return n.left>=r.left&&n.right<=r.right}),'mobile graph opens with its entry node fully visible');
  await page.locator('#ui button[data-action="expand"]').click();await page.locator('#graph-zoom-in').click();ok(await page.locator('#graph-dialog').evaluate(e=>e.getBoundingClientRect().right<=innerWidth),'expanded graph fits mobile viewport');await page.keyboard.press('Escape');
  await page.setViewportSize({width:1440,height:1000});await page.goto(pathToFileURL(input).href);await page.emulateMedia({media:'print'});
  await page.pdf({path:path.join(out,'print-proof.pdf'),preferCSSPageSize:true,printBackground:true});
  ok(!errors.length,'no browser JavaScript errors');ok(!requests.length,'no external requests needed to view document');
  fs.writeFileSync(path.join(out,'browser-results.json'),JSON.stringify({status:'passed',checks:tests.length,tests,errors,requests,meta},null,2));
  console.log(JSON.stringify({status:'passed',checks:tests.length,errors,requests,meta}));
 }finally{await browser.close()}
})().catch(e=>{fs.writeFileSync(path.join(out,'browser-failure.json'),JSON.stringify({error:e.stack,tests,errors,requests},null,2));console.error(e);process.exitCode=1});
