{% load static %}
/**
 * VAZIMBA — Service Worker PWA
 * Stratégies de cache + Background Sync + Push Notifications
 */

/* ── Version ─────────────────────────────────────────────────────────────────
   Incrémenter SW_VERSION pour forcer la mise à jour chez tous les clients.
   ─────────────────────────────────────────────────────────────────────────── */
const SW_VERSION  = 'vazimba-v9';
const STATIC_CACHE = SW_VERSION + '-static';
const PAGES_CACHE  = SW_VERSION + '-pages';
const IMG_CACHE    = SW_VERSION + '-images';
const OFFLINE_URL  = '/offline/';

/* ── Ressources précachées au démarrage (App Shell) ─────────────────────────*/
const PRECACHE_STATIC = [
    '{% static "logo/vazimba_v2_icon.png" %}',
    '{% static "logo/vazimba_icon.png" %}',
    '{% static "perso/bootstrap/css/bootstrap.min.css" %}',
];

const PRECACHE_PAGES = [
    OFFLINE_URL,
];

/* ── Limites des caches dynamiques ──────────────────────────────────────────*/
const MAX_PAGES  = 80;   // Pages HTML conservées (augmenté)
const MAX_IMAGES = 150;  // Images conservées (augmenté)

/* ── Pages qui ne doivent PAS être servies depuis le cache (données fraîches) */
const NO_CACHE_PATHS = ['/chat/', '/admin/', '/logout/', '/login/'];
function _isNoCachePath(url) {
    return NO_CACHE_PATHS.some(function(p) { return url.pathname.startsWith(p); });
}

/* ═══════════════════════════════════════════════════════════════════════════
   INSTALL — précacher le shell
   ═══════════════════════════════════════════════════════════════════════════ */
self.addEventListener('install', function(event) {
    event.waitUntil(
        Promise.all([
            caches.open(STATIC_CACHE).then(function(c) {
                return c.addAll(PRECACHE_STATIC);
            }),
            caches.open(PAGES_CACHE).then(function(c) {
                return c.addAll(PRECACHE_PAGES);
            }),
        ]).then(function() {
            return self.skipWaiting();
        })
    );
});

/* ═══════════════════════════════════════════════════════════════════════════
   ACTIVATE — supprimer les anciens caches
   ═══════════════════════════════════════════════════════════════════════════ */
self.addEventListener('activate', function(event) {
    var validCaches = [STATIC_CACHE, PAGES_CACHE, IMG_CACHE];
    event.waitUntil(
        caches.keys().then(function(keys) {
            return Promise.all(
                keys
                    .filter(function(k) { return !validCaches.includes(k); })
                    .map(function(k) { return caches.delete(k); })
            );
        }).then(function() {
            return clients.claim();
        })
    );
});

/* ═══════════════════════════════════════════════════════════════════════════
   FETCH — stratégies de cache
   ═══════════════════════════════════════════════════════════════════════════ */
self.addEventListener('fetch', function(event) {
    var req = event.request;
    var url = new URL(req.url);

    /* Ignorer les méthodes non-GET (elles ont leur propre gestion offline) */
    if (req.method !== 'GET') return;

    /* Ignorer admin, websocket, chrome-extension */
    if (url.pathname.startsWith('/admin/')) return;
    if (url.protocol === 'ws:' || url.protocol === 'wss:') return;
    if (req.url.startsWith('chrome-extension://')) return;

    /* Ignorer les réponses JSON API (WebSockets, AJAX) */
    var acceptHeader = req.headers.get('Accept') || '';
    if (acceptHeader.includes('application/json') && !acceptHeader.includes('text/html')) return;

    /* ── Ressources statiques locales : Cache-First ─────────────────────── */
    if (url.hostname === self.location.hostname && url.pathname.startsWith('/static/')) {
        event.respondWith(cacheFirst(req, STATIC_CACHE, false));
        return;
    }

    /* ── CDN externes (fonts, icons) : Cache-First ─────────────────────── */
    if (url.hostname !== self.location.hostname) {
        event.respondWith(cacheFirst(req, STATIC_CACHE, false));
        return;
    }

    /* ── Images media locales : Stale-While-Revalidate ─────────────────── */
    if (url.pathname.startsWith('/media/') ||
        url.hostname.includes('r2.cloudflarestorage') ||
        url.hostname.includes('cloudinary')) {
        event.respondWith(staleWhileRevalidate(req, IMG_CACHE, MAX_IMAGES));
        return;
    }

    /* ── Pages HTML ─────────────────────────────────────────────────────── */
    if (req.headers.get('Accept') && req.headers.get('Accept').includes('text/html')) {
        /* Chat, admin, login → Network-First (données toujours fraîches) */
        if (_isNoCachePath(url)) {
            event.respondWith(networkFirstHTML(req));
        } else {
            /* Toutes les autres pages → Stale-While-Revalidate
               → La page mise en cache s'affiche INSTANTANÉMENT,
                 le réseau met à jour le cache en arrière-plan             */
            event.respondWith(staleWhileRevalidateHTML(req));
        }
        return;
    }
});

/* ── Cache-First : servir depuis le cache, fetcher si absent ─────────────── */
function cacheFirst(request, cacheName, limit) {
    return caches.open(cacheName).then(function(cache) {
        return cache.match(request).then(function(cached) {
            if (cached) return cached;
            return fetch(request).then(function(response) {
                if (response && response.ok) {
                    cache.put(request, response.clone());
                    if (limit) trimCache(cacheName, limit);
                }
                return response;
            }).catch(function() {
                return new Response('', { status: 503, statusText: 'Service unavailable' });
            });
        });
    });
}

/* ── Network-First HTML : essayer le réseau, fallback cache puis offline ─── */
function networkFirstHTML(request) {
    return fetch(request).then(function(response) {
        if (response && response.ok) {
            var clone = response.clone();
            caches.open(PAGES_CACHE).then(function(cache) {
                cache.put(request, clone);
                trimCache(PAGES_CACHE, MAX_PAGES);
            });
        }
        return response;
    }).catch(function() {
        return caches.open(PAGES_CACHE).then(function(cache) {
            return cache.match(request).then(function(cached) {
                if (cached) return cached;
                return cache.match(OFFLINE_URL);
            });
        });
    });
}

/* ── Stale-While-Revalidate pour les pages HTML ─────────────────────────── */
function staleWhileRevalidateHTML(request) {
    return caches.open(PAGES_CACHE).then(function(cache) {
        return cache.match(request).then(function(cached) {
            /* Lancer la mise à jour réseau en parallèle (sans attendre) */
            var fetchPromise = fetch(request).then(function(response) {
                if (response && response.ok) {
                    cache.put(request, response.clone());
                    trimCache(PAGES_CACHE, MAX_PAGES);
                }
                return response;
            }).catch(function() {
                return caches.match(OFFLINE_URL);
            });
            /* Retourner le cache immédiatement si disponible, sinon attendre le réseau */
            return cached || fetchPromise;
        });
    });
}

/* ── Stale-While-Revalidate : servir le cache, rafraîchir en arrière-plan── */
function staleWhileRevalidate(request, cacheName, maxEntries) {
    return caches.open(cacheName).then(function(cache) {
        return cache.match(request).then(function(cached) {
            var fetchPromise = fetch(request).then(function(response) {
                if (response && response.ok) {
                    cache.put(request, response.clone());
                    trimCache(cacheName, maxEntries);
                }
                return response;
            });
            return cached || fetchPromise;
        });
    });
}

/* ── Limiter la taille d'un cache (supprimer les plus anciennes entrées) ─── */
function trimCache(cacheName, maxEntries) {
    return caches.open(cacheName).then(function(cache) {
        return cache.keys().then(function(keys) {
            if (keys.length > maxEntries) {
                return cache.delete(keys[0]).then(function() {
                    return trimCache(cacheName, maxEntries);
                });
            }
        });
    });
}

/* ═══════════════════════════════════════════════════════════════════════════
   BACKGROUND SYNC — publier les posts en attente
   ═══════════════════════════════════════════════════════════════════════════ */
self.addEventListener('sync', function(event) {
    if (event.tag === 'sync-pending-posts') {
        event.waitUntil(syncPendingPosts());
    }
});

function syncPendingPosts() {
    return openPostsDB().then(function(db) {
        return getAllPendingPosts(db).then(function(posts) {
            return Promise.all(posts.map(function(item) {
                var fd = new FormData();
                Object.keys(item.data).forEach(function(k) { fd.append(k, item.data[k]); });
                return fetch(item.url, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': item.csrf },
                    body: fd,
                }).then(function(resp) {
                    if (resp.ok) {
                        return deletePendingPost(db, item.id).then(function() {
                            // Notifier tous les clients que la sync a réussi
                            return self.clients.matchAll().then(function(clients) {
                                clients.forEach(function(c) {
                                    c.postMessage({ type: 'SYNC_SUCCESS', postId: item.id });
                                });
                            });
                        });
                    }
                }).catch(function() { /* retry next sync */ });
            }));
        });
    });
}

/* ── IndexedDB helpers ───────────────────────────────────────────────────── */
function openPostsDB() {
    return new Promise(function(resolve, reject) {
        var req = indexedDB.open('vazimba-offline', 1);
        req.onupgradeneeded = function(e) {
            var db = e.target.result;
            if (!db.objectStoreNames.contains('pending-posts')) {
                var store = db.createObjectStore('pending-posts', { keyPath: 'id', autoIncrement: true });
                store.createIndex('timestamp', 'timestamp', { unique: false });
            }
        };
        req.onsuccess = function(e) { resolve(e.target.result); };
        req.onerror   = function(e) { reject(e.target.error); };
    });
}

function getAllPendingPosts(db) {
    return new Promise(function(resolve, reject) {
        var tx    = db.transaction('pending-posts', 'readonly');
        var store = tx.objectStore('pending-posts');
        var req   = store.getAll();
        req.onsuccess = function(e) { resolve(e.target.result); };
        req.onerror   = function(e) { reject(e.target.error); };
    });
}

function deletePendingPost(db, id) {
    return new Promise(function(resolve, reject) {
        var tx    = db.transaction('pending-posts', 'readwrite');
        var store = tx.objectStore('pending-posts');
        var req   = store.delete(id);
        req.onsuccess = function() { resolve(); };
        req.onerror   = function(e) { reject(e.target.error); };
    });
}

/* ═══════════════════════════════════════════════════════════════════════════
   PUSH NOTIFICATIONS (code original conservé)
   ═══════════════════════════════════════════════════════════════════════════ */
self.addEventListener('push', function(event) {
    if (!event.data) return;

    var data = {};
    try {
        data = event.data.json();
    } catch(e) {
        data = { title: 'VAZIMBA', body: event.data.text() };
    }

    var title   = data.title || 'VAZIMBA';
    var options;

    /* ── Notification d'APPEL ENTRANT ────────────────────────────────────────
       Pattern spécial : sonnerie vibrante répétée, tag fixe (un seul appel
       à la fois), boutons Répondre / Refuser, reste à l'écran.              */
    if (data.type === 'incoming_call') {
        options = {
            body:             data.body || 'Appel entrant',
            icon:             data.icon || '/static/logo/vazimba_v2_icon.png',
            badge:            '/static/logo/vazimba_icon.png',
            // Sonnerie : 3 pulses longs puis pause, répétés par le navigateur
            vibrate:          [500, 300, 500, 300, 500, 1500,
                               500, 300, 500, 300, 500, 1500,
                               500, 300, 500],
            requireInteraction: true,   // reste à l'écran jusqu'à action
            renotify:         true,     // re-déclenche la sonnerie si déjà visible
            tag:              'vazimba-incoming-call',  // une seule notif appel à la fois
            data: {
                url:       data.url     || '/',
                room_id:   data.room_id || '',
                call_mode: data.call_mode || 'video',
                type:      'incoming_call',
            },
            actions: [
                { action: 'accept',  title: '✅ Répondre' },
                { action: 'decline', title: '❌ Refuser'  },
            ],
        };
    } else {
        /* ── Notification standard ───────────────────────────────────────── */
        options = {
            body:    data.body   || '',
            icon:    data.icon   || '/static/logo/vazimba_v2_icon.png',
            badge:   '/static/logo/vazimba_icon.png',
            data:    { url: data.url || '/', type: data.type || 'notif' },
            vibrate: [200, 100, 200],
            requireInteraction: true,
            actions: [
                { action: 'open',    title: 'Ouvrir' },
                { action: 'dismiss', title: 'Ignorer' },
            ],
            tag:      'vazimba-' + (data.type || 'notif') + '-' + Date.now(),
            renotify: false,
        };
    }

    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();

    var notifData = event.notification.data || {};
    var action    = event.action;

    /* ── Action "Refuser" sur appel entrant ───────────────────────────────
       Appel un endpoint Django qui envoie MSG_TYPE_CALL_REJECT au caller. */
    if (notifData.type === 'incoming_call' && action === 'decline') {
        var rejectUrl = self.location.origin + '/chat/call-reject-push/?room_id=' + (notifData.room_id || '');
        event.waitUntil(fetch(rejectUrl, { method: 'POST', credentials: 'include' }));
        return;
    }

    /* ── Action "Ignorer" sur notif standard → fermer sans ouvrir ────── */
    if (action === 'dismiss') return;

    /* ── Accepter l'appel OU clic principal → ouvrir la room ─────────── */
    var rawUrl;
    if (notifData.type === 'incoming_call') {
        rawUrl = notifData.url || '/';
    } else {
        rawUrl = notifData.url || '/';
    }

    // Normalise l'URL : si elle est relative, la rendre absolue avec l'origine du SW.
    var url;
    try {
        var parsed = new URL(rawUrl, self.location.origin);
        parsed.hostname === self.location.hostname
            ? url = parsed.href
            : url = self.location.origin + parsed.pathname + parsed.search;
    } catch(e) {
        url = self.location.origin + '/';
    }

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
        .then(function(clientList) {
            for (var i = 0; i < clientList.length; i++) {
                var client = clientList[i];
                if (client.url.startsWith(self.location.origin) && 'focus' in client) {
                    if ('navigate' in client) {
                        return client.navigate(url).then(function(c) {
                            return c ? c.focus() : null;
                        });
                    }
                    client.postMessage({ type: 'NAVIGATE', url: url });
                    return client.focus();
                }
            }
            if (clients.openWindow) return clients.openWindow(url);
        })
    );
});

/* ── Message depuis la page : forcer la mise à jour ─────────────────────── */
self.addEventListener('message', function(event) {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});
