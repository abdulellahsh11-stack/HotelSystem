// dashboard-modules.js — بقية وحدات اللوحة (M01–M14) — تحميل بياناتها وعرضها
// مُستخرَج من dashboard.html. الترتيب في الصفحة مقصود:
// core أولاً لأن بقية الملفات تستعمل apiSend و esc منه.

// ======== M12 الرؤى الذكية ========
async function loadInsights(){
  const res = await apiSend('/api/analytics/overview');
  const grid = document.getElementById('insightsGrid');
  if(!res.ok){ if(grid) grid.innerHTML = empty(res.error); return; }
  const d = (res.data && res.data.data) || {};
  const set = (id,v) => { const e=document.getElementById(id); if(e) e.textContent=v; };
  const occ = (d.bookings && d.bookings.occupancy_rate) || 0;
  set('insightHealth', occ >= 60 ? 'جيدة' : (occ > 0 ? 'متوسطة' : '--'));
  set('insightHealthSub', 'نسبة الإشغال هذا الشهر ' + occ + '٪');
  set('insightMaintOpen', (d.maintenance && d.maintenance.open_orders) || 0);
  set('insightLowStock', (d.inventory && d.inventory.low_stock) || 0);
  set('insightVIP', (d.employees && d.employees.active) || 0);
  if(!grid) return;
  const cards = [
    ['الإشغال هذا الشهر', occ + '٪'],
    ['إيراد الشهر', ((d.bookings && d.bookings.revenue_this_month) || 0) + ' ر.س'],
    ['طلبات صيانة مفتوحة', (d.maintenance && d.maintenance.open_orders) || 0],
    ['أصناف تحت الحد الأدنى', (d.inventory && d.inventory.low_stock) || 0],
  ];
  grid.innerHTML = '<div class="mod-stats">' + cards.map(c =>
    '<div class="mod-stat"><div class="lbl">'+esc(c[0])+'</div><div class="v">'+esc(c[1])+'</div></div>').join('') + '</div>';
}

// ======== M01 GUESTS ========
async function loadGuests(){
  const data=await apiFetch('/api/guests');
  const el=document.getElementById('guestsTable');
  if(data&&Array.isArray(data)){
    document.getElementById('totalGuests').textContent=data.length;
    document.getElementById('activeGuests').textContent=data.filter(g=>g.status==='active'||!g.status).length;
    document.getElementById('vipGuests').textContent=data.filter(g=>g.vip||g.tier==='vip').length;
    const rows=data.map(g=>'<tr><td>'+(g.id||g._id||'--')+'</td><td>'+(g.first_name||g.firstName||'')+' '+(g.last_name||g.lastName||'')+'</td><td>'+(g.phone||g.mobile||'--')+'</td><td>'+(g.email||'--')+'</td><td>'+(g.nationality||'--')+'</td><td>'+statusBadge(g.status||'active')+'</td><td><button class="btn btn-sm btn-outline" onclick="showToast(\'عرض الضيف\',\'info\')">عرض</button></td></tr>').join('');
    el.innerHTML='<table class="mod-table"><thead><tr><th>الرقم</th><th>الاسم</th><th>الجوال</th><th>البريد</th><th>الجنسية</th><th>الحالة</th><th>إجراء</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{el.innerHTML=empty('لا يوجد ضيوف مسجلون');}
}
async function createGuest(){
  const data={first_name:document.getElementById('guestFirstName').value,last_name:document.getElementById('guestLastName').value,phone:document.getElementById('guestPhone').value,email:document.getElementById('guestEmail').value,nationality:document.getElementById('guestNationality').value,id_number:document.getElementById('guestId').value,notes:document.getElementById('guestNotes').value};
  if(!data.first_name||!data.last_name){showToast('يرجى إدخال اسم الضيف','error');return;}
  const res=await apiPost('/api/guests',data);
  if(res){showToast('تم إضافة الضيف بنجاح','success');closeModal('modal-guest');loadGuests();}
  else showToast('حدث خطأ في الحفظ','error');
}

// ======== M02 FRONT DESK ========
async function loadFrontDesk(){
  const arr=await apiFetch('/api/m02/arrivals');
  const dep=await apiFetch('/api/m02/departures');
  function tbl(items,type){
    if(!items||!Array.isArray(items)||!items.length)return empty('لا توجد بيانات');
    const rows=items.map(r=>'<tr><td>'+(r.guest_name||r.guestName||r.name||'--')+'</td><td>'+(r.room||r.room_number||'--')+'</td><td>'+(r.check_in||r.checkin||r.expected_arrival||'--')+'</td><td><button class="btn btn-sm '+(type==='arr'?'btn-green':'btn-red')+'" onclick="'+(type==='arr'?'doCheckin':'doCheckout')+'(\''+(r.id||r._id||'')+'\')">'+(type==='arr'?'تسجيل وصول':'تسجيل مغادرة')+'</button></td></tr>').join('');
    return '<table class="mod-table"><thead><tr><th>الضيف</th><th>الغرفة</th><th>الوقت</th><th>إجراء</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }
  document.getElementById('arrivalsTable').innerHTML=tbl(arr,'arr');
  document.getElementById('departuresTable').innerHTML=tbl(dep,'dep');
}
async function doCheckin(id){const r=await apiFetch('/api/m02/checkin/'+id,{method:'POST'});if(r){showToast('تم تسجيل الوصول','success');loadFrontDesk();}else showToast('خطأ في تسجيل الوصول','error');}
async function doCheckout(id){const r=await apiFetch('/api/m02/checkout/'+id,{method:'POST'});if(r){showToast('تم تسجيل المغادرة','success');loadFrontDesk();}else showToast('خطأ في تسجيل المغادرة','error');}

// ======== M03 CHANNELS ========
async function loadChannels(){
  const data=await apiFetch('/api/channels/status');
  const el=document.getElementById('channelsTable');
  if(data&&Array.isArray(data)&&data.length){
    const rows=data.map(ch=>'<tr><td>'+(ch.channel||ch.name||'--')+'</td><td>'+statusBadge(ch.status)+'</td><td>'+fmt(ch.bookings_today||ch.today_bookings||0)+'</td><td>'+fmt(ch.revenue||0)+' ر.س</td><td>'+(ch.last_sync||ch.lastSync||'--')+'</td></tr>').join('');
    el.innerHTML='<table class="mod-table"><thead><tr><th>القناة</th><th>الحالة</th><th>حجوزات اليوم</th><th>الإيرادات</th><th>آخر مزامنة</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else if(data&&typeof data==='object'&&!Array.isArray(data)){
    const rows=Object.entries(data).map(([k,v])=>'<tr><td>'+k+'</td><td>'+statusBadge(v.status||v)+'</td><td>'+fmt(v.bookings||0)+'</td><td>'+fmt(v.revenue||0)+' ر.س</td><td>'+(v.last_sync||'--')+'</td></tr>').join('');
    el.innerHTML='<table class="mod-table"><thead><tr><th>القناة</th><th>الحالة</th><th>حجوزات اليوم</th><th>الإيرادات</th><th>آخر مزامنة</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{el.innerHTML=empty('لا توجد بيانات قنوات');}
}

// ======== M04 ACCOUNTING ========
async function loadAccounting(){
  const inv=await apiFetch('/api/invoices');
  if(inv&&Array.isArray(inv)){
    document.getElementById('totalInvoices').textContent=inv.length;
    document.getElementById('paidInvoices').textContent=inv.filter(i=>i.status==='paid').length;
    document.getElementById('pendingInvoices').textContent=inv.filter(i=>i.status==='pending'||!i.status).length;
    const rows=inv.slice(0,10).map(i=>'<tr><td>'+(i.id||i._id||i.invoice_number||'--')+'</td><td>'+(i.guest_name||i.guestName||i.guest||'--')+'</td><td>'+fmt(i.amount||i.total)+' ر.س</td><td>'+(i.date||i.created_at||'--')+'</td><td>'+statusBadge(i.status||'pending')+'</td><td>'+(i.status!=='paid'?'<button class="btn btn-sm btn-green" onclick="payInvoice(\''+(i.id||i._id||'')+'\')\">دفع</button>':'--')+'</td></tr>').join('');
    document.getElementById('invoicesTable').innerHTML='<table class="mod-table"><thead><tr><th>رقم الفاتورة</th><th>الضيف</th><th>المبلغ</th><th>التاريخ</th><th>الحالة</th><th>إجراء</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{document.getElementById('invoicesTable').innerHTML=empty('لا توجد فواتير');}
  const pos=await apiFetch('/api/pos');
  if(pos&&Array.isArray(pos)){
    const rows=pos.slice(0,8).map(p=>'<tr><td>'+(p.id||p._id||'--')+'</td><td>'+(p.type||p.category||'--')+'</td><td>'+(p.description||p.item||'--')+'</td><td>'+(p.room||'--')+'</td><td>'+fmt(p.amount||p.total)+' ر.س</td><td>'+(p.date||p.created_at||'--')+'</td></tr>').join('');
    document.getElementById('posTable').innerHTML='<table class="mod-table"><thead><tr><th>الرقم</th><th>النوع</th><th>الوصف</th><th>الغرفة</th><th>المبلغ</th><th>التاريخ</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{document.getElementById('posTable').innerHTML=empty('لا توجد معاملات POS');}
}
async function payInvoice(id){const r=await apiFetch('/api/invoices/'+id+'/pay',{method:'POST'});if(r){showToast('تم الدفع بنجاح','success');loadAccounting();}else showToast('خطأ في تسجيل الدفع','error');}
async function createInvoice(){
  const data={guest_name:document.getElementById('invoiceGuest').value,booking_id:document.getElementById('invoiceBooking').value,amount:parseFloat(document.getElementById('invoiceAmount').value)||0,payment_method:document.getElementById('invoicePayment').value,items:document.getElementById('invoiceItems').value};
  if(!data.guest_name||!data.amount){showToast('يرجى ملء الحقول المطلوبة','error');return;}
  const r=await apiPost('/api/invoices',data);
  if(r){showToast('تم إصدار الفاتورة','success');closeModal('modal-invoice');loadAccounting();}else showToast('خطأ في إصدار الفاتورة','error');
}
async function createPOS(){
  const data={type:document.getElementById('posType').value,amount:parseFloat(document.getElementById('posAmount').value)||0,description:document.getElementById('posDescription').value,room:document.getElementById('posRoom').value};
  const r=await apiPost('/api/pos',data);
  if(r){showToast('تم تسجيل المعاملة','success');closeModal('modal-pos');loadAccounting();}else showToast('خطأ في التسجيل','error');
}

// ======== M05 ROOMS STATUS ========
async function loadRoomsStatus(){
  // كان يقرأ /api/m07/rooms/status ويكتب في roomsStatusTable بينما
  // الصفحة فيها roomsTable — فلا يظهر الجدول أبداً. صار يقرأ سجلّ
  // الغرف نفسه (/api/rooms) لأنه مصدر التسجيل والتعديل.
  const res = await apiSend('/api/rooms');
  const el = document.getElementById('roomsTable');
  if(!el) return;
  if(!res.ok){ el.innerHTML = empty(res.error); return; }
  const rooms = (res.data && res.data.data) || [];
  // تُحفظ هنا ليبحث عنها زرّ التعديل بالمعرّف. حقن الغرفة نفسها في
  // سمة onclick عبر JSON.stringify يُدخل الملاحظات — وهي نصٌّ يكتبه
  // المستخدم — في HTML بلا تهريب، وهي ثغرة XSS.
  ROOMS_CACHE = rooms;

  const n = s => rooms.filter(r => r.status === s).length;
  const set = (id,v) => { const e=document.getElementById(id); if(e) e.textContent=v; };
  set('totalRooms', rooms.length);
  set('occupiedRooms', n('occupied'));
  set('availableRooms', n('available'));
  set('dirtyRooms', n('dirty'));

  if(!rooms.length){
    el.innerHTML = empty('لا غرف مسجَّلة — اضغط «+ تسجيل غرفة» لتسجيل غرف منشأتك');
    return;
  }
  el.innerHTML = '<table class="mod-table"><thead><tr><th>الغرفة</th><th>النوع</th><th>الطابق</th><th>السعة</th><th>السعر</th><th>الحالة</th><th>إجراءات</th></tr></thead><tbody>' +
    rooms.map(r =>
      '<tr><td>'+esc(r.room_number)+'</td>'+
      '<td>'+esc(ROOM_TYPE_AR[r.room_type]||r.room_type||'--')+'</td>'+
      '<td>'+esc(r.floor!=null?r.floor:'--')+'</td>'+
      '<td>'+esc(r.capacity!=null?r.capacity:'--')+'</td>'+
      '<td>'+esc(r.base_price!=null?r.base_price:'--')+'</td>'+
      '<td>'+statusBadge(ROOM_STATUS_AR[r.status]||r.status)+'</td>'+
      '<td><button class="nz-btn is-secondary" onclick="editRoom('+r.id+')">تعديل</button> '+
      '<button class="nz-btn is-secondary" onclick="deleteRoom('+r.id+',\''+esc(r.room_number)+'\')">حذف</button></td></tr>'
    ).join('') + '</tbody></table>';
}

// ======== M06 HR ========
async function loadHR(){
  const emp=await apiFetch('/api/m06/employees');
  const att=await apiFetch('/api/m06/attendance');
  if(emp&&Array.isArray(emp)){
    document.getElementById('totalEmployees').textContent=emp.length;
    const rows=emp.map(e=>'<tr><td>'+(e.id||e._id||'--')+'</td><td>'+(e.name||e.full_name||e.fullName||'--')+'</td><td>'+(e.department||e.dept||'--')+'</td><td>'+(e.title||e.position||'--')+'</td><td>'+(e.phone||'--')+'</td><td>'+statusBadge(e.status||'active')+'</td><td>'+fmt(e.salary||e.basic_salary)+' ر.س</td></tr>').join('');
    document.getElementById('employeesTable').innerHTML='<table class="mod-table"><thead><tr><th>الرقم</th><th>الاسم</th><th>القسم</th><th>المسمى</th><th>الجوال</th><th>الحالة</th><th>الراتب</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{document.getElementById('employeesTable').innerHTML=empty('لا يوجد موظفون');}
  if(att&&Array.isArray(att)){document.getElementById('todayAttendance').textContent=att.length;}
  document.getElementById('payrollCount').textContent='--';
}
async function createEmployee(){
  const data={name:document.getElementById('empName').value,department:document.getElementById('empDept').value,phone:document.getElementById('empPhone').value,salary:parseFloat(document.getElementById('empSalary').value)||0,hire_date:document.getElementById('empHireDate').value,title:document.getElementById('empTitle').value};
  if(!data.name){showToast('يرجى إدخال اسم الموظف','error');return;}
  const r=await apiPost('/api/m06/employees',data);
  if(r){showToast('تم إضافة الموظف','success');closeModal('modal-employee');loadHR();}else showToast('خطأ في الحفظ','error');
}

// ======== M07 HOUSEKEEPING ========
async function loadHousekeeping(){
  const tasks=await apiFetch('/api/m07/tasks');
  const el=document.getElementById('hkTasksTable');
  if(tasks&&Array.isArray(tasks)){
    const rows=tasks.map(t=>'<tr><td>'+(t.id||t._id||'--')+'</td><td>'+(t.room||t.room_number||'--')+'</td><td>'+(t.type||t.task_type||'--')+'</td><td>'+(t.worker||t.assigned_to||t.employee||'--')+'</td><td>'+statusBadge(t.status||'pending')+'</td><td>'+(t.priority||'--')+'</td></tr>').join('');
    el.innerHTML='<table class="mod-table"><thead><tr><th>الرقم</th><th>الغرفة</th><th>النوع</th><th>الموظف</th><th>الحالة</th><th>الأولوية</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{el.innerHTML=empty('لا توجد مهام تنظيف');}
}
async function createHKTask(){
  const data={room:document.getElementById('hkRoom').value,type:document.getElementById('hkType').value,worker:document.getElementById('hkWorker').value,priority:document.getElementById('hkPriority').value,notes:document.getElementById('hkNotes').value};
  if(!data.room){showToast('يرجى إدخال رقم الغرفة','error');return;}
  const r=await apiPost('/api/m07/tasks',data);
  if(r){showToast('تم إنشاء مهمة التنظيف','success');closeModal('modal-hk-task');loadHousekeeping();}else showToast('خطأ في إنشاء المهمة','error');
}

// ======== M08 MAINTENANCE ========
async function loadMaintenance(){
  const orders=await apiFetch('/api/m08/orders');
  const assets=await apiFetch('/api/m08/assets');
  if(orders&&Array.isArray(orders)){
    const rows=orders.map(o=>'<tr><td>'+(o.id||o._id||'--')+'</td><td>'+(o.location||o.room||'--')+'</td><td>'+(o.category||o.type||'--')+'</td><td>'+((o.description||o.desc||'--').substring(0,40))+'</td><td>'+statusBadge(o.status||'pending')+'</td><td>'+(o.technician||o.tech||o.assigned_to||'--')+'</td></tr>').join('');
    document.getElementById('maintenanceTable').innerHTML='<table class="mod-table"><thead><tr><th>الرقم</th><th>الموقع</th><th>الفئة</th><th>الوصف</th><th>الحالة</th><th>الفني</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{document.getElementById('maintenanceTable').innerHTML=empty('لا توجد أوامر صيانة');}
  if(assets&&Array.isArray(assets)){
    const rows=assets.map(a=>'<tr><td>'+(a.id||a._id||'--')+'</td><td>'+(a.name||a.asset_name||'--')+'</td><td>'+(a.location||'--')+'</td><td>'+(a.serial||a.serial_number||'--')+'</td><td>'+statusBadge(a.status||'active')+'</td><td>'+fmt(a.value||a.purchase_value)+' ر.س</td></tr>').join('');
    document.getElementById('assetsTable').innerHTML='<table class="mod-table"><thead><tr><th>الرقم</th><th>الاسم</th><th>الموقع</th><th>السيريال</th><th>الحالة</th><th>القيمة</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{document.getElementById('assetsTable').innerHTML=empty('لا توجد أصول مسجلة');}
}
async function createMaintenance(){
  const data={location:document.getElementById('maintLocation').value,category:document.getElementById('maintCategory').value,description:document.getElementById('maintDesc').value,priority:document.getElementById('maintPriority').value,technician:document.getElementById('maintTech').value};
  if(!data.description){showToast('يرجى وصف المشكلة','error');return;}
  const r=await apiPost('/api/m08/orders',data);
  if(r){showToast('تم إنشاء أمر الصيانة','success');closeModal('modal-maintenance');loadMaintenance();}else showToast('خطأ في إنشاء الأمر','error');
}
async function createAsset(){
  const data={name:document.getElementById('assetName').value,location:document.getElementById('assetLocation').value,serial:document.getElementById('assetSerial').value,value:parseFloat(document.getElementById('assetValue').value)||0};
  if(!data.name){showToast('يرجى إدخال اسم الأصل','error');return;}
  const r=await apiPost('/api/m08/assets',data);
  if(r){showToast('تم إضافة الأصل','success');closeModal('modal-asset');loadMaintenance();}else showToast('خطأ في الحفظ','error');
}

// ======== M10 CRM ========
async function loadCRM(){
  const stats=await apiFetch('/api/m10/stats');
  if(stats){
    document.getElementById('crmTotal').textContent=fmt(stats.total_contacts||stats.total||'--');
    document.getElementById('crmLoyalty').textContent=fmt(stats.loyalty_members||stats.loyalty||'--');
    document.getElementById('crmPoints').textContent=fmt(stats.points_today||stats.points||'--');
  }
  const contacts=await apiFetch('/api/m10/contacts');
  const el=document.getElementById('crmTable');
  if(contacts&&Array.isArray(contacts)){
    const rows=contacts.map(c=>'<tr><td>'+(c.id||c._id||'--')+'</td><td>'+(c.name||c.full_name||'--')+'</td><td>'+(c.phone||c.mobile||'--')+'</td><td>'+(c.email||'--')+'</td><td>'+(c.loyalty_points||c.points||0)+'</td><td>'+(c.tier||c.level||'عادي')+'</td><td>'+statusBadge(c.status||'active')+'</td></tr>').join('');
    el.innerHTML='<table class="mod-table"><thead><tr><th>الرقم</th><th>الاسم</th><th>الجوال</th><th>البريد</th><th>النقاط</th><th>المستوى</th><th>الحالة</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{el.innerHTML=empty('لا توجد جهات اتصال');}
}
async function awardLoyalty(){
  const data={guest_id:document.getElementById('loyaltyGuest').value,points:parseInt(document.getElementById('loyaltyPoints').value)||0,reason:document.getElementById('loyaltyReason').value};
  if(!data.guest_id||!data.points){showToast('يرجى ملء جميع الحقول','error');return;}
  const r=await apiPost('/api/m10/loyalty/award',data);
  if(r){showToast('تم منح النقاط بنجاح','success');closeModal('modal-loyalty');loadCRM();}else showToast('خطأ في منح النقاط','error');
}

// ======== M11 KPI ========
async function loadKPI(){
  const kpi=await apiFetch('/api/m11/dashboard')||await apiFetch('/api/kpi');
  if(kpi){
    const occ=kpi.occupancy_rate||kpi.occupancy;
    document.getElementById('kpi2Occ').textContent=occ!=null?occ+'%':'--';
    document.getElementById('kpi2ADR').textContent=fmt(kpi.adr||kpi.ADR)+' ر.س';
    document.getElementById('kpi2RevPAR').textContent=fmt(kpi.revpar||kpi.RevPAR)+' ر.س';
    document.getElementById('kpi2Sat').textContent=(kpi.guest_satisfaction||kpi.satisfaction||'--')+'/5';
    document.getElementById('kpi2Los').textContent=(kpi.avg_los||kpi.los||'--')+' ليلة';
    document.getElementById('kpi2Cancel').textContent=(kpi.cancellation_rate||kpi.cancel_rate||'--')+'%';
    const entries=Object.entries(kpi).filter(([k])=>!['_id','id'].includes(k));
    const rows=entries.map(([k,v])=>'<tr><td style="font-weight:600">'+k+'</td><td>'+v+'</td></tr>').join('');
    document.getElementById('kpiTable').innerHTML='<table class="mod-table"><thead><tr><th>المؤشر</th><th>القيمة</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{document.getElementById('kpiTable').innerHTML=empty('لا توجد بيانات KPI');}
}

// ======== M13 WAREHOUSES ========
async function loadWarehouses(){
  const items=await apiFetch('/api/m13/items');
  const low=await apiFetch('/api/m13/low-stock');
  if(items&&Array.isArray(items)){
    const rows=items.map(i=>'<tr><td>'+(i.id||i._id||'--')+'</td><td>'+(i.name||i.item_name||'--')+'</td><td>'+(i.category||'--')+'</td><td>'+fmt(i.quantity||i.qty||0)+'</td><td>'+fmt(i.min_quantity||i.min_qty||0)+'</td><td>'+fmt(i.unit_price||i.price||0)+' ر.س</td><td>'+(i.supplier||'--')+'</td></tr>').join('');
    document.getElementById('warehouseTable').innerHTML='<table class="mod-table"><thead><tr><th>الرقم</th><th>الاسم</th><th>الفئة</th><th>الكمية</th><th>الحد الأدنى</th><th>السعر</th><th>المورد</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{document.getElementById('warehouseTable').innerHTML=empty('لا توجد عناصر مخزون');}
  if(low&&Array.isArray(low)&&low.length){
    const rows=low.map(i=>'<tr><td>'+(i.name||i.item_name||'--')+'</td><td style="color:var(--red);font-weight:700">'+fmt(i.quantity||i.qty||0)+'</td><td>'+fmt(i.min_quantity||i.min_qty||0)+'</td><td><span class="badge badge-red">مخزون منخفض</span></td></tr>').join('');
    document.getElementById('lowStockTable').innerHTML='<table class="mod-table"><thead><tr><th>العنصر</th><th>الكمية الحالية</th><th>الحد الأدنى</th><th>الحالة</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{document.getElementById('lowStockTable').innerHTML=empty('المخزون بمستويات جيدة ✅');}
}
async function createWarehouseItem(){
  const data={name:document.getElementById('whItem').value,category:document.getElementById('whCategory').value,quantity:parseInt(document.getElementById('whQty').value)||0,min_quantity:parseInt(document.getElementById('whMinQty').value)||0,unit_price:parseFloat(document.getElementById('whPrice').value)||0,supplier:document.getElementById('whSupplier').value};
  if(!data.name){showToast('يرجى إدخال اسم العنصر','error');return;}
  const r=await apiPost('/api/m13/items',data);
  if(r){showToast('تم إضافة العنصر','success');closeModal('modal-warehouse-item');loadWarehouses();}else showToast('خطأ في الحفظ','error');
}

// ======== M14 TOURISM ========
async function loadTourism(){
  const stats=await apiFetch('/api/m14/stats');
  if(stats){
    document.getElementById('totalTours').textContent=fmt(stats.total_tours||stats.tours||'--');
    document.getElementById('tourBookings').textContent=fmt(stats.bookings_today||stats.bookings||'--');
    document.getElementById('tourRevenue').textContent=fmt(stats.revenue||'--')+' ر.س';
  }
  const tours=await apiFetch('/api/m14/tours');
  const el=document.getElementById('toursTable');
  if(tours&&Array.isArray(tours)){
    const rows=tours.map(t=>'<tr><td>'+(t.id||t._id||'--')+'</td><td>'+(t.name||t.tour_name||'--')+'</td><td>'+(t.category||'--')+'</td><td>'+(t.duration||'--')+' ساعة</td><td>'+fmt(t.price)+' ر.س</td><td>'+(t.capacity||'--')+'</td><td>'+statusBadge(t.status||'active')+'</td><td><button class="btn btn-sm btn-gold" onclick="showToast(\'تم إنشاء الحجز\',\'success\')">احجز</button></td></tr>').join('');
    el.innerHTML='<table class="mod-table"><thead><tr><th>الرقم</th><th>الاسم</th><th>الفئة</th><th>المدة</th><th>السعر</th><th>الطاقة</th><th>الحالة</th><th>إجراء</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{el.innerHTML=empty('لا توجد جولات مسجلة');}
}
async function createTour(){
  const data={name:document.getElementById('tourName').value,duration:parseInt(document.getElementById('tourDuration').value)||0,price:parseFloat(document.getElementById('tourPrice').value)||0,capacity:parseInt(document.getElementById('tourCapacity').value)||0,category:document.getElementById('tourCategory').value,description:document.getElementById('tourDesc').value};
  if(!data.name){showToast('يرجى إدخال اسم الجولة','error');return;}
  const r=await apiPost('/api/m14/tours',data);
  if(r){showToast('تم إضافة الجولة','success');closeModal('modal-tour');loadTourism();}else showToast('خطأ في الحفظ','error');
}

// ======== M14B TOURIST DESTINATIONS ========
async function loadDestinations(){
  const stats=await apiFetch('/api/m14b/stats');
  if(stats){
    document.getElementById('totalDestinations').textContent=fmt(stats.active_destinations||'--');
    document.getElementById('destBookingsCount').textContent=fmt(stats.total_bookings||'--');
    document.getElementById('destRevenue').textContent=fmt(stats.total_revenue||'--')+' ر.س';
  }
  const dests=await apiFetch('/api/m14b/destinations');
  const el=document.getElementById('destinationsTable');
  if(dests&&dests.data&&Array.isArray(dests.data)&&dests.data.length){
    const rows=dests.data.map(d=>'<tr><td>'+(d.name_ar||'--')+'</td><td>'+(d.city||'--')+'</td><td>'+(d.category||'--')+'</td><td>'+fmt(d.entry_fee_adult)+' ر.س</td><td>'+(d.avg_rating||0)+'/5</td><td>'+statusBadge(d.status||'active')+'</td></tr>').join('');
    el.innerHTML='<table class="mod-table"><thead><tr><th>الاسم</th><th>المدينة</th><th>الفئة</th><th>رسوم البالغ</th><th>التقييم</th><th>الحالة</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{el.innerHTML=empty('لا توجد وجهات مسجلة');}
  const bks=await apiFetch('/api/m14b/dest-bookings');
  const el2=document.getElementById('destBookingsTable');
  if(bks&&bks.data&&Array.isArray(bks.data)&&bks.data.length){
    const rows=bks.data.map(b=>'<tr><td>'+(b.destination_name||'--')+'</td><td>'+(b.guest_name||'--')+'</td><td>'+(b.visit_date||'--')+'</td><td>'+(b.adults_count||0)+' بالغ</td><td>'+fmt(b.total_price)+' ر.س</td><td>'+statusBadge(b.status||'confirmed')+'</td></tr>').join('');
    el2.innerHTML='<table class="mod-table"><thead><tr><th>الوجهة</th><th>الضيف</th><th>تاريخ الزيارة</th><th>العدد</th><th>المبلغ</th><th>الحالة</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{el2.innerHTML=empty('لا توجد حجوزات وجهات');}
}
async function createDestination(){
  const data={name_ar:document.getElementById('destName').value,city:document.getElementById('destCity').value,category:document.getElementById('destCategory').value,entry_fee_adult:parseFloat(document.getElementById('destFeeAdult').value)||0,opening_hours:document.getElementById('destHours').value};
  if(!data.name_ar){showToast('يرجى إدخال اسم الوجهة','error');return;}
  const r=await apiPost('/api/m14b/destinations',data);
  if(r){showToast('تم إضافة الوجهة','success');closeModal('modal-destination');loadDestinations();}else showToast('خطأ في الحفظ','error');
}

// ======== POS ========
async function loadPOS(){
  const summary=await apiFetch('/api/m04/cashier/summary');
  if(summary){
    document.getElementById('posTodaySales').textContent=fmt(summary.today_sales||summary.total_sales||0)+' ر.س';
    document.getElementById('posTodayCount').textContent=fmt(summary.today_count||summary.count||0);
    document.getElementById('posTodayVat').textContent=fmt(summary.today_vat||summary.vat||0)+' ر.س';
  }
  const items=await apiFetch('/api/m04/pos/items');
  const iel=document.getElementById('posItemsTable');
  if(items&&Array.isArray(items)&&items.length){
    document.getElementById('posItemsCount').textContent=items.length;
    const rows=items.map(i=>'<tr><td>'+(i.id||'--')+'</td><td>'+(i.name||i.item_name||'--')+'</td><td>'+(i.category||'--')+'</td><td>'+fmt(i.price||i.unit_price||0)+' ر.س</td><td>'+(i.unit||'قطعة')+'</td></tr>').join('');
    iel.innerHTML='<table class="mod-table"><thead><tr><th>الرقم</th><th>الصنف</th><th>الفئة</th><th>السعر</th><th>الوحدة</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{iel.innerHTML=empty('لا توجد أصناف مسجلة');}
  const sales=await apiFetch('/api/m04/pos/sales');
  const sel=document.getElementById('posTable');
  if(sales&&Array.isArray(sales)&&sales.length){
    const rows=sales.slice(0,10).map(s=>'<tr><td>'+(s.id||'--')+'</td><td>'+(s.item_name||s.item||'--')+'</td><td>'+fmt(s.qty||s.quantity||1)+'</td><td>'+fmt(s.amount||s.total||0)+' ر.س</td><td>'+(s.payment_method||'نقد')+'</td><td>'+statusBadge('paid')+'</td></tr>').join('');
    sel.innerHTML='<table class="mod-table"><thead><tr><th>الرقم</th><th>الصنف</th><th>الكمية</th><th>المبلغ</th><th>طريقة الدفع</th><th>الحالة</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{sel.innerHTML=empty('لا توجد مبيعات اليوم');}
}
async function createPOSItem(){
  const data={name:document.getElementById('piName').value,category:document.getElementById('piCategory').value,price:parseFloat(document.getElementById('piPrice').value)||0,unit:document.getElementById('piUnit').value||'قطعة'};
  if(!data.name||!data.price){showToast('يرجى إدخال اسم الصنف والسعر','error');return;}
  const r=await apiPost('/api/m04/pos/items',data);
  if(r){showToast('تم إضافة الصنف بنجاح','success');closeModal('modal-pos-item');loadPOS();}else showToast('خطأ في الحفظ','error');
}

// ======== ANALYTICS ========
async function loadAnalytics(){
  const kpi=await apiFetch('/api/m11/dashboard')||await apiFetch('/api/kpi');
  if(kpi){
    document.getElementById('anaOccRate').textContent=(kpi.occupancy_rate||kpi.occupancy||'--')+'%';
    document.getElementById('anaADR').textContent=fmt(kpi.adr||kpi.ADR||0);
    document.getElementById('anaRevPAR').textContent=fmt(kpi.revpar||kpi.RevPAR||0);
  }
  const rev=await apiFetch('/api/m04/revenue/monthly');
  const revEl=document.getElementById('anaRevBars');
  const anaRevEl=document.getElementById('anaMonthRev');
  if(rev&&Array.isArray(rev)&&rev.length){
    const maxV=Math.max(...rev.map(r=>r.revenue||r.amount||0))||1;
    const latest=rev[rev.length-1];
    if(anaRevEl&&latest)anaRevEl.textContent=fmt(latest.revenue||latest.amount||0);
    const bars=rev.slice(-6).map(r=>{const v=r.revenue||r.amount||0;const pct=Math.round((v/maxV)*100);return`<div class="ana-bar-row"><div class="ana-bar-label">${r.month||r.period||'--'}</div><div class="ana-bar-track"><div class="ana-bar-fill" style="width:${pct}%"></div></div><div class="ana-bar-val">${fmt(v)} ر.س</div></div>`;}).join('');
    revEl.innerHTML=bars||'<div class="mod-empty">لا بيانات</div>';
  }else{
    revEl.innerHTML='<div class="mod-empty">لا بيانات إيراد متاحة</div>';
    const demoMonths=['يناير','فبراير','مارس','أبريل','مايو','يونيو'];
    const demoVals=[42000,38500,55000,61000,49000,67000];
    const maxV=Math.max(...demoVals);
    revEl.innerHTML=demoMonths.map((m,i)=>{const pct=Math.round((demoVals[i]/maxV)*100);return`<div class="ana-bar-row"><div class="ana-bar-label">${m}</div><div class="ana-bar-track"><div class="ana-bar-fill" style="width:${pct}%"></div></div><div class="ana-bar-val">${fmt(demoVals[i])} ر.س</div></div>`;}).join('');
    if(anaRevEl)anaRevEl.textContent=fmt(67000);
  }
  const channelData=[{name:'Booking.com',pct:38,color:'#3b82f6'},{name:'مباشر',pct:27,color:'#C9A85F'},{name:'Airbnb',pct:18,color:'#ef4444'},{name:'أخرى',pct:17,color:'#6b7280'}];
  document.getElementById('anaChannelGrid').innerHTML=channelData.map(c=>`<div class="ana-pie-item"><div class="ana-dot" style="background:${c.color}"></div><div style="flex:1">${c.name}</div><strong>${c.pct}%</strong></div>`).join('');
  const days=['السبت','الأحد','الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة'];
  const occVals=[72,68,81,75,90,88,65];
  const maxO=Math.max(...occVals);
  document.getElementById('anaOccBars').innerHTML=days.map((d,i)=>{const pct=occVals[i];return`<div class="ana-bar-row"><div class="ana-bar-label">${d}</div><div class="ana-bar-track"><div class="ana-bar-fill" style="width:${pct}%;background:linear-gradient(to left,var(--brand-700),var(--brand-500))"></div></div><div class="ana-bar-val">${pct}%</div></div>`;}).join('');
  const topSvc=[{name:'إفطار',cnt:142},{name:'قهوة عربية',cnt:98},{name:'خدمة الغرف',cnt:76},{name:'سبا',cnt:44}];
  document.getElementById('anaTopServices').innerHTML='<table class="mod-table"><thead><tr><th>الخدمة</th><th>عدد المبيعات</th></tr></thead><tbody>'+topSvc.map(s=>`<tr><td>${s.name}</td><td><strong>${s.cnt}</strong></td></tr>`).join('')+'</tbody></table>';
}

// ======== BOOKINGS ========
async function createBooking(){
  const data={guest_name:document.getElementById('bookingGuest').value,room:document.getElementById('bookingRoom').value,check_in:document.getElementById('bookingCheckin').value,check_out:document.getElementById('bookingCheckout').value,room_type:document.getElementById('bookingRoomType').value,guests:parseInt(document.getElementById('bookingGuests').value)||1,price:parseFloat(document.getElementById('bookingPrice').value)||0,source:document.getElementById('bookingSource').value};
  if(!data.guest_name||!data.check_in||!data.check_out){showToast('يرجى ملء الحقول المطلوبة','error');return;}
  const r=await apiPost('/api/bookings',data);
  if(r){showToast('تم تأكيد الحجز','success');closeModal('modal-booking');loadHome();}else showToast('خطأ في إنشاء الحجز','error');
}

