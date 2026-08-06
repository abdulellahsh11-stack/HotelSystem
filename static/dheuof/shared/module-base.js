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

/* ── Form Validation (R3) ─────────────────────────────────────────────── */
DH.validate = {
  /* Validate a <form> element. Returns {ok, errors} where errors is {fieldName: message} */
  form: function(formEl) {
    var errors = {};
    if (!formEl) return { ok: false, errors: { _form: 'النموذج غير موجود' } };
    var fields = formEl.querySelectorAll('[data-validate]');
    fields.forEach(function(el) {
      var rules = el.getAttribute('data-validate').split(',');
      var name = el.name || el.id || 'field';
      var val = (el.value || '').trim();
      for (var i = 0; i < rules.length; i++) {
        var rule = rules[i].trim();
        var msg = DH.validate._check(rule, val, el);
        if (msg) { errors[name] = msg; break; }
      }
    });
    return { ok: Object.keys(errors).length === 0, errors: errors };
  },

  /* Apply errors to a form (sets border-color and aria-invalid) */
  showErrors: function(formEl, errors) {
    if (!formEl) return;
    formEl.querySelectorAll('[data-validate]').forEach(function(el) {
      var name = el.name || el.id || 'field';
      if (errors[name]) {
        el.style.borderColor = 'var(--danger-500, #ef4444)';
        el.setAttribute('aria-invalid', 'true');
        var hint = formEl.querySelector('[data-error-for="' + name + '"]');
        if (hint) hint.textContent = errors[name];
      } else {
        el.style.borderColor = '';
        el.removeAttribute('aria-invalid');
        var hint2 = formEl.querySelector('[data-error-for="' + name + '"]');
        if (hint2) hint2.textContent = '';
      }
    });
  },

  /* Clear all validation state */
  clearErrors: function(formEl) {
    if (!formEl) return;
    formEl.querySelectorAll('[data-validate]').forEach(function(el) {
      el.style.borderColor = '';
      el.removeAttribute('aria-invalid');
    });
    formEl.querySelectorAll('[data-error-for]').forEach(function(el) {
      el.textContent = '';
    });
  },

  _check: function(rule, val, el) {
    if (rule === 'required' && !val) return 'هذا الحقل مطلوب';
    if (rule === 'email' && val && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)) return 'البريد الإلكتروني غير صحيح';
    if (rule === 'phone' && val && !/^[\d\s\+\-\(\)]{7,20}$/.test(val)) return 'رقم الهاتف غير صحيح';
    if (rule === 'numeric' && val && isNaN(Number(val))) return 'يجب أن يكون رقماً';
    if (rule === 'positive' && val && Number(val) <= 0) return 'يجب أن يكون رقماً موجباً';
    if (rule === 'arabic' && val && !/[؀-ۿ]/.test(val)) return 'يجب إدخال نص عربي';
    if (/^min:(\d+)$/.test(rule)) {
      var min = parseInt(rule.split(':')[1]);
      if (val.length < min) return 'الحد الأدنى ' + min + ' أحرف';
    }
    if (/^max:(\d+)$/.test(rule)) {
      var max = parseInt(rule.split(':')[1]);
      if (val.length > max) return 'الحد الأقصى ' + max + ' أحرف';
    }
    return null;
  }
};
