/* Généré depuis templates/base.html — script servis en statique (cache navigateur + service worker)
   au lieu d'être renvoyés dans chaque réponse HTML. Modifier ICI, plus dans le gabarit. */

    var _zootLbImgs   = [];
    var _zootLbIdx    = 0;
    var _zootLbCap    = '';

    /* zootOpenImg(src, caption)              — image seule (legacy)
       zootOpenImg(src, caption, galleryId)  — toutes les images de la grille */
    function zootOpenImg(src, caption, galleryId) {
        _zootLbCap = caption || '';
        if (galleryId) {
            var gal = document.getElementById(galleryId);
            if (gal) {
                // Récupère TOUTES les images (y compris celles masquées par CSS nth-child)
                var imgs = Array.from(gal.querySelectorAll('.pc-gal-img'));
                _zootLbImgs = imgs.map(function(i){ return i.src; });
                _zootLbIdx  = Math.max(0, _zootLbImgs.indexOf(src));
            } else {
                _zootLbImgs = [src]; _zootLbIdx = 0;
            }
        } else {
            _zootLbImgs = [src]; _zootLbIdx = 0;
        }
        _zootLbRender();
        if (document.getElementById('zoot-lightbox').style.display !== 'flex' && window.vzLayers) vzLayers.push(zootCloseImg);
        document.getElementById('zoot-lightbox').style.display = 'flex';
        document.body.style.overflow = 'hidden';
        document.addEventListener('keydown', _zootLbKey);
        document.getElementById('zoot-lightbox')._tsx = null;
    }

    function _zootLbRender() {
        var img  = document.getElementById('zoot-lb-img');
        var cap  = document.getElementById('zoot-lb-cap');
        var ctr  = document.getElementById('zoot-lb-counter');
        var prev = document.getElementById('zoot-lb-prev');
        var next = document.getElementById('zoot-lb-next');
        var total = _zootLbImgs.length;

        img.style.opacity = '0';
        img.onload = function(){ img.style.opacity = '1'; };
        img.src = _zootLbImgs[_zootLbIdx] || '';
        if (cap) cap.textContent = _zootLbCap;

        var multi = total > 1;
        if (ctr)  { ctr.textContent  = (_zootLbIdx + 1) + ' / ' + total; ctr.style.display  = multi ? 'block' : 'none'; }
        if (prev) prev.style.display = multi ? 'flex' : 'none';
        if (next) next.style.display = multi ? 'flex' : 'none';
    }

    function _zootLbNav(dir) {
        var t = _zootLbImgs.length;
        if (t <= 1) return;
        _zootLbIdx = (_zootLbIdx + dir + t) % t;
        _zootLbRender();
    }

    function zootCloseImg() {
        if (window.vzLayers) vzLayers.remove(zootCloseImg);
        document.getElementById('zoot-lightbox').style.display = 'none';
        document.getElementById('zoot-lb-prev').style.display  = 'none';
        document.getElementById('zoot-lb-next').style.display  = 'none';
        document.body.style.overflow = '';
        document.removeEventListener('keydown', _zootLbKey);
    }
    function _zootLbKey(e) {
        if (e.key === 'Escape')      zootCloseImg();
        if (e.key === 'ArrowRight')  _zootLbNav(1);
        if (e.key === 'ArrowLeft')   _zootLbNav(-1);
    }
    // Swipe tactile dans le lightbox
    (function(){
        var lb = document.getElementById('zoot-lightbox');
        lb.addEventListener('touchstart', function(e){ lb._tsx = e.touches[0].clientX; }, {passive:true});
        lb.addEventListener('touchend',   function(e){
            if (lb._tsx == null) return;
            var dx = e.changedTouches[0].clientX - lb._tsx;
            if (Math.abs(dx) > 45) _zootLbNav(dx > 0 ? -1 : 1);
            lb._tsx = null;
        }, {passive:true});
    })();
    
