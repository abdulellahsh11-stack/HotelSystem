/* =========================================================================
   Dheuof motion toolkit — JS side
   - Splits [data-m-words] into individual word spans.
   - Sets up IntersectionObserver for [data-m-rise], [data-m-rise-stagger],
     and word-reveal containers.
   - Animates [data-m-count] from 0 → target on enter (with Arabic-Indic
     digit support).
   - Wires [data-m-parallax] to scroll.

   Auto-runs on DOMContentLoaded. Safe to load before or after content.
   ========================================================================= */

(function () {
  "use strict";

  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ── Arabic-Indic digit converter ───────────────────────────────────────
  const AR_DIGITS = ["٠","١","٢","٣","٤","٥","٦","٧","٨","٩"];
  function toArDigits(s) {
    return String(s).replace(/[0-9]/g, d => AR_DIGITS[+d]);
  }
  function detectArabic(s) {
    return /[\u0660-\u0669]/.test(String(s));
  }

  // ── 1) Split [data-m-words] into spans ─────────────────────────────────
  function splitWords(el) {
    if (el.dataset.mSplit === "1") return;
    el.dataset.mSplit = "1";
    el.classList.add("m-words");

    // Walk only top-level text nodes to preserve nested spans (like .accent)
    const replaceTextNodes = (node) => {
      const children = Array.from(node.childNodes);
      children.forEach(child => {
        if (child.nodeType === Node.TEXT_NODE) {
          const txt = child.textContent;
          if (!txt.trim()) return;
          const frag = document.createDocumentFragment();
          // Split on whitespace but keep it
          const tokens = txt.split(/(\s+)/);
          tokens.forEach(tok => {
            if (!tok) return;
            if (/^\s+$/.test(tok)) {
              frag.appendChild(document.createTextNode(tok));
            } else {
              const span = document.createElement("span");
              span.className = "m-word";
              span.textContent = tok;
              frag.appendChild(span);
            }
          });
          node.replaceChild(frag, child);
        } else if (child.nodeType === Node.ELEMENT_NODE) {
          // Recurse into inline children (like <span class="accent">) but
          // tag them as words wholesale.
          if (child.tagName === "BR") return;
          if (child.children.length === 0) {
            child.classList.add("m-word");
          } else {
            replaceTextNodes(child);
          }
        }
      });
    };
    replaceTextNodes(el);

    // Assign incremental index for stagger
    const words = el.querySelectorAll(".m-word");
    words.forEach((w, i) => w.style.setProperty("--w-i", i));
  }

  // ── 2) Stagger children index ──────────────────────────────────────────
  function indexStaggerChildren(parent) {
    Array.from(parent.children).forEach((child, i) => {
      if (!child.style.getPropertyValue("--i")) {
        child.style.setProperty("--i", i);
      }
    });
  }

  // ── 3) Count-up ────────────────────────────────────────────────────────
  function animateCount(el) {
    if (el.dataset.mCounted === "1") return;
    el.dataset.mCounted = "1";

    const target = parseFloat(el.dataset.mCount);
    if (isNaN(target)) return;

    const isArabic = detectArabic(el.textContent) || el.dataset.mDigits === "ar";
    const decimals = (el.dataset.mDecimals && parseInt(el.dataset.mDecimals, 10)) || 0;
    const suffix = el.dataset.mSuffix || "";
    const prefix = el.dataset.mPrefix || "";
    const dur = parseInt(el.dataset.mDuration || "1400", 10);
    const startTs = performance.now();
    const startVal = 0;

    // Cache original for accessibility (don't lose original Arabic for a11y)
    if (!el.dataset.mOriginal) el.dataset.mOriginal = el.textContent;

    function format(v) {
      const num = v.toFixed(decimals);
      const grouped = decimals === 0
        ? Number(num).toLocaleString("en-US")
        : num;
      const out = prefix + grouped + suffix;
      return isArabic ? toArDigits(out.replace(/,/g, "٬")) : out;
    }

    function step(now) {
      const t = Math.min(1, (now - startTs) / dur);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      const val = startVal + (target - startVal) * eased;
      el.textContent = format(val);
      if (t < 1) requestAnimationFrame(step);
      else el.textContent = format(target);
    }
    if (reduceMotion) { el.textContent = format(target); return; }
    requestAnimationFrame(step);
  }

  // ── 4) Parallax on scroll ──────────────────────────────────────────────
  const parallaxItems = [];
  function setupParallax(root) {
    root.querySelectorAll("[data-m-parallax]").forEach(el => {
      const speed = parseFloat(el.dataset.mParallax) || 0.2;
      parallaxItems.push({ el, speed });
    });
  }
  function runParallax() {
    if (reduceMotion) return;
    const scrollY = window.scrollY || window.pageYOffset;
    parallaxItems.forEach(({ el, speed }) => {
      const rect = el.getBoundingClientRect();
      const center = rect.top + window.scrollY + rect.height / 2;
      const delta = (window.scrollY + window.innerHeight / 2 - center) * speed;
      el.style.setProperty("--m-park", delta + "px");
    });
  }

  // ── IO setup ───────────────────────────────────────────────────────────
  function makeIO(rootMargin = "0px 0px -8% 0px") {
    return new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const el = entry.target;
          el.classList.add("is-in");
          // Trigger any count-ups inside
          el.querySelectorAll("[data-m-count]").forEach(animateCount);
          // Don't unobserve splitter parents — they may have nested counts
        }
      });
    }, { threshold: 0.15, rootMargin });
  }

  function init(root = document) {
    // 1) Pre-process [data-m-words] and split them
    root.querySelectorAll("[data-m-words]").forEach(el => splitWords(el));

    // 2) Stagger parents
    root.querySelectorAll("[data-m-rise-stagger]").forEach(indexStaggerChildren);

    // 3) Observe rise / words / stagger
    const io = makeIO();
    root.querySelectorAll("[data-m-rise], [data-m-rise-stagger], [data-m-words], [data-m-count]")
      .forEach(el => io.observe(el));

    // 4) Stand-alone counts (without rise) start immediately if visible
    root.querySelectorAll("[data-m-count]").forEach(el => {
      const rect = el.getBoundingClientRect();
      if (rect.top < window.innerHeight && rect.bottom > 0) animateCount(el);
    });

    // 5) Parallax
    setupParallax(root);
  }

  // Run when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => init());
  } else {
    init();
  }

  let ticking = false;
  window.addEventListener("scroll", () => {
    if (!ticking) {
      requestAnimationFrame(() => { runParallax(); ticking = false; });
      ticking = true;
    }
  }, { passive: true });

  // Expose for re-init after dynamic content (e.g. React mount)
  window.DheuofMotion = { init, splitWords, animateCount };
})();
