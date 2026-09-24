// Parser-blocking on purpose: choose the theme before styles or page content paint.
(() => {
  let saved = null;
  try { saved = localStorage.getItem('nektron-theme'); } catch (_) {}
  const system = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  document.documentElement.classList.toggle('theme-light', (saved || system) === 'light');
})();
