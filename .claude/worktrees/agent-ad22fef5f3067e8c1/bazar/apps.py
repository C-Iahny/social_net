from django.apps import AppConfig


class BazarConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bazar'
    verbose_name = 'Bazar Vazimba'

    def ready(self):
        # Enregistre pillow-heif comme plugin PIL dès le démarrage.
        # Permet à Django ImageField de valider et ouvrir les photos HEIC/HEIF
        # prises par iPhone (format par défaut depuis iOS 11).
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass  # Lib absente en dev local sans pillow-heif
