from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.http import HttpResponseRedirect
from django.urls import path, reverse

from .models import Announcement, HeroSettings


# ──────────────────────────────────────────────────────────────
# Announcement
# ──────────────────────────────────────────────────────────────
@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display  = ('title', 'priority', 'start_date', 'end_date', 'is_active', 'visible_now')
    list_filter   = ('priority', 'is_active')
    search_fields = ('title', 'content')
    list_editable = ('is_active',)
    ordering      = ('-start_date',)

    fieldsets = (
        ('Contenu', {
            'fields': ('title', 'content', 'priority')
        }),
        ('Planification', {
            'fields': ('start_date', 'end_date', 'is_active'),
            'description': 'Définissez la période de diffusion. Laissez "Date de fin" vide pour une annonce permanente.'
        }),
    )

    @admin.display(description='Visible maintenant', boolean=True)
    def visible_now(self, obj):
        return obj.is_visible()


# ──────────────────────────────────────────────────────────────
# HeroSettings  (singleton)
# ──────────────────────────────────────────────────────────────
@admin.register(HeroSettings)
class HeroSettingsAdmin(admin.ModelAdmin):
    """
    Page d'administration pour les réglages du Hero de la page Explore.
    • Color-pickers HTML5 pour les deux couleurs du dégradé
    • Prévisualisation live du dégradé + texte
    • Singleton : redirige la liste vers l'unique instance
    """

    # ── Champs affichés dans le formulaire ──
    readonly_fields = ('hero_preview',)

    fieldsets = (
        ('Textes', {
            'fields': ('title', 'subtitle'),
        }),
        ('Fond dégradé', {
            'fields': ('gradient_from', 'gradient_to'),
            'description': (
                'Choisissez les deux couleurs du dégradé. '
                'Si une image de fond est définie, le dégradé devient un calque semi-transparent par-dessus.'
            ),
        }),
        ('Image de fond', {
            'fields': ('background_image',),
            'description': (
                'Optionnel — téléversez une photo (paysage, bannière…). '
                'Elle remplace le fond uni et le dégradé s\'applique par-dessus pour garder le texte lisible.'
            ),
        }),
        ('Prévisualisation en direct', {
            'fields': ('hero_preview',),
        }),
    )

    # ── Widgets color-picker HTML5 ──
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name in ('gradient_from', 'gradient_to'):
            field.widget.attrs.update({
                'type': 'color',
                'style': 'width:80px; height:42px; padding:2px; border-radius:6px; cursor:pointer;',
                'id': f'id_{db_field.name}',
            })
        return field

    # ── Prévisualisation rendue ──
    @admin.display(description='Aperçu du Hero')
    def hero_preview(self, obj):
        # URL de l'image actuelle (vide si aucune)
        current_img_url = obj.background_image.url if obj.background_image else ''

        return format_html(
            '''
            <!-- Boîte de prévisualisation -->
            <div id="hero-preview-box" style="
                background: linear-gradient(135deg, {from_}cc 0%, {to_}cc 100%){img_bg};
                background-size: cover;
                background-position: center;
                border-radius: 14px;
                padding: 2.5rem 2rem;
                text-align: center;
                color: #fff;
                transition: all .4s;
                max-width: 680px;
                position: relative;
                overflow: hidden;
            ">
                <h2 id="hero-preview-title" style="
                    font-size:1.6rem; font-weight:900; margin:0 0 .7rem;
                    text-shadow:0 2px 12px rgba(0,0,0,.5);
                    position:relative; z-index:1;">{title}</h2>
                <p id="hero-preview-subtitle" style="
                    font-size:.98rem; opacity:.92; margin:0;
                    text-shadow:0 1px 6px rgba(0,0,0,.4);
                    position:relative; z-index:1;">{subtitle}</p>
            </div>

            <!-- Indicateur image actuelle -->
            <p style="margin-top:.6rem; font-size:.82rem; color:#666;" id="hero-img-status">
                {img_status}
            </p>

            <script>
            (function() {{
                var currentImgUrl = '{current_img_url}';

                function hexToRgba(hex, alpha) {{
                    var r = parseInt(hex.slice(1,3),16);
                    var g = parseInt(hex.slice(3,5),16);
                    var b = parseInt(hex.slice(5,7),16);
                    return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
                }}

                function buildBg(fromHex, toHex, imgUrl) {{
                    var fromRgba = hexToRgba(fromHex, 0.78);
                    var toRgba   = hexToRgba(toHex,   0.78);
                    if (imgUrl) {{
                        return 'linear-gradient(135deg, ' + fromRgba + ' 0%, ' + toRgba + ' 100%), url(' + imgUrl + ')';
                    }} else {{
                        return 'linear-gradient(135deg, ' + fromHex + ' 0%, ' + toHex + ' 100%)';
                    }}
                }}

                function sync() {{
                    var fromInput  = document.getElementById('id_gradient_from');
                    var toInput    = document.getElementById('id_gradient_to');
                    var box        = document.getElementById('hero-preview-box');
                    var titleEl    = document.getElementById('hero-preview-title');
                    var subtitleEl = document.getElementById('hero-preview-subtitle');
                    var titleInput    = document.getElementById('id_title');
                    var subtitleInput = document.getElementById('id_subtitle');
                    var imgInput      = document.getElementById('id_background_image');

                    if (fromInput && toInput && box) {{
                        // Si un nouveau fichier est sélectionné, lire son URL en local
                        if (imgInput && imgInput.files && imgInput.files[0]) {{
                            var reader = new FileReader();
                            reader.onload = function(e) {{
                                currentImgUrl = e.target.result;
                                box.style.background = buildBg(fromInput.value, toInput.value, currentImgUrl);
                                box.style.backgroundSize = 'cover';
                                box.style.backgroundPosition = 'center';
                                var status = document.getElementById('hero-img-status');
                                if (status) status.textContent = '📷 Nouvelle image sélectionnée (non encore enregistrée)';
                            }};
                            reader.readAsDataURL(imgInput.files[0]);
                        }} else {{
                            box.style.background = buildBg(fromInput.value, toInput.value, currentImgUrl);
                            box.style.backgroundSize = 'cover';
                            box.style.backgroundPosition = 'center';
                        }}
                    }}
                    if (titleEl && titleInput)       titleEl.textContent    = titleInput.value    || '(titre)';
                    if (subtitleEl && subtitleInput) subtitleEl.textContent = subtitleInput.value || '(texte)';
                }}

                // Écouter les changements sur le champ fichier
                var imgInput = document.getElementById('id_background_image');
                if (imgInput) imgInput.addEventListener('change', sync);

                document.addEventListener('input', sync);
                setTimeout(sync, 150);
            }})();
            </script>
            ''',
            from_=obj.gradient_from,
            to_=obj.gradient_to,
            title=obj.title,
            subtitle=obj.subtitle,
            current_img_url=current_img_url,
            # Fond inline : si image existante, l'appliquer dès le rendu côté serveur
            img_bg=(
                f', url({current_img_url})' if current_img_url else ''
            ),
            img_status=(
                f'📷 Image actuelle : {obj.background_image.name.split("/")[-1]}'
                if obj.background_image else
                '(aucune image — fond dégradé seul)'
            ),
        )

    # ── Permissions : pas d'ajout, pas de suppression ──
    def has_add_permission(self, request):
        return not HeroSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    # ── Singleton : la "liste" redirige vers l'instance unique ──
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '',
                self.admin_site.admin_view(self._redirect_to_instance),
                name='personal_herosettings_changelist',
            ),
        ]
        return custom + urls

    def _redirect_to_instance(self, request):
        obj = HeroSettings.get()   # crée l'instance si elle n'existe pas encore
        return HttpResponseRedirect(
            reverse('admin:personal_herosettings_change', args=[obj.pk])
        )
