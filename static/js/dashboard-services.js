// dashboard-services.js — الإفطار والتوصيل: قسمان يُطوى كلٌّ منهما وحده
// يعتمد على apiSend و esc من dashboard-core.js، فيُحمَّل بعده.

// حالة الطيّ لكل نوع على حدة — هذا جوهر الطلب: الإفطار يُطوى بمعزل
// عن التوصيل. مفتاحٌ واحد للاثنين كان سيطويهما معاً.
var SERVICE_OPEN = { breakfast: true, delivery: true };

var SERVICE_ICON = { breakfast: '🍳', delivery: '🚐' };
var SERVICE_STATUS_AR = { pending: 'بانتظار', done: 'تم', cancelled: 'ملغاة' };

function toggleServiceGroup(type){
  SERVICE_OPEN[type] = !SERVICE_OPEN[type];
  var body = document.getElementById('svc-body-' + type);
  var arrow = document.getElementById('svc-arrow-' + type);
  if(body)  body.style.display = SERVICE_OPEN[type] ? '' : 'none';
  if(arrow) arrow.style.transform = SERVICE_OPEN[type] ? '' : 'rotate(-90deg)';
}

// رأس القسم مع سهم الطي. `summary` نصٌّ يختلف بين شاشة الحجز وقائمة
// اليوم، فيُمرَّر بدل أن يُبنى هنا.
function serviceGroupHtml(group, summary, rowsHtml){
  var open = SERVICE_OPEN[group.type];
  return '<div class="mod-card" style="margin-bottom:12px">'
    + '<div class="mod-card-head" style="cursor:pointer;user-select:none" '
    +      'onclick="toggleServiceGroup(\'' + esc(group.type) + '\')">'
    +   '<div class="ttl">' + (SERVICE_ICON[group.type] || '') + ' ' + esc(group.label) + '</div>'
    +   '<div style="display:flex;align-items:center;gap:10px;margin-inline-start:auto">'
    +     '<span class="mod-empty" style="padding:0">' + esc(summary) + '</span>'
    +     '<span id="svc-arrow-' + esc(group.type) + '" '
    +           'style="display:inline-block;transition:transform 150ms'
    +           (open ? '' : ';transform:rotate(-90deg)') + '">▼</span>'
    +   '</div>'
    + '</div>'
    + '<div id="svc-body-' + esc(group.type) + '"' + (open ? '' : ' style="display:none"') + '>'
    +   rowsHtml
    + '</div>'
  + '</div>';
}

// ── قائمة التشغيل اليومية ─────────────────────────────────────
async function loadDailyServices(day){
  var el = document.getElementById('dailyServices');
  if(!el) return;
  var picker = document.getElementById('svcDay');
  var target = day || (picker && picker.value) || '';
  var res = await apiSend('/api/services/daily' + (target ? '?day=' + encodeURIComponent(target) : ''));
  if(!res.ok){ el.innerHTML = empty(res.error); return; }

  var data = (res.data && res.data.data) || {};
  if(picker && !picker.value && data.day) picker.value = data.day;

  el.innerHTML = (data.groups || []).map(function(g){
    var rows = g.items.length
      ? '<table class="mod-table"><thead><tr><th>الغرفة</th><th>النزيل</th><th>الكمية</th>'
        + (g.type === 'delivery' ? '<th>الوجهة</th>' : '')
        + '<th>الحالة</th><th>إجراء</th></tr></thead><tbody>'
        + g.items.map(function(it){
            return '<tr><td>' + esc(it.room_number || '—') + '</td>'
              + '<td>' + esc(it.guest_name || '—') + '</td>'
              + '<td>' + esc(it.quantity) + '</td>'
              + (g.type === 'delivery' ? '<td>' + esc(it.destination || '—') + '</td>' : '')
              + '<td>' + esc(SERVICE_STATUS_AR[it.status] || it.status) + '</td>'
              + '<td>' + (it.status === 'pending'
                  ? '<button class="nz-btn is-gold" onclick="markService(' + it.id + ',\'done\')">تم</button> '
                    + '<button class="nz-btn is-secondary" onclick="markService(' + it.id + ',\'cancelled\')">إلغاء</button>'
                  : '<button class="nz-btn is-secondary" onclick="markService(' + it.id + ',\'pending\')">تراجع</button>')
              + '</td></tr>';
          }).join('')
        + '</tbody></table>'
      : empty('لا ' + g.label + ' اليوم');
    var summary = g.pending + ' بانتظار · ' + g.quantity + ' وحدة';
    return serviceGroupHtml(g, summary, rows);
  }).join('');
}

async function markService(id, status){
  var res = await apiSend('/api/services/' + id,
                          {method:'PATCH', body:JSON.stringify({status:status})});
  if(!res.ok){ showToast(res.error, 'error'); return; }
  loadDailyServices();
}
