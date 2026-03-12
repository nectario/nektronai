// NektronAI — tiny client script (theme + mobile nav)
// No frameworks. Fast, accessible, and production-friendly.

(() => {
  const storageKey = "nektron-theme";
  const root = document.documentElement;
  const sunIconMarkup = `
  <path d="M12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12Z" stroke="currentColor" stroke-width="1.6"/>
  <path d="M12 2v2.5M12 19.5V22M22 12h-2.5M4.5 12H2M19.1 4.9l-1.8 1.8M6.7 17.3 4.9 19.1M19.1 19.1l-1.8-1.8M6.7 6.7 4.9 4.9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
  `;
  const moonIconMarkup = `
  <path d="M14.5 3.5a8.5 8.5 0 1 0 6 14.5 8 8 0 0 1-6-14.5Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
  `;

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
      const icon = themeBtn.querySelector("svg");
      if (icon) {
        icon.setAttribute("viewBox", "0 0 24 24");
        icon.innerHTML = useLight ? sunIconMarkup : moonIconMarkup;
      }
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

  function applyText(node, value) {
    if (!node || typeof value !== "string" || !value) return;
    node.textContent = value;
  }

  function setManagedDownloadLink(link, href, label, shouldDownload) {
    if (!link) return;

    const labelNode = link.querySelector("[data-download-label], [data-download-hero-label]");
    if (labelNode && typeof label === "string" && label) {
      labelNode.textContent = label;
    }

    if (typeof href === "string" && href) {
      link.setAttribute("href", href);
      if (shouldDownload) {
        link.setAttribute("download", "");
      } else {
        link.removeAttribute("download");
      }
      link.classList.remove("is-disabled");
      link.removeAttribute("aria-disabled");
      link.tabIndex = 0;
      return;
    }

    link.removeAttribute("href");
    link.removeAttribute("download");
    link.classList.add("is-disabled");
    link.setAttribute("aria-disabled", "true");
    link.tabIndex = -1;
  }

  function applyManagedRelease(card, release) {
    if (!card || !release) return;

    card.querySelectorAll("[data-download-field]").forEach((node) => {
      const fieldName = node.getAttribute("data-download-field");
      if (!fieldName || typeof release[fieldName] !== "string") return;
      node.textContent = release[fieldName];
    });

    setManagedDownloadLink(
      card.querySelector("[data-download-link]"),
      release.downloadHref,
      release.downloadLabel,
      !!release.download,
    );
  }

  async function initDownloadsPage() {
    const downloadsRoot = document.querySelector("[data-download-manifest]");
    if (!downloadsRoot) return;

    const manifestUrl = downloadsRoot.getAttribute("data-download-manifest");
    if (!manifestUrl) return;

    try {
      const response = await fetch(manifestUrl, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const manifest = await response.json();
      const releases = manifest.releases || {};

      Object.entries(releases).forEach(([releaseId, release]) => {
        applyManagedRelease(
          document.querySelector(`[data-download-release="${releaseId}"]`),
          release,
        );
      });

      const hero = manifest.hero || {};
      const primaryRelease = releases[hero.primaryReleaseId];
      if (primaryRelease) {
        setManagedDownloadLink(
          document.querySelector("[data-download-hero-link]"),
          primaryRelease.downloadHref,
          hero.primaryButtonLabel || primaryRelease.downloadLabel,
          !!primaryRelease.download,
        );
        applyText(
          document.querySelector("[data-download-hero-primary-version]"),
          primaryRelease.version,
        );
      }

      applyText(
        document.querySelector("[data-download-hero-artifacts]"),
        hero.artifacts,
      );
    } catch (error) {
      console.warn("NektronAI downloads manifest could not be applied.", error);
    }
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

  void initDownloadsPage();

  // Expose for optional future hooks (no globals leaked by default).
  void nav;
})();
