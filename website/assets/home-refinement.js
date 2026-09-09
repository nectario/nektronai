// Homepage-only progressive enhancement; shared download/theme logic stays in site.js.
(() => {
  if (!document.body.classList.contains('home-page')) return;
  const header = document.querySelector('body > header');
  const button = header?.querySelector('[data-nav-toggle]');
  const nav = header?.querySelector('#primary-nav');
  if (!header || !button || !nav) return;
  document.body.classList.add('home-nav-ready');

  // The shared script closes on Escape. Capture beforehand to restore focus only
  // when an open mobile navigation actually owned it (never jump from the page).
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && header.classList.contains('nav-open') &&
        (nav.contains(document.activeElement) || document.activeElement === button)) {
      button.focus();
    }
  }, true);
})();
