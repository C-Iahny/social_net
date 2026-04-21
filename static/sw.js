/**
 * VAZIMBA Service Worker
 * Gère les push notifications Web Push.
 */

const CACHE_NAME = 'vazimba-v1';
const OFFLINE_URL = '/';

// ── Installation ──────────────────────────────────────────────────────────────
self.addEventListener('install', function(event) {
    self.skipWaiting();
});

// ── Activation ────────────────────────────────────────────────────────────────
self.addEventListener('activate', function(event) {
    event.waitUntil(clients.claim());
});

// ── Push Event ────────────────────────────────────────────────────────────────
self.addEventListener('push', function(event) {
    if (!event.data) return;

    var data = {};
    try {
        data = event.data.json();
    } catch(e) {
        data = { title: 'VAZIMBA', body: event.data.text() };
    }

    var title   = data.title || 'VAZIMBA';
    var options = {
        body:    data.body   || '',
        icon:    data.icon   || '/static/images/icon-192.png',
        badge:   '/static/images/badge-72.png',
        data:    { url: data.url || '/' },
        vibrate: [200, 100, 200],
        actions: [
            { action: 'open',    title: 'Ouvrir',  icon: '/static/images/icon-check.png' },
            { action: 'dismiss', title: 'Ignorer', icon: '/static/images/icon-x.png' },
        ],
        tag:     'vazimba-notif',
        renotify: true,
    };

    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

// ── Notification Click ────────────────────────────────────────────────────────
self.addEventListener('notificationclick', function(event) {
    event.notification.close();

    if (event.action === 'dismiss') return;

    var url = (event.notification.data && event.notification.data.url) || '/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
        .then(function(clientList) {
            // Focus existing window if already open
            for (var i = 0; i < clientList.length; i++) {
                var client = clientList[i];
                if (client.url.includes(self.location.origin) && 'focus' in client) {
                    client.navigate(url);
                    return client.focus();
                }
            }
            // Open new window
            if (clients.openWindow) {
                return clients.openWindow(url);
            }
        })
    );
});
