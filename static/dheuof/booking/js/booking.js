/* =========================================================================
   booking.js — مسار الزائر: يبحث ويتصفّح

   بلا جلسة: الزائر يتصفّح قبل أن يُنشئ حساباً. إلزامُه بالتسجيل ليرى
   الأسعار يُفقده قبل أن يبدأ — والحساب يُطلب عند الحجز وحده.

   **الخيارات من الخادم لا من هنا.** عرض مدنٍ لا معروض فيها يُنتج بحثاً
   يعود فارغاً دائماً، فيظنّ الزائر أن التطبيق معطَّل.
   ========================================================================= */
(function () {
  'use strict';

  var FILTERS = { places: {}, kinds: [], amenities: [], price: {} };
  var state = { page: 1 };

  function $(id) { return document.getElementById(id); }
  function esc(v) {
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  async function api(path) {
    try {
      var res = await fetch(path, { credentials: 'same-origin' });
      var body = null;
      try { body = await res.json(); } catch (e) { /* ردٌّ بلا جسم */ }
      if (!res.ok) {
        return { ok: false, error: (body && body.detail) || ('خطأ ' + res.status) };
      }
      return { ok: true, data: body };
    } catch (e) {
      return { ok: false, error: 'تعذّر الاتصال — تحقّق من الشبكة' };
    }
  }

  /* ── الخيارات المتاحة فعلاً ──────────────────────────────────── */
  async function loadFilters() {
    var res = await api('/api/search/filters');
    if (!res.ok) return;
    FILTERS = (res.data && res.data.data) || FILTERS;

    fillSelect($('f-country'), Object.keys(FILTERS.places), 'كل الدول');
    $('f-country').addEventListener('change', onCountry);
    $('f-city').addEventListener('change', onCity);
    onCountry();

    fillSelect($('f-kind'), FILTERS.kinds.map(function (k) { return k.value; }),
               'كل الأنواع', FILTERS.kinds);

    var box = $('f-amenities');
    box.innerHTML = FILTERS.amenities.map(function (a) {
      return '<label class="bk-chip"><input type="checkbox" value="' + esc(a.value) +
        '"/><span>' + esc(a.label) + '</span></label>';
    }).join('');

    if (FILTERS.price && FILTERS.price.max) {
      $('f-price_max').placeholder = 'حتى ' + Math.round(FILTERS.price.max);
      $('f-price_min').placeholder = 'من ' + Math.round(FILTERS.price.min || 0);
    }
  }

  function fillSelect(sel, values, allLabel, labelled) {
    if (!sel) return;
    var opts = ['<option value="">' + esc(allLabel) + '</option>'];
    values.forEach(function (v) {
      var label = v;
      if (labelled) {
        labelled.forEach(function (x) { if (x.value === v) label = x.label; });
      }
      opts.push('<option value="' + esc(v) + '">' + esc(label) + '</option>');
    });
    sel.innerHTML = opts.join('');
  }

  function onCountry() {
    var country = $('f-country').value;
    var cities = country ? Object.keys(FILTERS.places[country] || {}) : [];
    fillSelect($('f-city'), cities, 'كل المدن');
    onCity();
  }

  function onCity() {
    var country = $('f-country').value;
    var city = $('f-city').value;
    var districts = (country && city && (FILTERS.places[country] || {})[city]) || [];
    fillSelect($('f-district'), districts, 'كل الأحياء');
  }

  /* ── البحث ───────────────────────────────────────────────────── */
  function buildQuery() {
    var q = new URLSearchParams();
    [['country', 'f-country'], ['city', 'f-city'], ['district', 'f-district'],
     ['landmark', 'f-landmark'], ['kind', 'f-kind'], ['guests', 'f-guests'],
     ['price_min', 'f-price_min'], ['price_max', 'f-price_max'],
     ['check_in', 'f-check_in'], ['check_out', 'f-check_out'],
     ['sort', 'f-sort']].forEach(function (pair) {
      var el = $(pair[1]);
      if (el && el.value) q.set(pair[0], el.value);
    });
    var chosen = Array.prototype.slice
      .call(document.querySelectorAll('#f-amenities input:checked'))
      .map(function (i) { return i.value; });
    if (chosen.length) q.set('amenities', chosen.join(','));
    q.set('page', state.page);
    return q.toString();
  }

  async function search(resetPage) {
    if (resetPage !== false) state.page = 1;
    var el = $('results');
    el.innerHTML = '<div class="bk-empty">جارٍ البحث…</div>';

    var res = await api('/api/search?' + buildQuery());
    if (!res.ok) { el.innerHTML = '<div class="bk-empty">' + esc(res.error) + '</div>'; return; }

    var body = res.data || {};
    var items = body.data || [];
    $('res-count').textContent = body.total || 0;

    if (!items.length) {
      el.innerHTML = '<div class="bk-empty">' +
        'لا نتائج بهذه المواصفات — جرّب توسيع البحث أو إزالة بعض المرافق.' +
        '</div>';
      renderPager(body);
      return;
    }
    el.innerHTML = items.map(card).join('');
    renderPager(body);
  }

  function card(u) {
    var place = [u.district, u.city, u.country].filter(Boolean).join(' · ');
    return '<a class="bk-card" href="unit.html?c=' + encodeURIComponent(u.client_id) +
             '&u=' + encodeURIComponent(u.id) + '">' +
      '<div class="bk-photo">' +
        (u.photo
          ? '<img src="' + esc(u.photo) + '" alt="' + esc(u.title) + '" loading="lazy"/>'
          : '<span class="bk-nophoto">بلا صورة</span>') +
        '<span class="bk-kind">' + esc(u.kind_label) + '</span>' +
      '</div>' +
      '<div class="bk-info">' +
        '<h3>' + esc(u.title) + '</h3>' +
        '<div class="bk-prop">' + esc(u.display_name) + '</div>' +
        '<div class="bk-place">' + esc(place) + '</div>' +
        (u.landmark
          ? '<div class="bk-landmark">📍 ' + esc(u.landmark) +
            (u.landmark_km != null ? ' · ' + esc(u.landmark_km) + ' كم' : '') + '</div>'
          : '') +
        '<div class="bk-specs">' +
          '<span>' + esc(u.capacity) + ' نزلاء</span>' +
          '<span>' + esc(u.bedrooms || 0) + ' غرف</span>' +
          (u.area_sqm ? '<span>' + esc(u.area_sqm) + ' م²</span>' : '') +
        '</div>' +
        '<div class="bk-price">' +
          '<b>' + esc(Number(u.base_price).toFixed(0)) + '</b> ر.س <small>/ الليلة</small>' +
          (u.total_price
            ? '<div class="bk-total">' + esc(Number(u.total_price).toFixed(0)) +
              ' ر.س لـ' + esc(u.nights) + ' ليالٍ</div>'
            : '') +
        '</div>' +
      '</div></a>';
  }

  function renderPager(body) {
    var el = $('pager');
    var total = body.total || 0;
    var per = body.per_page || 24;
    var pages = Math.ceil(total / per);
    if (pages <= 1) { el.innerHTML = ''; return; }
    el.innerHTML =
      '<button class="bk-page" id="prev"' + (state.page <= 1 ? ' disabled' : '') + '>السابق</button>' +
      // مُهرَّبة وإن كانت عدداً داخلياً: قاعدةٌ مطلقة — «كل ما يُحقن
      // يُهرَّب» — تُراجَع في لمحة، أما «يُهرَّب إلا ما أعرف أنه آمن»
      // فتحتاج إثباتاً جديداً عند كل تعديل.
      '<span>' + esc(state.page) + ' من ' + esc(pages) + '</span>' +
      '<button class="bk-page" id="next"' + (state.page >= pages ? ' disabled' : '') + '>التالي</button>';
    $('prev').addEventListener('click', function () {
      if (state.page > 1) { state.page--; search(false); window.scrollTo(0, 0); }
    });
    $('next').addEventListener('click', function () {
      if (state.page < pages) { state.page++; search(false); window.scrollTo(0, 0); }
    });
  }

  /* ── الربط ───────────────────────────────────────────────────── */
  function bind() {
    $('do-search').addEventListener('click', function () { search(); });
    $('clear').addEventListener('click', function () {
      document.querySelectorAll('.bk-filters input, .bk-filters select')
        .forEach(function (i) {
          if (i.type === 'checkbox') i.checked = false; else i.value = '';
        });
      onCountry();
      search();
    });
    // البحث بالمفتاح: الزائر يكتب المعلم ثم يضغط Enter، ولو لم يعمل
    // ظنّ أن التطبيق لا يستجيب.
    document.querySelector('.bk-filters').addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter') { ev.preventDefault(); search(); }
    });
    if ($('f-sort')) $('f-sort').addEventListener('change', function () { search(); });
  }

  async function init() {
    bind();
    await loadFilters();
    search();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
