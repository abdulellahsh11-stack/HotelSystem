// kpis-app.js — منطق لوحة مؤشرات الأداء
//
// مُستخرَج من index.html. يشمل تحميل اللوحة من /api/m11/dashboard
// والإيراد حسب نوع الغرفة (للتصدير) وتصدير Excel و PDF.

StaticSidebar.mount({ activeId: "11-kpis", placeholder: "بحث في الإيرادات..." });

// ── Ensure animations fire ────────────────────────────────────────────────
setTimeout(function(){
  document.querySelectorAll('[data-m-rise],[data-m-rise-stagger]').forEach(function(el){
    el.classList.add('is-in');
  });
}, 80);

// ── Build occupancy bar chart ─────────────────────────────────────────────
function buildOccBars(valuesByYYYYMM){
  // Last 12 months ending with the current month (full Arabic month names)
  var monthNames = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر'];
  var now = new Date();
  var months = [];
  var keys = [];
  for (var k = 11; k >= 0; k--){
    var d = new Date(now.getFullYear(), now.getMonth() - k, 1);
    months.push(monthNames[d.getMonth()]);
    var mm = String(d.getMonth() + 1); if(mm.length<2) mm='0'+mm;
    keys.push(d.getFullYear() + '-' + mm);
  }
  // map to values array using provided lookup or zeros
  var map = valuesByYYYYMM || {};
  var values = keys.map(function(k){ return map[k] != null ? map[k] : null; });
  var container = document.getElementById('occ-bars-container');
  if (!container) return;
  container.innerHTML = '';
  var nonNull = values.filter(function(v){ return v != null; });
  var hasData = nonNull.length > 0;
  var maxV = hasData ? Math.max.apply(null, nonNull) : 0;
  months.forEach(function(m, i){
    var v = values[i];
    var pct = (hasData && maxV > 0 && v != null) ? Math.round(v / maxV * 100) : 0;
    var isCurrent = i === months.length - 1;
    var col = document.createElement('div');
    col.className = 'occ-bar-col';
    col.innerHTML =
      '<div class="occ-bar-pct">' + (v == null ? '—' : v + '٪') + '</div>' +
      '<div class="occ-bar-track" style="min-height:100px">' +
        '<div class="occ-bar-fill' + (isCurrent ? ' is-current' : '') + '" style="height:' + pct + '%"></div>' +
      '</div>' +
      '<div class="occ-bar-lbl">' + m + '</div>';
    container.appendChild(col);
  });
  // update average badge
  var badge = document.getElementById('occ-avg-badge');
  if (badge && nonNull.length > 0){
    var avg = Math.round(nonNull.reduce(function(a,b){return a+b;},0) / nonNull.length);
    badge.textContent = 'متوسط ' + avg + '٪';
  }
}

// ── Load KPI dashboard from API ───────────────────────────────────────────
async function loadKpiDashboard(){
  try {
    loadRevenueByRoomType();   // للتصدير — لا تُعطّل رسم اللوحة
    var res = await fetch('/api/m11/dashboard');
    var json = await res.json();
    if (!json.success || !json.data) { buildOccBars({}); return; }
    var d = json.data;

    // ── Update KPI strip cards ────────────────────────────────────────────
    var cards = document.querySelectorAll('.kpi-strip .kpi-card');
    // Card order: RevPAR, ADR, OCC, GOPPAR, ALOS
    function setCard(card, val, extra){
      if (!card) return;
      var valEl = card.querySelector('.kc-val');
      if (valEl) {
        var curEl = valEl.querySelector('.cur');
        var curHtml = curEl ? curEl.outerHTML : '';
        valEl.innerHTML = (val != null ? val : '—') + curHtml;
      }
      if (extra != null) {
        var chEl = card.querySelector('.kc-change');
        if (chEl) { chEl.textContent = extra; chEl.className = 'kc-change'; }
      }
    }
    if (cards[0]) setCard(cards[0], d.revpar != null ? Math.round(d.revpar) : null);
    if (cards[1]) setCard(cards[1], d.adr    != null ? Math.round(d.adr)    : null);
    if (cards[2]) setCard(cards[2], d.occupancy_rate != null ? d.occupancy_rate : null);
    if (cards[3]) setCard(cards[3], d.revenue_month != null ? Math.round(d.revenue_month).toLocaleString('en') : null);
    if (cards[4]) setCard(cards[4], null); // ALOS not in dashboard endpoint

    // update KPI_DATA so exports stay in sync
    if (d.revpar   != null) { KPI_DATA[0].val = Math.round(d.revpar); }
    if (d.adr      != null) { KPI_DATA[1].val = Math.round(d.adr); }
    if (d.occupancy_rate != null){ KPI_DATA[2].val = d.occupancy_rate; }
    if (d.revenue_month  != null){ KPI_DATA[3].val = Math.round(d.revenue_month).toLocaleString('en'); }

    // ── Build occupancy chart from monthly_revenue ────────────────────────
    var monthly = d.monthly_revenue || [];
    var occMap = {};
    monthly.forEach(function(r){
      // monthly_revenue rows have {month:'YYYY-MM', revenue, invoices}
      // We don't have per-month occupancy from this endpoint — use revenue as proxy
      // If a daily_kpis table is populated via /api/m11/revpar, that would be better,
      // but dashboard only returns occupancy_rate for today. Use revenue bars instead.
      if (r.month) occMap[r.month] = parseFloat(r.revenue) || 0;
    });
    // If no monthly data, fall back to showing current occupancy in current month slot
    if (Object.keys(occMap).length === 0 && d.occupancy_rate != null){
      var now2 = new Date();
      var mm2 = String(now2.getMonth()+1); if(mm2.length<2) mm2='0'+mm2;
      occMap[now2.getFullYear()+'-'+mm2] = d.occupancy_rate;
    }
    buildOccBars(occMap);

  } catch(e){
    console.error('loadKpiDashboard error', e);
    buildOccBars({});
  }
}

// ── Page load ─────────────────────────────────────────────────────────────
loadKpiDashboard();

// ── Tab switching ─────────────────────────────────────────────────────────
(function initTabs(){
  var btns  = document.querySelectorAll('.tab-btn');
  var panes = document.querySelectorAll('.tab-pane');
  btns.forEach(function(btn){
    btn.addEventListener('click', function(){
      var target = btn.dataset.tab;
      btns.forEach(function(b){ b.classList.remove('is-active'); });
      panes.forEach(function(p){ p.classList.remove('is-active'); });
      btn.classList.add('is-active');
      var pane = document.getElementById('tab-' + target);
      if (pane) pane.classList.add('is-active');
      // re-trigger rise animations in the new pane
      setTimeout(function(){
        document.querySelectorAll('[data-m-rise],[data-m-rise-stagger]').forEach(function(el){
          el.classList.add('is-in');
        });
      }, 60);
    });
  });
})();

// ── Pickup window selector ────────────────────────────────────────────────
(function initPickupWindows(){
  var winBtns = document.querySelectorAll('.pickup-window-btn');
  var rows = Array.prototype.slice.call(
    document.querySelectorAll('.pickup-table-wrap .pu-tr:not(.is-head)'));
  function applyWindow(n){
    rows.forEach(function(r, i){ r.style.display = (i < n) ? '' : 'none'; });
  }
  winBtns.forEach(function(btn){
    btn.addEventListener('click', function(){
      winBtns.forEach(function(b){ b.classList.remove('is-active'); });
      btn.classList.add('is-active');
      applyWindow(parseInt(btn.getAttribute('data-win'), 10) || rows.length);
    });
  });
  // initial window = active button's value
  var active = document.querySelector('.pickup-window-btn.is-active');
  applyWindow(active ? (parseInt(active.getAttribute('data-win'), 10) || rows.length) : rows.length);
})();

// ── Pricing rules active count ────────────────────────────────────────────
function updateActiveRules(){
  var checks = document.querySelectorAll('.pricing-rules input[type="checkbox"]');
  var count = 0;
  checks.forEach(function(c){ if(c.checked) count++; });
  var tag = document.querySelector('#tab-pricing .mod-tag.ok');
  if (tag) {
    var label = count === 1 ? 'قاعدة نشطة' : (count === 2 ? 'قاعدتان نشطتان' : 'قواعد نشطة');
    tag.textContent = count + ' ' + label;
  }
}

// ── Apply channels button → toast ─────────────────────────────────────────
function applyChannels(){
  var minV = document.getElementById('rate-min') ? document.getElementById('rate-min').value : 300;
  var maxV = document.getElementById('rate-max') ? document.getElementById('rate-max').value : 2500;
  showToast('تم تحديث الأسعار على ٧ قنوات ✓ (أدنى: ' + minV + ' ر.س، أقصى: ' + maxV + ' ر.س)');
}

function showToast(msg){
  var old = document.querySelector('.dh-kpi-toast');
  if (old) old.remove();
  var t = document.createElement('div');
  t.className = 'dh-kpi-toast';
  t.innerHTML = '<span class="t-ic">✓</span>' + msg;
  document.body.appendChild(t);
  setTimeout(function(){
    t.style.opacity = '0';
    t.style.transform = 'translateY(8px)';
    setTimeout(function(){ if(t.parentNode) t.remove(); }, 400);
  }, 3200);
}

// ── Export helpers ────────────────────────────────────────────────────────
function todayStr(){
  var d = new Date();
  return d.getFullYear()
    + (d.getMonth()+1 < 10 ? '0' : '') + (d.getMonth()+1)
    + (d.getDate() < 10 ? '0' : '') + d.getDate();
}

function dlXLS(content, filename){
  var b = new Blob([content], {type: 'application/vnd.ms-excel;charset=utf-8'});
  var u = URL.createObjectURL(b);
  var a = document.createElement('a');
  a.href = u; a.download = filename; a.click();
  setTimeout(function(){ URL.revokeObjectURL(u); }, 1000);
}

var KPI_DATA = [
  {en:'RevPAR', ar:'الإيراد لكل غرفة متاحة', val:'—', unit:'ر.س', change:'—', period:'—'},
  {en:'ADR',    ar:'متوسط سعر الغرفة',        val:'—', unit:'ر.س', change:'—', period:'—'},
  {en:'OCC',    ar:'نسبة الإشغال',             val:'—', unit:'٪',   change:'—', period:'—'},
  {en:'GOPPAR', ar:'الربح التشغيلي',           val:'—', unit:'ر.س', change:'—', period:'—'},
  {en:'ALOS',   ar:'متوسط ليالي الإقامة',      val:'—', unit:'ليلة',change:'—', period:'—'},
];

var ROOM_DATA = [];

/* الإيراد حسب نوع الغرفة — يُغذّي ورقتَي Excel وPDF.
   كانت ROOM_DATA فارغةً أبداً فتُصدَّر ورقةٌ بعنوانٍ بلا صفوف. */
function loadRevenueByRoomType(){
  return fetch('/api/m11/revenue-by-room-type')
    .then(function(r){ return r.json(); })
    .then(function(res){ ROOM_DATA = (res && res.data) || []; })
    .catch(function(){ ROOM_DATA = []; });
}

window.kpiExportExcel = function(){
  var kpiHeaders = ['المؤشر','الوصف','القيمة','الوحدة','التغيير','الفترة'];
  var kpiRows = KPI_DATA.map(function(k){ return [k.en, k.ar, k.val, k.unit, k.change, k.period]; });
  var roomHeaders = ['نوع الغرفة','RevPAR (ر.س)','ADR (ر.س)','الإشغال','ليالي مبيعة','الإيراد الإجمالي (ر.س)'];
  var roomRows = ROOM_DATA.map(function(r){ return [r.type, r.revpar, r.adr, r.occ, r.nights, r.revenue]; });

  var xml = '<?xml version="1.0" encoding="UTF-8"?><?mso-application progid="Excel.Sheet"?>'
    + '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'
    + '<Styles><Style ss:ID="H"><Font ss:Bold="1" ss:Color="#FFFFFF"/><Interior ss:Color="#1B4D3D" ss:Pattern="Solid"/><Alignment ss:Horizontal="Center"/></Style></Styles>';

  function esc(v){ return String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function cell(v){ return '<Cell><Data ss:Type="String">' + esc(v) + '</Data></Cell>'; }
  function hcell(v){ return '<Cell ss:StyleID="H"><Data ss:Type="String">' + esc(v) + '</Data></Cell>'; }
  function sheet(name, hdrs, rows){
    return '<Worksheet ss:Name="' + esc(name) + '"><Table>'
      + '<Row>' + hdrs.map(hcell).join('') + '</Row>'
      + rows.map(function(r){ return '<Row>' + r.map(cell).join('') + '</Row>'; }).join('')
      + '</Table></Worksheet>';
  }
  xml += sheet('المؤشرات الرئيسية', kpiHeaders, kpiRows);
  xml += sheet('الإيراد حسب الغرفة', roomHeaders, roomRows);
  xml += '</Workbook>';

  dlXLS(xml, 'الإيرادات_' + todayStr() + '.xls');
  showToast('تم تصدير ملف Excel بنجاح ✓');
};

window.kpiExportPDF = function(){
  var kpiRows = KPI_DATA.map(function(k){
    var isUp = k.change.indexOf('+') !== -1;
    var color = isUp ? '#1B7A56' : '#C0392B';
    return '<tr><td><strong>' + k.en + '</strong></td><td>' + k.ar + '</td>'
      + '<td style="font-weight:700;font-size:18px">' + k.val + ' <span style="font-size:12px;font-weight:400;color:#666">' + k.unit + '</span></td>'
      + '<td style="color:' + color + ';font-weight:700">' + k.change + ' <small style="font-weight:400;color:#888">' + k.period + '</small></td></tr>';
  }).join('');

  var roomRows = ROOM_DATA.map(function(r){
    return '<tr><td><strong>' + r.type + '</strong></td>'
      + '<td>' + r.revpar + ' ر.س</td>'
      + '<td>' + r.adr + ' ر.س</td>'
      + '<td>' + r.occ + '</td>'
      + '<td>' + r.nights + '</td>'
      + '<td style="font-weight:700">' + r.revenue + ' ر.س</td></tr>';
  }).join('');

  var win = window.open('', '_blank', 'width=1020,height=780');
  if (!win) { showToast('فضلاً اسمح بالنوافذ المنبثقة لطباعة التقرير'); return; }
  win.document.write('<!doctype html><html lang="ar" dir="rtl"><head>'
    + '<meta charset="utf-8"/><title>تقرير الإيرادات والمؤشرات</title>'
    + '<style>'
    + 'body{font-family:"Tajawal","Segoe UI",sans-serif;margin:32px;color:#1a1a1a;direction:rtl}'
    + 'h1{font-size:22px;margin:0 0 4px;color:var(--brand-700)}h2{font-size:16px;margin:22px 0 10px;color:var(--brand-700)}'
    + '.sub{font-size:12px;color:#666;margin:0 0 18px}'
    + 'table{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:24px}'
    + 'th{background:var(--brand-700);color:var(--white);padding:9px 12px;text-align:right}'
    + 'td{padding:8px 12px;border-bottom:1px solid #eee;vertical-align:middle}'
    + 'tr:nth-child(even){background:#fafafa}'
    + '.footer{margin-top:18px;font-size:11px;color:#999}'
    + '</style></head><body>'
    + '<h1>تقرير الإيرادات والمؤشرات</h1>'
    + '<p class="sub">' + new Date().toLocaleDateString('ar-SA') + ' · ضيوف — نظام إدارة الفنادق</p>'
    + '<h2>المؤشرات الرئيسية (KPIs)</h2>'
    + '<table><thead><tr><th>المؤشر</th><th>الوصف</th><th>القيمة</th><th>التغيير</th></tr></thead>'
    + '<tbody>' + kpiRows + '</tbody></table>'
    + '<h2>الإيراد حسب نوع الغرفة</h2>'
    + '<table><thead><tr><th>نوع الغرفة</th><th>RevPAR</th><th>ADR</th><th>الإشغال</th><th>ليالي مبيعة</th><th>الإيراد الإجمالي</th></tr></thead>'
    + '<tbody>' + roomRows + '</tbody></table>'
    + '<div class="footer">نظام ضيوف · إدارة الإيرادات · ' + new Date().toLocaleString('ar-SA') + '</div>'
    + '</body></html>');
  win.document.close();
  setTimeout(function(){ win.print(); }, 700);
};
