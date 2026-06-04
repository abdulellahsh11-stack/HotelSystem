/* Shared module utilities — imported by all 17 modules */
window.DH = window.DH || {};

DH.API_BASE = '';

/* Safe fetch with error handling */
DH.fetch = async function(url, opts) {
  try {
    const resp = await fetch(DH.API_BASE + url, {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...(opts && opts.headers || {}) },
      ...opts
    });
    if (resp.status === 401) {
      window.dhShowAuth && window.dhShowAuth();
      return null;
    }
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    return await resp.json();
  } catch(e) {
    console.error('DH.fetch error:', url, e.message);
    return null;
  }
};

/* Format currency (SAR) */
DH.formatSAR = function(n) {
  return new Intl.NumberFormat('ar-SA', { style: 'currency', currency: 'SAR', maximumFractionDigits: 0 }).format(n || 0);
};

/* Format date (Arabic) */
DH.formatDate = function(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('ar-SA', { year: 'numeric', month: 'short', day: 'numeric' });
};

/* Show toast notification */
DH.toast = function(msg, type) {
  var t = document.createElement('div');
  t.className = 'dh-toast';
  t.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:99999;padding:12px 24px;border-radius:10px;font-family:var(--font-ar);font-size:14px;direction:rtl;transition:opacity .3s;box-shadow:var(--shadow-3);color:var(--paper);background:' + (type === 'error' ? 'var(--danger-700)' : type === 'warning' ? 'var(--warning-700)' : 'var(--brand-700)');
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(function(){ t.style.opacity='0'; setTimeout(function(){ t.remove(); }, 320); }, 2800);
};

/* Loading state helper */
DH.setLoading = function(el, loading) {
  if (!el) return;
  el.disabled = loading;
  el.style.opacity = loading ? '0.65' : '1';
};

/* Debounce */
DH.debounce = function(fn, ms) {
  var timer;
  return function() {
    clearTimeout(timer);
    timer = setTimeout(fn.bind(this, ...arguments), ms || 300);
  };
};

/* Session check */
DH.getSession = function() {
  try { return JSON.parse(localStorage.getItem('dheuof_session') || 'null'); } catch(e) { return null; }
};
