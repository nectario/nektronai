/* Check the production-based patch without contacting external services. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const {default:AxeBuilder}=require('@axe-core/playwright');
const baseline='http://127.0.0.1:8773';
const updated='http://127.0.0.1:8774';
const out=path.resolve(__dirname,'../dist/advertiser-review');
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({channel:'chrome'});
 try {
  for(const theme of ['light','dark']) for(const width of [390,1440]) {
   const context=await browser.newContext({viewport:{width,height:1000},colorScheme:theme,reducedMotion:'reduce'});
   await context.route('**/api/account/**',route=>route.fulfill({json:{authenticated:false}}));
   const before=await context.newPage(),after=await context.newPage();
   for(const [page,root] of [[before,baseline],[after,updated]]) {
    await page.goto(root+'/index.html');
    await page.locator('body.home-nav-ready').waitFor();
    await page.evaluate(()=>document.fonts.ready);
    for(const img of await page.locator('img[loading=lazy]').all()) {await img.scrollIntoViewIfNeeded();await img.evaluate(el=>el.decode());}
    await page.evaluate(()=>scrollTo(0,0));
   }
   // Align only the owner's subsequently approved venture ordering.
   await before.locator('.home-meta-row .meta-pill').evaluateAll(nodes=>{
    const facts=nodes.find(n=>n.textContent.trim().startsWith('Independent brands:'));
    const codes=facts?.querySelectorAll('code');
    if(codes?.length===3){codes[1].textContent='TagMySpend.com';codes[2].textContent='InterviewHelperAI';}
   });
   const old=await before.screenshot({fullPage:true});
   const current=await after.screenshot({fullPage:true,path:path.join(out,`home-${theme}-${width}.png`)});
   assert.ok(old.equals(current),`Homepage pixels changed: ${theme}/${width}`);
   for(const pageName of ['about','support','privacy','terms']) {
    await after.goto(updated+'/'+pageName+'.html');
    await after.locator('body.atelier-nav-ready').waitFor();
    await after.evaluate(()=>document.fonts.ready);
    assert.ok(await after.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    const report=await new AxeBuilder({page:after}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
    assert.deepEqual(report.violations.map(v=>v.id),[],`${pageName}/${theme}/${width}`);
    await after.screenshot({fullPage:true,path:path.join(out,`${pageName}-${theme}-${width}.png`)});
   }
   await context.close();
  }
  console.log('Homepage pixel-identical in four theme/viewport cases; 16 company/legal page layout and accessibility checks passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
