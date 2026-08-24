// dashboard-rooms.js — الغرف: التسجيل والتعديل والحذف، والمفتاح الذكي
// مُستخرَج من dashboard.html. الترتيب في الصفحة مقصود:
// core أولاً لأن بقية الملفات تستعمل apiSend و esc منه.

// ======== الغرف: تسجيل وتعديل ========
let ROOMS_CACHE = [];
function editRoom(id){ const r = ROOMS_CACHE.find(x => x.id === id); if(r) openRoomModal(r); }
const ROOM_STATUS_AR={available:'متاحة',occupied:'مشغولة',dirty:'تحتاج تنظيف',maintenance:'صيانة',blocked:'موقوفة'};
const ROOM_TYPE_AR={standard:'عادية',double:'مزدوجة',twin:'سريران',suite:'جناح',family:'عائلية'};

function openRoomModal(room){
  showFormError('roomError','');
  document.getElementById('roomModalTitle').textContent = room ? 'تعديل غرفة' : 'تسجيل غرفة';
  document.getElementById('roomId').value      = room ? room.id : '';
  document.getElementById('roomNumber').value  = room ? (room.room_number||'') : '';
  document.getElementById('roomType').value    = room ? (room.room_type||'standard') : 'standard';
  document.getElementById('roomFloor').value   = room ? (room.floor||1) : 1;
  document.getElementById('roomCapacity').value= room ? (room.capacity||2) : 2;
  document.getElementById('roomPrice').value   = room ? (room.base_price||0) : 0;
  document.getElementById('roomStatus').value  = room ? (room.status||'available') : 'available';
  document.getElementById('roomNotes').value   = room ? (room.notes||'') : '';
  openModal('modal-room');
}

async function saveRoom(){
  showFormError('roomError','');
  const id = document.getElementById('roomId').value;
  const body = {
    room_number: document.getElementById('roomNumber').value.trim(),
    room_type:   document.getElementById('roomType').value,
    floor:       document.getElementById('roomFloor').value,
    capacity:    document.getElementById('roomCapacity').value,
    base_price:  document.getElementById('roomPrice').value,
    status:      document.getElementById('roomStatus').value,
    notes:       document.getElementById('roomNotes').value.trim()
  };
  if(id) body.id = id;
  const res = await apiSend('/api/rooms', {method:'POST', body:JSON.stringify(body)});
  if(!res.ok){ showFormError('roomError', res.error); return; }
  closeModal('modal-room');
  loadRoomsStatus();
}

async function deleteRoom(id, number){
  if(!confirm('حذف الغرفة رقم '+number+'؟')) return;
  const res = await apiSend('/api/rooms/'+id, {method:'DELETE'});
  if(!res.ok){ showToast(res.error,'error'); return; }
  loadRoomsStatus();
}

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
    : empty('لا غرف مسجَّلة — سجّل الغرف أولاً من «حالة الغرف»');
}
