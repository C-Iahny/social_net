/* Généré depuis templates/snippets/base_js.html — script servis en statique (cache navigateur + service worker)
   au lieu d'être renvoyés dans chaque réponse HTML. Modifier ICI, plus dans le gabarit. */

/* ────────────────────────────────────────────────────────────────────────
   ZootMediaConverter — utilitaire global de conversion avant upload
   Usage :
     const files = await ZootMediaConverter.processFiles(fileList);
     // files : tableau de File objets, images converties en WebP, vidéos inchangées
   ──────────────────────────────────────────────────────────────────────── */
window.ZootMediaConverter = (function() {

    var HEIC2ANY_CDN = 'https://cdn.jsdelivr.net/npm/heic2any@0.0.4/dist/heic2any.min.js';
    var _heic2anyLoaded = false;
    var _heic2anyLoading = null;

    // ── Toast feedback ──────────────────────────────────────────────────────
    var _toastEl = null;
    var _toastTimer = null;
    function _showToast(msg) {
        if (window.vzToast) { vzToast(msg, { type: 'info', duration: 3000 }); return; }
        if (!_toastEl) {
            _toastEl = document.createElement('div');
            _toastEl.style.cssText = [
                'position:fixed', 'bottom:80px', 'left:50%',
                'transform:translateX(-50%)',
                'background:rgba(30,30,30,.88)', 'color:#fff',
                'font-size:.8rem', 'font-weight:600',
                'padding:.45rem 1rem', 'border-radius:20px',
                'z-index:99999', 'pointer-events:none',
                'white-space:nowrap',
                'box-shadow:0 4px 16px rgba(0,0,0,.3)',
                'transition:opacity .3s'
            ].join(';');
            document.body.appendChild(_toastEl);
        }
        _toastEl.textContent = msg;
        _toastEl.style.opacity = '1';
        clearTimeout(_toastTimer);
        _toastTimer = setTimeout(function() {
            _toastEl.style.opacity = '0';
        }, 3000);
    }

    function _fmtSize(bytes) {
        if (bytes >= 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' Mo';
        return Math.round(bytes / 1024) + ' Ko';
    }

    // ── HEIC loader ─────────────────────────────────────────────────────────
    function loadHeic2any() {
        if (_heic2anyLoaded) return Promise.resolve();
        if (_heic2anyLoading) return _heic2anyLoading;
        _heic2anyLoading = new Promise(function(resolve, reject) {
            var s = document.createElement('script');
            s.src = HEIC2ANY_CDN;
            s.onload = function() { _heic2anyLoaded = true; resolve(); };
            s.onerror = reject;
            document.head.appendChild(s);
        });
        return _heic2anyLoading;
    }

    function isHeic(file) {
        if (file.type === 'image/heic' || file.type === 'image/heif') return true;
        var n = (file.name || '').toLowerCase();
        return n.endsWith('.heic') || n.endsWith('.heif');
    }

    function isImage(file) {
        return file.type.startsWith('image/') || isHeic(file);
    }

    // ── Canvas → WebP (+ fallback JPEG si WebP non supporté) ───────────────
    // FIX : Promise.resolve(val, extra) ignore le 2e argument — on retourne
    // un objet {blob, mime} pour transmettre le type MIME correctement.
    function canvasToSmallest(canvas, origSize) {
        // Qualité adaptive : 0.72 pour les très gros fichiers, 0.82 sinon
        var q = origSize > 3 * 1024 * 1024 ? 0.72 : 0.82;
        return new Promise(function(resolve) {
            canvas.toBlob(function(webpBlob) {
                if (webpBlob && webpBlob.size < origSize) {
                    resolve({ blob: webpBlob, mime: 'image/webp' });
                    return;
                }
                // WebP non supporté ou plus grand → essayer JPEG
                canvas.toBlob(function(jpegBlob) {
                    if (jpegBlob && jpegBlob.size < origSize) {
                        resolve({ blob: jpegBlob, mime: 'image/jpeg' });
                    } else {
                        resolve(null); // conserver l'original
                    }
                }, 'image/jpeg', q);
            }, 'image/webp', q);
        });
    }

    function resizeAndConvert(imgEl, origSize) {
        var MAX = 1920;
        var w = imgEl.naturalWidth  || imgEl.width;
        var h = imgEl.naturalHeight || imgEl.height;

        // FIX portrait : on redimensionne selon la plus grande dimension
        if (w > MAX || h > MAX) {
            if (w >= h) { h = Math.round(h * MAX / w); w = MAX; }
            else        { w = Math.round(w * MAX / h); h = MAX; }
        }

        var canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        canvas.getContext('2d').drawImage(imgEl, 0, 0, w, h);
        return canvasToSmallest(canvas, origSize);
    }

    function convertImageToWebP(file) {
        return new Promise(function(resolve) {
            var baseName = file.name.replace(/\.[^.]+$/, '');

            function fromBlob(sourceBlob, reportOrig) {
                var url = URL.createObjectURL(sourceBlob);
                var img = new Image();
                img.onload = function() {
                    resizeAndConvert(img, reportOrig || file.size).then(function(result) {
                        URL.revokeObjectURL(url);
                        // result = { blob, mime } ou null
                        if (!result || !result.blob) { resolve(file); return; }
                        var mime = result.mime || 'image/webp';
                        var ext  = (mime === 'image/jpeg') ? '.jpg' : '.webp';
                        var compressed = new File(
                            [result.blob],
                            baseName + ext,
                            { type: mime, lastModified: Date.now() }
                        );
                        // Feedback toast
                        var saved = file.size - compressed.size;
                        if (saved > 10 * 1024) { // signaler uniquement si > 10 Ko économisés
                            _showToast('📦 ' + _fmtSize(file.size) + ' → ' + _fmtSize(compressed.size)
                                + '  (−' + Math.round(saved / file.size * 100) + '%)');
                        }
                        resolve(compressed);
                    });
                };
                img.onerror = function() {
                    URL.revokeObjectURL(url);
                    /* WebView Android (application) : une URL blob: peut être refusée
                       pour les images → second essai en data-URL avant d'abandonner
                       (sinon la photo partait sans aucune compression). */
                    try {
                        var rd = new FileReader();
                        rd.onload = function(e) {
                            var img2 = new Image();
                            img2.onload = function() {
                                resizeAndConvert(img2, reportOrig || file.size).then(function(result) {
                                    if (!result || !result.blob) { resolve(file); return; }
                                    var mime = result.mime || 'image/webp';
                                    resolve(new File([result.blob], baseName + (mime === 'image/jpeg' ? '.jpg' : '.webp'),
                                                     { type: mime, lastModified: Date.now() }));
                                }).catch(function() { resolve(file); });
                            };
                            img2.onerror = function() { resolve(file); };
                            img2.src = e.target.result;
                        };
                        rd.onerror = function() { resolve(file); };
                        rd.readAsDataURL(sourceBlob);
                    } catch (e) { resolve(file); }
                };
                img.src = url;
            }

            if (isHeic(file)) {
                loadHeic2any().then(function() {
                    heic2any({ blob: file, toType: 'image/jpeg', quality: 0.9 })
                        .then(function(jpegBlob) { fromBlob(jpegBlob, file.size); })
                        .catch(function() { resolve(file); });
                }).catch(function() { resolve(file); });
            } else {
                fromBlob(file, file.size);
            }
        });
    }

    function processFiles(fileListOrArray) {
        var files = Array.from(fileListOrArray);
        var promises = files.map(function(f) {
            if (isImage(f)) return convertImageToWebP(f);
            return Promise.resolve(f);   // vidéos et autres : inchangés
        });
        return Promise.all(promises);
    }

    return { processFiles: processFiles, isHeic: isHeic };

})();
