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
