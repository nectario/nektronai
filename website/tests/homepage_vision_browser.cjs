/* Test-only normalization for the owner-approved COPY change.
   The live after page is never modified. Only text nodes in the isolated baseline
   browser are updated to the approved copy, so natural text reflow is not mistaken
   for a CSS redesign. No attributes, elements, styles or resources are copied.
   homepage_vision.py separately proves the production DOM structure is unchanged. */
const assert = require('node:assert/strict');

async function textSnapshot(page) {
  return page.evaluate(() => {
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let node;
    while ((node = walk.nextNode())) {
      if (!node.nodeValue.trim() || node.parentElement.closest('script, style')) continue;
      const parent = node.parentElement;
      nodes.push({ tag: parent.tagName, id: parent.id, className: parent.getAttribute('class'), value: node.nodeValue });
    }
    return nodes;
  });
}

module.exports = async function alignApprovedHomepageCopy(before, after) {
  assert.equal((await after.locator('h1').innerText()).replace(/\s+/g, ' ').trim(),
    'Reimagine the apps we use. Rethink AI from the ground up.');
  assert.equal((await after.locator('.panel-kicker').textContent()).trim(), 'Our boldest undertaking');
  const note = after.locator('.home-product-note');
  assert.ok(await note.isVisible());
  const copy = (await note.innerText()).replace(/\s+/g, ' ');
  assert.ok(copy.includes('Current products do not yet use GrowNet.'));
  assert.ok(copy.includes('initially powered by existing AI models'));
  assert.ok(copy.includes('As GrowNet proves its capabilities, we will begin integrating it into our products.'));
  assert.equal(await after.locator('#products .product-card').count(), 5);
  const current = await textSnapshot(after), baseline = await textSnapshot(before);
  const shape = nodes => nodes.map(({value, ...structure}) => structure);
  assert.deepEqual(shape(current), shape(baseline), 'Copy comparison must not hide a structural redesign');
  await before.evaluate(values => {
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node, index = 0;
    while ((node = walk.nextNode())) {
      if (!node.nodeValue.trim() || node.parentElement.closest('script, style')) continue;
      node.nodeValue = values[index++];
    }
  }, current.map(node => node.value));
  await before.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
};
