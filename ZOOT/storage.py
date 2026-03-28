"""
Storage personnalisé pour les fichiers statiques en production.

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
from whitenoise.storage import CompressedManifestStaticFilesStorage, MissingFileError

logger = logging.getLogger(__name__)


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
        gen = super().post_process(paths, dry_run=dry_run, **options)
        while True:
            try:
                result = next(gen)
            except StopIteration:
                return
            except Exception as e:
                # Exception levée directement (cas rare) → on log et on ignore
                logger.warning("collectstatic: exception ignorée — %s", e)
                continue

            # result = (original_path, processed_path, processed)
            # Selon la version de Django/WhiteNoise, l'exception peut être
            # dans result[1] OU result[2] — on vérifie les deux.
            has_error = (
                isinstance(result, (tuple, list))
                and len(result) >= 2
                and any(isinstance(result[i], Exception) for i in range(len(result)))
            )
            if has_error:
                exc = next(r for r in result if isinstance(r, Exception))
                logger.warning("collectstatic: post-process ignoré pour '%s' — %s", result[0], exc)
                # Ne pas yield → Django ne verra jamais l'erreur
            else:
                yield result
