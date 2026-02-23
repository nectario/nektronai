// NektronAI — tiny client script (theme + mobile nav)
// No frameworks. Fast, accessible, and production-friendly.

(() => {
  const storageKey = "nektron-theme";
  const root = document.documentElement;
  const host = (window.location.hostname || "").toLowerCase();
  const productionHosts = new Set(["nektron.ai", "www.nektron.ai"]);

  // Show a simple maintenance screen only on production hostname.
  if (productionHosts.has(host)) {
    root.classList.remove("theme-light");
    document.title = "NektronAI | Coming Soon";
    document.body.className = "coming-soon-body";
    document.body.innerHTML = `
      <main class="coming-soon" id="content">
        <div class="coming-soon-inner">
          <img class="coming-soon-wordmark" src="/assets/brand/wordmark-dark-320.png" alt="NektronAI" width="320" height="74" decoding="async">
          <h1 class="coming-soon-title">Coming Soon</h1>
          <p class="coming-soon-copy">NektronAI is preparing the next version of our website.</p>
        </div>
      </main>
    `;
    return;
  }

  const header = document.querySelector("header");
  const themeBtn = document.querySelector("[data-theme-toggle]");
  const navBtn = document.querySelector("[data-nav-toggle]");
  const nav = header ? header.querySelector("#primary-nav") : null;

  function getSystemTheme() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches
      ? "light"
      : "dark";
  }

  function applyTheme(theme) {
    const useLight = theme === "light";
    root.classList.toggle("theme-light", useLight);

    if (themeBtn) {
      themeBtn.setAttribute("aria-label", useLight ? "Switch to dark theme" : "Switch to light theme");
      themeBtn.setAttribute("aria-pressed", useLight ? "true" : "false");
    }
  }

  function openNav() {
    if (!header || !navBtn) return;
    header.classList.add("nav-open");
    navBtn.setAttribute("aria-expanded", "true");
    navBtn.setAttribute("aria-label", "Close navigation");
  }

  function closeNav() {
    if (!header || !navBtn) return;
    header.classList.remove("nav-open");
    navBtn.setAttribute("aria-expanded", "false");
    navBtn.setAttribute("aria-label", "Open navigation");
  }

  // Init theme (use saved preference if present, otherwise follow system)
  let storedTheme = null;
  try {
    storedTheme = localStorage.getItem(storageKey);
  } catch (_) {}

  applyTheme(storedTheme || getSystemTheme());

  // Respect system theme changes unless the user explicitly chose a theme.
  const mql = window.matchMedia ? window.matchMedia("(prefers-color-scheme: light)") : null;
  if (mql && mql.addEventListener) {
    mql.addEventListener("change", () => {
      let hasStored = false;
      try {
        hasStored = !!localStorage.getItem(storageKey);
      } catch (_) {}
      if (!hasStored) applyTheme(getSystemTheme());
    });
  }

  // Theme toggle
  if (themeBtn) {
    themeBtn.addEventListener("click", () => {
      const next = root.classList.contains("theme-light") ? "dark" : "light";
      try {
        localStorage.setItem(storageKey, next);
      } catch (_) {}
      applyTheme(next);
    });
  }

  // Mobile nav toggle + a11y polish
  if (navBtn && header) {
    // Ensure a stable initial state
    navBtn.setAttribute("aria-expanded", header.classList.contains("nav-open") ? "true" : "false");

    navBtn.addEventListener("click", () => {
      const isOpen = header.classList.toggle("nav-open");
      navBtn.setAttribute("aria-expanded", isOpen ? "true" : "false");
      navBtn.setAttribute("aria-label", isOpen ? "Close navigation" : "Open navigation");
    });

    // Close nav when a link is clicked
    header.querySelectorAll("nav a").forEach((a) => {
      a.addEventListener("click", () => closeNav());
    });

    // Close on Escape
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeNav();
    });

    // Close when clicking outside the header/nav (mobile behavior)
    document.addEventListener("click", (e) => {
      if (!header.classList.contains("nav-open")) return;
      const target = e.target;
      if (target instanceof Node && !header.contains(target)) closeNav();
    });

    // Close nav on resize back to desktop
    window.addEventListener("resize", () => {
      if (window.innerWidth > 860) closeNav();
    });
  }

  // Expose for optional future hooks (no globals leaked by default).
  void nav;
})();
