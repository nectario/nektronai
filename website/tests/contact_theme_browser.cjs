const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const base=process.env.REVIEW_URL||'http://127.0.0.1:8771';
assert.ok(['localhost','127.0.0.1'].includes(new URL(base).hostname));
(async()=>{
 const browser=await chromium.launch({channel:'chrome'});
 try {
  for(const sample of [
   {system:'dark',saved:'light',light:true}, {system:'light',saved:'dark',light:false},
   {system:'light',saved:null,light:true}, {system:'dark',saved:null,light:false},
   {system:'light',blocked:true,light:true}, {system:'dark',blocked:true,light:false},
  ]) {
   const context=await browser.newContext({colorScheme:sample.system});
   await context.addInitScript(({saved,blocked})=>{
    if(blocked)Object.defineProperty(window,'localStorage',{get(){throw new Error('Storage unavailable');}});
    else if(saved)localStorage.setItem('nektron-theme',saved);
   },sample);
   await context.route('**/api/account/session',r=>r.fulfill({json:{authenticated:false}}));
   await context.route('**/api/account/csrf',r=>r.fulfill({json:{csrfToken:'test-csrf'}}));
   let release;
   const gate=new Promise(resolve=>{release=resolve;});
   await context.route(/\/assets\/site\.js(?:\?.*)?$/,async r=>{await gate;await r.continue();});
   const page=await context.newPage();const errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.goto(base+'/contact.html',{waitUntil:'commit'});
   try {
    await page.locator('h1').waitFor({state:'visible'});
    assert.equal(await page.evaluate(()=>document.documentElement.classList.contains('theme-light')),sample.light,'Correct theme before deferred site script');
    await page.evaluate(()=>{window.themeFlips=[];new MutationObserver(()=>window.themeFlips.push(document.documentElement.classList.contains('theme-light'))).observe(document.documentElement,{attributes:true,attributeFilter:['class']});});
   } finally {release();}
   await page.waitForLoadState('load');
   await page.locator('body.atelier-nav-ready').waitFor();
   assert.equal(await page.evaluate(()=>document.documentElement.classList.contains('theme-light')),sample.light);
   assert.ok((await page.evaluate(()=>window.themeFlips)).every(value=>value===sample.light));
   await page.locator('[data-theme-toggle]').click();
   assert.equal(await page.evaluate(()=>document.documentElement.classList.contains('theme-light')),!sample.light);
   assert.deepEqual(errors,[]);
   await context.close();
  }
  console.log('Six first-paint theme cases passed with the normal theme script deliberately delayed.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
