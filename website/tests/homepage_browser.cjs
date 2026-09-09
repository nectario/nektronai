/* Actual static-site browser review. No production URLs, logins, or writes. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const { default: AxeBuilder } = require('@axe-core/playwright');
const base = process.env.REVIEW_URL || 'http://127.0.0.1:8765';
const before = process.env.BASELINE_URL;
for (const url of [base, before].filter(Boolean)) {
  assert.ok(['127.0.0.1', 'localhost'].includes(new URL(url).hostname), 'Use only a local preview');
}
const out = path.resolve(process.env.REVIEW_OUTPUT || '../review');
fs.mkdirSync(path.join(out, 'screenshots'), { recursive: true });
const results = [];
async function ready(page, url) {
  await page.goto(url, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  await page.locator('h1').waitFor();
}
(async () => {
  const browser = await chromium.launch();
  try {
    for (const theme of ['light', 'dark']) {
      for (const width of [320, 390, 768, 900, 1440, 1920]) {
        const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme, reducedMotion: 'reduce' });
        const page = await context.newPage();
        const errors = [], failures = [];
        page.on('pageerror', e => errors.push(e.message));
        page.on('response', r => { if (r.url().startsWith(base) && r.status() >= 400) failures.push([r.status(), r.url()]); });
        await ready(page, base);
        await page.waitForFunction(() => document.body.classList.contains('home-nav-ready'));
        assert.equal(await page.locator('h1').count(), 1);
        assert.equal(await page.evaluate(() => document.documentElement.classList.contains('theme-light')), theme === 'light');
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${theme}/${width} overflow`);
        const material = await page.locator('.home-thesis-panel').evaluate(el => getComputedStyle(el).backgroundImage);
        assert.ok(material.includes('linear-gradient'));
        assert.equal(await page.locator('.home-ribbon .ribbon-card').count(), 3);
        assert.equal(await page.locator('.home-product-grid .product-card').count(), 3);
        assert.ok(await page.locator('.home-product-note').isVisible());
        const overlapping = await page.locator('.hero-cta .button, .signal-item, .ribbon-card, .resource-card, .contact-card').evaluateAll(els =>
          els.filter(el => el.scrollWidth > el.clientWidth + 1).map(el => el.textContent.trim()));
        assert.deepEqual(overlapping, [], 'Text containers must not overflow');
        const imageFailures = await page.locator('img').evaluateAll(imgs => imgs.filter(img => getComputedStyle(img).display !== 'none' && (!img.complete || img.naturalWidth === 0)).map(img => img.src));
        assert.deepEqual(imageFailures, [], 'Approved logo must load');
        const fonts = await page.evaluate(() => [...document.fonts].map(f => ({family:f.family, status:f.status})));
        await page.screenshot({ path: path.join(out, `screenshots/${theme}-${width}.png`), fullPage: true });
        if (width === 1440) {
          await page.screenshot({ path: path.join(out, `screenshots/${theme}-hero.png`) });
          await page.locator('.home-ribbon').screenshot({ path: path.join(out, `screenshots/${theme}-gradient-cards.png`) });
        }
        const axe = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
        fs.writeFileSync(path.join(out, `axe-${theme}-${width}.json`), JSON.stringify(axe.violations, null, 2));
        assert.deepEqual(axe.violations.map(v => ({id:v.id, nodes:v.nodes.map(n=>n.target)})), [], 'Automated accessibility rules');
        if (width <= 860) {
          const menu = page.locator('[data-nav-toggle]');
          assert.equal(await menu.getAttribute('aria-label'),'Open navigation');
          await menu.click();
          assert.equal(await menu.getAttribute('aria-expanded'),'true');
          await page.locator('#primary-nav a').first().focus();
          await page.keyboard.press('Escape');
          assert.equal(await page.locator('[data-nav-toggle]').getAttribute('aria-expanded'),'false');
          assert.ok(await page.locator('[data-nav-toggle]').evaluate(el=>el===document.activeElement));
          await page.getByRole('button',{name:'Open navigation',exact:true}).click();
          await page.locator('#primary-nav a[href="#products"]').click();
          assert.equal(await page.locator('[data-nav-toggle]').getAttribute('aria-expanded'),'false');
          assert.ok(await page.locator('#products').evaluate(el => el.getBoundingClientRect().top >= 70));
          await page.evaluate(()=>scrollTo(0,0));
        }
        const toggle = page.locator('[data-theme-toggle]');
        await toggle.click();
        assert.equal(await page.evaluate(()=>document.documentElement.classList.contains('theme-light')),theme!=='light');
        await page.reload({waitUntil:'load'});
        assert.equal(await page.evaluate(()=>document.documentElement.classList.contains('theme-light')),theme!=='light');
        assert.deepEqual(errors,[],'No JavaScript errors');
        assert.deepEqual(failures,[],'No missing same-origin assets');
        results.push({theme,width,overflow:false,axeViolations:0,themePersistence:'passed',mobileNavigation:width<=860?'passed':'not applicable',fonts});
        await context.close();
      }
    }
    // All original header/footer destinations still load. Research/docs/download
    // content is unmodified; these are navigation smoke checks, not rewrites.
    const context=await browser.newContext({viewport:{width:1440,height:1000},colorScheme:'light'});
    const page=await context.newPage();
    const destinations=['about.html','grownet.html','docs.html','downloads.html','changelog.html','privacy.html','terms.html','support.html'];
    for(const route of destinations){
      const response=await page.goto(`${base}/${route}`,{waitUntil:'load'});
      assert.equal(response.status(),200,route);
      assert.ok(await page.locator('h1').count()>=1,route);
      assert.equal(await page.locator('link[href="assets/home-refinement.css"]').count(),0,route+' must retain its existing styling');
    }
    await ready(page,base);
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(()=>document.activeElement.textContent.trim()),'Skip to content');
    await page.keyboard.press('Enter');
    await page.emulateMedia({forcedColors:'active'});
    await page.screenshot({path:path.join(out,'screenshots/forced-colors.png'),fullPage:true});
    await context.close();
    const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});
    const nojsPage=await nojs.newPage(); await ready(nojsPage,base);
    assert.ok(await nojsPage.locator('#primary-nav a[href="grownet.html"]').isVisible());
    await nojsPage.screenshot({path:path.join(out,'screenshots/no-javascript-mobile.png'),fullPage:true});
    await nojs.close();
    if(before){
      for(const theme of ['light','dark']){
        const p=await browser.newPage({viewport:{width:1440,height:1000},colorScheme:theme});
        await ready(p,before);
        await p.screenshot({path:path.join(out,`screenshots/before-${theme}.png`),fullPage:true});
        await p.close();
      }
    }
    fs.writeFileSync(path.join(out,'browser-results.json'),JSON.stringify({viewports:results,routeSmokeChecks:destinations,keyboard:'passed',noJsNavigation:'passed',forcedColors:'captured',note:'Automated checks are not a full accessibility certification. All content is served locally; original outbound links are not followed.'},null,2));
    console.log('Passed 12 theme/viewport cases, accessibility rules, navigation, persistence, keyboard and no-JS checks.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
