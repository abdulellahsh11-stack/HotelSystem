// registration-app.js — تسجيل النزيل: الحفظ والغرف والتواريخ والأقسام الاختيارية
//
// عالج ستّ ملاحظاتٍ من التشغيل الفعلي:
//   ١ — الغرف كانت قائمةً ثابتة بتسع عشرة غرفةً وهمية، لا من سجلّ المنشأة
//   ٢ — تاريخ الميلاد حقلُ نصٍّ حرّ، فيُكتب بأي صيغة
//   ٣ — الاستلام والتوصيل قسمٌ مفتوح دائماً رغم أنه اختياري
//   ٤ — الوجبات كذلك، ومُعلَّمة إلزامية وهي ليست كذلك
//   ٥ — لا وسيلة لتمديد إقامة نزيلٍ قائم
//   ٦ — زرّا الحفظ بلا `onclick` إطلاقاً: النموذج لا يحفظ شيئاً

(function () {
'use strict';

var API = '';

function q(sel){ return document.querySelector(sel); }
function field(name){ return q('[data-field="' + name + '"]'); }
function val(name){ var el = field(name); return el ? String(el.value || '').trim() : ''; }

function toast(msg, isError){
  if (window.GR && window.GR.toast) { window.GR.toast(msg, isError); return; }
  // بديلٌ مضمون: رسالة الخادم يجب أن تصل ولو لم تُحمَّل أدوات الصفحة
  (isError ? console.error : console.log)(msg);
  alert(msg);
}

async function send(url, options){
  try {
    var res = await fetch(API + url, {
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      ...(options || {})
    });
    var body = null;
    try { body = await res.json(); } catch (e) { /* ردٌّ بلا JSON */ }
    if (!res.ok) {
      return { ok: false, error: (body && (body.detail || body.error)) || 'تعذّر إتمام العملية' };
    }
    return { ok: true, data: body };
  } catch (e) {
    return { ok: false, error: 'تعذّر الاتصال بالخادم' };
  }
}

/* ═══════════════════════════════════════════════
   ١ — الغرف من سجلّ المنشأة
   كانت قائمةً ثابتة، فيختار الموظف غرفةً لا وجود لها ثم يفشل الحجز.
═══════════════════════════════════════════════ */
var ROOM_TYPE_AR = {
  standard: 'ستاندرد', double: 'مزدوجة', twin: 'سريران',
  suite: 'جناح', family: 'عائلية'
};

async function loadRooms(){
  var sel = q('#room-number-sel');
  if (!sel) return;
  var res = await send('/api/rooms');
  if (!res.ok) { sel.innerHTML = '<option value="">تعذّر تحميل الغرف</option>'; return; }

  var rooms = ((res.data && res.data.data) || []).filter(function (r) {
    return r.status === 'available';
  });
  if (!rooms.length) {
    sel.innerHTML = '<option value="">لا غرف متاحة — سجّل الغرف من «حالة الغرف»</option>';
    return;
  }
  // مجمَّعة بالدور: الموظف يفكّر بالدور أولاً ثم بالرقم
  var byFloor = {};
  rooms.forEach(function (r) {
    var f = (r.floor === null || r.floor === undefined) ? 0 : Number(r.floor);
    (byFloor[f] = byFloor[f] || []).push(r);
  });
  sel.innerHTML = Object.keys(byFloor).map(Number).sort(function (a, b) { return a - b; })
    .map(function (f) {
      var label = f === 0 ? 'الدور الأرضي' : 'الدور ' + f;
      var opts = byFloor[f]
        .sort(function (a, b) {
          return String(a.room_number).localeCompare(String(b.room_number), 'ar', { numeric: true });
        })
        .map(function (r) {
          var t = ROOM_TYPE_AR[r.room_type] || r.room_type || '';
          return '<option value="' + r.id + '" data-room="' + r.room_number + '">'
               + r.room_number + (t ? ' — ' + t : '') + '</option>';
        }).join('');
      return '<optgroup label="' + label + '">' + opts + '</optgroup>';
    }).join('');
}

/* ═══════════════════════════════════════════════
   ٢ — تاريخ الميلاد حقلَ تاريخ لا نصّاً حرّاً
   النصّ الحرّ يُدخَل بأي صيغة، فيصل الخادم غير قابل للمقارنة.
═══════════════════════════════════════════════ */
function fixBirthDate(){
  var dob = field('dob');
  if (!dob || dob.type === 'date') return;
  dob.type = 'date';
  dob.removeAttribute('class');
  dob.className = 'is-mono';
  // نزيلٌ عمره يوم غير وارد، ونزيلٌ من القرن الماضي وارد
  dob.max = new Date().toISOString().slice(0, 10);
  dob.min = '1900-01-01';
}

/* ═══════════════════════════════════════════════
   ٣ و٤ — أقسام اختيارية تُطوى بمربّع
   القسم المفتوح دائماً يوحي بأنه مطلوب. الطيّ يجعل الاختياري يبدو
   اختيارياً، ويُقصّر النموذج لمن لا يحتاجه.
═══════════════════════════════════════════════ */
function makeCollapsible(heading, key, openByDefault){
  var section = heading && heading.closest ? heading.closest('.gr-sec') : null;
  if (!section || section.dataset.collapsible === '1') return;
  section.dataset.collapsible = '1';

  var body = document.createElement('div');
  while (heading.nextSibling) body.appendChild(heading.nextSibling);
  section.appendChild(body);

  var box = document.createElement('input');
  box.type = 'checkbox';
  box.id = 'opt-' + key;
  box.checked = !!openByDefault;
  box.style.cssText = 'margin-inline-end:8px;cursor:pointer;width:16px;height:16px';

  var arrow = document.createElement('span');
  arrow.textContent = '▼';
  arrow.style.cssText = 'display:inline-block;margin-inline-start:8px;transition:transform 150ms;font-size:11px';

  function apply(){
    body.style.display = box.checked ? '' : 'none';
    arrow.style.transform = box.checked ? '' : 'rotate(-90deg)';
  }
  box.addEventListener('change', apply);
  // النقر على العنوان يطوي أيضاً — الهدف الأكبر أسهل إصابةً من مربّع صغير
  heading.style.cursor = 'pointer';
  heading.addEventListener('click', function (e) {
    if (e.target === box) return;
    box.checked = !box.checked;
    apply();
  });

  heading.insertBefore(box, heading.firstChild);
  heading.appendChild(arrow);
  apply();
}

function setupOptionalSections(){
  var headings = Array.prototype.slice.call(document.querySelectorAll('.gr-sec h4'));

  var airport = headings.find(function (h) { return /المطار/.test(h.textContent); });
  if (airport) makeCollapsible(airport, 'airport', false);

  // الوجبات حقلٌ داخل قسمٍ أكبر، فيُلفّ في قسمٍ خاص ليُطوى وحده
  var mealsLabel = Array.prototype.slice.call(document.querySelectorAll('.gr-field label'))
    .find(function (l) { return /خطة الوجبات/.test(l.textContent); });
  if (mealsLabel) {
    var req = mealsLabel.querySelector('.req');
    if (req) req.remove();          // ليست إلزامية — الإقامة بلا وجبات واردة
    var box = document.createElement('input');
    box.type = 'checkbox';
    box.id = 'opt-meals';
    box.style.cssText = 'margin-inline-end:8px;cursor:pointer;width:15px;height:15px';
    var arrow = document.createElement('span');
    arrow.textContent = '▼';
    arrow.style.cssText = 'display:inline-block;margin-inline-start:6px;font-size:10px;transition:transform 150ms';
    var select = mealsLabel.parentElement.querySelector('select');
    var hint = mealsLabel.parentElement.querySelector('.hint');
    function applyMeals(){
      var on = box.checked;
      if (select) select.style.display = on ? '' : 'none';
      if (hint) hint.style.display = on ? '' : 'none';
      arrow.style.transform = on ? '' : 'rotate(-90deg)';
    }
    box.addEventListener('change', applyMeals);
    mealsLabel.style.cursor = 'pointer';
    mealsLabel.addEventListener('click', function (e) {
      if (e.target === box) return;
      box.checked = !box.checked;
      applyMeals();
    });
    mealsLabel.insertBefore(box, mealsLabel.firstChild);
    mealsLabel.appendChild(arrow);
    applyMeals();
  }
}

/* ═══════════════════════════════════════════════
   ٥ — تمديد إقامة نزيلٍ قائم
   التمديد ليس حجزاً جديداً: نفس الضيف ونفس الغرفة، يتغيّر تاريخ
   المغادرة وحده. إنشاء حجزٍ ثانٍ يُضاعف الضيف في التقارير.
═══════════════════════════════════════════════ */
function setupExtension(){
  var co = field('checkout');
  if (!co || co.dataset.extendReady === '1') return;
  co.dataset.extendReady = '1';

  var wrap = document.createElement('div');
  wrap.style.cssText = 'margin-top:6px;font-size:12px;display:flex;align-items:center;gap:6px';

  var box = document.createElement('input');
  box.type = 'checkbox';
  box.id = 'extend-stay';
  box.style.cssText = 'cursor:pointer;width:15px;height:15px';

  var label = document.createElement('label');
  label.htmlFor = 'extend-stay';
  label.textContent = 'تمديد إقامة نزيل قائم (نفس الضيف والغرفة)';
  label.style.cursor = 'pointer';

  var picker = document.createElement('select');
  picker.id = 'extend-booking';
  picker.style.cssText = 'display:none;margin-top:6px;width:100%;padding:7px;border-radius:6px';

  wrap.appendChild(box);
  wrap.appendChild(label);
  co.parentElement.appendChild(wrap);
  co.parentElement.appendChild(picker);

  box.addEventListener('change', async function () {
    picker.style.display = box.checked ? '' : 'none';
    if (!box.checked) return;
    picker.innerHTML = '<option>جارٍ تحميل النزلاء الحاليين…</option>';
    var res = await send('/api/bookings?status=checked_in');
    var rows = (res.ok && res.data && res.data.data) || [];
    picker.innerHTML = rows.length
      ? rows.map(function (b) {
          return '<option value="' + b.id + '">' + (b.guest_name || b.id)
               + ' — غرفة ' + (b.room_number || '—')
               + ' — تنتهي ' + (b.check_out || '—') + '</option>';
        }).join('')
      : '<option value="">لا نزلاء حاليون</option>';
  });
}

async function submitExtension(){
  var picker = q('#extend-booking');
  var bookingId = picker && picker.value;
  if (!bookingId) { toast('اختر النزيل المراد تمديد إقامته', true); return; }
  var newCheckout = val('checkout');
  if (!newCheckout) { toast('اختر تاريخ المغادرة الجديد', true); return; }

  var res = await send('/api/bookings/' + encodeURIComponent(bookingId), {
    method: 'PUT',
    body: JSON.stringify({ check_out: newCheckout })
  });
  if (!res.ok) { toast(res.error, true); return; }
  toast('مُدّدت الإقامة حتى ' + newCheckout + ' ✓');
}

/* ═══════════════════════════════════════════════
   ٦ — الحفظ
   كان زرّا الحفظ بلا `onclick`: يُملأ النموذج ويُضغط الزر ولا يحدث
   شيء. النزيل يُحفظ أولاً ثم الحجز، لأن الحجز يشير إليه.
═══════════════════════════════════════════════ */
function collect(){
  var sel = q('#room-number-sel');
  var opt = sel && sel.selectedOptions && sel.selectedOptions[0];
  return {
    full_name: (q('[data-name="ar"]') || {}).value || '',
    full_name_en: (q('[data-name="en"]') || {}).value || '',
    id_number: val('idnum'),
    birth_date: val('dob'),
    nationality: val('nationality'),
    check_in: val('checkin'),
    check_out: val('checkout'),
    room_id: sel && sel.value ? Number(sel.value) : null,
    room_number: opt ? opt.getAttribute('data-room') : ''
  };
}

function validate(data){
  if (!data.full_name.trim()) return 'اسم النزيل مطلوب';
  if (!data.id_number) return 'رقم الهوية أو الجواز مطلوب';
  if (!data.check_in || !data.check_out) return 'تاريخا الوصول والمغادرة مطلوبان';
  if (data.check_out <= data.check_in) return 'تاريخ المغادرة يجب أن يلي تاريخ الوصول';
  if (!data.room_id) return 'اختر الغرفة';
  return '';
}

async function saveGuest(alsoCheckIn){
  if (q('#extend-stay') && q('#extend-stay').checked) { await submitExtension(); return; }

  var data = collect();
  var problem = validate(data);
  if (problem) { toast(problem, true); return; }

  var guest = await send('/api/guests', {
    method: 'POST',
    body: JSON.stringify({
      full_name: data.full_name,
      id_number: data.id_number,
      birth_date: data.birth_date || null,
      nationality: data.nationality
    })
  });
  if (!guest.ok) { toast(guest.error, true); return; }
  var guestId = guest.data && guest.data.data && guest.data.data.id;

  var booking = await send('/api/bookings', {
    method: 'POST',
    body: JSON.stringify({
      guest_id: guestId,
      room_id: data.room_id,
      check_in: data.check_in,
      check_out: data.check_out,
      status: 'confirmed'
    })
  });
  if (!booking.ok) {
    // النزيل حُفظ والحجز لم يُحفظ — يُقال صراحةً بدل ادّعاء نجاحٍ كامل
    toast('حُفظ النزيل، وتعذّر إنشاء الحجز: ' + booking.error, true);
    return;
  }
  var bookingId = booking.data && booking.data.data && booking.data.data.id;

  if (!alsoCheckIn) { toast('حُفظ النزيل وحجزه ✓'); return; }

  var cascade = await send('/api/integration/checkin', {
    method: 'POST',
    body: JSON.stringify({ booking_id: bookingId })
  });
  toast(cascade.ok
    ? 'حُفظ النزيل وسُجّل وصوله — الغرفة ' + data.room_number + ' صارت مشغولة ✓'
    : 'حُفظ الحجز، وتعذّر تسجيل الوصول: ' + cascade.error, !cascade.ok);
}

function wireSaveButtons(){
  Array.prototype.slice.call(document.querySelectorAll('.gr-btn')).forEach(function (btn) {
    var text = (btn.textContent || '').trim();
    if (/حفظ وتسجيل الدخول/.test(text)) {
      btn.addEventListener('click', function (e) { e.preventDefault(); saveGuest(true); });
    } else if (/حفظ كمسوّدة/.test(text)) {
      btn.addEventListener('click', function (e) { e.preventDefault(); saveGuest(false); });
    }
  });
}

document.addEventListener('DOMContentLoaded', function () {
  fixBirthDate();
  setupOptionalSections();
  setupExtension();
  wireSaveButtons();
  loadRooms();
});

// للاختبار من خارج المتصفح
window.RegistrationApp = {
  collect: collect, validate: validate, saveGuest: saveGuest,
  loadRooms: loadRooms, fixBirthDate: fixBirthDate,
  setupOptionalSections: setupOptionalSections, setupExtension: setupExtension,
  wireSaveButtons: wireSaveButtons
};

})();
