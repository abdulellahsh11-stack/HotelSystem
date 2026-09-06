/* i18n.js — لغة الواجهة على الخادم مصدرها.
 *
 * يقرأ حزمة اللغة من /api/i18n/bundle، يضبط lang/dir على <html>، ويترجم كل
 * عنصر يحمل data-i18n بمفتاحه. زرّ يحمل data-i18n-toggle يبدّل بين ar/en
 * ويثبّت الاختيار (الخادم يضع الكوكي). دفاعيٌّ: أي فشل يترك الصفحة كما هي.
 */
(function () {
  function apply(b) {
    if (!b || !b.lang) return;
    try {
      var root = document.documentElement;
      root.lang = b.lang;
      root.dir = b.dir || (b.lang === "ar" ? "rtl" : "ltr");
      var s = b.strings || {};
      var nodes = document.querySelectorAll("[data-i18n]");
      for (var i = 0; i < nodes.length; i++) {
        var k = nodes[i].getAttribute("data-i18n");
        if (s[k] != null) nodes[i].textContent = s[k];
      }
      var toggles = document.querySelectorAll("[data-i18n-toggle]");
      for (var j = 0; j < toggles.length; j++) {
        if (s["action.language"] != null) toggles[j].textContent = s["action.language"];
      }
      window.__lang = b.lang;
    } catch (e) { /* لا تكسر الصفحة لأجل الترجمة */ }
  }

  function load(lang) {
    var url = "/api/i18n/bundle" + (lang ? "?lang=" + encodeURIComponent(lang) : "");
    return fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(apply)
      .catch(function () {});
  }

  function toggle() {
    var cur = window.__lang || document.documentElement.lang || "ar";
    load(cur === "ar" ? "en" : "ar");
  }

  document.addEventListener("DOMContentLoaded", function () {
    load();
    var toggles = document.querySelectorAll("[data-i18n-toggle]");
    for (var i = 0; i < toggles.length; i++) {
      toggles[i].style.cursor = "pointer";
      toggles[i].addEventListener("click", function (ev) { ev.preventDefault(); toggle(); });
    }
  });

  window.Dheuofi18n = { load: load, toggle: toggle };
})();
