// Notifications bell — polls periodically, renders panel, and plays a sound on new alerts.
(function () {
    const bell = document.getElementById('notifBell');
    const panel = document.getElementById('notifPanel');
    const list = document.getElementById('notifList');
    const badge = document.getElementById('notifBadge');
    const readAll = document.getElementById('notifReadAll');
    const soundToggle = document.getElementById('notifSoundToggle');
    if (!bell || !panel) return;

    // ===== Sound preference (persisted per browser) =====
    function soundOn() {
        try { return localStorage.getItem('notifSound') !== 'off'; } catch (e) { return true; }
    }
    function setSoundOn(on) {
        try { localStorage.setItem('notifSound', on ? 'on' : 'off'); } catch (e) {}
        renderSoundToggle();
    }
    function renderSoundToggle() {
        if (!soundToggle) return;
        soundToggle.textContent = soundOn() ? '🔊' : '🔇';
        soundToggle.title = soundOn() ? 'الصوت مفعّل — اضغط للكتم' : 'الصوت مكتوم — اضغط للتفعيل';
    }

    // ===== Web Audio chime (no external file needed) =====
    let audioCtx = null;
    let audioUnlocked = false;   // becomes true only after a real user gesture
    function unlockAudio() {
        // Create the AudioContext only inside a user gesture — avoids the
        // "AudioContext was not allowed to start" console warnings.
        if (!audioCtx) {
            try {
                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            } catch (e) { audioCtx = null; return; }
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume().then(function () { audioUnlocked = true; }).catch(function () {});
        } else {
            audioUnlocked = true;
        }
    }
    // Browsers require a user gesture before audio can play — unlock on first interaction.
    document.addEventListener('click', unlockAudio, { once: true });
    document.addEventListener('keydown', unlockAudio, { once: true });
    document.addEventListener('touchstart', unlockAudio, { once: true });

    function playChime() {
        if (!soundOn()) return;
        // Do nothing until audio has been unlocked by a user gesture (prevents warnings)
        if (!audioUnlocked || !audioCtx || audioCtx.state !== 'running') return;
        const base = audioCtx.currentTime;
        // Three louder "ding-dong" pairs so it's hard to miss.
        for (let rep = 0; rep < 3; rep++) {
            const start = base + rep * 0.6;
            [[880, 0], [1174, 0.16]].forEach(function (pair) {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = 'sine';
                osc.frequency.value = pair[0];
                const t = start + pair[1];
                gain.gain.setValueAtTime(0.0001, t);
                gain.gain.exponentialRampToValueAtTime(0.6, t + 0.02);  // louder
                gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.45);
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.start(t); osc.stop(t + 0.5);
            });
        }
    }

    // ===== Native OS notification permission =====
    function ensurePermission() {
        if (!('Notification' in window)) return;
        if (Notification.permission === 'default') {
            // Ask on the first user gesture (some browsers require a gesture)
            Notification.requestPermission().catch(function () {});
        }
    }
    document.addEventListener('click', ensurePermission, { once: true });
    // also try immediately (desktop usually allows it)
    try { ensurePermission(); } catch (e) {}

    function vibrate() {
        try { if (navigator.vibrate) navigator.vibrate([300, 120, 300, 120, 300]); } catch (e) {}
    }

    // Show a system notification via the service worker (survives backgrounded tab)
    // and fall back to a page-level Notification if no SW is controlling.
    function systemNotify(n) {
        if (!('Notification' in window) || Notification.permission !== 'granted') return;
        var payload = {
            type: 'notify',
            id: n.id,
            title: n.title || 'تنبيه جديد',
            body: n.body || '',
            link: n.link || '/',
            tag: 'notif-' + n.id
        };
        try {
            if (navigator.serviceWorker && navigator.serviceWorker.controller) {
                navigator.serviceWorker.controller.postMessage(payload);
                return;
            }
            if (navigator.serviceWorker && navigator.serviceWorker.ready) {
                navigator.serviceWorker.ready.then(function (reg) {
                    reg.showNotification(payload.title, {
                        body: payload.body,
                        icon: '/static/img/pwa/icon-192.png',
                        badge: '/static/img/pwa/icon-192.png',
                        tag: payload.tag, renotify: true, requireInteraction: true,
                        vibrate: [300, 120, 300, 120, 300],
                        data: { link: payload.link }
                    });
                });
                return;
            }
        } catch (e) {}
        // Last resort: basic page notification
        try {
            var note = new Notification(payload.title, { body: payload.body, icon: '/static/img/pwa/icon-192.png' });
            note.onclick = function () { window.focus(); if (payload.link) location.href = payload.link; };
        } catch (e) {}
    }

    // ===== Track newest notification to detect fresh arrivals =====
    let lastMaxId = null;      // highest id we've seen
    let primed = false;        // skip the very first fetch (avoid chime on page load)

    async function fetchNotifs(render) {
        try {
            const r = await fetch('/notifications/api/recent');
            const d = await r.json();

            // Detect new notifications by max id
            let maxId = 0, hasUnread = false, newest = null;
            (d.items || []).forEach(function (n) {
                if (n.id > maxId) { maxId = n.id; }
                if (n.id > (lastMaxId || 0) && !newest) newest = n;
                if (!n.is_read) hasUnread = true;
            });
            if (primed && maxId > (lastMaxId || 0) && hasUnread) {
                playChime();
                vibrate();
                flashTitle();
                if (newest) systemNotify(newest);
            }
            if (maxId > (lastMaxId || 0)) lastMaxId = maxId;
            primed = true;

            if (badge) {
                badge.textContent = d.unread;
                badge.style.display = d.unread > 0 ? 'inline-flex' : 'none';
            }
            if (render !== false) renderList(d.items);
        } catch (e) {
            if (render !== false && list) {
                list.innerHTML = '<div class="text-center text-muted" style="padding:20px">تعذر التحميل</div>';
            }
        }
    }

    function renderList(items) {
        if (!list) return;
        if (items && items.length) {
            list.innerHTML = items.map(function (n) {
                return '<a href="' + (n.link || '#') + '" class="notif-item ' + (n.is_read ? '' : 'unread') + '" data-id="' + n.id + '">' +
                    '<span class="notif-icon">' + (n.icon || '🔔') + '</span>' +
                    '<div style="flex:1">' +
                    '<div class="notif-title">' + n.title + '</div>' +
                    '<div class="notif-body">' + (n.body || '') + '</div>' +
                    '<div class="notif-time">' + n.when + '</div>' +
                    '</div></a>';
            }).join('');
        } else {
            list.innerHTML = '<div class="text-center text-muted" style="padding:20px">لا يوجد تنبيهات</div>';
        }
    }

    // Flash the browser tab title so it's noticed even in another tab
    let titleTimer = null;
    function flashTitle() {
        const original = document.title;
        let on = false, count = 0;
        clearInterval(titleTimer);
        titleTimer = setInterval(function () {
            document.title = on ? original : '🔔 تنبيه جديد';
            on = !on;
            if (++count > 10) { clearInterval(titleTimer); document.title = original; }
        }, 800);
    }

    bell.addEventListener('click', function (e) {
        e.stopPropagation();
        unlockAudio();
        panel.classList.toggle('open');
        if (panel.classList.contains('open')) fetchNotifs(true);
    });

    if (soundToggle) {
        soundToggle.addEventListener('click', function (e) {
            e.stopPropagation();
            unlockAudio();
            setSoundOn(!soundOn());
            // audible confirmation after the context has resumed
            if (soundOn()) setTimeout(playChime, 150);
        });
        renderSoundToggle();
    }

    document.addEventListener('click', function (e) {
        if (!panel.contains(e.target) && !bell.contains(e.target)) {
            panel.classList.remove('open');
        }
    });

    if (readAll) {
        readAll.addEventListener('click', async function () {
            await fetch('/notifications/read-all', { method: 'POST' });
            fetchNotifs(true);
        });
    }

    // ===== Enable-notifications button =====
    const enableBtn = document.getElementById('notifEnable');
    function refreshEnableBtn() {
        if (!enableBtn || !('Notification' in window)) return;
        enableBtn.style.display = (Notification.permission === 'granted') ? 'none' : 'inline-flex';
    }
    if (enableBtn) {
        enableBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            unlockAudio();
            if (!('Notification' in window)) {
                alert('متصفحك لا يدعم إشعارات النظام');
                return;
            }
            Notification.requestPermission().then(function (perm) {
                refreshEnableBtn();
                if (perm === 'granted') {
                    // confirmation notification so the user sees it works
                    systemNotify({ id: Date.now(), title: 'تم تفعيل الإشعارات ✅',
                                   body: 'هتوصلك التنبيهات هنا بصوت واهتزاز.', link: '/' });
                    vibrate();
                    setTimeout(playChime, 150);
                } else {
                    alert('لم يتم تفعيل الإشعارات. فعّلها من إعدادات المتصفح للموقع.');
                }
            });
        });
        refreshEnableBtn();
    }

    // Poll every 10s so alerts arrive quickly; only re-render the list when the panel is open.
    setInterval(function () { fetchNotifs(panel.classList.contains('open')); }, 10000);
    setTimeout(function () { fetchNotifs(false); }, 2000);
})();
