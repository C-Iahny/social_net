/* Généré depuis templates/snippets/header.html — script servis en statique (cache navigateur + service worker)
   au lieu d'être renvoyés dans chaque réponse HTML. Modifier ICI, plus dans le gabarit. */

(function() {
    var btn  = document.getElementById('zoot-mobile-toggle');
    var menu = document.getElementById('zoot-mobile-menu');
    if (btn && menu) {
        function setOpen(open) {
            menu.classList.toggle('open', open);
            btn.setAttribute('aria-expanded', open ? 'true' : 'false');
            btn.querySelector('.material-icons').textContent = open ? 'close' : 'menu';
        }

        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            setOpen(!menu.classList.contains('open'));
        });

        // Refermer en cliquant hors du menu : il restait ouvert et masquait
        // le contenu tant qu'on ne rappuyait pas exactement sur le bouton.
        document.addEventListener('click', function (e) {
            if (menu.classList.contains('open') && !menu.contains(e.target) && e.target !== btn) {
                setOpen(false);
            }
        });

        // Échap referme le menu (navigation au clavier).
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && menu.classList.contains('open')) {
                setOpen(false);
                btn.focus();
            }
        });
    }
})();

/* ── Lock scroll fond de page quand un dropdown Bootstrap est ouvert (iOS fix) ── */
(function() {
    var _scrollY = 0;
    function lockScroll() {
        if (window.innerWidth > 575) return;  // desktop : ne rien faire
        _scrollY = window.scrollY;
        document.body.classList.add('zoot-dd-open');
        document.body.style.top = '-' + _scrollY + 'px';
    }
    function unlockScroll() {
        if (!document.body.classList.contains('zoot-dd-open')) return;
        document.body.classList.remove('zoot-dd-open');
        document.body.style.top = '';
        document.body.style.position = '';
        window.scrollTo(0, _scrollY);
    }
    /* Exposer globalement pour que les boutons du dropdown puissent fermer proprement */
    window._vzb_unlockScroll = unlockScroll;
    window._vzb_closeDropdown = function(btn) {
        /* Fermer le dropdown via manipulation DOM directe (évite les effets de bord
           de l'API jQuery Bootstrap qui peut déclencher d'autres dropdowns) */
        var dropdown = btn.closest('.dropdown');
        if (dropdown) {
            var menu   = dropdown.querySelector('.dropdown-menu');
            var toggle = dropdown.querySelector('[data-toggle="dropdown"]');
            if (menu)   { menu.classList.remove('show'); }
            if (toggle) { toggle.classList.remove('show'); toggle.setAttribute('aria-expanded','false'); }
        }
        /* Débloquer immédiatement le scroll iOS (ne pas attendre hidden.bs.dropdown) */
        unlockScroll();
    };
    /* Filet de sécurité : si le corps est verrouillé alors qu'aucun menu
       n'est plus ouvert (la WebView Android n'émet pas toujours
       hidden.bs.dropdown après un clic sur un bouton du menu, p. ex. le
       changement de thème), on déverrouille. Sans cela la page restait
       figée en position:fixed jusqu'au rechargement. */
    function _unlockIfNoMenu() {
        if (!document.body.classList.contains('zoot-dd-open')) return;
        if (!document.querySelector('.dropdown-menu.show')) unlockScroll();
    }
    document.addEventListener('click', function() { setTimeout(_unlockIfNoMenu, 120); }, true);
    document.addEventListener('touchend', function() { setTimeout(_unlockIfNoMenu, 200); }, { passive: true, capture: true });
    document.addEventListener('visibilitychange', _unlockIfNoMenu);

    // Bootstrap 4 événements jQuery
    if (window.jQuery) {
        $(document).on('show.bs.dropdown',   lockScroll);
        $(document).on('hidden.bs.dropdown', unlockScroll);
    } else {
        // Fallback vanilla : observer les aria-expanded
        document.querySelectorAll('[data-toggle="dropdown"]').forEach(function(el) {
            el.addEventListener('click', function() {
                setTimeout(function() {
                    var open = document.querySelector('.dropdown-menu.show');
                    if (open) lockScroll(); else unlockScroll();
                }, 50);
            });
        });
        document.addEventListener('click', function(e) {
            if (!e.target.closest('.dropdown')) unlockScroll();
        });
    }
})();
