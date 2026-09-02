/* =========================================================================
   listing.js — مسار المنشأة في تطبيق الحجوزات

   تُخصّص المنشأة ما يراه الزائر: هويتها المعروضة، ثم وحداتها بصورها
   وأسعارها ومرافقها.

   **المفردات من الخادم لا من هنا.** كتابة الأنواع والمرافق في الواجهة
   تُنتج قائمتين تتباعدان: يُضاف نوعٌ في القاعدة ولا يظهر هنا، أو
   تُرسل قيمةٌ يرفضها الخادم بلا سبب يفهمه المستخدم.
   ========================================================================= */
(function () {
  'use strict';

  var VOCAB = { kinds: [], amenities: [] };
  var UNITS = [];
  var editingId = null;

  function $(id) { return document.getElementById(id); }
  function esc(v) {
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function toast(msg, isError) {
    var t = document.createElement('div');
    t.className = 'ls-toast' + (isError ? ' is-err' : '');
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () {
      t.style.opacity = '0';
      setTimeout(function () { if (t.parentNode) t.remove(); }, 300);
    }, 3000);
  }

  /* رسالة الخادم تُعرض كما هي: «تعذّر الحفظ» يترك المستخدم بلا سبيل،
     بينما «نوع الوحدة غير معروف» يخبره بما يفعل. */
  async function api(path, opts) {
    opts = opts || {};
    try {
      var res = await fetch(path, Object.assign({
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }
      }, opts));
      var body = null;
      try { body = await res.json(); } catch (e) { /* ردٌّ بلا جسم */ }
      if (!res.ok) {
        return { ok: false, status: res.status,
                 error: (body && (body.detail || body.error)) || ('خطأ ' + res.status) };
      }
      return { ok: true, data: body };
    } catch (e) {
      return { ok: false, status: 0, error: 'تعذّر الاتصال بالخادم' };
    }
  }

  /* ── الهوية المعروضة ─────────────────────────────────────────── */
  var PROFILE_FIELDS = [
    'display_name', 'tagline', 'description', 'logo_url', 'cover_url',
    'country', 'city', 'district', 'address', 'landmark', 'landmark_km',
    'latitude', 'longitude', 'checkin_time', 'checkout_time', 'phone'
  ];

  async function loadProfile() {
    var res = await api('/api/listing/profile');
    if (!res.ok) { toast(res.error, true); return; }
    var p = (res.data && res.data.data) || {};
    PROFILE_FIELDS.forEach(function (f) {
      var el = $('pf-' + f);
      if (el) el.value = p[f] == null ? '' : p[f];
    });
    if ($('pf-published')) $('pf-published').checked = !!p.is_published;
    renderPublishState(!!p.is_published);
  }

  function renderPublishState(on) {
    var el = $('pf-state');
    if (!el) return;
    el.textContent = on ? '● معروضة للزوّار' : '○ مسوّدة — لا يراها أحد';
    el.className = 'ls-state' + (on ? ' is-live' : '');
  }

  async function saveProfile() {
    var body = { is_published: $('pf-published').checked };
    PROFILE_FIELDS.forEach(function (f) {
      var el = $('pf-' + f);
      if (el) body[f] = el.value.trim();
    });
    if (!body.display_name) { toast('اسم المنشأة المعروض مطلوب', true); return; }
    var res = await api('/api/listing/profile',
      { method: 'PUT', body: JSON.stringify(body) });
    if (!res.ok) { toast(res.error, true); return; }
    toast('حُفظت هوية المنشأة');
    renderPublishState(body.is_published);
  }

  /* ── المفردات ────────────────────────────────────────────────── */
  async function loadVocabulary() {
    var res = await api('/api/listing/vocabulary');
    if (!res.ok) { toast(res.error, true); return; }
    VOCAB = (res.data && res.data.data) || VOCAB;

    var sel = $('u-kind');
    if (sel) {
      sel.innerHTML = VOCAB.kinds.map(function (k) {
        return '<option value="' + esc(k.value) + '">' + esc(k.label) + '</option>';
      }).join('');
    }
    var box = $('u-amenities');
    if (box) {
      box.innerHTML = VOCAB.amenities.map(function (a) {
        return '<label class="ls-chip"><input type="checkbox" value="' +
          esc(a.value) + '"/><span>' + esc(a.label) + '</span></label>';
      }).join('');
    }
  }

  function kindLabel(value) {
    for (var i = 0; i < VOCAB.kinds.length; i++) {
      if (VOCAB.kinds[i].value === value) return VOCAB.kinds[i].label;
    }
    return value;
  }

  /* ── الوحدات ─────────────────────────────────────────────────── */
  async function loadUnits() {
    var res = await api('/api/listing/units');
    var el = $('units-list');
    if (!res.ok) { if (el) el.innerHTML = '<div class="ls-empty">' + esc(res.error) + '</div>'; return; }
    UNITS = (res.data && res.data.data) || [];
    $('units-count').textContent = UNITS.length;
    if (!el) return;
    if (!UNITS.length) {
      el.innerHTML = '<div class="ls-empty">لا وحدات معروضة — أضف أول وحدة أعلاه.</div>';
      return;
    }
    el.innerHTML = UNITS.map(renderUnit).join('');
  }

  function renderUnit(u) {
    var photos = u.photos || [];
    var amenities = u.amenities || [];
    return '<div class="ls-unit' + (u.is_published ? '' : ' is-draft') + '">' +
      '<div class="ls-unit-photos">' +
        (photos.length
          ? photos.map(function (p) {
              return '<div class="ls-thumb"><img src="' + esc(p.url) + '" alt="' +
                esc(p.caption || '') + '" loading="lazy"/>' +
                '<button class="ls-thumb-x" data-del-photo="' + esc(p.id) +
                '" data-unit="' + esc(u.id) + '" title="حذف">✕</button></div>';
            }).join('')
          : '<div class="ls-nophoto">بلا صور — الوحدة بلا صورة لا تُحجَز</div>') +
      '</div>' +
      '<div class="ls-unit-body">' +
        '<div class="ls-unit-head">' +
          '<h4>' + esc(u.title) + '</h4>' +
          '<span class="ls-tag">' + esc(kindLabel(u.kind)) + '</span>' +
          (u.is_published ? '<span class="ls-tag live">معروضة</span>'
                          : '<span class="ls-tag draft">مسوّدة</span>') +
        '</div>' +
        '<div class="ls-unit-meta">' +
          '<span><b>' + esc(Number(u.base_price || 0).toFixed(2)) + '</b> ر.س/ليلة</span>' +
          '<span>' + esc(u.capacity) + ' نزلاء</span>' +
          '<span>' + esc(u.bedrooms || 0) + ' غرف نوم</span>' +
          '<span>' + esc(u.bathrooms || 0) + ' حمّام</span>' +
          (u.area_sqm ? '<span>' + esc(u.area_sqm) + ' م²</span>' : '') +
          '<span>أقلّها ' + esc(u.min_nights) + ' ليلة</span>' +
          '<span class="' + (Number(u.rooms_linked) ? 'ok' : 'warn') + '">' +
            esc(u.rooms_linked) + ' غرفة مربوطة</span>' +
        '</div>' +
        (amenities.length
          ? '<div class="ls-unit-amen">' + amenities.map(function (a) {
              return '<span>' + esc(amenityLabel(a)) + '</span>';
            }).join('') + '</div>'
          : '') +
        '<div class="ls-unit-actions">' +
          '<button class="ls-x" data-edit="' + esc(u.id) + '">تعديل</button>' +
          '<button class="ls-x" data-photo="' + esc(u.id) + '">+ صورة</button>' +
          '<button class="ls-x" data-link="' + esc(u.id) + '">ربط بالغرف</button>' +
          '<button class="ls-x danger" data-del="' + esc(u.id) +
            '" data-title="' + esc(u.title) + '">حذف</button>' +
        '</div>' +
      '</div></div>';
  }

  function amenityLabel(value) {
    for (var i = 0; i < VOCAB.amenities.length; i++) {
      if (VOCAB.amenities[i].value === value) return VOCAB.amenities[i].label;
    }
    return value;
  }

  /* ── نموذج الوحدة ────────────────────────────────────────────── */
  var UNIT_FIELDS = ['title', 'description', 'base_price', 'weekend_price',
                     'capacity', 'bedrooms', 'bathrooms', 'area_sqm', 'min_nights'];

  function readUnitForm() {
    var body = { kind: $('u-kind').value, is_published: $('u-published').checked };
    UNIT_FIELDS.forEach(function (f) {
      var el = $('u-' + f);
      if (el) body[f] = el.value.trim();
    });
    body.amenities = Array.prototype.slice
      .call(document.querySelectorAll('#u-amenities input:checked'))
      .map(function (i) { return i.value; });
    return body;
  }

  function fillUnitForm(u) {
    $('u-kind').value = u ? u.kind : (VOCAB.kinds[0] || {}).value || 'room';
    UNIT_FIELDS.forEach(function (f) {
      var el = $('u-' + f);
      if (el) el.value = u ? (u[f] == null ? '' : u[f]) : '';
    });
    $('u-published').checked = u ? !!u.is_published : false;
    var chosen = (u && u.amenities) || [];
    Array.prototype.slice.call(document.querySelectorAll('#u-amenities input'))
      .forEach(function (i) { i.checked = chosen.indexOf(i.value) >= 0; });
    editingId = u ? u.id : null;
    $('u-save').textContent = u ? 'حفظ التعديل' : 'إضافة الوحدة';
    $('u-cancel').hidden = !u;
    $('u-form-title').textContent = u ? ('تعديل: ' + u.title) : 'وحدة جديدة';
  }

  async function saveUnit() {
    var body = readUnitForm();
    if (!body.title) { toast('عنوان الوحدة مطلوب', true); return; }
    var res = editingId
      ? await api('/api/listing/units/' + encodeURIComponent(editingId),
                  { method: 'PUT', body: JSON.stringify(body) })
      : await api('/api/listing/units', { method: 'POST', body: JSON.stringify(body) });
    if (!res.ok) { toast(res.error, true); return; }
    toast(editingId ? 'حُفظ التعديل' : 'أُضيفت الوحدة');
    fillUnitForm(null);
    loadUnits();
  }

  async function deleteUnit(id, title) {
    if (!confirm('حذف «' + title + '»؟ تُحذف صورها معها.')) return;
    var res = await api('/api/listing/units/' + encodeURIComponent(id), { method: 'DELETE' });
    if (!res.ok) { toast(res.error, true); return; }
    toast('حُذفت الوحدة');
    loadUnits();
  }

  async function addPhoto(id) {
    var url = prompt('عنوان الصورة (https://...):');
    if (!url) return;
    var caption = prompt('وصف الصورة (اختياري):') || '';
    var res = await api('/api/listing/units/' + encodeURIComponent(id) + '/photos',
      { method: 'POST', body: JSON.stringify({ url: url.trim(), caption: caption.trim() }) });
    if (!res.ok) { toast(res.error, true); return; }
    toast('أُضيفت الصورة');
    loadUnits();
  }

  async function deletePhoto(unitId, photoId) {
    var res = await api('/api/listing/units/' + encodeURIComponent(unitId) +
                        '/photos/' + encodeURIComponent(photoId), { method: 'DELETE' });
    if (!res.ok) { toast(res.error, true); return; }
    loadUnits();
  }

  /* الربط بالمخزون هو ما يجعل التوفّر حقيقياً — لا رقمٌ يُكتب ويُنسى. */
  async function linkRooms(unitId) {
    var res = await api('/api/rooms');
    if (!res.ok) { toast(res.error, true); return; }
    var rooms = (res.data && res.data.data) || [];
    if (!rooms.length) {
      toast('لا غرف مسجَّلة — سجّلها من «إعداد المنشأة» أولاً', true);
      return;
    }
    var picked = prompt(
      'أرقام الغرف لهذه الوحدة، مفصولةً بفاصلة:\n' +
      rooms.map(function (r) { return r.room_number; }).join(' · '),
      rooms.map(function (r) { return r.room_number; }).join(',')
    );
    if (!picked) return;
    var wanted = picked.split(',').map(function (s) { return s.trim(); });
    var ids = rooms.filter(function (r) {
      return wanted.indexOf(String(r.room_number)) >= 0;
    }).map(function (r) { return r.id; });
    if (!ids.length) { toast('لم تُطابَق أي غرفة', true); return; }
    var out = await api('/api/listing/units/' + encodeURIComponent(unitId) + '/rooms',
      { method: 'POST', body: JSON.stringify({ room_ids: ids }) });
    if (!out.ok) { toast(out.error, true); return; }
    toast('رُبطت ' + ((out.data && out.data.data) || {}).linked + ' غرفة');
    loadUnits();
  }

  /* ── الربط ───────────────────────────────────────────────────── */
  function bind() {
    if ($('pf-save')) $('pf-save').addEventListener('click', saveProfile);
    if ($('u-save')) $('u-save').addEventListener('click', saveUnit);
    if ($('u-cancel')) $('u-cancel').addEventListener('click', function () { fillUnitForm(null); });
    if ($('pf-published')) {
      $('pf-published').addEventListener('change', function () {
        renderPublishState(this.checked);
      });
    }

    // تفويضٌ على المستند: البطاقات تُعاد بناؤها بعد كل حفظ، فالربط
    // المباشر على أزرارها يضيع مع أول تحديث.
    document.addEventListener('click', function (ev) {
      var b = ev.target.closest && ev.target.closest('button');
      if (!b) return;
      if (b.dataset.edit) {
        var u = UNITS.filter(function (x) { return String(x.id) === b.dataset.edit; })[0];
        if (u) { fillUnitForm(u); $('u-form-title').scrollIntoView({ behavior: 'smooth' }); }
      } else if (b.dataset.del) {
        deleteUnit(b.dataset.del, b.dataset.title);
      } else if (b.dataset.photo) {
        addPhoto(b.dataset.photo);
      } else if (b.dataset.link) {
        linkRooms(b.dataset.link);
      } else if (b.dataset.delPhoto) {
        deletePhoto(b.dataset.unit, b.dataset.delPhoto);
      }
    });
  }

  async function init() {
    bind();
    await loadVocabulary();
    fillUnitForm(null);
    loadProfile();
    loadUnits();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.ListingModule = { loadUnits: loadUnits, loadProfile: loadProfile };
})();
