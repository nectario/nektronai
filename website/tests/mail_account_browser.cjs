/* Local-only account return and consent regression; no real identities or mail. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const { default: AxeBuilder } = require('@axe-core/playwright');
const base = process.env.REVIEW_URL || 'http://127.0.0.1:8771';
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname));
const oauth = fs.readFileSync(path.join(__dirname, '../server/accounts/mail_oauth.py'), 'utf8');
const template = oauth.match(/CONSENT = '''([\s\S]*?)'''/)[1];
const script = oauth.match(/CONSENT_JS = '''([\s\S]*?)'''/)[1];
const consent = template.replace('{{ csrf }}', 'synthetic-csrf').replace('{{ nonce }}', 'synthetic-nonce')
  .replace('{{ email }}', 'a'.repeat(64) + '@' + 'b'.repeat(60) + '.example');
const out = path.resolve(__dirname, '../dist/mail-account-review');
fs.mkdirSync(out, {recursive: true});

(async () => {
  const browser = await chromium.launch({channel: process.env.REVIEW_BROWSER || 'chrome'});
  try {
    for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({colorScheme: theme, reducedMotion: 'reduce'});
      const errors = [];
      let fallback = '/account.html';
      let consentCalls = 0;
      await context.route('**/*', route => {
        if (new URL(route.request().url()).origin !== new URL(base).origin) return route.abort();
        return route.continue();
      });
      await context.route('**/__mail-consent', route => route.fulfill({contentType: 'text/html', body: consent}));
      await context.route('**/api/account/**', route => {
        const req = route.request();
        const pathname = new URL(req.url()).pathname;
        if (pathname.endsWith('/consent.js')) return route.fulfill({contentType: 'application/javascript', body: script});
        if (pathname.endsWith('/session')) return route.fulfill({json: {authenticated: false}});
        if (pathname.endsWith('/csrf')) return route.fulfill({json: {csrfToken: 'synthetic-csrf'}});
        if (pathname.endsWith('/resume')) return route.fulfill({contentType: 'text/plain', body: 'Resumed safely'});
        if (pathname.endsWith('/login')) {
          assert.equal(req.method(), 'POST');
          assert.equal(req.headers()['x-csrf-token'], 'synthetic-csrf');
          return route.fulfill({json: {authenticated: true, redirect: fallback}});
        }
        return route.fulfill({status: 202, json: {accepted: true}});
      });
      const page = await context.newPage();
      page.on('pageerror', error => errors.push(error.message));
      async function login() {
        await page.locator('#email').fill('synthetic@example.com');
        await page.locator('#password').fill('local-only-password');
        await page.getByRole('button', {name: 'Log in', exact: true}).click();
      }
      // Only the fixed destination is stored. No code, access token or arbitrary URL.
      await page.goto(base + '/signup.html?returnTo=mail-authorize');
      assert.equal(await page.evaluate(() => sessionStorage.getItem('nektron.account.return')), 'mail-authorize');
      await page.goto(base + '/login.html');
      await login();
      await page.waitForURL('**/api/account/mail-oauth/resume');
      assert.equal(await page.evaluate(() => sessionStorage.getItem('nektron.account.return')), null);
      // A verification opened in another tab can use the server's fixed fallback.
      fallback = '/api/account/mail-oauth/resume';
      await page.goto(base + '/login.html');
      await login();
      await page.waitForURL('**/api/account/mail-oauth/resume');
      // Preserve Connector's explicit, fixed tab destination even if both are pending.
      await page.goto(base + '/login.html?returnTo=connector-authorize');
      await login();
      await page.waitForURL('**/api/account/oauth/resume');
      // Neither arbitrary query strings nor a tampered backend redirect is followed.
      fallback = 'https://untrusted.example/exfiltrate';
      await page.goto(base + '/login.html?returnTo=https%3A%2F%2Funtrusted.example');
      await login();
      await page.waitForURL('**/account.html');
      for (const width of [320, 390, 1440]) {
        await page.setViewportSize({width, height: 1000});
        await page.goto(base + '/__mail-consent');
        await page.evaluate(() => document.fonts.ready);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${theme}/${width} overflow`);
        assert.equal(await page.getByRole('heading', {level: 1}).count(), 1);
        assert.equal(await page.getByRole('button', {name: 'Connect Nektron Mail', exact: true}).count(), 1);
        await page.screenshot({path: path.join(out, `consent-${theme}-${width}.png`), fullPage: true});
        const report = await new AxeBuilder({page}).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
        assert.deepEqual(report.violations.map(v => ({id: v.id, targets: v.nodes.map(n => n.target)})), [], `${theme}/${width} accessibility`);
      }
      // Consent only submits once; cancellation is a protected, explicit action.
      await page.route('**/__mail-consent', route => {
        if (route.request().method() === 'GET') return route.fulfill({contentType: 'text/html', body: consent});
        consentCalls++;
        assert.equal(route.request().headers()['x-csrf-token'], 'synthetic-csrf');
        assert.deepEqual(route.request().postDataJSON(), {approve: false, nonce: 'synthetic-nonce'});
        return route.fulfill({status: 400, json: {error: 'invalid_request'}});
      });
      await page.getByRole('button', {name: 'Cancel', exact: true}).click();
      await page.getByRole('status').filter({hasText: 'Return to Nektron Mail'}).waitFor();
      assert.equal(consentCalls, 1);
      assert.equal(await page.getByRole('button', {name: 'Cancel', exact: true}).isDisabled(), true);
      assert.deepEqual(errors, []);
      await context.close();
    }
    // Exercise the real production-origin-only Connector journey helper, but
    // serve all bytes from loopback and mock account actions. No live site calls.
    const journey = await browser.newContext();
    await journey.route('**/*', async route => {
      const req = route.request();
      const url = new URL(req.url());
      if (url.origin !== 'https://nektron.ai') return route.abort();
      if (url.pathname === '/api/account/session') return route.fulfill({json: {authenticated: false}});
      if (url.pathname === '/api/account/csrf') return route.fulfill({json: {csrfToken: 'synthetic-csrf'}});
      if (url.pathname === '/api/account/login') return route.fulfill({json: {authenticated: true, redirect: '/api/account/mail-oauth/resume'}});
      if (url.pathname.endsWith('/resume')) return route.fulfill({body: 'Resumed safely'});
      if (url.pathname.startsWith('/api/')) return route.fulfill({json: {accepted: true}});
      return route.fulfill({response: await route.fetch({url: base + url.pathname + url.search, maxRedirects: 0})});
    });
    await journey.addInitScript(() => localStorage.setItem('nektron.connector.journey', JSON.stringify({
      target: 'connector-authorize', expires: Date.now() + 3600000,
    })));
    const page = await journey.newPage();
    await page.goto('https://nektron.ai/login.html?returnTo=mail-authorize');
    const create = page.getByRole('link', {name: 'Create an account', exact: true});
    assert.match(await create.getAttribute('href'), /returnTo=mail-authorize/);
    await create.click();
    await page.waitForURL('**/signup.html?returnTo=mail-authorize');
    assert.equal(await page.evaluate(() => sessionStorage.getItem('nektron.account.return')), 'mail-authorize');
    // New email-verification tab: old Connector localStorage is shared, but the
    // fresh server-validated Mail return wins without an explicit Connector URL.
    const newTab = await journey.newPage();
    await newTab.goto('https://nektron.ai/login.html');
    await newTab.locator('#email').fill('synthetic@example.com');
    await newTab.locator('#password').fill('local-only-password');
    await newTab.getByRole('button', {name: 'Log in', exact: true}).click();
    await newTab.waitForURL('**/api/account/mail-oauth/resume');
    await journey.close();
    process.stdout.write('Mail account return and consent browser regressions passed (light/dark; 320/390/1440 px).\n');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
