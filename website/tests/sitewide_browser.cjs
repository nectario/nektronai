/* Actual canonical pages served locally. No outbound navigation or service writes. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const { default: AxeBuilder } = require('@axe-core/playwright');
const checkApprovedHomepage = require('./homepage_preservation.cjs');
const base = process.env.REVIEW_URL || 'http://127.0.0.1:8765';
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
const out = path.resolve('../review/sitewide');
fs.mkdirSync(out, { recursive: true });
const routes = ['index','about','docs','downloads','changelog','grownet','grownet-formal-spec','privacy','terms','support'];
const readySelector = route => route === 'index' ? 'body.home-page.home-nav-ready' : 'body.atelier-site.atelier-nav-ready';
const results = [];
(async () => {
 const browser = await chromium.launch();
 try {
  for (const theme of ['light','dark']) {
   const context = await browser.newContext({colorScheme:theme,reducedMotion:'reduce'});
   const page = await context.newPage();
   const errors = [], missing = [];
   page.on('pageerror', e => errors.push(e.message));
   page.on('response', r => { if (r.url().startsWith(base) && r.status() >= 400) missing.push([r.status(),r.url()]); });
   for (const route of routes) {
    for (const width of [320,390,768,1440]) {
     await page.setViewportSize({width,height:1000});
     await page.goto(`${base}/${route}.html`,{waitUntil:'load'});
     await page.locator(readySelector(route)).waitFor();
     await page.evaluate(() => document.fonts.ready);
     assert.equal(await page.locator('h1').count(),1,route+' heading');
     assert.equal(await page.evaluate(() => document.documentElement.classList.contains('theme-light')),theme==='light');
     assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1),`${route}/${theme}/${width} overflow`);
     const assets = await page.locator('img').evaluateAll(images => images.filter(i=>getComputedStyle(i).display!=='none' && (!i.complete || !i.naturalWidth)).map(i=>i.src));
     assert.deepEqual(assets,[],route+' images');
     assert.ok(await page.evaluate(() => getComputedStyle(document.body,'::before').backgroundImage.includes('atelier-flow-')));
     if(width<=860) {
      const menu=page.locator('[data-nav-toggle]'); await menu.click();
      await page.locator('#primary-nav a').first().focus(); await page.keyboard.press('Escape');
      assert.equal(await menu.getAttribute('aria-expanded'),'false');
      assert.ok(await menu.evaluate(e=>e===document.activeElement));
     }
     if (width===390 || width===1440) {
      const name=`${route}-${theme}-${width}`;
      await page.screenshot({path:path.join(out,name+'.png'),fullPage:!route.startsWith('grownet')});
      const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
      fs.writeFileSync(path.join(out,name+'-axe.json'),JSON.stringify(axe.violations,null,2));
      assert.deepEqual(axe.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)})),[],name+' accessibility');
     }
     if(route==='index') {
      assert.equal(await page.locator('[data-added-products] .product-card').count(),2);
      assert.equal(await page.locator('.home-product-grid .product-card').count(),3);
      assert.equal(await page.locator('body.atelier-site').count(),0,'Homepage keeps its approved design scope');
     }
     if(route.startsWith('grownet') && width===390) {
      const region=page.locator('.grownet-table-wrap').first();
      await region.focus(); assert.ok(await region.evaluate(e=>e===document.activeElement));
      const old=await region.evaluate(e=>e.scrollLeft);await page.keyboard.press('ArrowRight');
      await page.waitForFunction(({old})=>document.activeElement.scrollLeft>old,{old});
     }
     results.push({route,theme,width,overflow:false});
    }
    // Persistence from each secondary page, not just from the homepage.
    const toggle=page.locator('[data-theme-toggle]');await toggle.click();
    await page.reload({waitUntil:'load'});await page.locator(readySelector(route)).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.classList.contains('theme-light')),theme!=='light');
    await toggle.click();
    assert.equal(await page.evaluate(() => document.documentElement.classList.contains('theme-light')),theme==='light');
   }
   assert.deepEqual(errors,[]);assert.deepEqual(missing,[]);
   await context.close();
  }
  const page=await browser.newPage({viewport:{width:390,height:900},colorScheme:'light'});
  await page.goto(`${base}/docs.html`,{waitUntil:'load'});await page.locator('body.atelier-site').waitFor();
  await page.locator('[data-theme-toggle]').click();
  assert.equal(await page.evaluate(()=>localStorage.getItem('nektron-theme')),'dark');
  await page.reload({waitUntil:'load'});await page.locator('body.atelier-site').waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.classList.contains('theme-light')),false);
  await page.emulateMedia({forcedColors:'active'});
  assert.equal(await page.evaluate(()=>getComputedStyle(document.body,'::before').display),'none');
  await page.screenshot({path:path.join(out,'docs-forced-colors.png'),fullPage:true});
  await page.close();
  // The root source pages are unchanged; disabled JS retains their original,
  // readable fallback. No dummy links or synthetic contact form are introduced.
  const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:1440,height:1000}});
  const fallback=await nojs.newPage();
  for(const route of ['docs','grownet','downloads','privacy']) {
   await fallback.goto(`${base}/${route}.html`,{waitUntil:'load'});
   assert.ok(await fallback.locator('h1').isVisible());
   assert.ok(await fallback.locator('#primary-nav a').first().isVisible());
  }
  await nojs.close();
  await checkApprovedHomepage(browser,base,process.env.BASELINE_URL || 'http://127.0.0.1:8767',out);
  fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({cases:results,homepagePreservation:'12 comparative cases passed',themePersistence:'passed',forcedColors:'passed',noJs:'Original presentation retained',note:'Real locally-served pages. Automated tests are not a complete accessibility audit.'},null,2));
  console.log('Passed '+results.length+' canonical route/theme/width cases.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
