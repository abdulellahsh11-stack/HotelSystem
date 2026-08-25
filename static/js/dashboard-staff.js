// dashboard-staff.js — حسابات دخول الموظفين وأدوارها، وتطبيق الموظفين
// مُستخرَج من dashboard.html. الترتيب في الصفحة مقصود:
// core أولاً لأن بقية الملفات تستعمل apiSend و esc منه.

// ======== حسابات الموظفين ========
async function loadStaffAccounts(){
  // قبل الجدول: أسماء الأدوار العربية تأتي من هنا، وتحميلها بعده يعرض
  // المفاتيح الإنجليزية في أول رسم.
  await loadRolesHelp();
  const res = await apiSend('/api/staff/accounts');
  const el = document.getElementById('staffTable');
  if(!el) return;
  if(!res.ok){ el.innerHTML = empty(res.error); return; }
  const rows = (res.data && res.data.data) || [];
  if(!rows.length){ el.innerHTML = empty('لا حسابات بعد — أنشئ حساباً لكل موظف يستخدم النظام'); }
  else{
    el.innerHTML = '<table class="mod-table"><thead><tr><th>الاسم</th><th>اسم المستخدم</th><th>الدور</th><th>الحالة</th><th>آخر دخول</th><th>إجراءات</th></tr></thead><tbody>' +
      rows.map(a =>
        '<tr><td>'+esc(a.full_name)+'</td><td dir="ltr">'+esc(a.username)+'</td>'+
        '<td>'+esc(STAFF_ROLE_AR[a.role]||a.role)+'</td>'+
        '<td>'+(a.is_active?'<span class="good">مُفعَّل</span>':'<span class="bad">مُوقَف</span>')+'</td>'+
        '<td>'+(a.last_login? esc(String(a.last_login).slice(0,16)) : '—')+'</td>'+
        '<td><button class="nz-btn is-secondary" onclick="toggleStaff('+a.id+','+(a.is_active?'false':'true')+')">'+(a.is_active?'إيقاف':'تفعيل')+'</button> '+
        '<button class="nz-btn is-secondary" onclick="resetStaffPassword('+a.id+')">كلمة مرور</button> '+
        '<button class="nz-btn is-secondary" onclick="deleteStaff('+a.id+',\''+esc(a.username)+'\')">حذف</button></td></tr>'
      ).join('') + '</tbody></table>';
  }
}

let STAFF_ROLE_AR = {};
async function loadRolesHelp(){
  const res = await apiSend('/api/staff/roles');
  if(!res.ok) return;
  const roles = (res.data && res.data.data && res.data.data.roles) || [];
  const perms = (res.data && res.data.data && res.data.data.permissions) || {};
  roles.forEach(r => { STAFF_ROLE_AR[r.value] = r.label; });

  const sel = document.getElementById('staffRole');
  if(sel && !sel.options.length){
    sel.innerHTML = roles.map(r => '<option value="'+esc(r.value)+'">'+esc(r.label)+'</option>').join('');
    sel.onchange = () => {
      const r = roles.find(x => x.value === sel.value);
      document.getElementById('staffRoleNote').textContent = r ? r.note : '';
    };
    if(roles.length) sel.onchange();
  }

  const help = document.getElementById('rolesHelp');
  if(help){
    help.innerHTML = '<table class="mod-table"><thead><tr><th>الدور</th><th>ماذا يستطيع</th></tr></thead><tbody>' +
      roles.map(r =>
        '<tr><td><strong>'+esc(r.label)+'</strong><div class="mod-empty" style="text-align:right;padding:0">'+esc(r.note)+'</div></td>'+
        '<td>'+(r.permissions[0]==='*' ? 'كل الصلاحيات' : r.permissions.map(pk => esc(perms[pk]||pk)).join(' · '))+'</td></tr>'
      ).join('') + '</tbody></table>';
  }
}

function openStaffModal(){
  showFormError('staffError','');
  ['staffFullName','staffUsername','staffPassword'].forEach(id => document.getElementById(id).value='');
  loadRolesHelp();
  openModal('modal-staff');
}

async function createStaffAccount(){
  showFormError('staffError','');
  const body = {
    full_name: document.getElementById('staffFullName').value.trim(),
    username:  document.getElementById('staffUsername').value.trim(),
    role:      document.getElementById('staffRole').value,
    password:  document.getElementById('staffPassword').value
  };
  const res = await apiSend('/api/staff/accounts', {method:'POST', body:JSON.stringify(body)});
  if(!res.ok){ showFormError('staffError', res.error); return; }
  closeModal('modal-staff');
  alert('أُنشئ الحساب.\n\nاسم المستخدم: '+body.username+'\nكلمة المرور: '+body.password+
        '\n\nسلّمها للموظف الآن — النظام لا يعرضها مرة أخرى.');
  loadStaffAccounts();
}

async function toggleStaff(id, activate){
  const res = await apiSend('/api/staff/accounts/'+id, {method:'PATCH', body:JSON.stringify({is_active:activate})});
  if(!res.ok){ showToast(res.error,'error'); return; }
  loadStaffAccounts();
}

async function resetStaffPassword(id){
  const pw = prompt('كلمة المرور الجديدة (٨ محارف فأكثر):');
  if(!pw) return;
  const res = await apiSend('/api/staff/accounts/'+id+'/reset-password', {method:'POST', body:JSON.stringify({password:pw})});
  if(!res.ok){ showToast(res.error,'error'); return; }
  showToast('تم. سلّم كلمة المرور الجديدة للموظف.','success');
  loadStaffAccounts();
}

async function deleteStaff(id, username){
  if(!confirm('حذف حساب «'+username+'»؟ سجلّه في الموارد البشرية لا يُمسّ.')) return;
  const res = await apiSend('/api/staff/accounts/'+id, {method:'DELETE'});
  if(!res.ok){ showToast(res.error,'error'); return; }
  loadStaffAccounts();
}

// يُخفي ما لا صلاحية له، فلا يرى الموظف أزراراً تُرفض عند الضغط
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
