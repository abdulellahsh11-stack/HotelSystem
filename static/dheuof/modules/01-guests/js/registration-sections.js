// registration-sections.js — طيّ الأقسام · المرافقون · توقيع العقد وطباعته
//
// عالج خمس ملاحظاتٍ من التشغيل الفعلي:
//   ١ — الاستلام والتوصيل للمطار بلا زرّ إخفاء مثل قسم السائق
//   ٤ — تسجيل الدخول يمرّ دون توقيع العقد
//   ٥ — العقد غير قابل للطباعة
//   ٦ — بقيّة الأقسام غير قابلة للطي، والمرافقون لا يتبعون العدد المُدخَل
//
// نمط الطيّ هنا هو نمط قسم السائق نفسه (زرّ «إخفاء ▲» في العنوان يحفظ
// حالته في localStorage) — التوحيد أهون على المستخدم من ثلاثة أنماط.

(function () {
'use strict';

function q(sel, root){ return (root || document).querySelector(sel); }
function qq(sel, root){ return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

function toast(msg, isError){
  if (window.GR && window.GR.toast) { window.GR.toast(msg, isError); return; }
  (isError ? console.error : console.log)(msg);
}

/* ═══════════════════════════════════════════════
   ١ و٦ — كل قسم قابل للطي، بنمط قسم السائق
   القسم المطويّ يبقى في الصفحة ببياناته؛ الإخفاء عرضٌ لا حذف.
═══════════════════════════════════════════════ */
var STORE_PREFIX = 'gr-sec-hidden:';

function sectionKey(heading){
  // مفتاحٌ من نصّ العنوان: مستقرٌّ عبر إعادة الترتيب، ولا يحتاج تعديل HTML
  return (heading.textContent || '').replace(/[\s▲▼]+/g, ' ').trim().slice(0, 40);
}

function makeSectionCollapsible(heading){
  var section = heading.closest && heading.closest('.gr-sec');
  if (!section || section.dataset.collapsibleSec === '1') return;
  section.dataset.collapsibleSec = '1';

  // كل ما بعد العنوان يُلفّ في وعاءٍ واحد ليُخفى دفعةً واحدة
  var body = document.createElement('div');
  body.className = 'gr-sec-body';
  while (heading.nextSibling) body.appendChild(heading.nextSibling);
  section.appendChild(body);

  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'gr-sec-toggle';
  btn.style.cssText = 'float:inline-end;font-family:var(--font-ar);font-size:11px;'
    + 'padding:4px 12px;border:1px solid var(--ink-100);border-radius:6px;'
    + 'background:var(--paper);color:var(--fg-2);cursor:pointer;font-weight:600';

  var key = STORE_PREFIX + sectionKey(heading);

  function apply(hidden, persist){
    body.style.display = hidden ? 'none' : '';
    btn.textContent = hidden ? 'إظهار ▼' : 'إخفاء ▲';
    if (persist) {
      try { localStorage.setItem(key, hidden ? '1' : '0'); } catch (e) { /* وضع خاص */ }
    }
  }

  btn.addEventListener('click', function (e) {
    e.preventDefault();
    e.stopPropagation();
    apply(body.style.display !== 'none', true);
  });

  var saved = null;
  try { saved = localStorage.getItem(key); } catch (e) { /* وضع خاص */ }
  heading.appendChild(btn);
  apply(saved === '1', false);
}

function setupCollapsibleSections(){
  qq('.gr-sec > h4').forEach(makeSectionCollapsible);
}

/* ═══════════════════════════════════════════════
   ٦ — المرافقون يتبعون العدد المُدخَل
   كان عددهم ثابتاً في HTML. الآن حقلٌ يُنشئ الصفوف ويحذفها، مع الحفاظ
   على ما أُدخل في الصفوف الباقية — إعادة بنائها كلها تمحو عمل الموظف.
═══════════════════════════════════════════════ */
var COMP_COLS = 'auto 1fr 1fr 1fr 1fr 32px';
var AR_DIGITS = '٠١٢٣٤٥٦٧٨٩';

function arabicNum(n){
  return String(n).replace(/[0-9]/g, function (d) { return AR_DIGITS[d]; });
}

function companionRow(index){
  var row = document.createElement('div');
  row.className = 'gr-comp';
  row.style.gridTemplateColumns = COMP_COLS;
  row.innerHTML =
      '<div class="n">' + arabicNum(index) + '</div>'
    + '<div class="gr-field"><label>الاسم الأول</label><input /></div>'
    + '<div class="gr-field"><label>الاسم الأخير</label><input /></div>'
    + '<div class="gr-field"><label>رقم الهوية</label>'
      + '<input class="is-mono" placeholder="اختياري" dir="ltr" /></div>'
    + '<div class="gr-field"><label>رقم الجوال</label>'
      + '<input class="is-mono" dir="ltr" /></div>'
    + '<button class="x" type="button">✕</button>';
  return row;
}

function renumberCompanions(){
  var list = q('.gr-comp-list');
  if (!list) return;
  qq('.gr-comp', list).forEach(function (row, i) {
    var n = q('.n', row);
    if (n) n.textContent = arabicNum(i + 1);
  });
  var badge = q('.gr-sec h4 .badge');
  var heading = compHeading();
  if (heading) {
    badge = q('.badge', heading);
    var count = qq('.gr-comp', list).length;
    if (badge) badge.textContent = arabicNum(count) + ' مرافقين';
  }
}

function compHeading(){
  return qq('.gr-sec > h4').find(function (h) { return /المرافقون/.test(h.textContent); });
}

function syncCompanions(target){
  var list = q('.gr-comp-list');
  if (!list) return;
  var rows = qq('.gr-comp', list);
  var want = Math.max(0, Math.min(target, 20));   // عشرون مرافقاً حدٌّ عمليّ

  while (rows.length < want) {
    list.appendChild(companionRow(rows.length + 1));
    rows = qq('.gr-comp', list);
  }
  // الحذف من الآخِر: الصفوف الأولى غالباً هي المُعبَّأة
  while (rows.length > want) {
    list.removeChild(rows[rows.length - 1]);
    rows = qq('.gr-comp', list);
  }
  renumberCompanions();
}

function setupCompanions(){
  var heading = compHeading();
  var list = q('.gr-comp-list');
  if (!heading || !list || heading.dataset.compReady === '1') return;
  heading.dataset.compReady = '1';

  var wrap = document.createElement('span');
  wrap.style.cssText = 'display:inline-flex;align-items:center;gap:6px;'
    + 'margin-inline-start:12px;font-size:11px;font-weight:500;color:var(--fg-2)';

  var label = document.createElement('label');
  label.textContent = 'عدد المرافقين';
  label.htmlFor = 'comp-count';

  var input = document.createElement('input');
  input.type = 'number';
  input.id = 'comp-count';
  input.min = '0';
  input.max = '20';
  input.value = String(qq('.gr-comp', list).length);
  input.className = 'is-mono';
  input.style.cssText = 'width:64px;padding:3px 6px;border:1px solid var(--ink-100);'
    + 'border-radius:5px;text-align:center';

  input.addEventListener('input', function () {
    var n = parseInt(input.value, 10);
    if (isNaN(n)) return;             // أثناء المسح لا يُعاد البناء
    syncCompanions(n);
  });

  wrap.appendChild(label);
  wrap.appendChild(input);
  heading.appendChild(wrap);

  // زرّا الإضافة والحذف يبقيان عاملين، ويُبقيان الحقل متّسقاً معهما
  var addBtn = q('.gr-add-comp');
  if (addBtn) {
    addBtn.addEventListener('click', function (e) {
      e.preventDefault();
      syncCompanions(qq('.gr-comp', list).length + 1);
      input.value = String(qq('.gr-comp', list).length);
    });
  }
  list.addEventListener('click', function (e) {
    if (!e.target || !e.target.classList.contains('x')) return;
    e.preventDefault();
    var row = e.target.closest('.gr-comp');
    if (row) row.remove();
    renumberCompanions();
    input.value = String(qq('.gr-comp', list).length);
  });
}

/* ═══════════════════════════════════════════════
   ٤ — لا تسجيل دخول قبل توقيع العقد
   العقد الموقَّع بعد الدخول لا قيمة إثباتية له: النزيل صار في الغرفة
   قبل أن يلتزم بشيء. البوابة هنا في الواجهة، وهي تذكيرٌ إجرائي لا
   حارسٌ أمني — الحارس الحقيقي يجب أن يكون في الخادم.
═══════════════════════════════════════════════ */
var SIGNED = false;

function contractHeading(){
  return qq('.gr-sec > h4').find(function (h) { return /العقد/.test(h.textContent); });
}

function setSigned(state){
  SIGNED = !!state;
  var badge = q('#ct-sign-state');
  if (badge) {
    badge.textContent = SIGNED ? '✓ موقَّع' : '✗ غير موقَّع';
    badge.style.background = SIGNED ? 'var(--brand-100)' : '#FEE2E2';
    badge.style.color = SIGNED ? 'var(--brand-800)' : '#991B1B';
  }
  var box = q('#ct-signed');
  if (box) box.checked = SIGNED;
}

function isSigned(){ return SIGNED; }

function setupSignatureGate(){
  var heading = contractHeading();
  if (!heading || heading.dataset.signReady === '1') return;
  heading.dataset.signReady = '1';

  var badge = document.createElement('span');
  badge.id = 'ct-sign-state';
  badge.className = 'badge';
  badge.style.marginInlineStart = '8px';
  heading.appendChild(badge);

  // مربّع التوقيع يوضع قرب معاينة العقد لا في العنوان: التوقيع يقع بعد
  // قراءة البنود، فيكون المربّع حيث تنتهي القراءة.
  var side = q('.ct-doc-pv');
  if (side) {
    var wrap = document.createElement('label');
    wrap.style.cssText = 'display:flex;align-items:center;gap:8px;margin-top:10px;'
      + 'padding:9px 11px;border:1.5px solid var(--brand-300);border-radius:8px;'
      + 'background:var(--brand-50);cursor:pointer;font-size:12px;font-weight:600;'
      + 'color:var(--brand-800);font-family:var(--font-ar)';

    var box = document.createElement('input');
    box.type = 'checkbox';
    box.id = 'ct-signed';
    box.style.cssText = 'width:16px;height:16px;cursor:pointer';
    box.addEventListener('change', function () {
      setSigned(box.checked);
      toast(box.checked ? 'سُجّل توقيع النزيل على العقد ✓'
                        : 'أُلغي تسجيل التوقيع');
    });

    var text = document.createElement('span');
    text.textContent = 'أقرّ النزيل ووقّع على العقد';

    wrap.appendChild(box);
    wrap.appendChild(text);
    side.appendChild(wrap);
  }
  setSigned(false);
}

/* ═══════════════════════════════════════════════
   ٥ — طباعة العقد
   يُبنى مستندٌ من بنود العقد الفعلية وبيانات النزيل المُدخَلة، لا من
   المعاينة الزخرفية (أسطرٌ رمادية لا نصّ فيها).
═══════════════════════════════════════════════ */
function fieldValue(name){
  var el = q('[data-field="' + name + '"]');
  return el ? String(el.value || '').trim() : '';
}

function collectClauses(){
  return qq('.ct-cl').map(function (cl) {
    var title = q('.ttl-in', cl);
    var body = q('textarea', cl);
    var required = q('input[type="checkbox"]', cl);
    return {
      title: title ? title.value : '',
      body: body ? body.value : '',
      required: required ? required.checked : true
    };
  }).filter(function (c) { return c.title || c.body; });
}

function contractMeta(){
  var metaInputs = qq('.ct-meta input, .ct-meta select');
  var roomSel = q('#room-number-sel');
  var opt = roomSel && roomSel.selectedOptions && roomSel.selectedOptions[0];
  return {
    title: (metaInputs[0] && metaInputs[0].value) || 'عقد إقامة',
    law: (metaInputs[2] && metaInputs[2].value) || '',
    guest: (q('[data-name="ar"]') || {}).value || '—',
    idnum: fieldValue('idnum') || '—',
    room: (opt && opt.getAttribute('data-room')) || (opt && opt.textContent) || '—',
    checkin: fieldValue('checkin') || '—',
    checkout: fieldValue('checkout') || '—',
    total: (typeof window.GR_INV_TOTAL === 'number')
      ? window.GR_INV_TOTAL.toLocaleString('en-US', { minimumFractionDigits: 2 }) + ' ر.س'
      : '—'
  };
}

function escapeHtml(s){
  return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}

function buildContractHtml(){
  var m = contractMeta();
  var clauses = collectClauses();

  var rows = [
    ['اسم النزيل', m.guest], ['رقم الهوية', m.idnum], ['الغرفة', m.room],
    ['تاريخ الوصول', m.checkin], ['تاريخ المغادرة', m.checkout],
    ['المبلغ الإجمالي', m.total]
  ].map(function (r) {
    return '<tr><th>' + escapeHtml(r[0]) + '</th><td>' + escapeHtml(r[1]) + '</td></tr>';
  }).join('');

  var body = clauses.map(function (c, i) {
    return '<section class="cl"><h3>' + arabicNum(i + 1) + ' — ' + escapeHtml(c.title)
      + (c.required ? '' : ' <em>(اختياري)</em>') + '</h3><p>'
      + escapeHtml(c.body) + '</p></section>';
  }).join('');

  return '<!doctype html><html dir="rtl" lang="ar"><head><meta charset="utf-8">'
    + '<title>' + escapeHtml(m.title) + '</title><style>'
    + 'body{font-family:"Segoe UI",Tahoma,sans-serif;line-height:1.85;color:#111;'
    + 'max-width:780px;margin:0 auto;padding:32px}'
    + 'h1{font-size:21px;margin:0 0 4px;text-align:center}'
    + '.sub{text-align:center;color:#666;font-size:12px;margin-bottom:20px}'
    + 'table{width:100%;border-collapse:collapse;margin-bottom:22px;font-size:13px}'
    + 'th,td{border:1px solid #ccc;padding:7px 10px;text-align:right}'
    + 'th{background:#f4f4f4;width:32%;font-weight:600}'
    + '.cl{margin-bottom:14px;page-break-inside:avoid}'
    + '.cl h3{font-size:14px;margin:0 0 3px}'
    + '.cl p{margin:0;font-size:13px;text-align:justify}'
    + '.sig{display:flex;gap:40px;margin-top:44px;page-break-inside:avoid}'
    + '.sb{flex:1;text-align:center}'
    + '.line{border-top:1px solid #333;margin-top:52px;padding-top:6px;font-size:12px}'
    + '@media print{body{padding:0}@page{margin:18mm}}'
    + '</style></head><body>'
    + '<h1>' + escapeHtml(m.title) + '</h1>'
    + '<div class="sub">' + escapeHtml(m.law) + '</div>'
    + '<table>' + rows + '</table>'
    + body
    + '<div class="sig"><div class="sb"><div class="line">توقيع النزيل</div></div>'
    + '<div class="sb"><div class="line">ختم الفندق</div></div></div>'
    + '</body></html>';
}

function printContract(){
  var win = window.open('', '_blank');
  if (!win) { toast('منَع المتصفّح فتح نافذة الطباعة — اسمح بالنوافذ المنبثقة', true); return; }
  win.document.write(buildContractHtml());
  win.document.close();
  win.focus();
  // الانتظار حتى يُرسَم المستند: الطباعة الفورية تُخرج صفحةً فارغة
  setTimeout(function () { try { win.print(); } catch (e) { /* أُغلقت */ } }, 250);
}

function setupContractPrint(){
  qq('.pv-actions .ck-mini').forEach(function (btn) {
    var text = (btn.textContent || '').trim();
    if (/طباعة/.test(text)) {
      btn.addEventListener('click', function (e) { e.preventDefault(); printContract(); });
    } else if (/معاينة/.test(text)) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        var win = window.open('', '_blank');
        if (!win) { toast('منَع المتصفّح فتح النافذة', true); return; }
        win.document.write(buildContractHtml());
        win.document.close();
      });
    }
  });
}

/* ═══════════════════════════════════════════════
   العقد والرسائل تتبع بيانات النزيل الفعلية

   كان نصّ العقد يقول «إقامة ٣ ليالٍ في الجناح الملكي ٤٠٢ بسعر ٢٬٤٠٠»
   ورسائل SMS تقول «عميلنا العزيز أحمد» — مهما أدخل الموظف. فيُرسَل عقدٌ
   باسم شخصٍ آخر وغرفةٍ أخرى ومبلغٍ آخر، ويُوقَّع.

   حقول الدمج `{{اسم_النزيل}}` كانت وسوماً زخرفية معروضة للعين ولا يملؤها
   شيء. الآن تُملأ فعلاً — ومن يُعدّل نصّاً بيده لا يُكتب فوقه.
═══════════════════════════════════════════════ */
function liveContractData(){
  var sel = q('#room-number-sel');
  var opt = sel && sel.selectedOptions && sel.selectedOptions[0];
  var nights = parseInt(fieldValue('nights'), 10);
  var rate = 0;
  if (opt) rate = Number(opt.getAttribute('data-price')) || 0;
  return {
    name: (q('[data-name="ar"]') || {}).value || '',
    room: (opt && opt.getAttribute('data-room')) || '',
    roomType: (opt && opt.getAttribute('data-type')) || '',
    nights: (isNaN(nights) || nights < 1) ? 1 : nights,
    rate: rate,
    total: Number(window.GR_INV_TOTAL || 0),
    checkin: fieldValue('checkin'),
    checkout: fieldValue('checkout')
  };
}

function money(n){
  return Number(n || 0).toLocaleString('ar-SA', { minimumFractionDigits: 2 }) + ' ر.س';
}

function refreshContractText(){
  var d = liveContractData();
  if (!d.name && !d.room) return;      // نموذجٌ فارغ — لا تُبدَّل النصوص

  var stay = q('#ct-clause-stay');
  // `data-auto` يسقط أول ما يُعدّل الموظف النصّ بيده: الكتابة فوق تعديله
  // إهدارٌ لعمله وإرباك.
  if (stay && stay.dataset.auto === 'stay') {
    var roomLabel = d.room ? ('الغرفة رقم ' + d.room + (d.roomType ? ' (' + d.roomType + ')' : ''))
                           : 'الغرفة المتفق عليها';
    stay.value = 'يتفق الطرفان على إقامة مدتها ' + d.nights + ' ليالٍ في '
      + roomLabel + (d.rate ? ' بسعر ' + money(d.rate) + '/ليلة' : '')
      + (d.checkin ? '، من ' + d.checkin : '')
      + (d.checkout ? ' إلى ' + d.checkout : '')
      + '، شاملاً ضريبة القيمة المضافة وضريبة السياحة.';
    stay.addEventListener('input', function once(){
      stay.dataset.auto = 'manual';
      stay.removeEventListener('input', once);
    });
  }

  var title = q('#ct-title');
  if (title && !title.dataset.touched) {
    title.value = 'عقد إقامة' + (d.name ? ' — ' + d.name : '')
                + (d.room ? ' · غرفة ' + d.room : '');
    title.addEventListener('input', function once(){
      title.dataset.touched = '1';
      title.removeEventListener('input', once);
    });
  }

  var first = (d.name || '').split(' ')[0];
  var signLine = q('#sms-sign-line');
  if (signLine && first) {
    signLine.textContent = 'عميلنا العزيز ' + first + '، يُرجى مراجعة وتوقيع عقد إقامتك:';
  }
  var payLine = q('#sms-pay-line');
  if (payLine && first) {
    payLine.textContent = 'عميلنا العزيز ' + first + '، رابط دفع آمن'
      + (d.total ? ' بمبلغ ' + money(d.total) : '') + ':';
  }
}

function watchContractInputs(){
  ['[data-name="ar"]', '#room-number-sel', '[data-field="nights"]',
   '[data-field="checkin"]', '[data-field="checkout"]'].forEach(function (sel) {
    var el = q(sel);
    if (!el) return;
    el.addEventListener('input', refreshContractText);
    el.addEventListener('change', refreshContractText);
  });
  // الفاتورة تُعلن إجماليها، فيتبعه نصّ رسالة الدفع
  var prev = window.GR_onInvoiceTotal;
  window.GR_onInvoiceTotal = function (t) {
    if (typeof prev === 'function') { try { prev(t); } catch (e) { /* لا يُوقف */ } }
    refreshContractText();
  };
  refreshContractText();
}


/* ═══════════════════════════════════════════════
   التصدير
═══════════════════════════════════════════════ */
function init(){
  setupCollapsibleSections();
  setupCompanions();
  setupSignatureGate();
  setupContractPrint();
  watchContractInputs();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

window.RegistrationSections = {
  isSigned: isSigned, setSigned: setSigned,
  syncCompanions: syncCompanions, printContract: printContract,
  buildContractHtml: buildContractHtml, collectClauses: collectClauses,
  setupCollapsibleSections: setupCollapsibleSections,
  setupCompanions: setupCompanions, init: init,
  refreshContractText: refreshContractText, liveContractData: liveContractData
};

})();
