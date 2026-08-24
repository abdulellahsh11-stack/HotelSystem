// guests-app.js — منطق وحدة النزلاء والحجوزات
//
// مُستخرَج من index.html كما هو، بلا تفكيك: المنطق كلّه داخل غلافٍ
// واحد `(function(){…})()`، فتقسيمه إلى ملفات منفصلة يقطع كل مرجع
// بين أجزائه. تقسيمه يحتاج تحويله إلى وحدات ES باستيرادات صريحة،
// وهو تغييرٌ يستحق مراجعةً على حدة.
//
// ما فيه: التبويبات · الحجوزات · النزلاء · خريطة الغرف (من /api/rooms)
//         · حسابات الموظفين (من /api/staff/accounts)

(function(){
'use strict';

/* ═══════════════════════════════════════════════
   DATA — all dates relative to today 2026-05-30
═══════════════════════════════════════════════ */

var RESERVATIONS = [];

var GUESTS = [];

var FLOORS = [];

var STAFF = [];

var staffCounter = 7;
var alertCounter = 100;

/* ═══════════════════════════════════════════════
   ROLE → PERMISSIONS MAP
═══════════════════════════════════════════════ */
var ALL_PROGRAMS = ["01","02","03","04","05","06","07","08","09","10","11","12","13","14","15","16"];
var ROLE_PERMS = {
  manager:      ["01","02","03","04","05","06","07","08","09","10","11","12","13","14","15","16"],
  reception:    ["01","02","06","08"],
  housekeeping: ["01","04"],
  maintenance:  ["04","05"],
  accounting:   ["06","07","11"],
  custom:       [],
};
var currentRole = "reception";

/* ═══════════════════════════════════════════════
   UTILITIES
═══════════════════════════════════════════════ */
function toast(msg, isErr){
  var old = document.querySelector('.dh-toast'); if(old) old.remove();
  var t = document.createElement('div'); t.className='dh-toast';
  t.style.background = isErr ? 'var(--danger-700)' : 'var(--brand-800)';
  t.innerHTML = '<span style="color:var(--gold-400)">'+(isErr?'✕':'✓')+'</span> '+msg;
  document.body.appendChild(t);
  setTimeout(function(){ t.style.opacity='0'; t.style.transition='opacity .4s'; setTimeout(function(){ if(t.parentNode)t.remove(); },400); },3200);
}

function modal(title, html, footHtml){
  var old = document.querySelector('.dh-modal-bd'); if(old) old.remove();
  var bd = document.createElement('div'); bd.className='dh-modal-bd';
  bd.addEventListener('click',function(e){ if(e.target===bd) bd.remove(); });
  bd.innerHTML = '<div class="dh-modal" dir="rtl">'
    +'<div class="modal-head"><div class="ttl">'+title+'</div>'
    +'<button class="close-btn" onclick="document.querySelector(\'.dh-modal-bd\').remove()">✕ إغلاق</button></div>'
    +'<div class="modal-body">'+html+'</div>'
    +(footHtml?'<div class="modal-foot">'+footHtml+'</div>':'')
    +'</div>';
  document.body.appendChild(bd);
}

function todayStr(){ return new Date().toISOString().split('T')[0]; }
function tomorrowStr(){ return new Date(Date.now()+86400000).toISOString().split('T')[0]; }
function weekEndStr(){ return new Date(Date.now()+7*86400000).toISOString().split('T')[0]; }

/* ═══════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════ */
document.querySelectorAll('.tab-btn').forEach(function(btn){
  btn.addEventListener('click',function(){
    document.querySelectorAll('.tab-btn').forEach(function(b){ b.classList.remove('is-on'); });
    document.querySelectorAll('.tab-pane').forEach(function(p){ p.classList.remove('is-on'); });
    btn.classList.add('is-on');
    var pane = document.getElementById('tab-'+btn.dataset.tab);
    if(pane) pane.classList.add('is-on');
    // تُحمَّل الخريطة عند فتح تبويبها لا عند فتح الصفحة: تحميلُ ما لا
    // يُنظَر إليه يُبطئ أول عرض بلا فائدة.
    if(btn.dataset.tab === 'rooms' && !FLOORS.length) loadRoomMap();
    if(btn.dataset.tab === 'reception' && !STAFF.length) loadStaffAccountsFromServer();
  });
});

/* ═══════════════════════════════════════════════
   TAB 1 — RESERVATIONS
═══════════════════════════════════════════════ */
var activeResFilter = 'all';

function renderReservations(list){
  var tbody = document.getElementById('res-tbody');
  if(!tbody) return;
  if(!list.length){
    tbody.innerHTML='<tr><td colspan="12" style="text-align:center;padding:32px;color:var(--fg-3)">لا توجد حجوزات تطابق البحث</td></tr>';
    return;
  }
  tbody.innerHTML = list.map(function(r){
    var payPill = '<span class="pill '+r.payClass+'"><span class="d"></span>'+r.payment+'</span>';
    var vipTag = r.vip ? '<span class="vip-tag">VIP</span>' : '';
    var rid = r.id;
    return '<tr>'
      +'<td><span style="font-family:var(--font-en);font-size:12px;color:var(--fg-3)">'+rid+'</span></td>'
      +'<td><div class="guest-cell"><div class="av'+(r.vip?' vip':'')+'">'+r.initials+'</div><div>'
        +'<div class="name">'+r.name+vipTag+'</div>'
        +'<div class="meta">'+r.nationality+' · '+r.idType+'</div>'
      +'</div></div></td>'
      +'<td><span style="font-family:var(--font-mono);font-size:11px;color:var(--fg-2)">'+r.idNum+'</span></td>'
      +'<td><div style="font-weight:600">'+r.room+'</div><div style="font-size:11px;color:var(--fg-3)">'+r.roomType+'</div></td>'
      +'<td style="font-family:var(--font-mono);font-size:12px">'+r.checkin+'</td>'
      +'<td style="font-family:var(--font-mono);font-size:12px">'+r.checkout+'</td>'
      +'<td style="text-align:center"><span style="font-family:var(--font-en);font-weight:600">'+r.nights+'</span> <span style="font-size:11px;color:var(--fg-3)">ليلة</span></td>'
      +'<td><span style="font-size:12px">'+r.channel+'</span></td>'
      +'<td>'+payPill+'</td>'
      +'<td class="amt">'+r.amt+'<span class="cur">ر.س</span></td>'
      +'<td><button class="checkin-btn" id="ci-'+rid+'" onclick="doCheckin(this)">تسجيل دخول</button></td>'
      +'<td><button class="icon-btn" onclick="showResDetail('+JSON.stringify(rid)+')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg></button></td>'
      +'</tr>';
  }).join('');
}

function filterAndRenderRes(){
  var q = ((document.getElementById('res-search')||{}).value||'').toLowerCase();
  var today = todayStr(), tomorrow = tomorrowStr(), weekEnd = weekEndStr();
  var filtered = RESERVATIONS.filter(function(r){
    var mQ = !q || r.name.toLowerCase().includes(q) || r.id.includes(q) || r.room.includes(q) || r.idNum.toLowerCase().includes(q);
    var mF = activeResFilter==='all'
      || (activeResFilter==='today'    && r.checkin===today)
      || (activeResFilter==='tomorrow' && r.checkin===tomorrow)
      || (activeResFilter==='week'     && r.checkin>=today && r.checkin<=weekEnd);
    return mQ && mF;
  });
  renderReservations(filtered);
}

document.querySelectorAll('[data-filter]').forEach(function(btn){
  btn.addEventListener('click',function(){
    document.querySelectorAll('[data-filter]').forEach(function(b){ b.classList.remove('is-on'); });
    btn.classList.add('is-on');
    activeResFilter = btn.dataset.filter;
    filterAndRenderRes();
  });
});
var resSearch = document.getElementById('res-search');
if(resSearch) resSearch.addEventListener('input', filterAndRenderRes);

window.doCheckin = function(btn){
  if(btn.disabled) return;
  btn.disabled = true; btn.textContent = '✓ مسجَّل';
  toast('تم تسجيل الدخول ✓');
};

window.showResDetail = function(rid){
  var r = RESERVATIONS.find(function(x){ return x.id===rid; });
  if(!r) return;
  var html = [
    {l:'اسم النزيل',v:r.name+(r.vip?' <span class="vip-tag">VIP</span>':'')},
    {l:'رقم الهوية',v:'<span style="font-family:var(--font-mono)">'+r.idNum+'</span>'},
    {l:'نوع الهوية',v:r.idType},
    {l:'الجنسية',v:r.nationality},
    {l:'الجوال',v:'<span style="direction:ltr;font-family:var(--font-mono)">'+r.phone+'</span>'},
    {l:'الغرفة',v:r.room+' — '+r.roomType},
    {l:'تاريخ الوصول',v:'<span style="font-family:var(--font-mono)">'+r.checkin+'</span>'},
    {l:'تاريخ المغادرة',v:'<span style="font-family:var(--font-mono)">'+r.checkout+'</span>'},
    {l:'عدد الليالي',v:r.nights+' ليالٍ'},
    {l:'القناة',v:r.channel},
    {l:'المبلغ',v:r.amt+' ر.س'},
    {l:'حالة الدفع',v:r.payment},
    {l:'نقاط الولاء',v:'<span style="color:var(--gold-500);font-weight:700;font-family:var(--font-en)">★ 1,240</span> نقطة · مستوى ذهبي'},
  ].map(function(row){ return '<div class="detail-row"><span class="lbl">'+row.l+'</span><span class="val">'+row.v+'</span></div>'; }).join('');
  modal('تفاصيل الحجز — '+rid, html,
    '<button class="btn-primary" onclick="var b=document.getElementById(\'ci-'+rid+'\');if(b)doCheckin(b);document.querySelector(\'.dh-modal-bd\').remove()">تسجيل دخول الآن</button>'
    +'<button class="close-btn" onclick="document.querySelector(\'.dh-modal-bd\').remove()">إغلاق</button>'
  );
};

/* ═══════════════════════════════════════════════
   TAB 2 — GUESTS
═══════════════════════════════════════════════ */
var activeGuestFilter = 'all';

function renderGuestAlerts(gid, alerts){
  return '<div class="alert-list" id="alr-'+gid+'">'
    + alerts.map(function(a){
        return '<span class="alert-tag '+a.color+'" onclick="removeAlert('+JSON.stringify(gid)+','+a.id+')">'
          +a.text+' <span class="x">✕</span></span>';
      }).join('')
    +'<button class="add-alert-btn" onclick="showAddAlert('+JSON.stringify(gid)+')">+ تنبيه</button>'
    +'</div>';
}

function renderGuests(list){
  var tbody = document.getElementById('guest-tbody');
  if(!tbody) return;
  if(!list.length){
    tbody.innerHTML='<tr><td colspan="9" style="text-align:center;padding:32px;color:var(--fg-3)">لا يوجد نزلاء يطابقون البحث</td></tr>';
    return;
  }
  var statusMap = {
    ok:        '<span class="pill info"><span class="d"></span>مقيم</span>',
    departing: '<span class="pill warn"><span class="d"></span>مغادر اليوم</span>',
  };
  tbody.innerHTML = list.map(function(g){
    var vipTag = g.vip ? '<span class="vip-tag">VIP</span>' : '';
    var balance = g.balanceLeft==='٠'
      ? '<span style="color:var(--success-700);font-weight:600">مسدَّد</span>'
      : '<span class="amt">'+g.balanceLeft+'<span class="cur">ر.س</span></span>';
    var checkoutBtn = g.status==='departing'
      ? '<button class="icon-btn" style="color:var(--warning-700)" onclick="doCheckout('+JSON.stringify(g.id)+')" title="تسجيل خروج">'
        +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg></button>'
      : '';
    return '<tr>'
      +'<td><div class="guest-cell"><div class="av'+(g.vip?' vip':'')+'">'+g.initials+'</div><div>'
        +'<div class="name">'+g.name+vipTag+'</div>'
        +'<div class="meta">'+g.nationality+'</div>'
      +'</div></div></td>'
      +'<td><div style="font-weight:600">'+g.room+'</div><div style="font-size:11px;color:var(--fg-3)">'+g.roomType+'</div></td>'
      +'<td style="font-family:var(--font-mono);font-size:12px">'+g.checkin+'</td>'
      +'<td style="font-family:var(--font-mono);font-size:12px">'+g.checkout+'</td>'
      +'<td style="direction:ltr;font-family:var(--font-mono);font-size:12px;color:var(--fg-2)">'+g.phone+'</td>'
      +'<td>'+balance+'</td>'
      +'<td>'+renderGuestAlerts(g.id, g.alerts)+'</td>'
      +'<td>'+statusMap[g.status]+'</td>'
      +'<td>'
        +'<button class="icon-btn" onclick="showGuestDetail('+JSON.stringify(g.id)+')" title="تفاصيل">'
          +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>'
        +'</button>'
        +checkoutBtn
      +'</td>'
      +'</tr>';
  }).join('');
}

function filterAndRenderGuests(){
  var q = ((document.getElementById('guest-search')||{}).value||'').toLowerCase();
  var filtered = GUESTS.filter(function(g){
    var mQ = !q || g.name.toLowerCase().includes(q) || g.room.includes(q);
    var mF = activeGuestFilter==='all'
      || (activeGuestFilter==='vip'      && g.vip)
      || (activeGuestFilter==='departing'&& g.status==='departing')
      || (activeGuestFilter==='alert'    && g.alerts.length>0);
    return mQ && mF;
  });
  renderGuests(filtered);
}

document.querySelectorAll('[data-gfilter]').forEach(function(btn){
  btn.addEventListener('click',function(){
    document.querySelectorAll('[data-gfilter]').forEach(function(b){ b.classList.remove('is-on'); });
    btn.classList.add('is-on');
    activeGuestFilter = btn.dataset.gfilter;
    filterAndRenderGuests();
  });
});
var guestSearch = document.getElementById('guest-search');
if(guestSearch) guestSearch.addEventListener('input', filterAndRenderGuests);

window.removeAlert = function(gid, aid){
  var g = GUESTS.find(function(x){ return x.id===gid; });
  if(!g) return;
  g.alerts = g.alerts.filter(function(a){ return a.id!==aid; });
  var wrap = document.getElementById('alr-'+gid);
  if(wrap) wrap.outerHTML = renderGuestAlerts(gid, g.alerts);
  updateBadges();
};

window.showAddAlert = function(gid){
  var g = GUESTS.find(function(x){ return x.id===gid; });
  if(!g) return;
  var colors = [
    {key:'red',  bg:'#fef2f2', label:'طارئ'},
    {key:'amber',bg:'#fffbeb', label:'تنبيه'},
    {key:'blue', bg:'#eff6ff', label:'معلومة'},
    {key:'gold', bg:'#fefce8', label:'طلب'},
    {key:'green',bg:'#f0fdf4', label:'إيجابي'},
  ];
  window._alertColor = 'amber';
  var html = '<div class="alert-form">'
    +'<div><label>نص التنبيه</label>'
    +'<input id="alert-txt" placeholder="مثال: يطلب فطور الساعة ٨، حساسية من..."/></div>'
    +'<div><label>اللون</label><div class="color-opts">'
    +colors.map(function(c,i){
      return '<div class="color-opt'+(i===1?' is-on':'')+'" style="background:'+c.bg+'" title="'+c.label+'" onclick="selectAlertColor(this,\''+c.key+'\')"></div>';
    }).join('')
    +'</div></div></div>';
  modal('إضافة تنبيه — '+g.name, html,
    '<button class="btn-primary" onclick="saveAlert('+JSON.stringify(gid)+')">حفظ</button>'
    +'<button class="close-btn" onclick="document.querySelector(\'.dh-modal-bd\').remove()">إلغاء</button>'
  );
};

window.selectAlertColor = function(el, key){
  document.querySelectorAll('.color-opt').forEach(function(c){ c.classList.remove('is-on'); });
  el.classList.add('is-on');
  window._alertColor = key;
};

window.saveAlert = function(gid){
  var inp = document.getElementById('alert-txt');
  var txt = inp ? inp.value.trim() : '';
  if(!txt){ toast('أدخل نص التنبيه',true); return; }
  var g = GUESTS.find(function(x){ return x.id===gid; });
  if(!g) return;
  alertCounter++;
  g.alerts.push({text:txt, color:window._alertColor||'amber', id:alertCounter});
  var bd = document.querySelector('.dh-modal-bd'); if(bd) bd.remove();
  filterAndRenderGuests();
  updateBadges();
  toast('تم إضافة التنبيه ✓');
};

window.doCheckout = function(gid){
  var g = GUESTS.find(function(x){ return x.id===gid; });
  if(!g) return;
  if(!confirm('تسجيل خروج '+g.name+' من غرفة '+g.room+'؟')) return;
  var roomNum = g.room;
  FLOORS.forEach(function(fl){
    fl.rooms.forEach(function(rm){
      if(rm.num===roomNum && rm.status==='occupied'){
        rm.status='hk-needed'; rm.guest=null;
      }
    });
  });
  GUESTS = GUESTS.filter(function(x){ return x.id!==gid; });
  filterAndRenderGuests();
  renderFloors();
  updateBadges();
  toast('تم تسجيل خروج '+g.name+' — غرفة '+roomNum+' بانتظار التنظيف ✓');
};

window.showGuestDetail = function(gid){
  var g = GUESTS.find(function(x){ return x.id===gid; });
  if(!g) return;
  var html = [
    {l:'الاسم',    v:g.name+(g.vip?' <span class="vip-tag">VIP</span>':'')},
    {l:'الغرفة',   v:g.room+' — '+g.roomType},
    {l:'الوصول',   v:'<span style="font-family:var(--font-mono)">'+g.checkin+'</span>'},
    {l:'المغادرة', v:'<span style="font-family:var(--font-mono)">'+g.checkout+'</span>'},
    {l:'الجوال',   v:'<span style="direction:ltr;font-family:var(--font-mono)">'+g.phone+'</span>'},
    {l:'المبلغ المتبقي',v:g.balanceLeft+' ر.س'},
    {l:'التنبيهات', v:g.alerts.length ? g.alerts.map(function(a){return a.text;}).join(' · ') : 'لا يوجد'},
    {l:'نقاط الولاء',v:'<span style="color:var(--gold-500);font-weight:700;font-family:var(--font-en)">★ 1,240</span> نقطة · مستوى ذهبي'},
  ].map(function(row){ return '<div class="detail-row"><span class="lbl">'+row.l+'</span><span class="val">'+row.v+'</span></div>'; }).join('');
  modal('ملف النزيل — '+g.name, html);
};

/* ═══════════════════════════════════════════════
   تحميل خريطة الغرف من سجلّ الغرف الحقيقي

   كانت FLOORS مصفوفةً فارغة لا يملؤها شيء، فالخريطة تُرسم خاويةً مهما
   سجّل المشترك من غرف. وسجلّ الغرف (/api/rooms) كان يعيش في اللوحة
   الرئيسية وحدها — تطبيقان لا يريان بعضهما.

   الأدوار تُشتق من حقل floor في كل غرفة: لا يُطلب عددها من المستخدم
   لأن رقم الدور مُسجَّل مع كل غرفة أصلاً، وطلبُه مرتين يفتح باب
   التناقض بينهما.
═══════════════════════════════════════════════ */
var ROOM_STATUS_MAP = {
  available:'available', occupied:'occupied', dirty:'hk-needed',
  maintenance:'maintenance', blocked:'out-of-order'
};

function floorLabel(n){
  if(n === 0) return 'الدور الأرضي';
  if(n === -1) return 'القبو';
  return 'الدور ' + n;
}

function buildFloorsFromRooms(rooms){
  var byFloor = {};
  rooms.forEach(function(r){
    var f = (r.floor === null || r.floor === undefined) ? 0 : Number(r.floor);
    (byFloor[f] = byFloor[f] || []).push({
      num: r.room_number,
      type: r.room_type || '—',
      status: ROOM_STATUS_MAP[r.status] || 'available',
      guest: null,
      checkin: null,
      id: r.id
    });
  });
  return Object.keys(byFloor)
    .map(Number)
    .sort(function(a, b){ return a - b; })
    .map(function(f){
      return {
        num: f,
        label: floorLabel(f),
        rooms: byFloor[f].sort(function(a, b){
          return String(a.num).localeCompare(String(b.num), 'ar', {numeric:true});
        })
      };
    });
}

function loadRoomMap(){
  var c = document.getElementById('floors-container');
  if(c && !FLOORS.length){
    c.innerHTML = '<div class="mod-empty" style="padding:24px;text-align:center">⏳ جارٍ تحميل خريطة الغرف…</div>';
  }
  return fetch('/api/rooms')
    .then(function(r){ return r.json(); })
    .then(function(res){
      var rooms = (res && res.data) || [];
      FLOORS = buildFloorsFromRooms(rooms);
      // كل دور مفتوح افتراضياً — الخريطة تُقرأ دفعةً واحدة عادةً
      floorOpen = FLOORS.map(function(){ return true; });
      if(!FLOORS.length && c){
        c.innerHTML = '<div class="mod-empty" style="padding:24px;text-align:center">'
          + 'لا غرف مسجَّلة بعد — سجّلها من «حالة الغرف» في لوحة التحكم</div>';
        return;
      }
      renderFloors();
      updateBadges();
    })
    .catch(function(){
      if(c) c.innerHTML = '<div class="mod-empty" style="padding:24px;text-align:center;color:#b91c1c">'
        + 'تعذّر تحميل خريطة الغرف</div>';
    });
}

/* ═══════════════════════════════════════════════
   TAB 3 — ROOMS
═══════════════════════════════════════════════ */
var floorOpen = [];   // يُبنى من عدد الأدوار الفعلي عند التحميل

function statusLabel(s){
  return {occupied:'مشغولة',available:'متاحة','hk-needed':'يحتاج تنظيف',maintenance:'صيانة',reserved:'محجوزة','out-of-order':'خارج الخدمة',cleaning:'تنظيف جارٍ'}[s]||s;
}

function renderFloors(){
  var c = document.getElementById('floors-container');
  if(!c) return;
  c.innerHTML='';
  FLOORS.forEach(function(fl,fi){
    var occ  = fl.rooms.filter(function(r){return r.status==='occupied';}).length;
    var avl  = fl.rooms.filter(function(r){return r.status==='available';}).length;
    var hk   = fl.rooms.filter(function(r){return r.status==='hk-needed';}).length;
    var mnt  = fl.rooms.filter(function(r){return r.status==='maintenance';}).length;
    var sec  = document.createElement('div'); sec.className='floor-section';
    var head = '<div class="floor-head" onclick="toggleFloor('+fi+')">'
      +'<span class="floor-num">'+fl.num+'</span>'
      +'<span class="floor-name">'+fl.label+'</span>'
      +'<div class="floor-stats">'
      +(occ  ?'<span class="floor-stat occ">'+occ+' مشغولة</span>':'')
      +(avl  ?'<span class="floor-stat avail">'+avl+' متاحة</span>':'')
      +(hk   ?'<span class="floor-stat hk">'+hk+' تنظيف</span>':'')
      +(mnt  ?'<span class="floor-stat maint">'+mnt+' صيانة</span>':'')
      +'</div>'
      +'<span class="floor-toggle'+(floorOpen[fi]?' open':'')+'">▼</span>'
      +'</div>';
    var grid = '<div class="rooms-grid" id="fg-'+fi+'" style="'+(floorOpen[fi]?'':'display:none')+'">'
      +fl.rooms.map(function(rm,ri){
        var hint = rm.guest
          ? '<div class="guest-hint">'+rm.guest+'</div>'
          : (rm.checkin?'<div class="guest-hint">وصول '+rm.checkin+'</div>':'');
        return '<div class="room-card '+rm.status+'" onclick="showRoomDetail('+fi+','+ri+')" title="غرفة '+rm.num+'">'
          +'<div class="rnum">'+rm.num+'</div>'
          +'<div class="rtype">'+rm.type+'</div>'
          +'<div class="rstatus">'+statusLabel(rm.status)+'</div>'
          +hint
          +'</div>';
      }).join('')
      +'</div>';
    sec.innerHTML = head + grid;
    c.appendChild(sec);
  });
}

window.toggleFloor = function(fi){
  floorOpen[fi] = !floorOpen[fi];
  var grid = document.getElementById('fg-'+fi);
  var tog  = document.querySelector('.floor-section:nth-child('+(fi+1)+') .floor-toggle');
  if(grid) grid.style.display = floorOpen[fi] ? '' : 'none';
  if(tog)  tog.classList.toggle('open', floorOpen[fi]);
};

window.showRoomDetail = function(fi,ri){
  var rm = FLOORS[fi].rooms[ri];
  var fl = FLOORS[fi];
  var sc = {occupied:'info',available:'ok','hk-needed':'warn',maintenance:'danger',reserved:'gold'};
  var html = [
    {l:'رقم الغرفة', v:'<span style="font-family:var(--font-en);font-size:18px;font-weight:700">'+rm.num+'</span>'},
    {l:'نوع الغرفة', v:rm.type},
    {l:'الدور',      v:fl.label},
    {l:'الحالة',     v:'<span class="pill '+sc[rm.status]+'"><span class="d"></span>'+statusLabel(rm.status)+'</span>'},
  ].map(function(row){ return '<div class="detail-row"><span class="lbl">'+row.l+'</span><span class="val">'+row.v+'</span></div>'; });
  if(rm.guest)    html.push('<div class="detail-row"><span class="lbl">النزيل</span><span class="val">'+rm.guest+'</span></div>');
  if(rm.checkout) html.push('<div class="detail-row"><span class="lbl">تاريخ المغادرة</span><span class="val" style="font-family:var(--font-mono)">'+rm.checkout+'</span></div>');
  if(rm.checkin)  html.push('<div class="detail-row"><span class="lbl">تاريخ الوصول</span><span class="val" style="font-family:var(--font-mono)">'+rm.checkin+'</span></div>');

  var statusOptions = [
    {val:'available',    label:'✅ متاحة ونظيفة'},
    {val:'hk-needed',   label:'🧹 تحتاج تنظيف'},
    {val:'cleaning',    label:'🫧 تنظيف جارٍ'},
    {val:'maintenance', label:'🔧 صيانة'},
    {val:'out-of-order',label:'⛔ خارج الخدمة'},
    {val:'occupied',    label:'🛏 مشغولة'},
    {val:'reserved',    label:'📅 محجوزة'}
  ];
  var act = '<select id="rm-status-sel" style="flex:1;padding:7px 12px;border:1px solid var(--ink-100);border-radius:6px;font-family:var(--font-ar);font-size:13px">'
    +statusOptions.map(function(s){ return '<option value="'+s.val+'"'+(rm.status===s.val?' selected':'')+'>'+s.label+'</option>'; }).join('')
    +'</select>'
    +'<button class="btn-primary" onclick="changeRoomStatus('+fi+','+ri+')">✓ تغيير الحالة</button>'
    +'<button class="close-btn" onclick="document.querySelector(\'.dh-modal-bd\').remove()">إغلاق</button>';

  modal('غرفة '+rm.num+' — '+statusLabel(rm.status), html.join(''), act);
};

window.markRoomClean = function(fi,ri){
  var num = FLOORS[fi].rooms[ri].num;
  FLOORS[fi].rooms[ri].status = 'available';
  FLOORS[fi].rooms[ri].guest  = null;
  var bd = document.querySelector('.dh-modal-bd'); if(bd) bd.remove();
  renderFloors(); updateBadges();
  toast('غرفة '+num+' — تم التحويل إلى متاحة ✓');
};

window.markRoomMaint = function(fi,ri){
  var num = FLOORS[fi].rooms[ri].num;
  FLOORS[fi].rooms[ri].status = 'maintenance';
  var bd = document.querySelector('.dh-modal-bd'); if(bd) bd.remove();
  renderFloors(); updateBadges();
  toast('غرفة '+num+' — تم التحويل إلى صيانة');
};

window.changeRoomStatus = function(fi,ri){
  var sel = document.getElementById('rm-status-sel');
  if(!sel) return;
  var newStatus = sel.value;
  var num = FLOORS[fi].rooms[ri].num;
  FLOORS[fi].rooms[ri].status = newStatus;
  if(newStatus==='available'||newStatus==='out-of-order') FLOORS[fi].rooms[ri].guest = null;
  var bd = document.querySelector('.dh-modal-bd'); if(bd) bd.remove();
  renderFloors(); updateBadges();
  toast('غرفة '+num+' — '+statusLabel(newStatus)+' ✓');
};

/* ═══════════════════════════════════════════════
   TAB 4 — RECEPTION / STAFF ACCOUNTS
═══════════════════════════════════════════════ */
function renderPermGrid(){
  var grid = document.getElementById('perm-grid');
  if(!grid) return;
  var rolePerms = ROLE_PERMS[currentRole] || [];
  grid.innerHTML = ALL_PROGRAMS.map(function(p){
    var on = rolePerms.indexOf(p)!==-1;
    return '<label class="perm-item'+(on?' is-on':'')+'" onclick="togglePerm(this,\''+p+'\')">'
      +'<input type="checkbox"'+(on?' checked':'')+'/> '
      +'<span>'+p+'</span>'
      +'</label>';
  }).join('');
}

window.selectRole = function(el){
  document.querySelectorAll('.role-card').forEach(function(c){ c.classList.remove('is-on'); });
  el.classList.add('is-on');
  currentRole = el.dataset.role;
  if(currentRole !== 'custom') ROLE_PERMS.custom = ROLE_PERMS[currentRole].slice();
  renderPermGrid();
};

window.togglePerm = function(label, prog){
  var idx = ROLE_PERMS.custom.indexOf(prog);
  if(idx===-1) ROLE_PERMS.custom.push(prog);
  else ROLE_PERMS.custom.splice(idx,1);
  label.classList.toggle('is-on');
  var cb = label.querySelector('input');
  if(cb) cb.checked = !cb.checked;
};

function getActivePerms(){
  if(currentRole==='custom') return ROLE_PERMS.custom.slice();
  return (ROLE_PERMS[currentRole]||[]).slice();
}

/* ═══════════════════════════════════════════════
   حسابات الموظفين — من الخادم لا من مصفوفة محلية

   كان التبويب يُنشئ الحسابات في `STAFF` داخل الصفحة فقط: تختفي عند
   أول تحديث، ولا يستطيع صاحبها الدخول، ولا تراها شاشة الحسابات في
   لوحة التحكم. واجهتان لنفس الشيء، إحداهما بلا خادم.

   المصدر الآن `/api/staff/accounts` — نفسه الذي تستعمله اللوحة.
═══════════════════════════════════════════════ */

// أدوار الواجهة القديمة ← أدوار الخادم. الاسم وحده لا يكفي: «الصيانة»
// لا مقابل لها في الخادم، فتُسنَد لأقرب دور وظيفي بدل أن تُرفض.
var ROLE_TO_SERVER = {
  manager:'manager', reception:'receptionist', housekeeping:'housekeeping',
  maintenance:'housekeeping', accounting:'accountant', custom:'receptionist'
};
var SERVER_ROLE_AR = {
  gm:'مدير عام', manager:'مدير مناوبة', receptionist:'موظف استقبال',
  housekeeping:'إشراف داخلي', accountant:'محاسب', pos_cashier:'كاشير'
};

function staffInitials(name){
  return String(name||'').trim().split(' ').slice(0,2)
    .map(function(w){ return w[0] || ''; }).join('');
}

function loadStaffAccountsFromServer(){
  return fetch('/api/staff/accounts')
    .then(function(r){ return r.json(); })
    .then(function(res){
      var rows = (res && res.data) || [];
      STAFF = rows.map(function(a){
        return {
          id: a.id,
          initials: staffInitials(a.full_name),
          name: a.full_name,
          email: a.username,
          role: SERVER_ROLE_AR[a.role] || a.role,
          roleKey: a.role === 'receptionist' ? 'reception' : a.role,
          dept: SERVER_ROLE_AR[a.role] || a.role,
          shift: '—',
          active: !!a.is_active,
          lastLogin: a.last_login ? String(a.last_login).slice(0, 16) : '—',
          perms: []
        };
      });
      renderStaff();
      updateBadges();
    })
    .catch(function(){
      var tbody = document.getElementById('staff-tbody');
      if(tbody) tbody.innerHTML =
        '<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--danger-600)">'
        + 'تعذّر تحميل الحسابات</td></tr>';
    });
}

var roleLabels = {
  manager:'المدير', reception:'الاستقبال', housekeeping:'التدبير',
  maintenance:'الصيانة', accounting:'المحاسبة', custom:'مخصص'
};

window.createStaffAccount = function(){
  var name = (document.getElementById('nw-name')||{}).value||'';
  var username = (document.getElementById('nw-username')||{}).value||'';
  var password = (document.getElementById('nw-password')||{}).value||'';
  if(!name.trim()){ toast('أدخل اسم الموظف',true); return; }
  if(!username.trim()){ toast('أدخل اسم المستخدم',true); return; }
  if(password.length < 8){ toast('كلمة المرور ٨ محارف فأكثر',true); return; }

  fetch('/api/staff/accounts', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      full_name: name.trim(),
      username: username.trim(),
      password: password,
      role: ROLE_TO_SERVER[currentRole] || 'receptionist'
    })
  })
  .then(function(r){ return r.json().then(function(b){ return {ok:r.ok, body:b}; }); })
  .then(function(res){
    if(!res.ok){
      // رسالة الخادم تُعرض كما هي: «اسم المستخدم مستخدم» أوضح من
      // «فشل الإنشاء».
      toast((res.body && (res.body.detail || res.body.error)) || 'تعذّر إنشاء الحساب', true);
      return;
    }
    ['nw-name','nw-email','nw-phone','nw-username','nw-password'].forEach(function(id){
      var el = document.getElementById(id); if(el) el.value = '';
    });
    toast('أُنشئ حساب '+name+' — سلّم كلمة المرور للموظف الآن ✓');
    loadStaffAccountsFromServer();
  })
  .catch(function(){ toast('تعذّر الاتصال بالخادم', true); });
};


function renderStaff(){
  var tbody = document.getElementById('staff-tbody');
  if(!tbody) return;
  var countLbl = document.getElementById('staff-count-lbl');
  if(countLbl) countLbl.textContent = STAFF.length+' حسابات';
  tbody.innerHTML = STAFF.map(function(s){
    var chips = s.perms.map(function(p){
      return '<span class="perm-chip">'+p+'</span>';
    }).join('');
    var dotCls = s.active ? 'active' : 'inactive';
    var statusTxt = s.active ? 'نشط' : 'معطَّل';
    var avClass = s.roleKey==='manager' ? 'av mgr' : 'av';
    return '<tr>'
      +'<td><div class="guest-cell"><div class="'+avClass+'">'+s.initials+'</div><div>'
        +'<div class="name">'+s.name+'</div>'
        +'<div class="meta">'+s.email+'</div>'
      +'</div></div></td>'
      +'<td><span class="role-tag '+s.roleKey+'">'+s.role+'</span></td>'
      +'<td><div class="perm-chips">'+chips+'</div></td>'
      +'<td style="font-size:12px;color:var(--fg-2)">'+s.shift+'</td>'
      +'<td><span style="font-size:12px"><span class="status-dot '+dotCls+'"></span>'+statusTxt+'</span></td>'
      +'<td style="font-size:12px;color:var(--fg-3)">'+s.lastLogin+'</td>'
      +'<td style="display:flex;gap:4px">'
        +'<button class="btn-sec" style="font-size:11px;padding:4px 10px" onclick="editStaff('+s.id+')">تعديل</button>'
        +(s.active
          ?'<button class="btn-sec" style="font-size:11px;padding:4px 10px;color:var(--danger-600)" onclick="toggleActive('+s.id+')">تعطيل</button>'
          :'<button class="btn-primary" style="font-size:11px;padding:4px 10px" onclick="toggleActive('+s.id+')">تفعيل</button>'
        )
      +'</td>'
      +'</tr>';
  }).join('');
}

window.editStaff = function(sid){
  var s = STAFF.find(function(x){ return x.id===sid; });
  if(!s) return;
  var roleOpts = [
    {k:'reception',l:'🛎 استقبال'},
    {k:'housekeeping',l:'🧹 تدبير'},
    {k:'maintenance',l:'🔧 صيانة'},
    {k:'accounting',l:'💼 محاسبة'},
    {k:'manager',l:'👑 مدير'},
  ];
  var html = '<div class="alert-form">'
    +'<div><label>الاسم</label><input id="ed-name" value="'+s.name+'"/></div>'
    +'<div><label>البريد</label><input id="ed-email" dir="ltr" value="'+s.email+'"/></div>'
    +'<div><label>الدور</label><select id="ed-role">'
    +roleOpts.map(function(r){
      return '<option value="'+r.k+'"'+(s.roleKey===r.k?' selected':'')+'>'+r.l+'</option>';
    }).join('')
    +'</select></div>'
    +'</div>';
  modal('تعديل — '+s.name, html,
    '<button class="btn-primary" onclick="saveEditStaff('+sid+')">حفظ التعديلات</button>'
    +'<button class="close-btn" onclick="document.querySelector(\'.dh-modal-bd\').remove()">إلغاء</button>'
  );
};

window.saveEditStaff = function(sid){
  var s = STAFF.find(function(x){ return x.id===sid; });
  if(!s) return;
  var nm  = (document.getElementById('ed-name')||{}).value||'';
  var em  = (document.getElementById('ed-email')||{}).value||'';
  var rk  = (document.getElementById('ed-role')||{}).value||s.roleKey;
  if(nm.trim()) s.name  = nm.trim();
  if(em.trim()) s.email = em.trim();
  s.roleKey = rk;
  s.role    = roleLabels[rk]||rk;
  s.perms   = (ROLE_PERMS[rk]||[]).slice();
  var bd = document.querySelector('.dh-modal-bd'); if(bd) bd.remove();
  renderStaff();
  toast('تم حفظ تعديلات '+s.name+' ✓');
};

window.toggleActive = function(sid){
  var s = STAFF.find(function(x){ return x.id===sid; });
  if(!s) return;
  fetch('/api/staff/accounts/'+sid, {
    method:'PATCH',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ is_active: !s.active })
  })
  .then(function(r){ return r.json().then(function(b){ return {ok:r.ok, body:b}; }); })
  .then(function(res){
    if(!res.ok){
      toast((res.body && (res.body.detail || res.body.error)) || 'تعذّر التعديل', true);
      return;
    }
    // الإيقاف يقطع جلسة الموظف فوراً على الخادم
    toast(s.active ? 'أُوقف الحساب وقُطعت جلسته' : 'أُعيد تفعيل الحساب');
    loadStaffAccountsFromServer();
  })
  .catch(function(){ toast('تعذّر الاتصال بالخادم', true); });
};


/* ═══════════════════════════════════════════════
   BADGES & KPIs
═══════════════════════════════════════════════ */
function updateBadges(){
  var hkCount = 0;
  FLOORS.forEach(function(fl){ fl.rooms.forEach(function(rm){ if(rm.status==='hk-needed') hkCount++; }); });
  var totalRooms = 0;
  var occCount   = 0;
  FLOORS.forEach(function(fl){
    fl.rooms.forEach(function(rm){
      totalRooms++;
      if(rm.status==='occupied') occCount++;
    });
  });
  var occPct = totalRooms>0 ? Math.round(occCount/totalRooms*100) : 0;

  function set(id,v){ var el=document.getElementById(id); if(el) el.textContent=v; }
  set('kpi-occ', occPct);
  set('kpi-inhouse',   GUESTS.length);
  set('kpi-upcoming',  RESERVATIONS.length);
  set('kpi-hk',        hkCount);
  set('kpi-inhouse-delta', GUESTS.filter(function(g){return g.status==='departing';}).length+' مغادر اليوم');
  set('kpi-upcoming-delta', RESERVATIONS.filter(function(r){return r.payment==='لم يدفع';}).length+' لم يدفع بعد');

  var hkD = document.getElementById('kpi-hk-delta');
  if(hkD){ hkD.textContent = hkCount>0 ? 'تحتاج تنظيف' : 'جميع الغرف نظيفة ✓'; hkD.style.color=hkCount>0?'var(--warning-700)':'var(--success-700)'; }

  set('res-badge',    RESERVATIONS.length);
  set('guests-badge', GUESTS.length);
  set('rooms-badge',  hkCount+' HK');
  set('staff-badge',  STAFF.filter(function(s){return s.active;}).length);
}

/* ═══════════════════════════════════════════════
   API — LOAD GUESTS (GET /api/guests)
═══════════════════════════════════════════════ */
function loadGuests(){
  var tbody = document.getElementById('guest-tbody');
  if(tbody) tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:32px;color:var(--fg-3)">⏳ جارٍ تحميل النزلاء...</td></tr>';
  fetch('/api/guests')
    .then(function(r){ return r.json(); })
    .then(function(res){
      if(!res.success){ throw new Error(res.detail||'خطأ'); }
      var raw = res.data || [];
      GUESTS = raw.map(function(g){
        var nm = g.full_name||g.name||'—';
        var parts = nm.trim().split(/\s+/);
        var initials = parts.slice(0,2).map(function(w){ return w[0]||''; }).join('');
        return {
          id:        g.id,
          name:      nm,
          initials:  initials,
          nationality: g.nationality||'—',
          room:      g.room_number||g.room||'—',
          roomType:  g.room_type||'—',
          checkin:   g.check_in||g.checkin||'—',
          checkout:  g.check_out||g.checkout||'—',
          phone:     g.phone||g.mobile||'—',
          balanceLeft: g.balance_due!=null ? String(g.balance_due) : '٠',
          vip:       !!(g.vip||g.is_vip),
          status:    g.status==='departing'||g.checkout_today ? 'departing' : 'ok',
          alerts:    g.alerts||[],
          bookingId: g.booking_id||g.id,
        };
      });
      filterAndRenderGuests();
      updateBadges();
    })
    .catch(function(err){
      var tbody2 = document.getElementById('guest-tbody');
      if(tbody2) tbody2.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:32px;color:var(--danger-600)">⚠ تعذّر تحميل النزلاء — '+err.message+'</td></tr>';
    });
}

/* ═══════════════════════════════════════════════
   API — LOAD ARRIVALS (GET /api/m02/arrivals)
═══════════════════════════════════════════════ */
function loadArrivals(){
  var tbody = document.getElementById('res-tbody');
  if(tbody) tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;padding:32px;color:var(--fg-3)">⏳ جارٍ تحميل الحجوزات...</td></tr>';
  fetch('/api/m02/arrivals')
    .then(function(r){ return r.json(); })
    .then(function(res){
      if(!res.success){ throw new Error(res.detail||'خطأ'); }
      var raw = res.data || [];
      RESERVATIONS = raw.map(function(b){
        var nm = b.full_name||b.name||'—';
        var parts = nm.trim().split(/\s+/);
        var initials = parts.slice(0,2).map(function(w){ return w[0]||''; }).join('');
        var cin  = (b.check_in||'').split('T')[0];
        var cout = (b.check_out||'').split('T')[0];
        var nights = 0;
        if(cin && cout){ var d1=new Date(cin),d2=new Date(cout); nights=Math.max(0,Math.round((d2-d1)/86400000)); }
        var payMap = {paid:'ok', deposit:'warn', unpaid:'danger', confirmed:'info'};
        var payLbl = {paid:'مدفوع', deposit:'عربون', unpaid:'لم يدفع', confirmed:'مؤكّد'};
        var ps = b.payment_status||b.payment||'confirmed';
        return {
          id:          b.id||b.booking_id||('RES-'+Date.now()),
          name:        nm,
          initials:    initials,
          nationality: b.nationality||'—',
          idNum:       b.id_number||'—',
          idType:      b.id_type||'هوية',
          room:        b.room_number||b.room||'—',
          roomType:    b.room_type||'—',
          checkin:     cin,
          checkout:    cout,
          nights:      nights,
          channel:     b.channel||b.booking_source||'مباشر',
          payment:     payLbl[ps]||ps,
          payClass:    payMap[ps]||'neu',
          amt:         b.total_amount!=null ? String(b.total_amount) : '—',
          vip:         !!(b.vip||b.is_vip),
          phone:       b.phone||b.mobile||'—',
        };
      });
      filterAndRenderRes();
      updateBadges();
    })
    .catch(function(err){
      var tbody2 = document.getElementById('res-tbody');
      if(tbody2) tbody2.innerHTML = '<tr><td colspan="12" style="text-align:center;padding:32px;color:var(--danger-600)">⚠ تعذّر تحميل الحجوزات — '+err.message+'</td></tr>';
    });
}

/* ═══════════════════════════════════════════════
   API — LOAD DEPARTURES (GET /api/m02/departures)
═══════════════════════════════════════════════ */
function loadDepartures(){
  fetch('/api/m02/departures')
    .then(function(r){ return r.json(); })
    .then(function(res){
      if(!res.success){ throw new Error(res.detail||'خطأ'); }
      var raw = res.data || [];
      // Merge today's departures into GUESTS (mark status=departing)
      raw.forEach(function(b){
        var nm = b.full_name||b.name||'—';
        var bid = b.id||b.booking_id;
        var existing = GUESTS.find(function(g){ return g.bookingId===bid||g.id===bid; });
        if(existing){
          existing.status = 'departing';
        } else {
          var parts = nm.trim().split(/\s+/);
          var initials = parts.slice(0,2).map(function(w){ return w[0]||''; }).join('');
          GUESTS.push({
            id:        bid,
            name:      nm,
            initials:  initials,
            nationality: b.nationality||'—',
            room:      b.room_number||b.room||'—',
            roomType:  b.room_type||'—',
            checkin:   (b.check_in||'').split('T')[0],
            checkout:  (b.check_out||'').split('T')[0],
            phone:     b.phone||b.mobile||'—',
            balanceLeft: b.balance_due!=null ? String(b.balance_due) : '٠',
            vip:       !!(b.vip||b.is_vip),
            status:    'departing',
            alerts:    [],
            bookingId: bid,
          });
        }
      });
      filterAndRenderGuests();
      updateBadges();
    })
    .catch(function(err){
      // Non-blocking — departures panel relies on guests already loaded
      console.warn('loadDepartures:', err.message);
    });
}

/* ═══════════════════════════════════════════════
   API — WIRE CHECKIN (POST /api/integration/checkin)
   Cascade: room→occupied, revenue, inventory, KPI
═══════════════════════════════════════════════ */
function cascadeSummary(res){
  var parts = [];
  if(res.room_status || res.room) parts.push('الغرفة: '+(res.room_status||res.room));
  if(res.revenue!=null) parts.push('إيراد: '+(DH.formatSAR ? DH.formatSAR(res.revenue) : res.revenue));
  var inv = res.inventory_deducted||res.inventory;
  if(inv!=null){
    if(typeof inv==='number') parts.push('خصم مخزون: '+inv+' صنف');
    else if(Array.isArray(inv)) parts.push('خصم مخزون: '+inv.length+' صنف');
  }
  return parts.join(' · ');
}
window.doCheckin = function(btn){
  if(btn.disabled) return;
  // Find booking id from row  (id stored in button id="ci-<bookingId>")
  var bid = btn.id.replace('ci-','');
  var r = RESERVATIONS.find(function(x){ return String(x.id)===String(bid); }) || {};
  var amount = parseFloat(r.amt)||0;
  btn.disabled = true;
  btn.textContent = '⏳ جارٍ...';
  DH.fetch('/api/integration/checkin', {
    method:'POST',
    body: JSON.stringify({ booking_id: bid, amount: amount, payment_method:'cash', checkin_by:'استقبال' })
  }).then(function(res){
    if(res){
      btn.textContent = '✓ مسجَّل';
      var sum = cascadeSummary(res);
      toast('تم تسجيل الدخول ✓'+(sum?' — '+sum:''));
    } else {
      btn.disabled = false;
      btn.textContent = 'تسجيل دخول';
      toast('فشل تسجيل الدخول', true);
    }
  });
};

/* ═══════════════════════════════════════════════
   API — WIRE CHECKOUT (POST /api/integration/checkout)
   Cascade: room→cleaning, revenue, KPI
═══════════════════════════════════════════════ */
window.doCheckout = function(gid){
  var g = GUESTS.find(function(x){ return x.id===gid; });
  if(!g) return;
  if(!confirm('تسجيل خروج '+g.name+' من غرفة '+g.room+'؟')) return;
  var bid = g.bookingId||gid;
  DH.fetch('/api/integration/checkout', {
    method:'POST',
    body: JSON.stringify({ booking_id: bid, final_amount: parseFloat(g.balanceLeft)||0, payment_method:'cash' })
  }).then(function(res){
    if(res){
      FLOORS.forEach(function(fl){
        fl.rooms.forEach(function(rm){
          if(rm.num===g.room && rm.status==='occupied'){
            rm.status='hk-needed'; rm.guest=null;
          }
        });
      });
      GUESTS = GUESTS.filter(function(x){ return x.id!==gid; });
      filterAndRenderGuests();
      renderFloors();
      updateBadges();
      var sum = cascadeSummary(res);
      toast('تم تسجيل خروج '+g.name+' — غرفة '+g.room+' بانتظار التنظيف ✓'+(sum?' — '+sum:''));
    } else {
      toast('فشل تسجيل الخروج', true);
    }
  });
};

/* ═══════════════════════════════════════════════
   INIT
═══════════════════════════════════════════════ */
loadArrivals();
loadGuests();
loadDepartures();
renderFloors();
renderPermGrid();
renderStaff();
updateBadges();

/* ═══════════════════════════════════════════════
   EXPORT — Excel + PDF
═══════════════════════════════════════════════ */
function todayStr(){var d=new Date();return d.getFullYear()+(d.getMonth()+1<10?'0':'')+(d.getMonth()+1)+(d.getDate()<10?'0':'')+d.getDate();}
function toXLS(headers,rows,name){
  var s='<Styles>'
    +'<Style ss:ID="H"><Font ss:Bold="1" ss:Color="#FFFFFF"/><Interior ss:Color="#1B4D3D" ss:Pattern="Solid"/><Alignment ss:Horizontal="Center"/></Style>'
    +'<Style ss:ID="BAD"><Interior ss:Color="#C0392B" ss:Pattern="Solid"/><Font ss:Color="#FFFFFF" ss:Bold="1"/></Style>'
    +'<Style ss:ID="WARN"><Interior ss:Color="#D97706" ss:Pattern="Solid"/><Font ss:Color="#FFFFFF" ss:Bold="1"/></Style>'
    +'<Style ss:ID="OK"><Interior ss:Color="#BBF7D0" ss:Pattern="Solid"/><Font ss:Color="#1B7A56" ss:Bold="1"/></Style>'
    +'<Style ss:ID="EXC"><Interior ss:Color="#1B7A56" ss:Pattern="Solid"/><Font ss:Color="#FFFFFF" ss:Bold="1"/></Style>'
    +'</Styles>';
  function esc(v){return String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
  function cell(v){if(v&&typeof v==='object'&&'s' in v)return '<Cell ss:StyleID="'+v.s+'"><Data ss:Type="String">'+esc(v.v)+'</Data></Cell>';return '<Cell><Data ss:Type="'+(typeof v==='number'?'Number':'String')+'">'+esc(v)+'</Data></Cell>';}
  var hRow='<Row>'+headers.map(function(h){return '<Cell ss:StyleID="H"><Data ss:Type="String">'+esc(h)+'</Data></Cell>';}).join('')+'</Row>';
  var dRows=rows.map(function(r){return '<Row>'+r.map(cell).join('')+'</Row>';}).join('');
  return '<?xml version="1.0" encoding="UTF-8"?><?mso-application progid="Excel.Sheet"?><Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'+s+'<Worksheet ss:Name="'+esc(name)+'"><Table>'+hRow+dRows+'</Table></Worksheet></Workbook>';
}
function dlXLS(c,fn){var b=new Blob([c],{type:'application/vnd.ms-excel;charset=utf-8'});var u=URL.createObjectURL(b);var a=document.createElement('a');a.href=u;a.download=fn;a.click();setTimeout(function(){URL.revokeObjectURL(u);},1000);}

window.exportReservations = function(){
  var payMap = {
    'مدفوع':   {v:'مدفوع',  s:'EXC'},
    'عربون':   {v:'عربون',  s:'WARN'},
    'لم يدفع': {v:'لم يدفع',s:'BAD'}
  };
  var headers = ['رقم الحجز','الضيف','الجنسية','الغرفة','النوع','الوصول','المغادرة','الليالي','القناة','الدفع','المبلغ (ر.س)'];
  var rows = RESERVATIONS.map(function(r){
    return [r.id, r.name, r.nationality.replace(/[^؀-ۿ\s\w]/g,'').trim(), r.room, r.roomType,
      r.checkin, r.checkout, r.nights, r.channel,
      payMap[r.payment]||{v:r.payment,s:'OK'}, r.amt];
  });
  var paid=RESERVATIONS.filter(function(r){return r.payment==='مدفوع';}).length;
  var dep =RESERVATIONS.filter(function(r){return r.payment==='عربون';}).length;
  var unpd=RESERVATIONS.filter(function(r){return r.payment==='لم يدفع';}).length;
  var t=rows.length; function _p(n){return t>0?Math.round(n/t*100):0;}
  rows.push([]);
  rows.push([{v:'📊 ملخص الإحصائيات — الدفع',s:'EXC'},{v:'العدد',s:'EXC'},{v:'النسبة %',s:'EXC'},'','','','','','','','']);
  rows.push([{v:'⭐ مدفوع بالكامل',s:'EXC'},{v:paid,s:'EXC'},{v:_p(paid)+'%',s:'EXC'}]);
  rows.push([{v:'🟠 عربون مدفوع',s:'WARN'},{v:dep,s:'WARN'},{v:_p(dep)+'%',s:'WARN'}]);
  rows.push([{v:'🔴 لم يدفع',s:'BAD'},{v:unpd,s:'BAD'},{v:_p(unpd)+'%',s:'BAD'}]);
  dlXLS(toXLS(headers,rows,'الحجوزات'),'الحجوزات_'+todayStr()+'.xls');
  toast('تم تصدير '+RESERVATIONS.length+' حجز ✓');
};

window.exportPDF = function(){
  var paid    = RESERVATIONS.filter(function(r){return r.payment==='مدفوع';}).length;
  var deposit = RESERVATIONS.filter(function(r){return r.payment==='عربون';}).length;
  var unpaid  = RESERVATIONS.filter(function(r){return r.payment==='لم يدفع';}).length;
  var inhouse = GUESTS.length;
  var departing = GUESTS.filter(function(g){return g.status==='departing';}).length;
  var totRes = RESERVATIONS.length;
  function _pPct(n){return totRes>0?Math.round(n/totRes*100):0;}

  var statsHtml = '<div style="background:linear-gradient(135deg,#f0f7f4,#f8faf9);border:1px solid #c6ddd7;border-radius:12px;padding:18px 20px;margin-bottom:20px">'
    +'<div style="font-size:14px;font-weight:700;color:var(--brand-700);margin-bottom:14px">📊 ملخص الإحصائيات · إجمالي الحجوزات: '+totRes+'</div>'
    +'<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px">'
    +'<div style="flex:1;min-width:80px;text-align:center;background:#f0f0f0;border-radius:8px;padding:12px 8px"><div style="font-size:26px;font-weight:700;color:#333">'+totRes+'</div><div style="font-size:10px;color:#666;margin-top:4px">الحجوزات</div></div>'
    +'<div style="flex:1;min-width:80px;text-align:center;background:#D1FAE5;border-radius:8px;padding:12px 8px"><div style="font-size:26px;font-weight:700;color:#1B7A56">'+paid+'</div><div style="font-size:13px;font-weight:700;color:#1B7A56">'+_pPct(paid)+'%</div><div style="font-size:10px;color:rgba(0,0,0,0.5)">مدفوع ✓</div></div>'
    +'<div style="flex:1;min-width:80px;text-align:center;background:#FEF3C7;border-radius:8px;padding:12px 8px"><div style="font-size:26px;font-weight:700;color:var(--warning-700)">'+deposit+'</div><div style="font-size:13px;font-weight:700;color:var(--warning-700)">'+_pPct(deposit)+'%</div><div style="font-size:10px;color:rgba(0,0,0,0.5)">عربون</div></div>'
    +'<div style="flex:1;min-width:80px;text-align:center;background:#FEE2E2;border-radius:8px;padding:12px 8px"><div style="font-size:26px;font-weight:700;color:#C0392B">'+unpaid+'</div><div style="font-size:13px;font-weight:700;color:#C0392B">'+_pPct(unpaid)+'%</div><div style="font-size:10px;color:rgba(0,0,0,0.5)">لم يدفع</div></div>'
    +'<div style="flex:1;min-width:80px;text-align:center;background:#DBEAFE;border-radius:8px;padding:12px 8px"><div style="font-size:26px;font-weight:700;color:#1d4ed8">'+inhouse+'</div><div style="font-size:10px;color:rgba(0,0,0,0.5);margin-top:4px">نزلاء حاليون</div></div>'
    +(departing?'<div style="flex:1;min-width:80px;text-align:center;background:#FEE2E2;border-radius:8px;padding:12px 8px"><div style="font-size:26px;font-weight:700;color:#C0392B">'+departing+'</div><div style="font-size:10px;color:rgba(0,0,0,0.5);margin-top:4px">مغادر اليوم</div></div>':'')
    +'</div>'
    +'<div style="background:#e8eceb;border-radius:6px;height:12px;overflow:hidden;display:flex">'
    +(paid>0?'<div style="width:'+_pPct(paid)+'%;background:#1B7A56;height:100%"></div>':'')
    +(deposit>0?'<div style="width:'+_pPct(deposit)+'%;background:var(--warning-700);height:100%"></div>':'')
    +(unpaid>0?'<div style="width:'+_pPct(unpaid)+'%;background:#C0392B;height:100%"></div>':'')
    +'</div>'
    +'<div style="margin-top:8px;font-size:10px;color:#666;display:flex;gap:14px;flex-wrap:wrap">'
    +'<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#1B7A56;margin-left:3px"></span>مدفوع '+_pPct(paid)+'%</span>'
    +'<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:var(--warning-700);margin-left:3px"></span>عربون '+_pPct(deposit)+'%</span>'
    +'<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#C0392B;margin-left:3px"></span>لم يدفع '+_pPct(unpaid)+'%</span>'
    +'</div>'
    +'</div>';

  var resRows = RESERVATIONS.map(function(r){
    var payStyle = r.payment==='مدفوع'?'color:#1B7A56;font-weight:700':r.payment==='عربون'?'color:var(--warning-700);font-weight:700':'color:#C0392B;font-weight:700';
    var vip = r.vip?'<span style="background:#FEF3C7;color:#b45309;padding:2px 6px;border-radius:4px;font-size:10px">VIP</span>':'';
    return '<tr><td><strong>'+r.id+'</strong></td><td>'+r.name+' '+vip+'</td><td>'+r.room+'</td>'
      +'<td>'+r.checkin+'</td><td>'+r.checkout+' ('+r.nights+' ل)</td>'
      +'<td>'+r.channel+'</td>'
      +'<td style="'+payStyle+'">'+r.payment+'</td>'
      +'<td style="font-weight:600">'+r.amt+' ر.س</td></tr>';
  }).join('');

  var guestRows = GUESTS.map(function(g){
    var depStyle = g.status==='departing'?'color:#C0392B;font-weight:700':'color:#1B7A56';
    var depLabel = g.status==='departing'?'⚠ مغادر اليوم':'✓ مقيم';
    var vip = g.vip?'<span style="background:#FEF3C7;color:#b45309;padding:2px 6px;border-radius:4px;font-size:10px">VIP</span>':'';
    return '<tr><td>'+g.name+' '+vip+'</td><td>'+g.room+' ('+g.roomType+')</td>'
      +'<td>'+g.checkin+'</td><td>'+g.checkout+'</td>'
      +'<td style="font-weight:600;color:var(--warning-700)">'+g.balanceLeft+' ر.س</td>'
      +'<td style="'+depStyle+'">'+depLabel+'</td></tr>';
  }).join('');

  var win=window.open('','_blank','width=1020,height=760');
  win.document.write('<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"/><title>تقرير الضيوف</title>'
    +'<style>body{font-family:"Tajawal","Segoe UI",sans-serif;margin:32px;color:#1a1a1a;direction:rtl}'
    +'h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:24px 0 10px;color:var(--brand-700)}'
    +'.sub{font-size:12px;color:#666;margin:0 0 18px}'
    +'table{width:100%;border-collapse:collapse;font-size:12px;margin-bottom:24px}'
    +'th{background:var(--brand-700);color:var(--white);padding:9px 10px;text-align:right}'
    +'td{padding:8px 10px;border-bottom:1px solid #eee;vertical-align:middle}'
    +'tr:nth-child(even){background:#fafafa}'
    +'.footer{margin-top:18px;font-size:11px;color:#999}@media print{.no-print{display:none}}'
    +'</style></head><body>'
    +'<h1>🏨 تقرير لوحة الضيوف</h1>'
    +'<p class="sub">'+new Date().toLocaleDateString('ar-SA')+' · الحجوزات والنزلاء الحاليون</p>'
    +statsHtml
    +'<h2>الحجوزات القادمة ('+RESERVATIONS.length+')</h2>'
    +'<table><thead><tr><th>رقم الحجز</th><th>الضيف</th><th>الغرفة</th><th>الوصول</th><th>المغادرة</th><th>القناة</th><th>الدفع</th><th>المبلغ</th></tr></thead>'
    +'<tbody>'+resRows+'</tbody></table>'
    +'<h2>النزلاء الحاليون ('+inhouse+')</h2>'
    +'<table><thead><tr><th>الاسم</th><th>الغرفة</th><th>الوصول</th><th>المغادرة</th><th>الرصيد المتبقي</th><th>الحالة</th></tr></thead>'
    +'<tbody>'+guestRows+'</tbody></table>'
    +'<div class="footer">نظام ضيوف · لوحة الضيوف · '+new Date().toLocaleString('ar-SA')+'</div>'
    +'</body></html>');
  win.document.close();
  setTimeout(function(){win.print();},700);
};

/* ═══════════════════════════════════════════════
   FEATURE A — GROUP BOOKING
═══════════════════════════════════════════════ */
window.openGroupBooking = function(){
  var today = new Date();
  var tomorrow = new Date(today); tomorrow.setDate(today.getDate()+1);
  var fmt = function(d){ return d.toISOString().split('T')[0]; };
  document.getElementById('gb-in').value = fmt(today);
  document.getElementById('gb-out').value = fmt(tomorrow);
  document.getElementById('group-booking-modal').style.display='flex';
  updateGroupSummary();
};
window.closeGroupBooking = function(){ document.getElementById('group-booking-modal').style.display='none'; };
window.updateGroupSummary = function(){
  var n = parseInt(document.getElementById('gb-rooms').value||0,10);
  var rate = parseFloat(document.getElementById('gb-rate').value||0);
  var inD = document.getElementById('gb-in').value;
  var outD = document.getElementById('gb-out').value;
  var name = document.getElementById('gb-name').value||'—';
  var nights = 0;
  if(inD && outD){ var d1=new Date(inD),d2=new Date(outD); nights=Math.max(0,Math.round((d2-d1)/86400000)); }
  var total = n * rate * nights;
  var el = document.getElementById('gb-summary-text');
  if(!n||!nights){ el.textContent='أدخل التفاصيل لعرض الملخص'; return; }
  el.innerHTML = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">'
    +'<div>المجموعة: <strong>'+name+'</strong></div>'
    +'<div>الغرف: <strong>'+n+' غرفة</strong></div>'
    +'<div>الليالي: <strong>'+nights+' ليلة</strong></div>'
    +'<div>سعر الليلة: <strong>'+rate.toLocaleString('ar-SA')+' ر.س</strong></div>'
    +'<div style="grid-column:1/-1;border-top:1px solid var(--brand-200);padding-top:8px;margin-top:4px">الإجمالي: <strong style="color:var(--brand-700);font-size:15px">'+total.toLocaleString('ar-SA')+' ر.س</strong></div>'
    +'</div>';
};
window.confirmGroupBooking = function(){
  var name = document.getElementById('gb-name').value||'مجموعة';
  var n = document.getElementById('gb-rooms').value;
  closeGroupBooking();
  var t = document.createElement('div');
  t.style.cssText='position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--brand-700);color:var(--paper);padding:12px 24px;border-radius:10px;font-family:var(--font-ar);font-size:13px;font-weight:600;z-index:9999;box-shadow:0 4px 16px rgba(0,0,0,.25)';
  t.textContent='✓ تم تأكيد الحجز الجماعي لـ'+name+' ('+n+' غرف)';
  document.body.appendChild(t);
  setTimeout(function(){ t.remove(); }, 3500);
};

/* ═══════════════════════════════════════════════
   FEATURE B — WAITLIST
═══════════════════════════════════════════════ */
window.addToWaitlist = function(){
  var name = prompt('اسم العميل:');
  if(!name) return;
  var type = prompt('نوع الغرفة (ستاندرد/ديلوكس/جناح):') || 'ستاندرد';
  var tbody = document.getElementById('waitlist-tbody');
  var tr = document.createElement('tr');
  tr.innerHTML = '<td style="padding:10px 12px;border-bottom:1px solid var(--hairline)">'+name+'</td>'
    +'<td style="padding:10px 12px;text-align:center;border-bottom:1px solid var(--hairline)">'+type+'</td>'
    +'<td style="padding:10px 12px;text-align:center;border-bottom:1px solid var(--hairline);font-family:var(--font-mono)">'+new Date().toISOString().split("T")[0]+'</td>'
    +'<td style="padding:10px 12px;text-align:center;border-bottom:1px solid var(--hairline)">—</td>'
    +'<td style="padding:10px 12px;text-align:center;border-bottom:1px solid var(--hairline)"><span style="background:#FEF3C7;color:#92400E;padding:2px 8px;border-radius:4px;font-size:11px">في الانتظار</span></td>'
    +'<td style="padding:10px 8px;text-align:center;border-bottom:1px solid var(--hairline)"><button onclick="notifyWaitlist(this)" style="padding:4px 10px;background:var(--brand-700);color:var(--paper);border:none;border-radius:4px;font-family:var(--font-ar);font-size:11px;cursor:pointer">إبلاغ</button></td>';
  tbody.appendChild(tr);
};
window.notifyWaitlist = function(btn){
  btn.textContent='✓ أُبلغ';
  btn.style.background='var(--success-600)';
  btn.disabled=true;
};

/* ═══════════════════════════════════════════════
   FEATURE C — RATE PLANS
═══════════════════════════════════════════════ */
window.addRatePlan = function(){
  var name = prompt('اسم الخطة:');
  if(!name) return;
  var rate = prompt('السعر بالريال/ليلة:') || '500';
  var grid = document.getElementById('rate-plans-grid');
  var div = document.createElement('div');
  div.style.cssText='border:1.5px solid var(--hairline);border-radius:10px;padding:14px';
  div.innerHTML='<div style="font-size:12px;font-weight:700;color:var(--ink-900);margin-bottom:6px">'+name+'</div>'
    +'<div style="font-size:20px;font-weight:700;color:var(--ink-900);font-family:var(--font-en)">'+rate+' <span style="font-size:11px;color:var(--fg-3)">ر.س/ليلة</span></div>'
    +'<div style="margin-top:8px"><span style="background:#F3F4F6;color:var(--ink-400);font-size:10px;padding:2px 7px;border-radius:4px">جديد</span></div>';
  grid.appendChild(div);
};

})();
