// dashboard-staff.js — عرض حسابات الموظفين، وتطبيق الموظفين
//
// الإنشاء والإيقاف والحذف وإعادة كلمة المرور انتقلت إلى
// `modules/00-setup`. ما بقي هنا **عرضٌ فقط**: نموذجان لنفس العمل
// يتباعدان، فيُصلَح أحدهما ويبقى الآخر ولا يعرف المستخدم أيّهما الصحيح.
// core أولاً لأن هذا الملف يستعمل apiSend و esc منه.

// ======== حسابات الموظفين — عرض ========
let STAFF_ROLE_AR = {};

async function loadStaffAccounts(){
  // قبل الجدول: أسماء الأدوار العربية تأتي من هنا، وتحميلها بعده يعرض
  // المفاتيح الإنجليزية في أول رسم.
  await loadRolesHelp();
  const res = await apiSend('/api/staff/accounts');
  const el = document.getElementById('staffTable');
  if(!el) return;
  if(!res.ok){ el.innerHTML = empty(res.error); return; }
  const rows = (res.data && res.data.data) || [];
  if(!rows.length){
    el.innerHTML = empty('لا حسابات بعد — أنشئ حساباً لكل موظف من «إعداد المنشأة»');
    return;
  }
  el.innerHTML = '<table class="mod-table"><thead><tr><th>الاسم</th><th>اسم المستخدم</th><th>الدور</th><th>الحالة</th><th>آخر دخول</th></tr></thead><tbody>' +
    rows.map(a =>
      '<tr><td>'+esc(a.full_name)+'</td><td dir="ltr">'+esc(a.username)+'</td>'+
      '<td>'+esc(STAFF_ROLE_AR[a.role]||a.role)+'</td>'+
      '<td>'+(a.is_active?'<span class="good">مُفعَّل</span>':'<span class="bad">مُوقَف</span>')+'</td>'+
      '<td>'+(a.last_login? esc(String(a.last_login).slice(0,16)) : '—')+'</td></tr>'
    ).join('') + '</tbody></table>';
}

async function loadRolesHelp(){
  const res = await apiSend('/api/staff/roles');
  if(!res.ok) return;
  const roles = (res.data && res.data.data && res.data.data.roles) || [];
  const perms = (res.data && res.data.data && res.data.data.permissions) || {};
  roles.forEach(r => { STAFF_ROLE_AR[r.value] = r.label; });

  const help = document.getElementById('rolesHelp');
  if(!help) return;
  help.innerHTML = '<table class="mod-table"><thead><tr><th>الدور</th><th>ماذا يستطيع</th></tr></thead><tbody>' +
    roles.map(r =>
      '<tr><td><strong>'+esc(r.label)+'</strong><div class="mod-empty" style="text-align:right;padding:0">'+esc(r.note)+'</div></td>'+
      '<td>'+(r.permissions[0]==='*' ? 'كل الصلاحيات' : r.permissions.map(pk => esc(perms[pk]||pk)).join(' · '))+'</td></tr>'
    ).join('') + '</tbody></table>';
}

async function applySessionPermissions(){
  const res = await apiSend('/api/staff/me');
  if(!res.ok) return;
  const me = res.data && res.data.data;
  if(!me) return;
  const nav = document.getElementById('navOwnerOnly');
  const canManage = me.is_owner || (me.permissions||[]).indexOf('staff.manage') >= 0;
  if(nav && !canManage) nav.style.display='none';
}


// ======== M15 تطبيق الموظفين ========
async function loadStaffApp(){
  const hk = await apiSend('/api/m07/tasks');
  const mt = await apiSend('/api/m08/orders');
  const tasks  = (hk.ok && hk.data && (hk.data.data || hk.data)) || [];
  const orders = (mt.ok && mt.data && (mt.data.data || mt.data)) || [];
  const list = Array.isArray(tasks) ? tasks : [];
  const ords = Array.isArray(orders) ? orders : [];
  const set = (id,v) => { const e=document.getElementById(id); if(e) e.textContent=v; };
  set('staffHKPending', list.filter(t => t.status==='pending').length);
  set('staffHKDone',    list.filter(t => t.status==='done' || t.status==='completed').length);
  set('staffMaintOpen', ords.filter(o => o.status==='open').length);
  set('staffUrgent',    ords.filter(o => o.priority==='urgent' || o.priority==='high').length);
  const el = document.getElementById('staffHKTable');
  if(!el) return;
  el.innerHTML = list.length
    ? '<table class="mod-table"><thead><tr><th>الغرفة</th><th>المهمة</th><th>الموظف</th><th>الحالة</th></tr></thead><tbody>' +
      list.map(t => '<tr><td>'+esc(t.room_number||t.room||'--')+'</td><td>'+esc(t.task_type||t.title||'--')+'</td>'+
        '<td>'+esc(t.assigned_to||'--')+'</td><td>'+statusBadge(t.status)+'</td></tr>').join('') +
      '</tbody></table>'
    : empty('لا مهام اليوم');
}
