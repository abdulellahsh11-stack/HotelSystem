/* vibrant.js — shared vibrant hero + tier counters renderer */
(function(){
  window.renderVibrantHero = function(opts){
    /* opts: { icon, num, title, en, sub, badges:[], actions:[] } */
    var badges = (opts.badges||[]).map(function(b){
      return '<div class="hero-badge"><div class="bv">'+b.v+'</div><div class="bl">'+b.l+'</div></div>';
    }).join('');
    var actions = (opts.actions||[]).map(function(a){
      return '<button onclick="'+a.fn+'()" style="padding:9px 18px;border-radius:999px;border:1px solid rgba(201,168,95,0.4);background:rgba(255,255,255,0.08);color:#fff;font-family:var(--font-ar);font-size:13px;cursor:pointer;">'+a.label+'</button>';
    }).join('');
    var html = '<div class="vib-hero">'+
      '<div class="hero-left">'+
        '<div class="hero-ic">'+opts.icon+'</div>'+
        '<div class="hero-text">'+
          '<div class="hero-num">MODULE · '+opts.num+'</div>'+
          '<div class="hero-title">'+opts.title+'</div>'+
          '<div class="hero-en">'+opts.en+'</div>'+
          (opts.sub?'<div class="hero-sub">'+opts.sub+'</div>':'')+
          (actions?'<div class="hero-actions">'+actions+'</div>':'')+
        '</div>'+
      '</div>'+
      (badges?'<div class="hero-right">'+badges+'</div>':'')+
    '</div>';
    var wrap = document.getElementById('vib-hero-wrap');
    if(wrap) wrap.innerHTML = html;
  };

  window.renderTierBar = function(opts){
    /* opts: { exc, good, low, bad } — percentages 0-100 */
    var total = (opts.exc||0)+(opts.good||0)+(opts.low||0)+(opts.bad||0);
    function pct(v){ return total ? Math.round(v/total*100) : 0; }
    var tiers = [
      {cls:'tier-exc',  label:'⭐ ممتاز',    key:'exc',  emoji:'⭐'},
      {cls:'tier-good', label:'✅ جيد',       key:'good', emoji:'✅'},
      {cls:'tier-low',  label:'⚠️ منخفض',    key:'low',  emoji:'⚠️'},
      {cls:'tier-bad',  label:'🔴 تحت الحد', key:'bad',  emoji:'🔴'},
    ];
    var html = '<div class="tier-bar">';
    tiers.forEach(function(t){
      var count = opts[t.key]||0;
      var p = pct(count);
      html += '<div class="tier-card '+t.cls+'">'+
        '<div class="t-label">'+t.label+'</div>'+
        '<div class="t-pct">'+p+'<span style="font-size:18px">٪</span></div>'+
        '<div class="t-count">'+count+' من '+total+'</div>'+
        '<div class="t-bar"><div class="t-bar-fill" style="width:'+p+'%"></div></div>'+
      '</div>';
    });
    html += '</div>';
    var wrap = document.getElementById('tier-bar-wrap');
    if(wrap) wrap.innerHTML = html;
  };
})();
