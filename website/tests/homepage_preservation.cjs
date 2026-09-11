/* Compare existing homepage elements against the approved PR base.
   Only the decorative pseudo-element, two added cards and downstream page height may differ.
   For the explicitly approved copy PR, compare identical text on both style systems. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const alignApprovedHomepageCopy = require('./homepage_vision_browser.cjs');
const copyReview = process.env.HOMEPAGE_COPY_REVIEW === '1';

async function signature(page) {
  return page.evaluate(() => {
    const properties = ['display','position','width','max-width','min-width','color','background-color',
      'background-image','font-family','font-size','font-weight','font-style','line-height','letter-spacing',
      'text-align','text-transform','white-space','padding','margin','border','border-radius','box-shadow',
      'gap','grid-template-columns','align-items','justify-content','flex-direction','transform',
      'outline','outline-offset','opacity','filter'];
    return Array.from(document.querySelectorAll('body > header, body > header *, main, main *, body > .footer, body > .footer *'))
      .filter(el => !el.closest('[data-added-products]'))
      .map(el => {
        const style = getComputedStyle(el);
        const values = Object.fromEntries(properties.map(key => [key, style.getPropertyValue(key)]));
        // The extra product row legitimately increases its ancestors' heights.
        if (!el.matches('main, main > .container, #products')) values.height = style.height;
        return {tag: el.tagName, id: el.id, className: el.getAttribute('class'), styles: values};
      });
  });
}

module.exports = async function checkApprovedHomepage(browser, base, baseline, out) {
  for (const url of [base, baseline]) assert.ok(['localhost','127.0.0.1'].includes(new URL(url).hostname));
  const cases = [];
  for (const theme of ['light','dark']) {
    for (const width of [320,390,768,900,1440,1920]) {
      const context = await browser.newContext({viewport:{width,height:1000},colorScheme:theme,reducedMotion:'reduce'});
      try {
        const before = await context.newPage(), after = await context.newPage();
        for (const [page, url] of [[before, baseline], [after, base]]) {
          await page.goto(url + '/index.html', {waitUntil:'load'});
          await page.locator('body.home-nav-ready').waitFor();
          await page.evaluate(() => document.fonts.ready);
        }
        if (copyReview) await alignApprovedHomepageCopy(before, after);
        assert.equal(await after.locator('link[href$="/atelier.css"]').count(),0,'Secondary stylesheet must not load on Home');
        assert.equal(await after.locator('body.atelier-site').count(),0,'Secondary enhancement must exclude Home');
        assert.deepEqual(await signature(after), await signature(before), `${theme}/${width}: approved element styles changed`);
        // A pixel-position guard for everything preceding the added product row.
        for (const selector of ['body > header','.home-hero','.research-loop','.home-ribbon','.home-resource-shelf','.home-product-grid']) {
          assert.deepEqual(await after.locator(selector).boundingBox(), await before.locator(selector).boundingBox(),selector);
        }
        const original = await after.locator('.home-product-grid .product-card').first().boundingBox();
        const cards = after.locator('[data-added-products] .product-card');
        assert.equal(await cards.count(),2);
        for (const card of await cards.all()) {
          const bounds = await card.boundingBox();
          assert.ok(Math.abs(bounds.width - original.width) <= 1,'New product cards must match existing column width');
          assert.ok(bounds.y > original.y + original.height,'New cards belong after the original product row');
        }
        // Compare existing controls in their interactive states, not just a static screenshot.
        for (const selector of ['.hero-cta .primary','.resource-card-journal','[data-theme-toggle]']) {
          for (const page of [before,after]) await page.locator(selector).hover();
          assert.deepEqual(await signature(after),await signature(before),selector+' hover');
          for (const page of [before,after]) { await page.mouse.move(0,0); await page.locator(selector).focus(); }
          assert.deepEqual(await signature(after),await signature(before),selector+' focus');
          for (const page of [before,after]) await page.locator(selector).evaluate(el=>el.blur());
        }
        if (width===1440 || width===390) {
          await after.evaluate(()=>scrollTo(0,0));
          await after.screenshot({path:path.join(out,`preserved-home-${theme}-${width}.png`)});
          await after.locator('#products').screenshot({path:path.join(out,`preserved-products-${theme}-${width}.png`)});
        }
        cases.push({theme,width,existingStyles:'unchanged',existingPositions:copyReview?'unchanged with identical approved text':'unchanged',hoverFocus:'unchanged',newCardWidths:'matching'});
      } finally { await context.close(); }
    }
  }
  fs.writeFileSync(path.join(out,'homepage-preservation.json'),JSON.stringify({cases,
    exceptions:copyReview?['Approved text changes naturally reflow; baseline text is aligned for style/geometry comparisons only']:['decorative background','two added product cards','resulting downstream vertical displacement'],
    note:'Element-style comparison is not a whole-page pixel-diff or full accessibility audit.'},null,2));
  console.log('Passed '+cases.length+' approved-homepage preservation cases.');
};
