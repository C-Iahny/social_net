/* ════════════════════════════════════════════════════════════════════════
   vz-post-card.js — comportements partagés de la carte de post
   (fil, profil, groupe, hashtag, pages chargées en AJAX)
   • vzPostMenu(btn)        : menu ⋯ (copier le lien, partager, sauvegarder,
                              republier, masquer, signaler, bloquer, modifier, supprimer)
   • vzPostBookmark(id,btn) : sauvegarder / retirer, avec toast et action « Voir »
   • vzPostRepost(id)       : republier / annuler
   • vzPostHide(id)         : masquer la carte avec « Annuler »
   • compte à rebours Vintana : une seule boucle pour toutes les capsules
   Dépend de vz-core.js (vzMenu, vzToast, vzShare, vzCopy, vzConfirm) et de
   window.VZ_URLS / window.VZ_CSRF / window.VZ_I18N fournis par base.html.
   ════════════════════════════════════════════════════════════════════════ */
(function () {
    'use strict';
    var I18N = window.VZ_I18N || {};
    var URLS = window.VZ_URLS || {};
    function t(k, fb) { return I18N[k] || fb; }
    function csrf() {
        if (window.VZ_CSRF) return window.VZ_CSRF;
        var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : '';
    }
    function post(url, data) {
        var fd = new FormData();
        Object.keys(data || {}).forEach(function (k) { fd.append(k, data[k]); });
        fd.append('csrfmiddlewaretoken', csrf());
        return fetch(url, { method: 'POST', body: fd, headers: { 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' })
            .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
    }
    function card(id) { return document.getElementById('post-' + id); }
    function absolute(url) { try { return new URL(url, location.href).href; } catch (e) { return url; } }

    /* ── Sauvegarder ─────────────────────────────────────────────────── */
    window.vzPostBookmark = function (postId, btn) {
        if (!URLS.bookmark) return;
        btn = btn || document.getElementById('bk-btn-' + postId);
        return post(URLS.bookmark, { post_id: postId }).then(function (d) {
            if (!d.ok) throw new Error('ko');
            var saved = !!d.saved;
            var c = card(postId);
            if (c) {
                c.querySelectorAll('[data-bookmarked]').forEach(function (el) { el.setAttribute('data-bookmarked', saved ? '1' : '0'); });
                var b = c.querySelector('#bk-btn-' + postId);
                if (b) {
                    b.classList.toggle('bookmarked', saved);
                    b.setAttribute('aria-pressed', saved ? 'true' : 'false');
                    var ic = b.querySelector('.material-icons'); if (ic) ic.textContent = saved ? 'bookmark' : 'bookmark_border';
                    b.setAttribute('aria-label', saved ? t('postUnsave', 'Retirer des sauvegardes') : t('postSave', 'Sauvegarder'));
                }
            }
            if (saved) {
                window.vzToast(t('postSaved', 'Post sauvegardé'), { type: 'success',
                    action: URLS.bookmarks ? { label: t('view', 'Voir'), onClick: function () { location.href = URLS.bookmarks; } } : null });
            } else {
                window.vzToast(t('postUnsaved', 'Retiré des sauvegardes'), 'info');
            }
            return saved;
        }).catch(function () { window.vzToast(t('error', 'Une erreur est survenue'), 'error'); });
    };

    /* ── Republier ───────────────────────────────────────────────────── */
    window.vzPostRepost = function (postId) {
        if (!URLS.repost) return;
        return post(URLS.repost, { post_id: postId }).then(function (d) {
            var c = card(postId);
            if (c) c.querySelectorAll('[data-reposted]').forEach(function (el) { el.setAttribute('data-reposted', d.reposted ? '1' : '0'); });
            var cnt = document.getElementById('repost-count-' + postId);
            if (cnt) { cnt.textContent = d.repost_count > 0 ? d.repost_count : ''; cnt.style.display = d.repost_count > 0 ? '' : 'none'; }
            window.vzToast(d.reposted ? t('reposted', 'Republié sur votre profil') : t('unreposted', 'Republication annulée'), d.reposted ? 'success' : 'info');
        }).catch(function () { window.vzToast(t('error', 'Une erreur est survenue'), 'error'); });
    };

    /* ── Masquer ─────────────────────────────────────────────────────── */
    window.vzPostHide = function (postId) {
        if (!URLS.hide) return;
        var c = card(postId);
        if (c) { c.classList.add('pc-hiding'); setTimeout(function () { c.style.display = 'none'; }, 220); }
        return post(URLS.hide, { post_id: postId }).then(function () {
            window.vzToast(t('postHidden', 'Post masqué'), { type: 'info', duration: 6000,
                action: { label: t('undo', 'Annuler'), onClick: function () {
                    post(URLS.hide, { post_id: postId, undo: '1' }).then(function () {
                        if (c) { c.style.display = ''; c.classList.remove('pc-hiding'); }
                    });
                } } });
        }).catch(function () {
            if (c) { c.style.display = ''; c.classList.remove('pc-hiding'); }
            window.vzToast(t('error', 'Une erreur est survenue'), 'error');
        });
    };

    /* ── Menu ⋯ ───────────────────────────────────────────────────────── */
    window.vzPostMenu = function (btn) {
        var d = btn.dataset;
        var id = d.postId, url = absolute(d.postUrl), owner = d.owner === '1';
        var saved = d.bookmarked === '1', reposted = d.reposted === '1';
        var items = [
            { icon: 'link', label: t('copyLink', 'Copier le lien'), onClick: function () { window.vzCopy(url); } },
            { icon: 'share', label: t('share', 'Partager'), onClick: function () { window.vzShare({ title: d.postTitle || document.title, url: url }); } },
            { icon: saved ? 'bookmark' : 'bookmark_border', label: saved ? t('postUnsave', 'Retirer des sauvegardes') : t('postSave', 'Sauvegarder'),
              onClick: function () { window.vzPostBookmark(id); } },
            URLS.repost ? { icon: 'repeat', label: reposted ? t('unrepost', 'Annuler la republication') : t('repost', 'Republier'),
              onClick: function () { window.vzPostRepost(id); } } : null,
            'sep'
        ];
        if (owner) {
            items.push({ icon: 'edit', label: t('edit', 'Modifier'), href: d.editUrl });
            items.push({ icon: 'delete_outline', label: t('delete', 'Supprimer'), danger: true, onClick: function () {
                window.vzConfirm({ text: t('deleteConfirm', 'Supprimer ce post ?'), danger: true, confirmText: t('delete', 'Supprimer') })
                    .then(function (yes) { if (yes) location.href = d.deleteUrl; });
            } });
        } else {
            items.push({ icon: 'visibility_off', label: t('postHide', 'Masquer ce post'), onClick: function () { window.vzPostHide(id); } });
            items.push({ icon: 'flag', label: t('report', 'Signaler'), onClick: function () {
                if (window.openReportModal) window.openReportModal('post', id);
            } });
            if (d.blockUrl) items.push({ icon: 'block', label: t('block', 'Bloquer') + ' ' + (d.authorName || ''), danger: true, onClick: function () {
                window.vzConfirm({ text: t('blockConfirm', 'Bloquer cette personne ? Vous ne verrez plus ses publications.'), danger: true, confirmText: t('block', 'Bloquer') })
                    .then(function (yes) {
                        if (!yes) return;
                        post(d.blockUrl, {}).then(function () { location.reload(); })
                            .catch(function () { location.href = d.blockUrl; });
                    });
            } });
        }
        window.vzMenu(btn, items, { title: d.authorName ? '@' + d.authorName : '' });
    };

    /* ── Compte à rebours Vintana : une seule boucle ─────────────────── */
    function tickVintana() {
        var nodes = document.querySelectorAll('.vt-cntdwn[data-target]');
        if (!nodes.length) return;
        var now = Date.now();
        for (var i = 0; i < nodes.length; i++) {
            var target = Date.parse(nodes[i].getAttribute('data-target'));
            if (isNaN(target)) continue;
            var diff = target - now;
            if (diff <= 0) { nodes[i].textContent = t('now', 'maintenant !'); continue; }
            var dd = Math.floor(diff / 86400000), h = Math.floor(diff % 86400000 / 3600000),
                m = Math.floor(diff % 3600000 / 60000), s = Math.floor(diff % 60000 / 1000);
            nodes[i].textContent = (dd > 0 ? dd + 'j ' : '') + (h > 0 ? h + 'h ' : '') + (m > 0 ? m + 'min ' : '') + s + 's';
        }
    }
    setInterval(tickVintana, 1000);
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', tickVintana); else tickVintana();
})();
