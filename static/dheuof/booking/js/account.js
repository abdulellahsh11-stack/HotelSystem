/* =========================================================================
   account.js — حساب الزائر: يدخل، يطلب حجزاً لنفسه، يرى طلباته

   **لا حقل اسم ضيفٍ ولا رقم هوية.** صاحب الجلسة هو صاحب الطلب —
   وحقلُ اسمٍ يجعل البوابة قناة إدخال هوياتٍ لا يملكها المُدخِل.
   ========================================================================= */
(function () {
  'use strict';

  var params = new URLSearchParams(location.search);
  var presetClient = params.get('c') || '';

  function $(id) { return document.getElementById(id); }
  function esc(v) {
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function toast(msg, isError) {
    var t = document.createElement('div');
    t.className = 'ac-toast' + (isError ? ' is-err' : '');
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () {
      t.style.opacity = '0';
      setTimeout(function () { if (t.parentNode) t.remove(); }, 300);
    }, 3200);
  }

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
      return { ok: false, status: 0, error: 'تعذّر الاتصال — تحقّق من الشبكة' };
    }
  }

  /* ── من أنا ──────────────────────────────────────────────────── */
  async function refresh() {
    var res = await api('/api/visit/me');
    if (res.ok) {
      var me = (res.data && res.data.data) || {};
      $('gate').hidden = true;
      $('panel').hidden = false;
      $('who').textContent = me.full_name || '';
      loadBookings();
      loadRooms();
    } else {
      $('gate').hidden = false;
      $('panel').hidden = true;
      // رقم المنشأة يُملأ من رابط الوحدة: الزائر جاء من صفحتها، فطلبُه
      // كتابته يدوياً عقبةٌ بلا سبب.
      if (presetClient && $('g-client')) $('g-client').value = presetClient;
    }
  }

  /* ── الدخول والتسجيل ─────────────────────────────────────────── */
  function readGate() {
    return {
      client_id: $('g-client').value.trim(),
      phone: $('g-phone').value.trim(),
      password: $('g-password').value
    };
  }

  async function doLogin() {
    var body = readGate();
    if (!body.client_id || !body.phone || !body.password) {
      toast('أكمل الحقول', true); return;
    }
    var res = await api('/api/visit/login', { method: 'POST', body: JSON.stringify(body) });
    if (!res.ok) { toast(res.error, true); return; }
    refresh();
  }

  async function doRegister() {
    var body = readGate();
    body.full_name = $('g-name').value.trim();
    body.email = $('g-email').value.trim();
    if (!body.client_id || !body.full_name || !body.phone || !body.password) {
      toast('الاسم والجوال ورقم المنشأة وكلمة المرور مطلوبة', true); return;
    }
    var res = await api('/api/visit/register', { method: 'POST', body: JSON.stringify(body) });
    if (!res.ok) { toast(res.error, true); return; }
    toast('أهلاً بك');
    refresh();
  }

  async function doLogout() {
    await api('/api/visit/logout', { method: 'POST' });
    refresh();
  }

  function toggleMode(isRegister) {
    $('g-name').parentElement.hidden = !isRegister;
    $('g-email').parentElement.hidden = !isRegister;
    $('g-submit').textContent = isRegister ? 'إنشاء الحساب' : 'دخول';
    $('g-switch').textContent = isRegister ? 'لديك حساب؟ سجّل الدخول' : 'لا حساب لك؟ أنشئ واحداً';
    $('g-submit').dataset.mode = isRegister ? 'register' : 'login';
  }

  /* ── الغرف المتاحة ───────────────────────────────────────────── */
  async function loadRooms() {
    var res = await api('/api/visit/rooms');
    var sel = $('b-room_type');
    if (!res.ok || !sel) return;
    var rooms = (res.data && res.data.data) || [];
    sel.innerHTML = '<option value="">أي نوع</option>' + rooms.map(function (r) {
      return '<option value="' + esc(r.room_type) + '">' + esc(r.room_type) +
        ' — ' + esc(Number(r.price).toFixed(0)) + ' ر.س (' + esc(r.available) + ' متاح)</option>';
    }).join('');
  }

  /* ── الطلبات ─────────────────────────────────────────────────── */
  async function loadBookings() {
    var res = await api('/api/visit/bookings');
    var el = $('bookings');
    if (!res.ok) { el.innerHTML = '<div class="ac-empty">' + esc(res.error) + '</div>'; return; }
    var rows = (res.data && res.data.data) || [];
    if (!rows.length) {
      el.innerHTML = '<div class="ac-empty">لا طلبات بعد.</div>';
      return;
    }
    var LABEL = { pending: 'قيد المراجعة', confirmed: 'مؤكّد', cancelled: 'ملغى' };
    el.innerHTML = rows.map(function (b) {
      return '<div class="ac-booking">' +
        '<div class="ac-b-main">' +
          '<b>' + esc(b.room_type || 'أي نوع') + '</b>' +
          '<span class="ac-status s-' + esc(b.status) + '">' +
            esc(LABEL[b.status] || b.status) + '</span>' +
        '</div>' +
        '<div class="ac-b-meta">' +
          esc(String(b.check_in).slice(0, 10)) + ' ← ' +
          esc(String(b.check_out).slice(0, 10)) + ' · ' +
          esc(b.guests_count) + ' نزلاء' +
        '</div>' +
        (b.status === 'pending'
          ? '<button class="ac-x" data-cancel="' + esc(b.id) + '">إلغاء الطلب</button>'
          : '') +
        '</div>';
    }).join('');
  }

  async function requestBooking() {
    var body = {
      room_type: $('b-room_type').value,
      check_in: $('b-check_in').value,
      check_out: $('b-check_out').value,
      guests_count: $('b-guests').value,
      notes: $('b-notes').value.trim()
    };
    if (!body.check_in || !body.check_out) { toast('حدّد تاريخي الوصول والمغادرة', true); return; }
    var res = await api('/api/visit/bookings', { method: 'POST', body: JSON.stringify(body) });
    if (!res.ok) { toast(res.error, true); return; }
    toast((res.data && res.data.note) || 'وصل طلبك');
    $('b-notes').value = '';
    loadBookings();
  }

  async function cancelBooking(id) {
    if (!confirm('إلغاء هذا الطلب؟')) return;
    var res = await api('/api/visit/bookings/' + encodeURIComponent(id), { method: 'DELETE' });
    if (!res.ok) { toast(res.error, true); return; }
    toast('أُلغي الطلب');
    loadBookings();
  }

  /* ── الربط ───────────────────────────────────────────────────── */
  function bind() {
    $('g-submit').addEventListener('click', function () {
      if (this.dataset.mode === 'register') doRegister(); else doLogin();
    });
    $('g-switch').addEventListener('click', function () {
      toggleMode($('g-submit').dataset.mode !== 'register');
    });
    $('logout').addEventListener('click', doLogout);
    $('b-submit').addEventListener('click', requestBooking);

    document.addEventListener('click', function (ev) {
      var b = ev.target.closest && ev.target.closest('button');
      if (b && b.dataset.cancel) cancelBooking(b.dataset.cancel);
    });
    $('gate').addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter') { ev.preventDefault(); $('g-submit').click(); }
    });
  }

  function init() {
    bind();
    toggleMode(false);
    refresh();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
