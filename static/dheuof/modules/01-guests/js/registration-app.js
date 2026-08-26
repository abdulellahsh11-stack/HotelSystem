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
          var price = Number(r.base_price || 0);
          return '<option value="' + r.id + '" data-room="' + r.room_number + '"'
               + ' data-price="' + price + '" data-type="' + (t || '') + '">'
               + r.room_number + (t ? ' — ' + t : '') + '</option>';
        }).join('');
      return '<optgroup label="' + label + '">' + opts + '</optgroup>';
    }).join('');
  computeInvoice();   // السعر الحقيقي للغرفة المختارة يدخل الفاتورة فور تحميلها
}

/* ═══════════════════════════════════════════════
   الفاتورة الحيّة — تتحدّث مع كل مُدخَل
   كانت أرقاماً ثابتة (٧٧٤٠) لا تتأثر بالغرفة ولا الليالي ولا الوجبات.
   هنا تُحسب من: سعر الغرفة × الليالي + الوجبة × الأيام × النزلاء.
   منطق الضرائب يبقى في registration-form.js؛ نحن نُغذّيه بالأساس فقط.
═══════════════════════════════════════════════ */

// أسعار احتياطية بالريال حين لا يأتي سعرٌ من سجلّ الغرف (خيارات العرض
// قبل تحميل /api/rooms). الغرفة الحقيقية تُقدَّم دائماً بسعرها المسجَّل.
var FALLBACK_ROOM_PRICE = [
  { re: /ملكي|royal/i, price: 2400 },
  { re: /جناح|suite/i, price: 1200 },
  { re: /ديلوكس|deluxe/i, price: 720 },
  { re: /ستاندرد|standard/i, price: 480 }
];

// سعر الوجبة للفرد في اليوم، حسب خطة الوجبات.
var MEAL_RATE = [
  { re: /بدون فطور|room only/i, rate: 0, name: 'بدون وجبات' },
  { re: /نصف إقامة|half board/i, rate: 120, name: 'نصف إقامة' },
  { re: /كاملة|full board/i, rate: 180, name: 'إقامة كاملة' },
  { re: /شامل كل شيء|all inclusive/i, rate: 250, name: 'شامل كل شيء' },
  { re: /فطور|breakfast/i, rate: 60, name: 'فطور' }
];

function toArabicNum(n){
  var s = Number(n || 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, '٬').replace('.', '٫');
  return s.replace(/[0-9]/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'[d]; });
}

function intVal(name, dflt){
  var v = parseInt(val(name), 10);
  return (isNaN(v) || v < 1) ? dflt : v;
}

function roomPrice(){
  var sel = q('#room-number-sel');
  var opt = sel && sel.selectedOptions && sel.selectedOptions[0];
  if (opt) {
    var p = Number(opt.getAttribute('data-price'));
    if (p > 0) return p;
  }
  var typeSel = q('#room-type-sel');
  var text = (typeSel && typeSel.value) || (opt && opt.textContent) || '';
  var hit = FALLBACK_ROOM_PRICE.find(function (m) { return m.re.test(text); });
  return hit ? hit.price : 480;
}

function mealRate(){
  var sel = q('#meal-plan-sel');
  var text = (sel && sel.value) || '';
  var hit = MEAL_RATE.find(function (m) { return m.re.test(text); });
  return hit || { rate: 0, name: 'بدون وجبات' };
}

function computeInvoice(){
  if (!q('#inv-subtotal')) return;   // لا فاتورة في هذه الصفحة
  var nights = intVal('nights', 1);
  var guests = intVal('guests', 1);
  var rp = roomPrice();
  var meal = mealRate();

  var roomTotal = rp * nights;
  var mealTotal = meal.rate * nights * guests;

  var roomLabel = q('#inv-room-label');
  var opt = (q('#room-number-sel') || {}).selectedOptions;
  var typeName = (opt && opt[0] && opt[0].getAttribute('data-type'))
              || (q('#room-type-sel') && q('#room-type-sel').value) || '';
  if (roomLabel) {
    roomLabel.textContent = 'سعر الغرفة × ' + toArabicNum(nights).replace('٫٠٠', '')
      + ' ليالٍ' + (typeName ? ' (' + typeName + ')' : '');
  }
  var roomAmt = q('#inv-room-amt');
  if (roomAmt) roomAmt.textContent = toArabicNum(roomTotal);

  var mealRow = q('#inv-meal-row');
  var mealLabel = q('#inv-meal-label');
  var mealAmt = q('#inv-meal-amt');
  if (meal.rate <= 0) {
    if (mealRow) mealRow.style.display = 'none';
  } else {
    if (mealRow) mealRow.style.display = '';
    if (mealLabel) {
      mealLabel.textContent = meal.name + ' × ' + toArabicNum(nights).replace('٫٠٠', '')
        + ' أيام × ' + toArabicNum(guests).replace('٫٠٠', '') + ' أشخاص';
    }
    if (mealAmt) mealAmt.textContent = toArabicNum(mealTotal);
  }

  // الاستلام والتوصيل للمطار — يدخلان الفاتورة فعلاً.
  //
  // كان القسم يعرض «+٢٢٠ ر.س» بجانب كل اتجاه ولا يضيفهما إلى شيء:
  // يُعلّم الموظف الاتجاهين فيرى وعداً بالسعر، ويخرج النزيل بفاتورةٍ
  // لا تحوي النقل. والمنشأة تخسره صامتاً في كل حجز.
  var transferTotal = 0;
  var legs = [];
  [['#ap-arrival', 'استلام من المطار'], ['#ap-departure', 'توصيل إلى المطار']]
    .forEach(function (pair) {
      var box = q(pair[0]);
      if (box && box.checked) {
        transferTotal += Number(box.getAttribute('data-price')) || 0;
        legs.push(pair[1]);
      }
    });
  var trRow = q('#inv-transfer-row');
  if (trRow) {
    if (transferTotal > 0) {
      trRow.style.display = 'flex';
      var trLabel = q('#inv-transfer-label');
      if (trLabel) trLabel.textContent = legs.join(' + ');
      var trAmt = q('#inv-transfer-amt');
      if (trAmt) trAmt.textContent = toArabicNum(transferTotal);
    } else {
      trRow.style.display = 'none';
    }
  }

  var base = roomTotal + mealTotal + transferTotal;
  var sub = q('#inv-subtotal');
  if (sub) sub.textContent = toArabicNum(base);

  window.GR_INV_BASE = base;
  if (typeof window.recalcInvoice === 'function') window.recalcInvoice();
  updateSettlement();
}

/* التسوية النهائية = الإجمالي − الدفعات المُدخَلة قبلها.
   الدفعات المبكرة يُدخلها الموظف؛ الصفّ الأخير يُحسب لا يُكتب يدوياً. */
function updateSettlement(){
  var rows = Array.prototype.slice.call(document.querySelectorAll('.pay-row'));
  if (rows.length < 2) return;
  var total = Number(window.GR_INV_TOTAL || 0);
  if (!total) return;

  function amtInput(row){ return row.querySelector('.amt input'); }
  function num(inp){ return inp ? Number(String(inp.value).replace(/[^\d.]/g, '')) || 0 : 0; }

  var prior = 0;
  for (var i = 0; i < rows.length - 1; i++) prior += num(amtInput(rows[i]));

  var last = amtInput(rows[rows.length - 1]);
  if (!last) return;
  var settle = total - prior;
  last.value = Math.max(0, settle).toLocaleString('en-US',
    { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  // الدفعات المبكرة قد تتجاوز الإجمالي بعد تقصير الإقامة أو تغيير الغرفة.
  // إظهار «٠٫٠٠» وحده يُخفي الفائض ويبدو كأن الحساب مضبوط.
  var warn = q('#pay-overpaid');
  if (!warn) {
    warn = document.createElement('div');
    warn.id = 'pay-overpaid';
    warn.style.cssText = 'margin-top:8px;padding:8px 12px;border-radius:6px;'
      + 'background:#FEF3C7;color:#92400E;border:1px solid #FCD34D;'
      + 'font-size:12px;font-weight:600;font-family:var(--font-ar)';
    var list = q('.pay-rows');
    if (list && list.parentElement) list.parentElement.insertBefore(warn, list.nextSibling);
  }
  if (settle < -0.005) {
    warn.style.display = '';
    warn.textContent = 'الدفعات المُدخَلة تتجاوز الإجمالي بمقدار '
      + Math.abs(settle).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      + ' ر.س — راجع الدفعات أو استرد الفرق للنزيل';
  } else {
    warn.style.display = 'none';
  }
}

function wireInvoiceInputs(){
  ['#room-number-sel', '#room-type-sel', '#meal-plan-sel'].forEach(function (s) {
    var el = q(s); if (el) el.addEventListener('change', computeInvoice);
  });
  ['nights', 'guests', 'checkin', 'checkout'].forEach(function (f) {
    var el = field(f);
    if (el) { el.addEventListener('input', computeInvoice); el.addEventListener('change', computeInvoice); }
  });
  // مربّعا المطار يدخلان الحساب فور تعليمهما
  ['#ap-arrival', '#ap-departure'].forEach(function (s) {
    var el = q(s); if (el) el.addEventListener('change', computeInvoice);
  });

  // الدفعات: الاستماع على الحاوية لا على كل حقل.
  //
  // كان الربط يُعلَّق على الصفوف الموجودة وقت التحميل، فأي دفعةٍ تُضاف
  // بـ«+ إضافة دفعة» تُولد **بلا ربط**: يكتب فيها الموظف مبلغاً فلا
  // تتغيّر التسوية ولا الإجمالي. الاستماع على الحاوية يشمل ما لم يُخلق بعد.
  var payList = q('.pay-rows');
  if (payList) {
    payList.addEventListener('input', function (e) {
      if (e.target && e.target.closest('.amt')) updateSettlement();
    });
    // الحذف يغيّر الصفّ الأخير — فتُعاد التسوية بعد أن يستقرّ الحذف
    payList.addEventListener('click', function (e) {
      if (e.target && e.target.classList.contains('x')) setTimeout(updateSettlement, 0);
    });
    // إضافة صفٍّ جديد تُعيد الحساب أيضاً
    var addBtn = q('.pay-add');
    if (addBtn) addBtn.addEventListener('click', function () { setTimeout(updateSettlement, 0); });
  }
  computeInvoice();
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
   ٣ و٤ — حقل الوجبات الاختياري
   القسم المفتوح دائماً يوحي بأنه مطلوب. طيّ الأقسام كلها في
   registration-sections.js؛ هنا حقل الوجبات وحده.
═══════════════════════════════════════════════ */
function setupOptionalSections(){
  // طيّ الأقسام كلها (المطار منها) صار في registration-sections.js بنمط
  // زرّ قسم السائق الموحَّد. يبقى هنا طيُّ حقل الوجبات وحده — وهو حقل
  // داخل قسمٍ أكبر لا قسمٌ قائم بذاته.
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

  // العقد يُوقَّع قبل تسجيل الدخول لا بعده: نزيلٌ دخل غرفته قبل أن
  // يلتزم بشيء يجعل العقد ورقةً بلا أثر. الحفظ كمسوّدة يبقى متاحاً.
  var sections = window.RegistrationSections;
  if (alsoCheckIn && sections && !sections.isSigned()) {
    toast('وقّع العقد قبل تسجيل الدخول — علّم «أقرّ النزيل ووقّع على العقد» في قسم العقد', true);
    var mark = q('#ct-signed');
    if (mark && mark.scrollIntoView) mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return;
  }

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

  // المبالغ تُرسَل مع الحجز.
  //
  // كانت الفاتورة تُحسب على الشاشة ثم تُرمى: الحجز يُنشأ بلا سعرٍ ولا
  // ضرائب ولا إجمالي، فيُقيَّد إيراداً صفراً وتبقى المحاسبة فارغة مهما
  // سجّل الاستقبال من نزلاء. الأعمدة موجودة في الجدول منذ البداية —
  // الصفحة وحدها لم تكن تملؤها.
  var nights = intVal('nights', 1);
  var totalWithTax = Number(window.GR_INV_TOTAL || 0);
  var roomOnly = roomPrice() * nights;

  var booking = await send('/api/bookings', {
    method: 'POST',
    body: JSON.stringify({
      guest_id: guestId,
      room_id: data.room_id,
      room_number: data.room_number,
      check_in: data.check_in,
      check_out: data.check_out,
      nights: nights,
      guests_count: intVal('guests', 1),
      nightly_rate: roomPrice(),
      total_room: roomOnly,
      total_amount: totalWithTax,
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

  // المبلغ المدفوع عند الوصول يُرسَل مع تسجيل الدخول، وإلا قُيّد إيراداً
  // صفراً: السلسلة تُنشئ قيداً محاسبياً بما يصلها لا بما على الشاشة.
  var paidNow = 0;
  var firstPay = q('.pay-row .amt input');
  if (firstPay) paidNow = Number(String(firstPay.value).replace(/[^\d.]/g, '')) || 0;

  var cascade = await send('/api/integration/checkin', {
    method: 'POST',
    body: JSON.stringify({
      booking_id: bookingId,
      amount: paidNow || totalWithTax,
      payment_method: 'cash',
      checkin_by: 'استقبال'
    })
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
  wireInvoiceInputs();
  loadRooms();
});

// للاختبار من خارج المتصفح
window.RegistrationApp = {
  collect: collect, validate: validate, saveGuest: saveGuest,
  loadRooms: loadRooms, fixBirthDate: fixBirthDate,
  setupOptionalSections: setupOptionalSections, setupExtension: setupExtension,
  wireSaveButtons: wireSaveButtons,
  computeInvoice: computeInvoice, updateSettlement: updateSettlement,
  roomPrice: roomPrice, mealRate: mealRate
};

})();
