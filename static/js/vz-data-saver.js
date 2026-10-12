/* Généré depuis templates/base.html — script servis en statique (cache navigateur + service worker)
   au lieu d'être renvoyés dans chaque réponse HTML. Modifier ICI, plus dans le gabarit. */

/* ═══════════════════════════════════════════════════════════════════════
   MODE ÉCONOMIE DE DONNÉES — Vazimba Data Saver
   Stockage : localStorage 'vzb-data-saver' = '1' | '0' | null (auto)
   ═══════════════════════════════════════════════════════════════════════ */
(function() {
'use strict';

/* ── Activer / désactiver ── */
window.dsEnable = function(on, fromBanner) {
    var html = document.documentElement;
    if (on) {
        html.classList.add('data-saver');
        window.__VZB_DATA_SAVER = true;
        try { localStorage.setItem('vzb-data-saver', '1'); } catch(e) {}
        _applyDataSaver();
    } else {
        html.classList.remove('data-saver');
        window.__VZB_DATA_SAVER = false;
        try { localStorage.setItem('vzb-data-saver', '0'); } catch(e) {}
        _removeDataSaverImages();
    }
    _syncDsButton(on);
    if (fromBanner) dsDismissBanner();
};

/* ── Sync du bouton dans le dropdown ── */
function _syncDsButton(on) {
    var icon  = document.getElementById('dd-datasaver-icon');
    var label = document.getElementById('dd-datasaver-label');
    if (icon)  { icon.textContent = on ? 'data_saver_on' : 'data_saver_off'; icon.classList.toggle('active', on); }
    if (label) { label.textContent = on ? 'Mode économie actif' : 'Mode économie'; label.classList.toggle('active', on); }
}

/* ── Toggle depuis le bouton ── */
window.toggleDataSaver = function() {
    dsEnable(!window.__VZB_DATA_SAVER);
};

/* ── Appliquer le mode économie (photos toujours chargées, vidéos lazy) ── */
function _applyDataSaver() {
    /* Les images se chargent toujours normalement (loading="lazy" natif suffit).
       Le mode économie n'affecte que les vidéos, déjà lazy par défaut via ds-vid-overlay. */
}

/* ── Retirer le mode économie (no-op pour images, vidéos non affectées) ── */
function _removeDataSaverImages() {
    /* Les images ne sont plus gérées par le data-saver : rien à faire */
}

/* ── Clic sur une image en mode économie → charger la vraie ── */
document.addEventListener('click', function(e) {
    var img = e.target.closest('.ds-img-wrap .ds-img.ds-pending');
    if (!img) return;
    if (img.dataset.fullSrc) {
        e.stopPropagation(); /* Ne pas ouvrir la lightbox globale tout de suite */
        img.src = img.dataset.fullSrc;
        img.onload = function() {
            img.classList.remove('ds-pending');
            img.classList.add('ds-loaded');
            img.style.minHeight = '';
            var wrap = img.closest('.ds-img-wrap');
            if (wrap) { wrap.removeAttribute('data-hint'); wrap.click(); } /* ouvrir lightbox */
        };
    }
}, true);

/* ── Lecture explicite (clic overlay) — toujours avec son ── */
window.dsPlayVideo = function(overlay) {
    var wrap = overlay.closest('.ds-vid-wrap');
    var vid  = wrap ? wrap.querySelector('video') : null;
    if (!vid) return;
    if (!vid.src && vid.dataset.src) { vid.src = vid.dataset.src; vid.load(); }
    vid.setAttribute('playsinline', '');
    vid.setAttribute('webkit-playsinline', '');
    vid.muted = false;   /* clic utilisateur = son activé */
    vid.play().catch(function() { vid.muted = true; vid.play().catch(function(){}); });
    wrap.classList.add('ds-playing');
};

/* ════════════════════════════════════════════════════════════
   AUTOPLAY VIDÉO — hover (desktop) / IntersectionObserver (mobile)
   • Première image affichée via preload="metadata" (src chargé
     dès que la vidéo approche du viewport, ~200 px avant)
   • Mode économie désactivé = autoplay muet uniquement
   ════════════════════════════════════════════════════════════ */
(function() {
    var _touch  = ('ontouchstart' in window) || navigator.maxTouchPoints > 0;
    var _ioMeta = null;  /* Observer pré-chargement 1ère image */
    var _ioPlay = null;  /* Observer lecture (mobile seulement)  */

    function _preloadMeta(vid) {
        if (vid.src || !vid.dataset.src) return;
        vid.preload = 'metadata';
        vid.src = vid.dataset.src;   /* navigateur charge métadonnées → affiche 1ère frame */
    }

    function _play(wrap, vid) {
        _preloadMeta(vid);
        /* playsinline indispensable sur Android/iOS pour éviter le plein écran natif */
        vid.setAttribute('playsinline', '');
        vid.setAttribute('webkit-playsinline', '');
        vid.muted = true;
        vid.play().then(function() {
            wrap.classList.add('ds-playing');
        }).catch(function() {});
    }

    function _pause(wrap, vid) {
        if (!vid.paused) vid.pause();
        wrap.classList.remove('ds-playing');
    }

    function _initWrap(wrap) {
        if (wrap.dataset.apInit) return;
        wrap.dataset.apInit = '1';
        var vid = wrap.querySelector('video');
        if (!vid) return;

        /* Sync classe ds-playing sur les événements natifs */
        vid.addEventListener('play',  function() { wrap.classList.add('ds-playing'); });
        vid.addEventListener('pause', function() { wrap.classList.remove('ds-playing'); });

        /* Pré-charger la 1ère image dès que la vidéo approche du viewport */
        if (_ioMeta) _ioMeta.observe(wrap);

        if (_touch) {
            if (_ioPlay) _ioPlay.observe(wrap);
        } else {
            /* Desktop : lecture au survol */
            wrap.addEventListener('mouseenter', function() {
                if (window.__VZB_DATA_SAVER) return;
                _play(wrap, vid);
            });
            wrap.addEventListener('mouseleave', function() { _pause(wrap, vid); });
        }
    }

    /* Exposé pour l'infinite scroll et les pages qui ajoutent du contenu */
    window.vzInitVideoAutoplay = function() {
        document.querySelectorAll('.ds-vid-wrap:not([data-ap-init])').forEach(_initWrap);
    };

    document.addEventListener('DOMContentLoaded', function() {
        /* Observer pré-chargement : charge métadonnées 200 px avant le viewport */
        _ioMeta = new IntersectionObserver(function(entries) {
            entries.forEach(function(e) {
                if (!e.isIntersecting) return;
                var vid = e.target.querySelector('video');
                if (vid && !window.__VZB_DATA_SAVER) _preloadMeta(vid);
                _ioMeta.unobserve(e.target); /* une seule passe suffit */
            });
        }, { rootMargin: '200px' });

        /* Observer lecture mobile : joue quand > 50 % visible */
        if (_touch && !window.__VZB_DATA_SAVER) {
            _ioPlay = new IntersectionObserver(function(entries) {
                entries.forEach(function(e) {
                    var wrap = e.target;
                    var vid  = wrap.querySelector('video');
                    if (!vid) return;
                    if (e.isIntersecting && !window.__VZB_DATA_SAVER) {
                        _play(wrap, vid);
                    } else {
                        _pause(wrap, vid);
                    }
                });
            }, { threshold: 0.5 });
        }

        window.vzInitVideoAutoplay();

        /* MutationObserver : initialiser les nouvelles vidéos (infinite scroll) */
        var feed = document.querySelector('.feed-main');
        if (feed) {
            new MutationObserver(window.vzInitVideoAutoplay)
                .observe(feed, { childList: true });
        }
    });
})();

/* ── Bannière connexion lente ── */
window.dsDismissBanner = function() {
    var b = document.getElementById('ds-slow-banner');
    if (!b) return;
    b.classList.add('ds-hiding');
    setTimeout(function() { b.style.display = 'none'; b.classList.remove('ds-hiding'); }, 300);
    try { sessionStorage.setItem('vzb-ds-banner-dismissed', '1'); } catch(e) {}
};

/* ── Init au chargement ── */
document.addEventListener('DOMContentLoaded', function() {
    /* Sync bouton dropdown */
    _syncDsButton(!!window.__VZB_DATA_SAVER);

    /* Appliquer data-saver aux images existantes si actif */
    if (window.__VZB_DATA_SAVER) {
        _applyDataSaver();
    }

    /* Bannière connexion lente (auto-détecté, user n'a pas encore choisi) */
    if (window.__VZB_AUTO_SLOW) {
        var dismissed = false;
        try { dismissed = !!sessionStorage.getItem('vzb-ds-banner-dismissed'); } catch(e) {}
        if (!dismissed) {
            setTimeout(function() {
                var b = document.getElementById('ds-slow-banner');
                if (b) b.style.display = 'flex';
            }, 1500); /* attendre 1.5s que la page soit stable */
        }
    }
});

})(); /* /IIFE data-saver */
