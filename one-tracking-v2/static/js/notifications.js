// Notifications bell — polls periodically and renders panel
(function () {
    const bell = document.getElementById('notifBell');
    const panel = document.getElementById('notifPanel');
    const list = document.getElementById('notifList');
    const badge = document.getElementById('notifBadge');
    const readAll = document.getElementById('notifReadAll');
    if (!bell || !panel) return;

    async function fetchNotifs() {
        try {
            const r = await fetch('/notifications/api/recent');
            const d = await r.json();
            if (badge) {
                badge.textContent = d.unread;
                badge.style.display = d.unread > 0 ? 'inline-flex' : 'none';
            }
            if (d.items && d.items.length) {
                list.innerHTML = d.items.map(n => `
                    <a href="${n.link || '#'}" class="notif-item ${n.is_read ? '' : 'unread'}" data-id="${n.id}">
                        <span class="notif-icon">${n.icon || '🔔'}</span>
                        <div style="flex:1">
                            <div class="notif-title">${n.title}</div>
                            <div class="notif-body">${n.body || ''}</div>
                            <div class="notif-time">${n.when}</div>
                        </div>
                    </a>
                `).join('');
            } else {
                list.innerHTML = '<div class="text-center text-muted" style="padding:20px">لا يوجد تنبيهات</div>';
            }
        } catch (e) {
            list.innerHTML = '<div class="text-center text-muted" style="padding:20px">تعذر التحميل</div>';
        }
    }

    bell.addEventListener('click', function (e) {
        e.stopPropagation();
        panel.classList.toggle('open');
        if (panel.classList.contains('open')) fetchNotifs();
    });

    document.addEventListener('click', function (e) {
        if (!panel.contains(e.target) && !bell.contains(e.target)) {
            panel.classList.remove('open');
        }
    });

    if (readAll) {
        readAll.addEventListener('click', async function () {
            await fetch('/notifications/read-all', { method: 'POST' });
            fetchNotifs();
        });
    }

    // Auto-refresh every 60s
    setInterval(fetchNotifs, 60000);
    // Initial fetch after 3s
    setTimeout(fetchNotifs, 3000);
})();
