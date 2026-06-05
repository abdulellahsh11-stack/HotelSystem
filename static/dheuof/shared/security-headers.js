/* Security headers + localStorage hardening */
(function() {
  // Remove any plaintext passwords that might have been stored
  var s = localStorage.getItem('dheuof_session');
  if (s) {
    try {
      var obj = JSON.parse(s);
      delete obj.password; delete obj.pass; delete obj.pwd;
      localStorage.setItem('dheuof_session', JSON.stringify(obj));
    } catch(e) {}
  }
  // Add CSP meta if not present
  if (!document.querySelector('meta[http-equiv="Content-Security-Policy"]')) {
    var m = document.createElement('meta');
    m.httpEquiv = 'Content-Security-Policy';
    m.content = "default-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data:;";
    document.head.appendChild(m);
  }
})();
