// ONE Tracking — global UI interactions
document.addEventListener('DOMContentLoaded', function () {
    // Mobile menu toggle
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

    // Confirm-before-submit (works on <form data-confirm="..."> and <button data-confirm="...">)
    document.querySelectorAll('form[data-confirm]').forEach(function (f) {
        f.addEventListener('submit', function (e) {
            if (!confirm(f.getAttribute('data-confirm'))) e.preventDefault();
        });
    });
    document.querySelectorAll('button[data-confirm]').forEach(function (b) {
        b.addEventListener('click', function (e) {
            if (!confirm(b.getAttribute('data-confirm'))) e.preventDefault();
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

    // ===== Image Lightbox — click any .clickable-image or any <img> inside .card to zoom =====
    var overlay = document.createElement('div');
    overlay.className = 'lightbox-overlay';
    overlay.innerHTML = '<button class="lightbox-close" aria-label="close">✕</button><img alt="preview">';
    document.body.appendChild(overlay);
    var overlayImg = overlay.querySelector('img');
    var closeBtn = overlay.querySelector('.lightbox-close');

    function openLightbox(src) {
        overlayImg.src = src;
        overlay.classList.add('open');
        document.body.style.overflow = 'hidden';
    }
    function closeLightbox() {
        overlay.classList.remove('open');
        overlayImg.src = '';
        document.body.style.overflow = '';
    }

    // Auto-tag all uploaded images inside cards
    document.querySelectorAll('.image-thumb, .card img[src*="/static/uploads/"]').forEach(function (img) {
        if (!img.classList.contains('clickable-image')) img.classList.add('clickable-image');
    });

    document.addEventListener('click', function (e) {
        var img = e.target.closest('.clickable-image');
        if (img && img.tagName === 'IMG' && img.src) {
            e.preventDefault();
            openLightbox(img.src);
            return;
        }
        if (e.target === overlay || e.target === closeBtn) {
            closeLightbox();
        }
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && overlay.classList.contains('open')) closeLightbox();
    });
});
