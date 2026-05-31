"""
Storage personnalisé pour les fichiers statiques et médias en production.

Deux problèmes à résoudre avec WhiteNoise 6.x :

1. collectstatic : CompressedManifestStaticFilesStorage lève MissingFileError
   pour les fichiers référencés mais absents (ex. *.css.map sourcemaps).
   → On intercepte dans post_process.

2. Rendu des templates : quand {% static 'xxx' %} est évalué, Django appelle
   stored_name() qui appelle hashed_name() → ValueError si le fichier n'est
   pas dans le manifeste. manifest_strict=False ne suffit pas car WhiteNoise
   surcharge hashed_name() sans attraper l'exception.
   → On surcharge stored_name() pour retourner le nom original en fallback.
"""
import logging
import warnings
from django.conf import settings
from whitenoise.storage import CompressedManifestStaticFilesStorage, MissingFileError

# ── Media Cloudflare R2 (S3-compatible) ──────────────────────────────────────
try:
    from storages.backends.s3boto3 import S3Boto3Storage

    class R2MediaStorage(S3Boto3Storage):
        """
        Backend Cloudflare R2 via l'API S3-compatible.
        Hérite de S3Boto3Storage mais utilise l'endpoint R2 configuré dans settings.py.
        Les fichiers uploadés sont publics (ACL public-read via AWS_DEFAULT_ACL).
        """
        # Pas besoin de surcharger : tout vient de settings.py (AWS_* variables)
        pass

except ImportError:
    # En développement sans django-storages, on utilise le backend local.
    from django.core.files.storage import FileSystemStorage as R2MediaStorage  # noqa: F811

# Alias rétro-compatible : les migrations existantes importent AutoMediaCloudinaryStorage
AutoMediaCloudinaryStorage = R2MediaStorage
# ─────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

# CKEditor référence des assets (PNG/SVG/GIF) absents du manifeste → Django émet
# des RuntimeWarning très verbeux à chaque collectstatic. On les supprime ici
# car ils ne représentent aucun vrai problème de fonctionnement.
warnings.filterwarnings(
    "ignore",
    message=r"The CSS file .* references a file which could not be found",
    category=RuntimeWarning,
)


class RelaxedStaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False  # Indique à Django de ne pas lever de ValueError

    def stored_name(self, name):
        """
        Fallback : si le fichier n'est pas dans le manifeste (ValueError),
        retourner le nom original sans hash. Le fichier sera servi tel quel.
        """
        try:
            return super().stored_name(name)
        except (ValueError, Exception) as e:
            logger.warning("RelaxedStaticFilesStorage: fichier absent du manifeste — %s (%s)", name, e)
            return name

    def post_process(self, paths, dry_run=False, **options):
        """
        Surcharge du générateur de post-traitement.

        WhiteNoise ne lève PAS l'exception directement : il la retourne dans
        un tuple (original_path, exception, False). C'est Django qui ensuite
        re-lève l'exception dans collect(). Il faut donc inspecter chaque
        tuple et supprimer ceux qui contiennent une erreur de fichier manquant.
        """
        skipped = []
        gen = super().post_process(paths, dry_run=dry_run, **options)
        while True:
            try:
                result = next(gen)
            except StopIteration:
                break
            except Exception as e:
                # Exception levée directement (cas rare) → on log et on ignore
                logger.warning("collectstatic: exception ignorée — %s", e)
                continue

            # result = (original_path, processed_path, processed)
            #