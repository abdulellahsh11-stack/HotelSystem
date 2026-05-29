/* =========================================================================
   Dheuof — bilingual toggle
   Adds a top-corner switch (AR ⇄ EN) that:
     • Toggles <html dir> and <html lang>
     • Swaps any element with [data-en] between its inner text and the EN copy
     • Persists choice in localStorage (key: dheuof-lang)
   Drop this script on any page that has [data-en] attributes.
   ========================================================================= */
(function () {
  "use strict";
  const KEY = "dheuof-lang";

  function getLang() {
    return localStorage.getItem(KEY) || "ar";
  }

  function applyLang(lang) {
    const root = document.documentElement;
    const isAr = lang === "ar";
    root.setAttribute("lang", isAr ? "ar" : "en");
    root.setAttribute("dir", isAr ? "rtl" : "ltr");

    // Swap every element that has data-en
    document.querySelectorAll("[data-en]").forEach((el) => {
      const en = el.getAttribute("data-en");
      // Stash original Arabic on first run
      if (!el.dataset.ar) el.dataset.ar = el.textContent;
      el.textContent = isAr ? el.dataset.ar : en;
    });

    // Toggle button label
    document.querySelectorAll("[data-lang-toggle]").forEach((btn) => {
      btn.textContent = isAr ? "EN" : "ع";
    });

    localStorage.setItem(KEY, lang);
  }

  function toggle() {
    applyLang(getLang() === "ar" ? "en" : "ar");
  }

  function attach() {
    document.querySelectorAll("[data-lang-toggle]").forEach((btn) => {
      btn.addEventListener("click", (e) => { e.preventDefault(); toggle(); });
    });
    applyLang(getLang());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", attach);
  } else {
    attach();
  }

  window.DheuofLang = { toggle, applyLang, getLang };
})();
