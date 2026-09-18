/* Local form and layout regression tests; no real accounts or mail. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const { default: AxeBuilder } = require('@axe-core/playwright');
const base = process.env.REVIEW_URL || 'http://127.0.0.1:8771';
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname));
const out = path.resolve(__dirname, '../dist/account-review');
fs.mkdirSync(out, {recursive:true});

(async () => {
  const browser = await chromium.launch({channel:'chrome'});
  try {
    for (const theme of ['light','dark']) {
      const context = await browser.newContext({colorScheme:theme, reducedMotion:'reduce'});
      const calls = [], errors = [];
      let authenticated = false;
      let failure = '';
      await context.route('**/api/account/**', async route => {
        const request = route.request();
        const action = new URL(request.url()).pathname.split('/').pop();
        if (action === 'session') return route.fulfill({json:{authenticated,csrfToken:authenticated?'test-csrf':undefined,user:{email:'test@example.com',firstName:'Test',middleName:'Sample',lastName:'Member',country:'United States of America',phoneNumber:'+1 202 555 0123'}}});
        if (action === 'csrf') return route.fulfill({json:{csrfToken:'test-csrf'}});
        assert.equal(request.method(),'POST');
        assert.equal(request.headers()['x-csrf-token'],'test-csrf');
        calls.push({action,body:request.postDataJSON()});
        if (failure) return route.fulfill({status:401,json:{error:failure}});
        if (action === 'login') authenticated = true;
        if (action === 'logout') authenticated = false;
        return route.fulfill({status:['signup','request-reset','request-verification'].includes(action)?202:200,json:{accepted:true}});
      });
      const page = await context.newPage();
      page.on('pageerror', error => errors.push(error.message));
      for (const width of [320,390,1440]) {
        await page.setViewportSize({width,height:1000});
        for (const name of ['signup','login','forgot-password','reset-password','verify-email','account']) {
          const fragment = ['reset-password','verify-email'].includes(name)?'#token='+'a'.repeat(43):'';
          await page.goto(base+'/'+name+'.html'+fragment);
          await page.locator('body.atelier-nav-ready').waitFor();
          await page.evaluate(() => document.fonts.ready);
          if (await page.locator('form:not([hidden])').count()) {
            await page.locator('form:not([hidden]) [type=submit]').waitFor({state:'visible'});
            await page.waitForFunction(() => [...document.querySelectorAll('form:not([hidden]) [type=submit]')].every(b=>!b.disabled));
          }
          assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${name}/${theme}/${width} overflow`);
          assert.equal(await page.locator('h1').count(),1);
          if (name === 'signup') {
            assert.equal(await page.getByRole('heading',{level:1,name:'Create your NektronAI account.',exact:true}).count(),1);
            const wordmark = page.locator('h1 .account-brand-wordmark');
            assert.equal(await wordmark.count(),1);
            assert.equal(await wordmark.locator('path').count(),9);
            assert.equal(await wordmark.getAttribute('aria-hidden'),'true');
            assert.equal(await wordmark.locator('[fill="#00acd8"]').count(),2,'Preserve cyan AI lettering');
            assert.equal(await wordmark.evaluate(el=>getComputedStyle(el).color),theme==='light'?'rgb(0, 0, 0)':'rgb(255, 255, 255)');
            assert.ok(await wordmark.evaluate(el=>el.getBoundingClientRect().right<=innerWidth),'Wordmark fits the viewport');
          }
          assert.equal(new URL(page.url()).hash,'');
          if (width !== 320) {
            await page.screenshot({path:path.join(out,`${name}-${theme}-${width}.png`),fullPage:true});
            const report=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
            assert.deepEqual(report.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)})),[],`${name}/${theme}/${width} accessibility`);
          }
        }
      }
      await page.goto(base+'/signup.html');
      await page.locator('#email').fill('test@example.com');
      await page.locator('#password').fill('short');
      assert.equal(await page.locator('form').evaluate(f=>f.checkValidity()),false,'names/country required');
      await page.locator('#first-name').fill('Test');
      await page.locator('#last-name').fill('Member');
      assert.equal(await page.locator('form').evaluate(f=>f.checkValidity()),false,'country requires explicit selection');
      await page.locator('#country').selectOption('US');
      assert.equal(await page.locator('form').evaluate(f=>f.checkValidity()),true,'optional fields may be empty');
      await page.locator('#middle-name').fill('Sample');
      await page.locator('#phone').fill('+1 202 555 0123');
      await page.locator('[data-show-password]').click();
      assert.equal(await page.locator('#password').getAttribute('type'),'text');
      await page.getByRole('button',{name:'Create account',exact:true}).click();
      await page.locator('[data-auth-success]').waitFor({state:'visible'});
      assert.equal(calls.at(-1).action,'signup');
      assert.equal(calls.at(-1).body.password,'short');
      assert.equal(calls.at(-1).body.countryCode,'US');
      assert.equal(calls.at(-1).body.middleName,'Sample');
      assert.equal(calls.at(-1).body.phoneNumber,'+1 202 555 0123');
      assert.equal(new URL(page.url()).origin,new URL(base).origin);

      await page.goto(base+'/login.html');
      failure = 'INVALID_CREDENTIALS';
      await page.locator('#email').fill('test@example.com');
      await page.locator('#password').fill('bad password');
      await page.locator('[data-show-password]').click();
      await page.getByRole('button',{name:'Log in',exact:true}).click();
      await page.locator('[data-account-status][data-error]').waitFor();
      assert.equal(await page.locator('#password').inputValue(),'');
      failure = '';
      await page.locator('#password').fill('a unique long passphrase');
      await page.getByRole('button',{name:'Log in',exact:true}).click();
      await page.waitForURL('**/account.html');
      await page.locator('[data-account-profile]').waitFor({state:'visible'});
      assert.equal(await page.locator('[data-account-country]').innerText(),'United States of America');
      assert.equal(await page.locator('[data-account-phone]').innerText(),'+1 202 555 0123');
      await page.locator('[data-account-logout]').click();
      await page.locator('[data-account-guest]').waitFor({state:'visible'});
      assert.equal(calls.at(-1).action,'logout');

      await page.goto(base+'/verify-email.html#token='+'b'.repeat(43));
      const previous = calls.length;
      await page.getByRole('button',{name:'Verify email',exact:true}).click();
      await page.locator('[data-auth-success]').waitFor({state:'visible'});
      assert.equal(calls.length,previous+1);
      assert.equal(calls.at(-1).body.token,'b'.repeat(43));
      await page.goto(base+'/reset-password.html');
      assert.equal(await page.locator('form:visible').count(),0);
      assert.deepEqual(errors,[]);
      await context.close();
    }
    console.log('Account forms: 36 responsive/theme checks, 24 accessibility checks, native form actions passed.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
