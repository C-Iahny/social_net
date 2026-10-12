/* Généré depuis templates/base.html — script servis en statique (cache navigateur + service worker)
   au lieu d'être renvoyés dans chaque réponse HTML. Modifier ICI, plus dans le gabarit. */

(function(){
    var _srcs = [], _idx = 0;

    /* ── Zoom state ──────────────────────────────────────────────────────── */
    var _scale    = 1,   _minScale = 1, _maxScale = 4;
    var _posX     = 0,   _posY = 0;
    var _lastTap  = 0;
    var _pinching = false, _initDist = 0, _initScale = 1;
    var _panning  = false, _panSX = 0, _panSY = 0, _panOX = 0, _panOY = 0;

    function _applyXform(img) {
        img.style.transform = 'translate('+_posX+'px,'+_posY+'px) scale('+_scale+')';
        img.style.cursor = _scale > 1 ? 'move' : 'grab';
    }
    function _resetZoom() {
        var img = document.getElementById('g-lb-img');
        _scale = 1; _posX = 0; _posY = 0;
        if (img) { img.style.transform = ''; img.style.cursor = 'grab'; }
    }

    /* ── Swipe navigation (quand pas zoomé) ─────────────────────────────── */
    var _swipeStartX = 0, _swipeStartY = 0, _swipeActive = false;

    /* ── Setup des touch events sur l'image ─────────────────────────────── */
    function _setupTouch() {
        var img = document.getElementById('g-lb-img');
        if (!img || img._lbTouchReady) return;
        img._lbTouchReady = true;

        img.addEventListener('touchstart', function(e) {
            if (e.touches.length === 2) {
                /* Pinch start */
                _pinching = true;
                _panning  = false;
                _swipeActive = false;
                _initDist  = Math.hypot(
                    e.touches[0].clientX - e.touches[1].clientX,
                    e.touches[0].clientY - e.touches[1].clientY
                );
                _initScale = _scale;
                e.preventDefault();
            } else if (e.touches.length === 1) {
                var now = Date.now();
                var dx  = e.touches[0].clientX;
                var dy  = e.touches[0].clientY;
                /* Double-tap : zoom 2.5× / reset */
                if (now - _lastTap < 280) {
                    if (_scale > 1) { _resetZoom(); }
                    else { _scale = 2.5; _posX = 0; _posY = 0; _applyXform(img); }
                    _lastTap = 0;
                    e.preventDefault();
                    return;
                }
                _lastTap = now;
                if (_scale > 1) {
                    /* Pan */
                    _panning = true; _swipeActive = false;
                    _panSX = dx; _panSY = dy;
                    _panOX = _posX; _panOY = _posY;
                    e.preventDefault();
                } else {
                    /* Swipe potentiel pour navigation */
                    _swipeActive = true;
                    _swipeStartX = dx; _swipeStartY = dy;
                }
            }
        }, {passive: false});

        img.addEventListener('touchmove', function(e) {
            if (e.touches.length === 2 && _pinching) {
                var dist = Math.hypot(
                    e.touches[0].clientX - e.touches[1].clientX,
                    e.touches[0].clientY - e.touches[1].clientY
                );
                _scale = Math.min(_maxScale, Math.max(_minScale, _initScale * (dist / _initDist)));
                _applyXform(img);
                e.preventDefault();
            } else if (e.touches.length === 1 && _panning && _scale > 1) {
                _posX = _panOX + (e.touches[0].clientX - _panSX);
                _posY = _panOY + (e.touches[0].clientY - _panSY);
                _applyXform(img);
                e.preventDefault();
            }
            /* Si swipe, laisser le scroll naturel (pas de e.preventDefault) */
        }, {passive: false});

        img.addEventListener('touchend', function(e) {
            if (e.touches.length < 2) _pinching = false;
            if (e.touches.length === 0) {
                if (_panning) _panning = false;
                /* Swipe navigation (uniquement si scale = 1) */
                if (_swipeActive && _scale <= 1 && _srcs.length > 1) {
                    var dx = (e.changedTouches[0] || {clientX:_swipeStartX}).clientX - _swipeStartX;
                    var dy = (e.changedTouches[0] || {clientY:_swipeStartY}).clientY - _swipeStartY;
                    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) {
                        window.gLbNav(dx < 0 ? 1 : -1);
                    }
                }
                _swipeActive = false;
                /* Si dézoomé accidentellement sous 1 → reset */
                if (_scale < 1.05) { _scale = 1; _posX = 0; _posY = 0; if (_scale!==1) _applyXform(img); }
            }
        }, {passive: true});
    }

    /* ── API publique ────────────────────────────────────────────────────── */
    window.openGalleryLightbox = function(srcs, idx) {
        _srcs = Array.isArray(srcs) ? srcs : [srcs];
        _idx  = (idx >= 0 && idx < _srcs.length) ? idx : 0;
        _setupTouch();
        _show();
    };

    /* Compatibilité page profil : openLightbox(src, title, counter0) */
    window.openLightbox = function(src, title, idx) {
        var thumbs = document.querySelectorAll('.photo-thumb img');
        if (thumbs.length > 0) {
            var srcs = Array.from(thumbs).map(function(i){ return i.src; });
            window.openGalleryLightbox(srcs, idx || 0);
        } else {
            window.openGalleryLightbox([src], 0);
        }
    };

    window.gLbClose = function() {
        var lb = document.getElementById('g-lightbox');
        if (lb) lb.style.display = 'none';
        document.body.style.overflow = '';
        if (window.vzLayers) vzLayers.remove(window.gLbClose);
        _resetZoom();
    };

    window.gLbNav = function(dir) {
        if (_srcs.length < 2) return;
        /* Si zoomé → reset le zoom avant de naviguer */
        _resetZoom();
        _idx = (_idx + dir + _srcs.length) % _srcs.length;
        _show();
    };

    /* Ouvrir la lightbox depuis un élément .pc-gal-item */
    window.openPostMedia = function(el) {
        var gallery = el.closest('.pc-gallery');
        var items   = gallery ? gallery.querySelectorAll('.pc-gal-item:not(.pc-gal-video)') : [el];
        var srcs    = Array.from(items).map(function(it){
            var img = it.querySelector('img');
            return img ? img.src : '';
        }).filter(Boolean);
        if (!srcs.length) return;
        var idx = Array.from(items).indexOf(el);
        window.openGalleryLightbox(srcs, idx < 0 ? 0 : idx);
    };

    function _show() {
        var lb   = document.getElementById('g-lightbox');
        var img  = document.getElementById('g-lb-img');
        var cnt  = document.getElementById('g-lb-counter');
        var prev = document.getElementById('g-lb-prev');
        var next = document.getElementById('g-lb-next');
        if (!lb) return;
        _resetZoom();
        if (lb.style.display !== 'flex' && window.vzLayers) vzLayers.push(window.gLbClose);
        lb.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        if (img) {
            img.style.opacity = '0';
            img.src = _srcs[_idx] || '';
            img.onload = function(){ img.style.opacity = '1'; };
        }
        if (cnt) cnt.textContent = _srcs.length > 1 ? (_idx+1)+' / '+_srcs.length : '';
        var multi = _srcs.length > 1;
        if (prev) prev.style.display = multi ? 'flex' : 'none';
        if (next) next.style.display = multi ? 'flex' : 'none';
    }

    document.addEventListener('keydown', function(e) {
        var lb = document.getElementById('g-lightbox');
        if (!lb || lb.style.display === 'none') return;
        if (e.key === 'Escape')     { window.gLbClose(); }
        if (e.key === 'ArrowLeft')  { window.gLbNav(-1); }
        if (e.key === 'ArrowRight') { window.gLbNav(1); }
    });
})();
