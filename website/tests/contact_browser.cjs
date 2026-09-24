const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const {default:AxeBuilder}=require('@axe-core/playwright');
const base=process.env.REVIEW_URL||'http://127.0.0.1:8771';
assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname));
const out=path.resolve(__dirname,'../dist/contact-review');fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({channel:'chrome'});
 try{
  for(const theme of ['light','dark'])for(const width of [320,390,1440]){
   const context=await browser.newContext({viewport:{width,height:1000},colorScheme:theme,reducedMotion:'reduce'});
   const page=await context.newPage();let calls=0,failure='';const errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await context.route('**/api/account/**',async route=>{
    const endpoint=new URL(route.request().url()).pathname.split('/').pop();
    if(endpoint==='session')return route.fulfill({json:{authenticated:false}});
    if(endpoint==='csrf')return route.fulfill({json:{csrfToken:'test-csrf'}});
    assert.equal(endpoint,'contact');assert.equal(route.request().headers()['x-csrf-token'],'test-csrf');
    calls++;assert.equal(route.request().postDataJSON().email,'visitor@example.com');
    return route.fulfill(failure?{status:failure==='TRY_LATER'?429:503,json:{error:failure}}:{json:{sent:true}});
   });
   await page.goto(base+'/contact.html');await page.locator('body.atelier-nav-ready').waitFor();
   await page.waitForFunction(()=>!document.querySelector('[type=submit]').disabled);
   await page.evaluate(()=>document.fonts.ready);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   assert.equal(await page.getByRole('heading',{level:1,name:'Contact NektronAI.'}).count(),1);
   assert.ok(await page.locator('a[href="mailto:info@nektron.ai"]').count());
   assert.equal(await page.locator('input[type=file]').count(),0);
   const report=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
   assert.deepEqual(report.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)})),[]);
   await page.screenshot({path:path.join(out,`${theme}-${width}.png`),fullPage:true});
   await page.locator('#contact-name').fill('Test Visitor');await page.locator('#contact-email').fill('visitor@example.com');
   await page.locator('#contact-topic').selectOption('general');
   const message='<script>alert(1)</script> Please tell me about your products.';
   await page.locator('#contact-message').fill(message);
   failure='TRY_LATER';await page.getByRole('button',{name:'Send message',exact:true}).click();
   await page.getByText('Too many submissions.',{exact:false}).waitFor();
   assert.equal(await page.locator('#contact-message').inputValue(),message);
   failure='';await page.getByRole('button',{name:'Send message',exact:true}).click();
   await page.getByText('Thank you. Your message has been sent to NektronAI.',{exact:true}).waitFor();
   assert.equal(calls,2);assert.deepEqual(errors,[]);
   await context.close();
  }
  console.log('Contact page: six responsive/theme and accessibility cases; safe error recovery and submission passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
