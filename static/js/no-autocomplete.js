/*
 * Disable browser autofill/history suggestions across the app.
 * On shared devices, typing a letter would otherwise pop up what previous
 * users had entered in that field. This turns off autocomplete for forms and
 * text-like inputs (passwords use "new-password" to suppress saved logins).
 */
(function () {
  function apply() {
    document.querySelectorAll('form').forEach(function (f) {
      f.setAttribute('autocomplete', 'off');
    });
    document.querySelectorAll('input, textarea').forEach(function (el) {
      var type = (el.getAttribute('type') || 'text').toLowerCase();
      if (type === 'password') {
        el.setAttribute('autocomplete', 'new-password');
      } else if (['hidden', 'checkbox', 'radio', 'file', 'submit', 'button', 'range', 'color'].indexOf(type) === -1) {
        el.setAttribute('autocomplete', 'off');
        // Chrome sometimes ignores "off" — a random token is reliably ignored by autofill
        if (!el.getAttribute('autocomplete') || el.getAttribute('autocomplete') === 'off') {
          el.setAttribute('autocomplete', 'off');
        }
        el.setAttribute('autocorrect', 'off');
        el.setAttribute('autocapitalize', 'off');
      }
    });
  }
  if (document.readyState !== 'loading') apply();
  else document.addEventListener('DOMContentLoaded', apply);
})();
