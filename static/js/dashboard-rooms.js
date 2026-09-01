// dashboard-rooms.js — عرض الغرف والمفتاح الذكي
//
// التسجيل والتعديل والحذف انتقلت إلى `modules/00-setup`: نموذجان لنفس
// العمل يتباعدان، فيُصلَح أحدهما ويبقى الآخر. ما بقي هنا **عرضٌ فقط**.
// core أولاً لأن هذا الملف يستعمل apiSend و esc منه.

const ROOM_STATUS_AR = {available:'متاحة', occupied:'مشغولة', dirty:'تحتاج تنظيف', maintenance:'صيانة', blocked:'موقوفة'};
const ROOM_TYPE_AR   = {standard:'عادية', double:'مزدوجة', twin:'سريران', suite:'جناح', family:'عائلية'};

// ======== M09 المفتاح الذكي ========
// لا نقطة API مخصّصة لهذه الوحدة؛ تُبنى من سجلّ الغرف نفسه.
async function loadSmartKey(){
  const res = await apiSend('/api/rooms');
  const el = document.getElementById('smartKeyTable');
  if(!res.ok){ if(el) el.innerHTML = empty(res.error); return; }
  const rooms = (res.data && res.data.data) || [];
  const n = st => rooms.filter(r => r.status === st).length;
  const set = (id,v) => { const e=document.getElementById(id); if(e) e.textContent=v; };
  set('smartKeyTotal', rooms.length);
  set('smartKeyOccupied', n('occupied'));
  set('smartKeyDirty', n('dirty'));
  set('smartKeyAvail', n('available'));
  set('smartKeyActive', n('occupied'));
  if(!el) return;
  el.innerHTML = rooms.length
    ? '<table class="mod-table"><thead><tr><th>الغرفة</th><th>النوع</th><th>الحالة</th><th>المفتاح</th></tr></thead><tbody>' +
      rooms.map(r => '<tr><td>'+esc(r.room_number)+'</td><td>'+esc(ROOM_TYPE_AR[r.room_type]||r.room_type||'--')+'</td>'+
        '<td>'+statusBadge(ROOM_STATUS_AR[r.status]||r.status)+'</td>'+
        '<td>'+(r.status==='occupied'?'<span class="good">مُفعَّل</span>':'<span class="mod-empty" style="padding:0">غير مُفعَّل</span>')+'</td></tr>').join('') +
      '</tbody></table>'
    : empty('لا غرف مسجَّلة — سجّلها من «إعداد المنشأة»');
}
