// NektronAI — tiny client script (theme + mobile nav)
// No frameworks. Runs in <1ms on modern browsers.

(() => {
  const storageKey = "nektron-theme";
  const root = document.documentElement;
  const header = document.querySelector("header");
  const themeBtn = document.querySelector("[data-theme-toggle]");
  const navBtn = document.querySelector("[data-nav-toggle]");

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

  // Init theme
  let theme = null;
  try {
    theme = localStorage.getItem(storageKey);
  } catch (_) {}

  if (!theme) theme = getSystemTheme();
  applyTheme(theme);

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

  // Mobile nav toggle
  if (navBtn && header) {
    navBtn.addEventListener("click", () => {
      header.classList.toggle("nav-open");
    });

    // Close nav when a link is clicked
    header.querySelectorAll("nav a").forEach((a) => {
      a.addEventListener("click", () => header.classList.remove("nav-open"));
    });
  }
})();
