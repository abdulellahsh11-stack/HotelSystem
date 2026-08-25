// guests-staff-extras.js — حسابات الموظفين والتصدير والميزات الإضافية
//
// مُستخرَج من guests-app.js ليبقى كل ملف ضمن حدٍّ يُقرأ.
// يُحمَّل **بعده** لأنه يقرأ window.GuestsShared الذي يُصدّره ذاك.
//
// ما فيه: تبويب الاستقبال · حسابات الموظفين (من /api/staff/accounts)
//         · تصدير Excel و PDF · الحجز الجماعي · قائمة الانتظار
//         · خطط الأسعار

(function(){
'use strict';

var S = window.GuestsShared || {};
var toast = S.toast, modal = S.modal, updateBadges = S.updateBadges;
var ROLE_PERMS = S.ROLE_PERMS, ALL_PROGRAMS = S.ALL_PROGRAMS;

// الحالة المشتركة تُقرأ من الجسر عند كل استعمال لا تُنسخ مرة واحدة:
// النسخة تتجمّد على قيمتها ساعةَ التحميل بينما الأصل يتغيّر.
Object.defineProperty(window, 'STAFF', {
  get: function(){ return S.STAFF; },
  set: function(v){ S.STAFF = v; },
  configurable: true
});
Object.defineProperty(window, 'GUESTS', {
  get: function(){ return S.GUESTS; }, configurable: true
});
Object.defineProperty(window, 'RESERVATIONS', {
  get: function(){ return S.RESERVATIONS; }, configurable: true
});
var currentRole = S.currentRole;

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


// يُسجّل ما يناديه الملف الأول. التسجيل في الآخر لا الأول: الدوال
// مُعرَّفة بحلول هذه النقطة قطعاً.
window.GuestsExtras = {
  renderPermGrid: typeof renderPermGrid === 'function' ? renderPermGrid : null,
  renderStaff: typeof renderStaff === 'function' ? renderStaff : null,
  loadStaffAccountsFromServer:
    typeof loadStaffAccountsFromServer === 'function' ? loadStaffAccountsFromServer : null
};

})();
