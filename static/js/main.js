// Mobile menu toggle
document.addEventListener('DOMContentLoaded', function () {
    var toggle = document.getElementById('menuToggle');
    var nav = document.getElementById('navLinks');
    if (toggle && nav) {
        toggle.addEventListener('click', function () {
            nav.classList.toggle('open');
        });
    }

    // Auto-fade flashes
    setTimeout(function () {
        document.querySelectorAll('.flash').forEach(function (el) {
            el.style.transition = 'opacity 0.4s';
            el.style.opacity = '0';
            setTimeout(function () { el.remove(); }, 400);
        });
    }, 6000);

    // Confirm-before-submit
    document.querySelectorAll('form[data-confirm]').forEach(function (f) {
        f.addEventListener('submit', function (e) {
            if (!confirm(f.getAttribute('data-confirm'))) e.preventDefault();
        });
    });

    // Client → devices dynamic dropdown
    var clientSelect = document.getElementById('client_id_selector');
    var deviceSelect = document.getElementById('device_id_selector');
    if (clientSelect && deviceSelect) {
        clientSelect.addEventListener('change', function () {
            var cid = clientSelect.value;
            if (!cid) { deviceSelect.innerHTML = '<option value="">(بدون جهاز)</option>'; return; }
            fetch('/api/clients/' + cid + '/devices')
                .then(function (r) { return r.json(); })
                .then(function (devices) {
                    var html = '<option value="">(بدون جهاز)</option>';
                    devices.forEach(function (d) {
                        html += '<option value="' + d.id + '">' + d.name + (d.location ? ' - ' + d.location : '') + '</option>';
                    });
                    deviceSelect.innerHTML = html;
                });
        });
    }
});
