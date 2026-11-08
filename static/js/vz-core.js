/* ════════════════════════════════════════════════════════════════════════
   vz-core.js — socle commun d'interface Vazimba
   • vzToast(msg, opts)      : notification brève (remplace les toasts maison)
   • vzAlert(msg)            : remplace alert()  (toast d'avertissement, 5 s)
   • vzConfirm(opts)         : remplace confirm() → Promise<boolean>, en feuille
   • vzLayers                : pile des calques ouverts (feuilles, modales) pour
                               le bouton Retour Android et la touche Échap
   • vzLock / vzUnlock       : verrou de défilement unique, à compteur
   • garde anti double-soumission sur tous les formulaires POST
   • data-vz-confirm="…"     : confirmation avant soumission d'un formulaire
   • messages Django (#vz-flash) rendus en toasts
   • vzTimeAgo(date)         : « à l'instant · 5 min · 3 h · 2 j · 8 nov. » ; les
                               <time data-vz-since> sont rafraîchis chaque minute
   • vzCopy(text)            : presse-papiers + toast « Lien copié »
   • vzShare({title,url})    : partage natif, repli sur vzCopy
   • vzMenu(anchor, items)   : menu d'actions contextuel (feuille sur mobile,
                               popover sur bureau), items = [{icon,label,onClick,danger,href}]
   Libellés traduits fournis par base.html dans window.VZ_I18N.
   ════════════════════════════════════════════════════════════════════════ */
(function () {
    'use strict';
    var I18N = window.VZ_I18N || {};
    function t(key, fallback) { return I18N[key] || fallback; }

    /* ── Verrou de défilement à compteur ──────────────────────────────── */
    var _locks = 0;
    window.vzLock = function () {
        _locks++;
        document.body.classList.add('vz-lock');
    };
    window.vzUnlock = function (force) {
        _locks = force ? 0 : Math.max(0, _locks - 1);
        if (_locks === 0) document.body.classList.remove('vz-lock');
    };

    /* ── Pile des calques ouverts ─────────────────────────────────────── */
    var _layers = [];
    window.vzLayers = {
        push: function (closeFn) { _layers.push(closeFn); return closeFn; },
        remove: function (closeFn) {
            var i = _layers.lastIndexOf(closeFn);
            if (i >= 0) _layers.splice(i, 1);
        },
        closeTop: function () {
            var fn = _layers.pop();
            if (!fn) return false;
            try { fn(); } catch (e) {}
            return true;
        },
        count: function () { return _layers.length; }
    };
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && _layers.length) {
            e.preventDefault();
            window.vzLayers.closeTop();
        }
    });

    /* ── Toasts ──────────────────────────────────────────────────────── */
    var ICONS = { success: 'check_circle', error: 'error', warning: 'warning', info: 'info' };
    function _container() {
        var c = document.getElementById('vz-toasts');
        if (!c) {
            c = document.createElement('div');
            c.id = 'vz-toasts';
            c.setAttribute('role', 'status');
            c.setAttribute('aria-live', 'polite');
            (document.body || document.documentElement).appendChild(c);
        }
        return c;
    }
    function _el(tag, cls, text) {
        var el = document.createElement(tag);
        if (cls) el.className = cls;
        if (text != null) el.textContent = text;
        return el;
    }
    window.vzToast = function (msg, opts) {
        if (typeof opts === 'string') opts = { type: opts };
        if (typeof opts === 'number') opts = { duration: opts };
        opts = opts || {};
        var type = ICONS[opts.type] ? opts.type : 'info';
        var duration = (opts.duration != null) ? opts.duration : (type === 'error' ? 5000 : 3200);
        var box = _container();
        var item = _el('div', 'vz-toast vz-toast--' + type);
        item.appendChild(_el('span', 'material-icons', opts.icon || ICONS[type]));
        item.appendChild(_el('span', 'vz-toast-msg', String(msg == null ? '' : msg)));
        var timer = null;
        function close() {
            clearTimeout(timer);
            if (!item.parentNode) return;
            item.classList.add('vz-toast-out');
            setTimeout(function () { if (item.parentNode) item.parentNode.removeChild(item); }, 220);
        }
        if (opts.action && opts.action.label) {
            var a = _el('button', 'vz-toast-action', opts.action.label);
            a.type = 'button';
            a.onclick = function () { close(); try { opts.action.onClick && opts.action.onClick(); } catch (e) {} };
            item.appendChild(a);
        }
        if (!duration || opts.closable) {
            var x = _el('button', 'vz-toast-close');
            x.type = 'button';
            x.setAttribute('aria-label', t('close', 'Fermer'));
            x.appendChild(_el('span', 'material-icons', 'close'));
            x.onclick = close;
            item.appendChild(x);
        }
        /* 3 toasts visibles au plus */
        while (box.children.length >= 3) box.removeChild(box.firstChild);
        box.appendChild(item);
        if (duration) timer = setTimeout(close, duration);
        item.close = close;
        return item;
    };
    window.vzAlert = function (msg) {
        return window.vzToast(msg, { type: 'warning', duration: 5000, closable: true });
    };

    /* ── Confirmation en feuille ──────────────────────────────────────── */
    window.vzConfirm = function (opts) {
        if (typeof opts === 'string') opts = { text: opts };
        opts = opts || {};
        return new Promise(function (resolve) {
            var overlay = _el('div', 'vz-overlay');
            var dlg = _el('div', 'vz-dialog' + (opts.danger ? ' vz-dialog--danger' : ''));
            dlg.setAttribute('role', 'alertdialog');
            dlg.setAttribute('aria-modal', 'true');
            dlg.appendChild(_el('div', 'vz-dialog-handle'));
            var head = _el('div', 'vz-dialog-head');
            head.appendChild(_el('span', 'material-icons', opts.icon || (opts.danger ? 'delete_outline' : 'help_outline')));
            var title = _el('h3', 'vz-dialog-title', opts.title || t('confirmTitle', 'Confirmer'));
            title.id = 'vz-dlg-title-' + Date.now();
            dlg.setAttribute('aria-labelledby', title.id);
            head.appendChild(title);
            dlg.appendChild(head);
            if (opts.text) dlg.appendChild(_el('p', 'vz-dialog-text', opts.text));
            var actions = _el('div', 'vz-dialog-actions');
            var cancel = _el('button', 'vz-btn vz-btn--secondary', opts.cancelText || t('cancel', 'Annuler'));
            cancel.type = 'button';
            var ok = _el('button', 'vz-btn ' + (opts.danger ? 'vz-btn--danger' : 'vz-btn--primary'),
                         opts.confirmText || t('confirm', 'Confirmer'));
            ok.type = 'button';
            actions.appendChild(cancel); actions.appendChild(ok);
            dlg.appendChild(actions);
            overlay.appendChild(dlg);

            var done = false, previous = document.activeElement;
            function finish(value) {
                if (done) return; done = true;
                window.vzLayers.remove(closeFromLayer);
                overlay.classList.remove('open');
                window.vzUnlock();
                setTimeout(function () { if (overlay.parentNode) overlay.parentNode.removeChild(overlay); }, 200);
                try { previous && previous.focus && previous.focus(); } catch (e) {}
                resolve(value);
            }
            function closeFromLayer() { finish(false); }
            cancel.onclick = function () { finish(false); };
            ok.onclick = function () { finish(true); };
            overlay.addEventListener('click', function (e) { if (e.target === overlay) finish(false); });
            /* piège de focus minimal : Tab reste dans la boîte */
            dlg.addEventListener('keydown', function (e) {
                if (e.key !== 'Tab') return;
                var f = [cancel, ok];
                if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[1].focus(); }
                else if (!e.shiftKey && document.activeElement === f[1]) { e.preventDefault(); f[0].focus(); }
            });
            document.body.appendChild(overlay);
            window.vzLock();
            window.vzLayers.push(closeFromLayer);
            overlay.getBoundingClientRect();
            overlay.classList.add('open');
            setTimeout(function () { (opts.danger ? cancel : ok).focus(); }, 30);
        });
    };

    /* ── Formulaires : confirmation déclarative + garde anti double clic ── */
    function _submitButtons(form) {
        return Array.prototype.slice.call(
            form.querySelectorAll('button[type="submit"], input[type="submit"], button:not([type])')
        );
    }
    function _release(form) {
        if (form.dataset.vzSubmitting !== '1') return;
        delete form.dataset.vzSubmitting;
        _submitButtons(form).forEach(function (b) {
            b.classList.remove('is-loading');
            b.removeAttribute('aria-busy');
            if (b.dataset.vzWasDisabled !== '1') b.disabled = false;
            delete b.dataset.vzWasDisabled;
        });
    }
    window.vzReleaseForm = _release;

    /* Liens et boutons simples porteurs de data-vz-confirm */
    document.addEventListener('click', function (e) {
        var el = e.target.closest && e.target.closest('a[data-vz-confirm], button[type="button"][data-vz-confirm]');
        if (!el || el.dataset.vzConfirmed === '1') return;
        e.preventDefault();
        e.stopImmediatePropagation();
        window.vzConfirm({ text: el.dataset.vzConfirm, danger: el.hasAttribute('data-vz-danger'),
                           confirmText: el.dataset.vzConfirmLabel })
        .then(function (yes) {
            if (!yes) return;
            if (el.tagName === 'A' && el.getAttribute('href')) { window.location.href = el.href; return; }
            el.dataset.vzConfirmed = '1';
            el.click();
            setTimeout(function () { delete el.dataset.vzConfirmed; }, 0);
        });
    }, true);

    /* Phase de capture : intercepter avant les gestionnaires de la page */
    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!(form instanceof HTMLFormElement)) return;
        var submitter = e.submitter || null;
        var msg = (submitter && submitter.dataset.vzConfirm) || form.dataset.vzConfirm;
        if (!msg || form.dataset.vzConfirmed === '1') return;
        e.preventDefault();
        e.stopImmediatePropagation();
        var danger = (submitter && submitter.hasAttribute('data-vz-danger')) || form.hasAttribute('data-vz-danger');
        window.vzConfirm({ text: msg, danger: danger,
                           confirmText: (submitter && submitter.dataset.vzConfirmLabel) || form.dataset.vzConfirmLabel })
        .then(function (yes) {
            if (!yes) return;
            form.dataset.vzConfirmed = '1';
            if (form.requestSubmit) {
                try { submitter ? form.requestSubmit(submitter) : form.requestSubmit(); }
                catch (err) { form.submit(); }
            } else {
                form.submit();
            }
            setTimeout(function () { delete form.dataset.vzConfirmed; }, 0);
        });
    }, true);

    /* Phase de bouillonnement : s'exécute après les gestionnaires de la
       page ; si l'un d'eux a annulé l'envoi (fetch maison, validation), on
       ne touche à rien. */
    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!(form instanceof HTMLFormElement)) return;
        if (e.defaultPrevented || form.hasAttribute('data-no-guard')) return;
        if ((form.getAttribute('method') || 'get').toLowerCase() !== 'post') return;
        if (form.dataset.vzSubmitting === '1') { e.preventDefault(); return; }
        form.dataset.vzSubmitting = '1';
        var btns = _submitButtons(form);
        /* désactiver après la constitution des données du formulaire */
        setTimeout(function () {
            btns.forEach(function (b) {
                b.dataset.vzWasDisabled = b.disabled ? '1' : '0';
                b.classList.add('is-loading');
                b.setAttribute('aria-busy', 'true');
                b.disabled = true;
            });
        }, 0);
        setTimeout(function () { _release(form); }, 12000);
    }, false);
    window.addEventListener('pageshow', function () {
        document.querySelectorAll('form[data-vz-submitting="1"]').forEach(_release);
    });


    /* ── Dates relatives ──────────────────────────────────────────────── */
    var MONTHS = {
        fr: ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'],
        en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
        mg: ['Jan', 'Feb', 'Mar', 'Apr', 'Mey', 'Jon', 'Jol', 'Aog', 'Sep', 'Okt', 'Nov', 'Des']
    };
    var UNITS = {
        fr: { m: ' min', h: ' h', d: ' j' },
        en: { m: ' min', h: ' h', d: ' d' },
        mg: { m: ' min', h: ' ora', d: ' andro' }
    };
    function _lang() { return (I18N.lang || document.documentElement.lang || 'fr').slice(0, 2); }
    window.vzTimeAgo = function (value, now) {
        var d = (value instanceof Date) ? value : new Date(value);
        if (isNaN(d.getTime())) return '';
        now = now || new Date();
        var lang = _lang(), u = UNITS[lang] || UNITS.fr, mo = MONTHS[lang] || MONTHS.fr;
        var s = Math.round((now - d) / 1000);
        if (s < 45) return t('justNow', "à l'instant");
        var m = Math.floor(s / 60);
        if (m < 60) return Math.max(m, 1) + u.m;
        var h = Math.floor(m / 60);
        if (h < 24) return h + u.h;
        var days = Math.floor(h / 24);
        if (days < 7) return days + u.d;
        var label = d.getDate() + ' ' + mo[d.getMonth()];
        return d.getFullYear() === now.getFullYear() ? label : label + ' ' + d.getFullYear();
    };
    function _refreshTimes() {
        var now = new Date();
        var nodes = document.querySelectorAll('time[data-vz-since]');
        for (var i = 0; i < nodes.length; i++) {
            var iso = nodes[i].getAttribute('datetime');
            if (!iso) continue;
            var label = window.vzTimeAgo(iso, now);
            if (label && nodes[i].textContent !== label) nodes[i].textContent = label;
        }
    }
    setInterval(_refreshTimes, 60000);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) _refreshTimes(); });

    /* ── Presse-papiers et partage ───────────────────────────────────── */
    window.vzCopy = function (text, msg) {
        function ok() { window.vzToast(msg || t('copied', 'Lien copié'), 'success'); return true; }
        function legacy() {
            try {
                var ta = document.createElement('textarea');
                ta.value = text; ta.setAttribute('readonly', '');
                ta.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0';
                document.body.appendChild(ta); ta.select();
                var done = document.execCommand('copy');
                document.body.removeChild(ta);
                return done ? ok() : false;
            } catch (e) { return false; }
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text).then(ok, legacy);
        }
        return Promise.resolve(legacy());
    };
    window.vzShare = function (data) {
        data = data || {};
        var url = data.url || location.href;
        try { url = new URL(url, location.href).href; } catch (e) {}
        if (navigator.share) {
            return navigator.share({ title: data.title || document.title, text: data.text || '', url: url })
                .then(function () { return true; })
                .catch(function (err) {
                    if (err && err.name === 'AbortError') return false;
                    return window.vzCopy(url);
                });
        }
        if (window.ZootShare && window.ZootShare.open) { window.ZootShare.open(url, data.title || ''); return Promise.resolve(true); }
        return window.vzCopy(url);
    };

    /* ── Menu d'actions contextuel ───────────────────────────────────── */
    var _menuOpen = null;
    function _closeMenu() {
        var m = _menuOpen; if (!m) return;
        _menuOpen = null;
        window.vzLayers.remove(_closeMenu);
        m.overlay.classList.remove('open');
        if (m.sheet) window.vzUnlock();
        document.removeEventListener('click', m.onDoc, true);
        window.removeEventListener('resize', _closeMenu);
        window.removeEventListener('scroll', m.onScroll, true);
        setTimeout(function () { if (m.overlay.parentNode) m.overlay.parentNode.removeChild(m.overlay); }, 180);
        try { m.anchor && m.anchor.setAttribute('aria-expanded', 'false'); } catch (e) {}
        try { m.anchor && m.anchor.focus && m.anchor.focus(); } catch (e) {}
    }
    window.vzMenu = function (anchor, items, opts) {
        opts = opts || {};
        if (_menuOpen) { var same = _menuOpen.anchor === anchor; _closeMenu(); if (same) return; }
        items = (items || []).filter(Boolean);
        if (!items.length) return;
        var sheet = window.matchMedia('(max-width: 639px)').matches;
        var overlay = _el('div', 'vz-menu-overlay' + (sheet ? ' vz-menu-overlay--sheet' : ''));
        var menu = _el('div', 'vz-menu' + (sheet ? ' vz-menu--sheet' : ''));
        menu.setAttribute('role', 'menu');
        if (sheet) {
            menu.appendChild(_el('div', 'vz-dialog-handle'));
            if (opts.title) menu.appendChild(_el('div', 'vz-menu-title', opts.title));
        }
        items.forEach(function (it) {
            if (it === 'sep' || it.sep) { menu.appendChild(_el('div', 'vz-menu-sep')); return; }
            var row = _el(it.href ? 'a' : 'button', 'vz-menu-item' + (it.danger ? ' vz-menu-item--danger' : ''));
            if (it.href) row.href = it.href; else row.type = 'button';
            row.setAttribute('role', 'menuitem');
            if (it.icon) row.appendChild(_el('span', 'material-icons', it.icon));
            var txt = _el('span', 'vz-menu-label', it.label);
            row.appendChild(txt);
            if (it.hint) row.appendChild(_el('span', 'vz-menu-hint', it.hint));
            row.addEventListener('click', function (e) {
                if (!it.href) e.preventDefault();
                _closeMenu();
                try { it.onClick && it.onClick(e); } catch (err) { console.error(err); }
            });
            menu.appendChild(row);
        });
        if (sheet) {
            var cancel = _el('button', 'vz-menu-item vz-menu-cancel', t('cancel', 'Annuler'));
            cancel.type = 'button'; cancel.onclick = _closeMenu;
            menu.appendChild(cancel);
        }
        overlay.appendChild(menu);
        document.body.appendChild(overlay);

        if (!sheet && anchor && anchor.getBoundingClientRect) {
            var r = anchor.getBoundingClientRect();
            menu.style.position = 'fixed';
            menu.style.visibility = 'hidden';
            menu.style.display = 'block';
            var mw = menu.offsetWidth, mh = menu.offsetHeight;
            var left = Math.min(Math.max(8, r.right - mw), window.innerWidth - mw - 8);
            var top = r.bottom + 6;
            if (top + mh > window.innerHeight - 8) top = Math.max(8, r.top - mh - 6);
            menu.style.left = left + 'px'; menu.style.top = top + 'px';
            menu.style.visibility = '';
        }
        var state = {
            overlay: overlay, anchor: anchor, sheet: sheet,
            onDoc: function (e) { if (!menu.contains(e.target)) { e.preventDefault(); e.stopPropagation(); _closeMenu(); } },
            onScroll: function () { if (!sheet) _closeMenu(); }
        };
        _menuOpen = state;
        if (sheet) window.vzLock();
        window.vzLayers.push(_closeMenu);
        setTimeout(function () {
            document.addEventListener('click', state.onDoc, true);
            window.addEventListener('resize', _closeMenu);
            window.addEventListener('scroll', state.onScroll, true);
        }, 0);
        try { anchor && anchor.setAttribute('aria-expanded', 'true'); } catch (e) {}
        overlay.getBoundingClientRect();
        overlay.classList.add('open');
        menu.addEventListener('keydown', function (e) {
            var focusables = menu.querySelectorAll('.vz-menu-item');
            var idx = Array.prototype.indexOf.call(focusables, document.activeElement);
            if (e.key === 'ArrowDown') { e.preventDefault(); (focusables[idx + 1] || focusables[0]).focus(); }
            if (e.key === 'ArrowUp') { e.preventDefault(); (focusables[idx - 1] || focusables[focusables.length - 1]).focus(); }
        });
        setTimeout(function () { var f = menu.querySelector('.vz-menu-item'); f && f.focus(); }, 30);
        return _closeMenu;
    };
    /* Déclencheur déclaratif : <button data-vz-menu="id-du-template"> où le
       template contient des <a>/<button data-icon data-danger>. */
    document.addEventListener('click', function (e) {
        var btn = e.target.closest && e.target.closest('[data-vz-menu]');
        if (!btn) return;
        var tpl = document.getElementById(btn.getAttribute('data-vz-menu'));
        if (!tpl) return;
        e.preventDefault();
        var items = [];
        Array.prototype.forEach.call(tpl.content ? tpl.content.children : tpl.children, function (node) {
            if (node.tagName === 'HR') { items.push('sep'); return; }
            var clone = node;
            items.push({
                icon: node.getAttribute('data-icon'),
                label: node.textContent.trim(),
                danger: node.hasAttribute('data-danger'),
                href: node.tagName === 'A' ? node.getAttribute('href') : null,
                onClick: function () { if (node.tagName !== 'A') { var fn = node.getAttribute('data-onclick'); if (fn) { try { (new Function(fn)).call(btn); } catch (err) { console.error(err); } } } }
            });
        });
        window.vzMenu(btn, items, { title: btn.getAttribute('data-vz-menu-title') || '' });
    });

    /* ── Afficher / masquer le mot de passe ──────────────────────────── */
    function _pwToggles() {
        document.querySelectorAll('.auth-input-wrap > input[type="password"], .vz-field input[type="password"], .edit-input-wrap > input[type="password"]').forEach(function (inp) {
            if (inp.dataset.vzPw === '1') return;
            inp.dataset.vzPw = '1';
            var b = _el('button', 'vz-pw-toggle');
            b.type = 'button';
            b.setAttribute('aria-label', t('showPassword', 'Afficher le mot de passe'));
            b.setAttribute('aria-pressed', 'false');
            b.appendChild(_el('span', 'material-icons', 'visibility'));
            b.addEventListener('click', function () {
                var show = inp.type === 'password';
                inp.type = show ? 'text' : 'password';
                b.firstChild.textContent = show ? 'visibility_off' : 'visibility';
                b.setAttribute('aria-pressed', show ? 'true' : 'false');
                b.setAttribute('aria-label', show ? t('hidePassword', 'Masquer le mot de passe') : t('showPassword', 'Afficher le mot de passe'));
                inp.focus();
            });
            inp.parentNode.insertBefore(b, inp.nextSibling);
        });
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', _pwToggles); else _pwToggles();

    /* ── Messages Django → toasts ─────────────────────────────────────── */
    function _flash() {
        var node = document.getElementById('vz-flash');
        if (!node) return;
        var list = [];
        try { list = JSON.parse(node.textContent || '[]'); } catch (e) {}
        node.parentNode && node.parentNode.removeChild(node);
        list.forEach(function (m, i) {
            var tags = String(m.t || '');
            var type = /error|danger/.test(tags) ? 'error' : /success/.test(tags) ? 'success'
                     : /warning/.test(tags) ? 'warning' : 'info';
            setTimeout(function () { window.vzToast(m.m, { type: type, duration: type === 'error' ? 6000 : 4000 }); }, 150 * i);
        });
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', _flash);
    else _flash();
})();
