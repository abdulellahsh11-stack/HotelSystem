/* =========================================================================
   unit.js — صفحة الوحدة: صورها ومرافقها وموقعها

   عنوانٌ عامّ يُشارَك ويُفهرَس. ولا خطر: لا يُعرض إلا المنشور، والمعروض
   لا يحمل بيانات نزيلٍ ولا رقم غرفة.
   ========================================================================= */
(function () {
  'use strict';

  function $(id) { return document.getElementById(id); }
  function esc(v) {
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  var params = new URLSearchParams(location.search);
  var clientId = params.get('c') || '';
  var unitId = params.get('u') || '';

  async function load() {
    var host = $('unit');
    if (!clientId || !unitId) {
      host.innerHTML = '<div class="bk-empty">رابطٌ غير مكتمل.</div>';
      return;
    }
    var res, body;
    try {
      res = await fetch('/api/search/' + encodeURIComponent(clientId) +
                        '/' + encodeURIComponent(unitId), { credentials: 'same-origin' });
      body = await res.json();
    } catch (e) {
      host.innerHTML = '<div class="bk-empty">تعذّر الاتصال — تحقّق من الشبكة.</div>';
      return;
    }
    if (!res.ok) {
      host.innerHTML = '<div class="bk-empty">' +
        esc((body && body.detail) || 'هذه الوحدة غير متاحة الآن.') + '</div>';
      return;
    }
    render((body && body.data) || {});
  }

  function render(u) {
    document.title = u.title + ' — ' + u.display_name + ' | ضيوف';
    var place = [u.district, u.city, u.country].filter(Boolean).join(' · ');
    var photos = u.photos || [];

    $('unit').innerHTML =
      '<div class="un-gallery">' +
        (photos.length
          ? photos.map(function (p, i) {
              return '<figure class="un-shot' + (i === 0 ? ' is-main' : '') + '">' +
                '<img src="' + esc(p.url) + '" alt="' + esc(p.caption || u.title) +
                '" loading="' + (i === 0 ? 'eager' : 'lazy') + '"/>' +
                (p.caption ? '<figcaption>' + esc(p.caption) + '</figcaption>' : '') +
                '</figure>';
            }).join('')
          : '<div class="bk-empty">لا صور لهذه الوحدة</div>') +
      '</div>' +

      '<div class="un-body">' +
        '<div class="un-main">' +
          '<span class="un-kind">' + esc(u.kind_label) + '</span>' +
          '<h1>' + esc(u.title) + '</h1>' +
          '<div class="un-prop">' + esc(u.display_name) +
            (u.tagline ? ' — ' + esc(u.tagline) : '') + '</div>' +
          '<div class="un-place">' + esc(place) +
            (u.address ? '<br/>' + esc(u.address) : '') + '</div>' +
          (u.landmark
            ? '<div class="un-landmark">📍 ' + esc(u.landmark) +
              (u.landmark_km != null ? ' · على بُعد ' + esc(u.landmark_km) + ' كم' : '') +
              '</div>'
            : '') +

          '<div class="un-specs">' +
            '<div><b>' + esc(u.capacity) + '</b><span>نزلاء</span></div>' +
            '<div><b>' + esc(u.bedrooms || 0) + '</b><span>غرف نوم</span></div>' +
            '<div><b>' + esc(u.bathrooms || 0) + '</b><span>حمّامات</span></div>' +
            (u.area_sqm ? '<div><b>' + esc(u.area_sqm) + '</b><span>م²</span></div>' : '') +
          '</div>' +

          (u.description
            ? '<h2>عن الوحدة</h2><p class="un-desc">' + esc(u.description) + '</p>'
            : '') +

          ((u.amenity_labels || []).length
            ? '<h2>المرافق</h2><div class="un-amen">' +
              u.amenity_labels.map(function (a) {
                return '<span>' + esc(a.label) + '</span>';
              }).join('') + '</div>'
            : '') +

          (u.property_description
            ? '<h2>عن المنشأة</h2><p class="un-desc">' +
              esc(u.property_description) + '</p>'
            : '') +
        '</div>' +

        '<aside class="un-side">' +
          '<div class="un-price">' +
            '<b>' + esc(Number(u.base_price).toFixed(0)) + '</b> ر.س' +
            '<small>الليلة</small>' +
          '</div>' +
          (u.weekend_price
            ? '<div class="un-weekend">نهاية الأسبوع: ' +
              esc(Number(u.weekend_price).toFixed(0)) + ' ر.س</div>'
            : '') +
          '<div class="un-rule">أقل مدة: ' + esc(u.min_nights) + ' ليلة</div>' +
          '<div class="un-rule">الدخول ' + esc(u.checkin_time) +
            ' · الخروج ' + esc(u.checkout_time) + '</div>' +
          '<a class="un-book" href="account.html?c=' + encodeURIComponent(u.client_id) +
            '&u=' + encodeURIComponent(u.id) + '">اطلب الحجز</a>' +
          '<p class="un-note">' +
            'طلبك يصل المنشأة وتؤكّده وتتواصل معك. لا يُطلب رقم هويتك هنا — ' +
            'تُؤخذ عند الوصول.' +
          '</p>' +
        '</aside>' +
      '</div>';
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }
})();
