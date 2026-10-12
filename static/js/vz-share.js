/* Généré depuis templates/snippets/base_js.html — script servis en statique (cache navigateur + service worker)
   au lieu d'être renvoyés dans chaque réponse HTML. Modifier ICI, plus dans le gabarit. */

/*  ZootShare.open(url, title)
 *  1. navigator.share() → feuille native iOS / Android (WhatsApp, FB, etc.)
 *  2. Fallback : bottom-sheet avec boutons WhatsApp, Facebook, Copier  */
window.ZootShare = (function() {
    var _url   = '';
    var _sheet = null;   // élément DOM, créé à la demande

    /* ── styles injectés une seule fois ─────────────────────────── */
    function _ensureStyles() {
        if (document.getElementById('_zshr-style')) return;
        var s = document.createElement('style');
        s.id = '_zshr-style';
        s.textContent = [
            '#_zshr-ov{position:fixed;inset:0;background:rgba(0,0,0,.52);',
            'z-index:9900;display:flex;align-items:flex-end;justify-content:center;',
            'opacity:0;pointer-events:none;transition:opacity .22s;}',
            '#_zshr-ov.open{opacity:1;pointer-events:auto;}',
            '#_zshr-sh{background:var(--bg-card);border-radius:20px 20px 0 0;',
            'padding:1.2rem 1.2rem calc(1.4rem + env(safe-area-inset-bottom));',
            'width:100%;max-width:480px;',
            'transform:translateY(100%);',
            'transition:transform .28s cubic-bezier(.32,.72,0,1);',
            'box-shadow:0 -8px 40px rgba(0,0,0,.2);}',
            '#_zshr-ov.open #_zshr-sh{transform:translateY(0);}',
            '._zshr-ttl{font-weight:800;font-size:1rem;color:var(--text);',
            'text-align:center;padding-bottom:.75rem;margin-bottom:1rem;',
            'border-bottom:1px solid var(--border);}',
            '._zshr-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.75rem;margin-bottom:1rem;}',
            '._zshr-btn{display:flex;flex-direction:column;align-items:center;gap:.4rem;',
            'background:none;border:1px solid var(--border);border-radius:14px;',
            'padding:.85rem .5rem;cursor:pointer;text-decoration:none;color:var(--text);',
            'font-family:inherit;transition:background .14s,transform .12s;}',
            '._zshr-btn:hover{background:var(--btn-bg);transform:translateY(-2px);text-decoration:none;color:var(--text);}',
            '._zshr-ico{font-size:1.65rem;line-height:1;}',
            '._zshr-lbl{font-size:.72rem;font-weight:700;}',
            '._zshr-copyrow{display:flex;align-items:center;gap:.5rem;',
            'padding:.6rem 1rem;background:var(--btn-bg);border:1px solid var(--border);',
            'border-radius:12px;font-size:.82rem;color:var(--text-muted);',
            'margin-bottom:.75rem;overflow:hidden;cursor:pointer;}',
            '._zshr-copyrow:hover{background:var(--border);}',
            '._zshr-copyrow .material-icons{font-size:1rem;color:var(--accent);flex-shrink:0;}',
            '._zshr-copyrow span{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}',
            '._zshr-cancel{width:100%;padding:.7rem;background:var(--btn-bg);',
            'border:none;border-radius:12px;font-size:.92rem;font-weight:700;',
            'color:var(--text-muted);cursor:pointer;font-family:inherit;}',
            '._zshr-cancel:hover{background:var(--border);}'
        ].join('');
        document.head.appendChild(s);
    }

    /* ── création du DOM une seule fois ─────────────────────────── */
    function _ensureDOM() {
        if (_sheet) return;
        _ensureStyles();
        var ov = document.createElement('div');
        ov.id = '_zshr-ov';
        ov.innerHTML = [
            '<div id="_zshr-sh">',
                '<div class="_zshr-ttl" id="_zshr-ttl">Partager</div>',
                '<div class="_zshr-grid">',
                    '<a class="_zshr-btn" id="_zshr-wa" href="#" target="_blank" rel="noopener">',
                        '<span class="_zshr-ico">💬</span>',
                        '<span class="_zshr-lbl" style="color:#25d366;">WhatsApp</span>',
                    '</a>',
                    '<a class="_zshr-btn" id="_zshr-fb" href="#" target="_blank" rel="noopener">',
                        '<span class="_zshr-ico">📘</span>',
                        '<span class="_zshr-lbl" style="color:#1877f2;">Facebook</span>',
                    '</a>',
                    '<button class="_zshr-btn" id="_zshr-cp" onclick="ZootShare._copy()">',
                        '<span class="_zshr-ico" id="_zshr-cp-ico">🔗</span>',
                        '<span class="_zshr-lbl" style="color:var(--accent);">Copier</span>',
                    '</button>',
                '</div>',
                '<div class="_zshr-copyrow" onclick="ZootShare._copy()">',
                    '<span class="material-icons">link</span>',
                    '<span id="_zshr-url-txt"></span>',
                '</div>',
                '<button class="_zshr-cancel" onclick="ZootShare.close()">Annuler</button>',
            '</div>'
        ].join('');
        ov.addEventListener('click', function(e){ if(e.target===ov) ZootShare.close(); });
        document.body.appendChild(ov);
        _sheet = ov;
    }

    /* ── API publique ────────────────────────────────────────────── */
    function open(url, title) {
        _url   = url   || window.location.href;
        title  = title || document.title || 'Vazimba';

        /* 1. Feuille native iOS / Android — inclut WhatsApp, Messenger, etc. */
        if (navigator.share) {
            navigator.share({ title: title, url: _url }).catch(function(){});
            return;
        }

        /* 2. Fallback bottom-sheet */
        _ensureDOM();
        var enc = encodeURIComponent(_url);
        var etl = encodeURIComponent(title);
        document.getElementById('_zshr-ttl').textContent      = title.substring(0,60);
        document.getElementById('_zshr-wa').href              = 'https://wa.me/?text=' + etl + '%20' + enc;
        document.getElementById('_zshr-fb').href              = 'https://www.facebook.com/sharer/sharer.php?u=' + enc;
        document.getElementById('_zshr-url-txt').textContent  = _url;
        document.getElementById('_zshr-cp-ico').textContent   = '🔗';
        _sheet.classList.add('open');
        document.body.style.overflow = 'hidden';
    }

    function close() {
        if (!_sheet) return;
        _sheet.classList.remove('open');
        document.body.style.overflow = '';
    }

    function _copy() {
        var ico = document.getElementById('_zshr-cp-ico');
        function done() { if(ico){ico.textContent='✅';} setTimeout(function(){if(ico){ico.textContent='🔗';}},2000); }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(_url).then(done).catch(done);
        } else {
            var t = document.createElement('textarea');
            t.value = _url; t.style.cssText='position:fixed;opacity:0;';
            document.body.appendChild(t); t.select();
            try{document.execCommand('copy');}catch(e){}
            document.body.removeChild(t); done();
        }
    }

    return { open:open, close:close, _copy:_copy };
})();
