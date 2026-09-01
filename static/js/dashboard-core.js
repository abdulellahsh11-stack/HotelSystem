// dashboard-core.js — أدوات مشتركة: نداء الـAPI، التهريب، مُوزِّع الأقسام، لوحة البداية
// مُستخرَج من dashboard.html. الترتيب في الصفحة مقصود:
// core أولاً لأن بقية الملفات تستعمل apiSend و esc منه.



// ======== UTILITIES ========
const API='';
function showSection(id,el){
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  document.querySelectorAll('.dh-nav-item').forEach(n=>n.classList.remove('is-active'));
  const sec=document.getElementById('section-'+id);
  if(sec)sec.classList.add('active');
  if(el)el.classList.add('is-active');
  const titles={home:'لوحة التحكم الرئيسية',m01:'إدارة الضيوف',m02:'الاستقبال',m03:'مدير القنوات',m04:'المحاسبة',pos:'نقطة البيع',m05:'حالة الغرف',m06:'الموارد البشرية',m07:'الإشراف الداخلي',m08:'الصيانة',m09:'المفتاح الذكي',m10:'CRM والولاء',m11:'مؤشرات الأداء KPI',analytics:'تحليل البيانات',m12:'الرؤى الذكية',m13:'المستودعات',m14:'الجولات السياحية',m14b:'وجهات سياحية',m15:'تطبيق الموظفين'};
  document.getElementById('topbarTitle').textContent=titles[id]||'';
  loadSection(id);
}
function openModal(id){document.getElementById(id).classList.add('open');}
function closeModal(id){document.getElementById(id).classList.remove('open');}
document.querySelectorAll('.modal-overlay').forEach(o=>o.addEventListener('click',function(e){if(e.target===this)this.classList.remove('open');}));
function showToast(msg,type='info'){
  const c=document.getElementById('toastContainer');
  const t=document.createElement('div');
  const icons={success:'✅',error:'❌',info:'ℹ️'};
  t.className='toast '+type;
  t.innerHTML='<span>'+(icons[type]||'ℹ️')+'</span><span>'+msg+'</span>';
  c.appendChild(t);
  setTimeout(()=>t.remove(),3500);
}
function fmt(n){if(n===undefined||n===null||n==='--')return '--';return Number(n).toLocaleString('ar-SA');}
function statusBadge(s){
  const m={confirmed:'ok',active:'ok',paid:'ok',completed:'ok',available:'ok',clean:'ok',pending:'warn',trial:'warn',processing:'warn',cancelled:'err',overdue:'err',dirty:'err','out-of-order':'err','checked-in':'info','in-house':'info','in progress':'info'};
  const l={confirmed:'مؤكد',active:'نشط',paid:'مدفوع',completed:'مكتمل',available:'متاح',clean:'نظيف',pending:'معلق',trial:'تجريبي',processing:'قيد المعالجة',cancelled:'ملغي',overdue:'متأخر',dirty:'يحتاج تنظيف','out-of-order':'خارج الخدمة','checked-in':'تم الوصول','in-house':'داخل الفندق','in progress':'قيد التنفيذ'};
  const k=(s||'').toLowerCase();
  return '<span class="mod-tag '+(m[k]||'gold')+'">'+(l[k]||s||'--')+'</span>';
}
function esc(v){
  if(v===null||v===undefined) return '';
  return String(v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function empty(msg){return '<div class="mod-empty">'+msg+'</div>';}
async function apiFetch(url,opts={}){
  try{const r=await fetch(API+url,{headers:{'Content-Type':'application/json','Accept':'application/json'},...opts});if(!r.ok)throw new Error();return await r.json();}catch(e){return null;}
}
async function apiPost(url,data){return apiFetch(url,{method:'POST',body:JSON.stringify(data)});}


// apiFetch يبتلع كل خطأ ويُعيد null، فرسائل التحقق من الخادم لا تصل
// للمستخدم إطلاقاً. هذا المساعد يُعيد {ok, data, error} فتُعرض الرسالة.
async function apiSend(url, opts={}){
  try{
    const r = await fetch(API+url, {headers:{'Content-Type':'application/json','Accept':'application/json'}, ...opts});
    let body = null;
    try{ body = await r.json(); }catch(e){}
    if(!r.ok){
      const msg = (body && (body.detail || body.error)) || 'تعذّر إتمام العملية';
      return {ok:false, error:msg};
    }
    return {ok:true, data:body};
  }catch(e){
    return {ok:false, error:'تعذّر الاتصال بالخادم'};
  }
}

// ======== SECTION LOADER ========
function loadSection(id){
  // الخريطة كانت تُقيّم كل الدوال عند كل نداء، فدالة واحدة غير معرَّفة
  // ترمي ReferenceError وتمنع **كل** قسم من تحميل بياناته — لا القسم
  // المعطوب وحده. الأسماء نصوصٌ الآن، وتُحلّ عند الحاجة فقط.
  const map={home:'loadHome',m01:'loadGuests',m02:'loadFrontDesk',m03:'loadChannels',
    m04:'loadAccounting',pos:'loadPOS',m05:'loadRoomsStatus',m06:'loadHR',
    m07:'loadHousekeeping',m08:'loadMaintenance',m09:'loadSmartKey',m10:'loadCRM',
    m11:'loadKPI',analytics:'loadAnalytics',m12:'loadInsights',m13:'loadWarehouses',
    m14:'loadTourism',m14b:'loadDestinations',m15:'loadStaffApp',staff:'loadStaffAccounts',
    services:'loadDailyServices'};
  const fn = map[id] && window[map[id]];
  if(typeof fn === 'function'){
    try{ fn(); }
    catch(e){ console.error('تعذّر تحميل القسم '+id, e); }
  }
}

// ======== HOME ========
async function loadHome(){
  const kpi=await apiFetch('/api/kpi')||await apiFetch('/api/analytics');
  if(kpi){
    const occ=kpi.occupancy_rate||kpi.occupancy;
    document.getElementById('kpiOcc').textContent=occ!=null?occ+'%':'--';
    document.getElementById('kpiADR').textContent=fmt(kpi.adr||kpi.ADR);
    document.getElementById('kpiRevPAR').textContent=fmt(kpi.revpar||kpi.RevPAR);
    document.getElementById('kpiRevenue').textContent=fmt(kpi.monthly_revenue||kpi.revenue);
  }
  const arr=await apiFetch('/api/m02/arrivals');
  const dep=await apiFetch('/api/m02/departures');
  document.getElementById('kpiArrivals').textContent=Array.isArray(arr)?arr.length:(arr&&arr.count!=null?arr.count:'--');
  document.getElementById('kpiDepartures').textContent=Array.isArray(dep)?dep.length:(dep&&dep.count!=null?dep.count:'--');
  const bk=await apiFetch('/api/bookings');
  const el=document.getElementById('latestBookingsTable');
  if(bk&&Array.isArray(bk)&&bk.length){
    const rows=bk.slice(0,5).map(b=>'<tr><td>'+(b.id||b._id||'--')+'</td><td>'+(b.guest_name||b.guestName||b.guest||'--')+'</td><td>'+(b.room||b.room_number||'--')+'</td><td>'+(b.check_in||b.checkin||'--')+'</td><td>'+(b.check_out||b.checkout||'--')+'</td><td>'+statusBadge(b.status)+'</td><td>'+fmt(b.total_price||b.price||b.amount)+' ر.س</td></tr>').join('');
    el.innerHTML='<table class="mod-table"><thead><tr><th>رقم الحجز</th><th>الضيف</th><th>الغرفة</th><th>الوصول</th><th>المغادرة</th><th>الحالة</th><th>المبلغ</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }else{el.innerHTML=empty('لا توجد حجوزات حتى الآن');}
}

// ======== INIT ========
//
// `DOMContentLoaded` لا زينةً بل ضرورة: هذا الملف يُحمَّل **أولاً**
// وينادي `applySessionPermissions` المعرَّفة في `dashboard-staff.js`
// بعده. تنفيذُه فور التحليل يرمي «is not defined» فيقطع بقية التهيئة —
// فلا تُربَط مستمعات إغلاق النوافذ، ولا تُطبَّق الصلاحيات على الشريط،
// ولا شيء في الصفحة يقول إن شيئاً انكسر.
function init(){
  const now=new Date();
  const d=now.toLocaleDateString('ar-SA-u-nu-latn',{weekday:'long',year:'numeric',month:'long',day:'numeric'});
  const topDate=document.getElementById('topbarDate');
  if(topDate)topDate.textContent=d;
  const curDate=document.getElementById('currentDate');
  if(curDate)curDate.textContent=d;
  loadHome();
  applySessionPermissions();
  document.querySelectorAll('.modal-overlay').forEach(o=>o.addEventListener('click',function(e){if(e.target===this)this.classList.remove('open');}));
}

if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init);
else init();
