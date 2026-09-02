/* =========================================================================
   setup.js — إعداد المنشأة: الغرف والأدوار وحسابات الموظفين

   لماذا وُحّدت هنا؟ كانت هاتان الشاشتان في `dashboard.html` وحدها،
   فيُرسَل المستخدم إليها برسالة «سجّل غرفك من لوحة التحكم» ولا يجد
   إليها سبيلاً — ولا شيء في المنصة يعمل بلا غرف: لا خريطة ولا حجز ولا
   فاتورة. مكانُ الإعداد حيث يُشغَّل النظام، لا في شاشةٍ منفصلة.

   الصلاحيات هنا **للعرض فقط**. المنع الحقيقي على الخادم:
   `rooms.write` للغرف و`staff.manage` للحسابات، و`gm` لا يُسنده إلا
   المالك. إخفاء زرٍّ ليس حمايةً — من عطّل الجافاسكربت يرى الزرّ.
   ========================================================================= */
(function () {
  'use strict';

  var ROOM_TYPES = {
    standard: 'عادية', double: 'مزدوجة', twin: 'سريران',
    suite: 'جناح', family: 'عائلية'
  };
  var ROOM_STATUS = {
    available: 'متاحة', occupied: 'مشغولة', dirty: 'تحتاج تنظيف',
    maintenance: 'صيانة', blocked: 'موقوفة'
  };

  var me = { role: 'owner', permissions: [] };

  function esc(v) {
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function $(id) { return document.getElementById(id); }
  function can(perm) {
    return me.role === 'owner' || me.role === 'gm' ||
           me.permissions.indexOf('*') >= 0 || me.permissions.indexOf(perm) >= 0;
  }

  function toast(msg, isError) {
    var t = document.createElement('div');
    t.className = 'su-toast' + (isError ? ' is-err' : '');
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () {
      t.style.opacity = '0';
      setTimeout(function () { if (t.parentNode) t.remove(); }, 320);
    }, 3000);
  }

  /* لا تبتلع رسالة الخادم: «تعذّر الحفظ» يترك المستخدم بلا سبيل، بينما
     «الغرفة ١٠١ مسجَّلة» يخبره بما يفعل. */
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

  /* ── من أنا؟ ─────────────────────────────────────────────────────── */
  async function loadMe() {
    var res = await api('/api/staff/me');
    if (res.ok && res.data && res.data.data) {
      me.role = res.data.data.role || 'owner';
      me.permissions = res.data.data.permissions || [];
    }
    // الأقسام تُخفى بحسب الدور — تخفيفاً للازدحام لا حمايةً.
    if (!can('rooms.write')) hideSection('sec-rooms', 'تسجيل الغرف يحتاج صلاحية rooms.write');
    if (!can('staff.manage')) hideSection('sec-staff', 'إدارة الحسابات تحتاج صلاحية staff.manage');
    var who = $('su-who');
    if (who) who.textContent = 'دورك: ' + roleLabel(me.role);
  }

  function roleLabel(role) {
    return ({ owner: 'مالك المنشأة', gm: 'مدير عام', manager: 'مدير مناوبة',
              receptionist: 'استقبال', housekeeping: 'إشراف داخلي',
              accountant: 'محاسب', pos_cashier: 'كاشير' })[role] || role;
  }

  function hideSection(id, why) {
    var el = $(id);
    if (!el) return;
    var body = el.querySelector('.su-body');
    if (body) body.innerHTML = '<div class="su-empty">' + esc(why) + '</div>';
  }

  /* ── الغرف ───────────────────────────────────────────────────────── */
  var rooms = [];

  async function loadRooms() {
    var res = await api('/api/rooms');
    var tbl = $('su-rooms-table');
    if (!res.ok) { if (tbl) tbl.innerHTML = '<div class="su-empty">' + esc(res.error) + '</div>'; return; }
    rooms = (res.data && res.data.data) || [];
    $('su-rooms-count').textContent = rooms.length;
    if (!tbl) return;
    if (!rooms.length) {
      tbl.innerHTML = '<div class="su-empty">لا غرف مسجَّلة بعد — ابدأ بـ«تسجيل دفعة» أدناه.</div>';
      return;
    }
    tbl.innerHTML =
      '<table class="su-table"><thead><tr>' +
        '<th>الغرفة</th><th>الدور</th><th>النوع</th><th>السعة</th>' +
        '<th>السعر</th><th>الحالة</th><th></th></tr></thead><tbody>' +
      rooms.map(function (r) {
        return '<tr><td class="num">' + esc(r.room_number) + '</td>' +
          '<td>' + esc(r.floor == null ? '--' : r.floor) + '</td>' +
          '<td>' + esc(ROOM_TYPES[r.room_type] || r.room_type || '--') + '</td>' +
          '<td>' + esc(r.capacity || '--') + '</td>' +
          '<td class="num">' + esc(Number(r.base_price || 0).toFixed(2)) + '</td>' +
          '<td><span class="su-badge s-' + esc(r.status || '') + '">' +
            esc(ROOM_STATUS[r.status] || r.status || '--') + '</span></td>' +
          '<td><button class="su-x" data-del-room="' + esc(r.id) +
            '" data-num="' + esc(r.room_number) + '">حذف</button></td></tr>';
      }).join('') + '</tbody></table>';
  }

  function bulkParams() {
    var v = function (id) { var e = $(id); return e ? e.value : ''; };
    return {
      floors: parseInt(v('su-floors'), 10) || 0,
      rooms_per_floor: parseInt(v('su-per-floor'), 10) || 0,
      first_floor: parseInt(v('su-first-floor'), 10) || 1,
      start_number: parseInt(v('su-start'), 10) || 1,
      digits: parseInt(v('su-digits'), 10) || 2,
      room_type: v('su-type'),
      capacity: v('su-capacity'),
      base_price: v('su-price')
    };
  }

  /* المعاينة قبل الإنشاء: رؤية «١٠١ … ٤١٠» تكشف خطأ النمط قبل إنشاء
     أربعين غرفةً بأرقامٍ لا تُراد ثم حذفها واحدةً واحدة. */
  function previewBulk() {
    var el = $('su-preview');
    if (!el) return;
    var p = bulkParams();
    var total = p.floors * p.rooms_per_floor;
    if (p.floors < 1 || p.rooms_per_floor < 1) {
      el.textContent = 'أدخل عدد الأدوار وعدد الغرف في الدور.'; return;
    }
    if (total > 500) { el.textContent = 'الحدّ ٥٠٠ غرفة في العملية الواحدة — قلّل العدد.'; return; }
    var num = function (f, j) {
      return String(f) + String(p.start_number + j).padStart(p.digits, '0');
    };
    var names = [];
    for (var i = 0; i < p.floors; i++) {
      var f = p.first_floor + i;
      names.push(num(f, 0) + '…' + num(f, p.rooms_per_floor - 1));
    }
    el.textContent = 'ستُنشأ ' + total + ' غرفة: ' +
      names.slice(0, 4).join(' · ') + (names.length > 4 ? ' …' : '');
  }

  async function saveBulk() {
    var btn = $('su-bulk-save');
    if (btn) btn.disabled = true;
    var res = await api('/api/rooms/bulk',
      { method: 'POST', body: JSON.stringify(bulkParams()) });
    if (btn) btn.disabled = false;
    if (!res.ok) { toast(res.error, true); return; }
    var d = (res.data && res.data.data) || {};
    toast('أُنشئت ' + (d.created_count || 0) + ' غرفة' +
      (d.skipped_count ? ' · تُخطّيت ' + d.skipped_count + ' مسجَّلة مسبقاً' : ''));
    loadRooms();
  }

  async function saveOneRoom() {
    var v = function (id) { var e = $(id); return e ? e.value.trim() : ''; };
    if (!v('su-r-number')) { toast('رقم الغرفة مطلوب', true); return; }
    var res = await api('/api/rooms', { method: 'POST', body: JSON.stringify({
      room_number: v('su-r-number'), room_type: v('su-r-type'),
      floor: v('su-r-floor'), capacity: v('su-r-capacity'),
      base_price: v('su-r-price'), status: 'available'
    }) });
    if (!res.ok) { toast(res.error, true); return; }
    toast('سُجّلت الغرفة ' + v('su-r-number'));
    $('su-r-number').value = '';
    loadRooms();
  }

  async function delRoom(id, number) {
    if (!confirm('حذف الغرفة رقم ' + number + '؟')) return;
    var res = await api('/api/rooms/' + encodeURIComponent(id), { method: 'DELETE' });
    if (!res.ok) { toast(res.error, true); return; }
    toast('حُذفت الغرفة ' + number);
    loadRooms();
  }

  /* ── حسابات الموظفين ─────────────────────────────────────────────── */
  var accounts = [];

  async function loadRoles() {
    var res = await api('/api/staff/roles');
    var sel = $('su-a-role');
    if (!sel) return;
    if (!res.ok) { sel.innerHTML = '<option value="">' + esc(res.error) + '</option>'; return; }
    // الخادم يُرجع ما يحقّ لهذه الجلسة إسناده — فلا يظهر «مدير عام»
    // لمن لا يملك تعيينه، ولو ظهر لرُدّ الطلب بـ٤٠٣.
    var roles = (res.data && res.data.data && res.data.data.roles) || [];
    sel.innerHTML = roles.map(function (r) {
      return '<option value="' + esc(r.value) + '">' + esc(r.label) + '</option>';
    }).join('');
    var note = $('su-a-note');
    var showNote = function () {
      var r = roles.filter(function (x) { return x.value === sel.value; })[0];
      if (note) note.textContent = r ? r.note : '';
    };
    sel.addEventListener('change', showNote);
    showNote();
  }

  async function loadAccounts() {
    var res = await api('/api/staff/accounts');
    var tbl = $('su-staff-table');
    if (!res.ok) { if (tbl) tbl.innerHTML = '<div class="su-empty">' + esc(res.error) + '</div>'; return; }
    accounts = (res.data && res.data.data) || [];
    $('su-staff-count').textContent = accounts.length;
    if (!tbl) return;
    if (!accounts.length) {
      tbl.innerHTML = '<div class="su-empty">لا حسابات بعد — أنشئ حساب المدير العام أولاً.</div>';
      return;
    }
    tbl.innerHTML =
      '<table class="su-table"><thead><tr><th>الاسم</th><th>اسم المستخدم</th>' +
      '<th>الدور</th><th>الحالة</th><th>آخر دخول</th><th></th></tr></thead><tbody>' +
      accounts.map(function (a) {
        return '<tr><td>' + esc(a.full_name) + '</td>' +
          '<td class="num">' + esc(a.username) + '</td>' +
          '<td>' + esc(roleLabel(a.role)) + '</td>' +
          '<td><span class="su-badge ' + (a.is_active ? 's-available' : 's-blocked') + '">' +
            (a.is_active ? 'نشط' : 'موقوف') + '</span></td>' +
          '<td>' + esc(a.last_login ? String(a.last_login).slice(0, 10) : 'لم يدخل بعد') + '</td>' +
          '<td>' +
            '<button class="su-x" data-toggle-acc="' + esc(a.id) + '" data-active="' +
              (a.is_active ? '1' : '0') + '">' + (a.is_active ? 'إيقاف' : 'تفعيل') + '</button> ' +
            '<button class="su-x" data-del-acc="' + esc(a.id) + '" data-name="' +
              esc(a.username) + '">حذف</button>' +
          '</td></tr>';
      }).join('') + '</tbody></table>';
  }

  async function createAccount() {
    var v = function (id) { var e = $(id); return e ? e.value.trim() : ''; };
    var body = {
      username: v('su-a-username').toLowerCase(),
      full_name: v('su-a-name'),
      role: v('su-a-role'),
      password: $('su-a-pass') ? $('su-a-pass').value : ''
    };
    if (!body.username || !body.full_name || !body.password) {
      toast('الاسم واسم المستخدم وكلمة المرور مطلوبة', true); return;
    }
    var res = await api('/api/staff/accounts', { method: 'POST', body: JSON.stringify(body) });
    if (!res.ok) { toast(res.error, true); return; }
    // كلمة المرور لا تُخزَّن ولا تُعرض لاحقاً — تُسلَّم الآن أو تُعاد.
    var box = $('su-a-result');
    if (box) {
      box.hidden = false;
      box.innerHTML = '<strong>أُنشئ الحساب.</strong> سلّم الموظف هذه البيانات الآن — ' +
        'النظام لا يحتفظ بكلمة المرور:<br>' +
        'رقم المنشأة · اسم المستخدم <code>' + esc(body.username) + '</code> · كلمة المرور التي أدخلتها.<br>' +
        'بابه: <code>/static/dheuof/staff-login.html</code>';
    }
    ['su-a-username', 'su-a-name', 'su-a-pass'].forEach(function (id) {
      if ($(id)) $(id).value = '';
    });
    loadAccounts();
  }

  async function toggleAccount(id, isActive) {
    var res = await api('/api/staff/accounts/' + encodeURIComponent(id),
      { method: 'PATCH', body: JSON.stringify({ is_active: !isActive }) });
    if (!res.ok) { toast(res.error, true); return; }
    toast(isActive ? 'أُوقف الحساب — وجلساته القائمة أُبطلت' : 'فُعّل الحساب');
    loadAccounts();
  }

  async function delAccount(id, username) {
    if (!confirm('حذف حساب «' + username + '»؟ سجلّه في الموارد البشرية لا يُمسّ.')) return;
    var res = await api('/api/staff/accounts/' + encodeURIComponent(id), { method: 'DELETE' });
    if (!res.ok) { toast(res.error, true); return; }
    toast('حُذف الحساب');
    loadAccounts();
  }

  /* ── الربط ───────────────────────────────────────────────────────── */
  function bind() {
    ['su-floors', 'su-per-floor', 'su-first-floor', 'su-start', 'su-digits']
      .forEach(function (id) { if ($(id)) $(id).addEventListener('input', previewBulk); });

    if ($('su-bulk-save')) $('su-bulk-save').addEventListener('click', saveBulk);
    if ($('su-one-save')) $('su-one-save').addEventListener('click', saveOneRoom);
    if ($('su-a-save')) $('su-a-save').addEventListener('click', createAccount);

    // تفويضٌ على الحاوية: الصفوف تُعاد بناؤها بعد كل حفظ، فالربط
    // المباشر على الأزرار يضيع مع أول تحديث.
    document.addEventListener('click', function (ev) {
      var b = ev.target.closest && ev.target.closest('button');
      if (!b) return;
      if (b.dataset.delRoom) delRoom(b.dataset.delRoom, b.dataset.num);
      else if (b.dataset.delAcc) delAccount(b.dataset.delAcc, b.dataset.name);
      else if (b.dataset.toggleAcc) toggleAccount(b.dataset.toggleAcc, b.dataset.active === '1');
    });
  }

  async function init() {
    bind();
    previewBulk();
    await loadMe();
    if (can('rooms.read')) loadRooms();
    if (can('staff.manage')) { loadRoles(); loadAccounts(); }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.SetupModule = { loadRooms: loadRooms, loadAccounts: loadAccounts, previewBulk: previewBulk };
})();
