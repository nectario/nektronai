/* Local-only Turnstile mocks; no provider calls, accounts or outbound mail. */
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const base = process.env.REVIEW_URL || 'http://127.0.0.1:8771';
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname));

const sdk = `
window.challengeMock = {options:null, resets:0};
window.turnstile = {
  render(container, options) {
    window.challengeMock.options = options;
    container.textContent = 'Test security check';
    return 'test-widget';
  },
  reset() { window.challengeMock.resets++; },
};`;

(async () => {
  const browser = await chromium.launch({channel:'chrome'});
  try {
    for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({colorScheme:theme, viewport:{width:320,height:1000}});
      const calls = [], errors = [];
      let fail = '', scriptFailed = false, siteKey = 'public-test-key', sdkLoads = 0;
      await context.route('https://challenges.cloudflare.com/**', route => {
        sdkLoads++;
        return scriptFailed ? route.abort('failed') : route.fulfill({contentType:'application/javascript',body:sdk});
      });
      await context.route('**/api/account/**', route => {
        const request = route.request();
        const action = new URL(request.url()).pathname.split('/').pop();
        if (action === 'session') return route.fulfill({json:{authenticated:false}});
        if (action === 'csrf') return route.fulfill({json:{csrfToken:'test-csrf',turnstileSiteKey:siteKey}});
        calls.push({action, body:request.postDataJSON()});
        if (fail) return route.fulfill({status:429,json:{error:fail}});
        return route.fulfill({status:action==='verify-email'?200:202,json:action==='verify-email'?{verified:true}:{accepted:true}});
      });
      const page = await context.newPage();
      page.on('pageerror', error => errors.push(error.message));
      for (const [file, action] of [['signup','signup'],['forgot-password','request-reset'],['verify-email','request-verification']]) {
        await page.goto(`${base}/${file}.html`);
        await page.waitForFunction(() => Boolean(window.challengeMock?.options));
        assert.equal(await page.evaluate(() => window.challengeMock.options.action), action);
        assert.equal(await page.evaluate(() => window.challengeMock.options.theme),
          await page.evaluate(() => document.documentElement.dataset.theme || 'auto'));
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1));
        const form = page.locator(`[data-auth-form="${action}"]`);
        const button = form.locator('[type=submit]');
        assert.equal(await button.isDisabled(), true);
        assert.equal(await form.locator('[name=website]').getAttribute('tabindex'), '-1');
        assert.equal(await form.locator('.account-honeypot').getAttribute('aria-hidden'), 'true');
        await form.locator('[name=email]').fill('controlled@example.com');
        if (action === 'signup') {
          await form.locator('[name=password]').fill('local test passphrase');
          await form.locator('[name=firstName]').fill('Local');
          await form.locator('[name=lastName]').fill('Test');
          await form.locator('[name=countryCode]').selectOption('US');
        }
        const before = calls.length;
        await form.evaluate(form => form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
        await page.locator('[data-account-status][data-error]').waitFor();
        assert.equal(calls.length, before, 'No challenge token means no POST');
        await page.evaluate(() => window.challengeMock.options.callback('first-token'));
        assert.equal(await button.isEnabled(), true);
        await page.evaluate(() => window.challengeMock.options['expired-callback']());
        assert.equal(await button.isDisabled(), true);
        await page.evaluate(() => window.challengeMock.options.callback('second-token'));
        await page.evaluate(() => window.challengeMock.options['error-callback']());
        assert.equal(await button.isDisabled(), true);
        await page.evaluate(() => window.challengeMock.options.callback('third-token'));
        fail = 'TRY_LATER';
        await button.click();
        await page.waitForFunction(() => window.challengeMock.resets === 2);
        assert.equal(calls.at(-1).body.turnstileToken, 'third-token');
        assert.equal(calls.at(-1).body.website, '');
        assert.equal(await button.isDisabled(), true, 'Failed POST consumes challenge token');
        if (action === 'signup') await form.locator('[name=password]').fill('local test passphrase');
        fail = '';
        await page.evaluate(() => window.challengeMock.options.callback('new-token'));
        await button.click();
        await page.locator('[data-auth-success]').waitFor({state:'visible'});
        assert.equal(calls.at(-1).body.turnstileToken, 'new-token');
        assert.equal(calls.at(-1).action, action);
      }
      scriptFailed = true;
      await page.goto(`${base}/signup.html`);
      await page.locator('[data-account-status][data-error]').waitFor();
      assert.equal(await page.locator('[type=submit]').isDisabled(), true, 'Provider outage fails closed');
      const beforeLoads = sdkLoads;
      await page.goto(`${base}/verify-email.html#token=${'a'.repeat(43)}`);
      await page.locator('[data-auth-success]').waitFor({state:'visible'});
      assert.equal(sdkLoads, beforeLoads, 'Emailed links do not require the challenge SDK');
      assert.equal(calls.at(-1).action, 'verify-email');
      await page.goto(`${base}/login.html`);
      await page.waitForFunction(() => !document.querySelector('[type=submit]').disabled);
      assert.equal(sdkLoads, beforeLoads, 'Login remains challenge-free');
      siteKey = '';
      await page.goto(`${base}/signup.html`);
      await page.waitForFunction(() => !document.querySelector('[type=submit]').disabled);
      assert.equal(sdkLoads, beforeLoads, 'No configured keys means no challenge SDK');
      assert.deepEqual(errors, []);
      await context.close();
    }
    console.log('Account abuse browser checks passed: light/dark, three protected forms, expiry/retry/outage, unchanged login and emailed links.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode=1;});
