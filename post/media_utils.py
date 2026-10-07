"""
Utilitaires de compression des médias uploadés sur les posts.

Images : Pillow — redimensionnement max 1280px + conversion WebP (qualité 82)
Vidéos  : ffmpeg — reencoder en H.264 + AAC, résolution max 720p, bitrate ~1.5 Mbps

En cas d'erreur, on retourne le fichier original sans planter le post.
"""
import io
import os
import subprocess
import tempfile
import logging

from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

IMAGE_MAX_DIM  = 1280    # px — dimension max (largeur ou hauteur)
IMAGE_QUALITY  = 82      # WebP quality
VIDEO_MAX_DIM  = 720     # px — hauteur max
VIDEO_CRF      = 28      # H.264 CRF (18=lossless, 28=bon compromis)
VIDEO_PRESET   = 'fast'
VIDEO_AUDIO_BR = '96k'

VIDEO_EXTS = {'mp4', 'webm', 'ogg', 'mov', 'mkv', 'avi', 'm4v', '3gp'}


def _ext(filename):
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


def compress_image(django_file):
    """
    Reçoit un django InMemoryUploadedFile / TemporaryUploadedFile.
    Retourne un ContentFile WebP compressé, ou le fichier original si erreur.
    """
    try:
        from PIL import Image, ImageOps

        django_file.seek(0)
        img = Image.open(django_file)
        img = ImageOps.exif_transpose(img)  # corriger la rotation EXIF

        # Convertir en RGB (supprime canal alpha si PNG/GIF)
        if img.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            bg.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Redimensionner si trop grand
        w, h = img.size
        if max(w, h) > IMAGE_MAX_DIM:
            ratio = IMAGE_MAX_DIM / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format='WEBP', quality=IMAGE_QUALITY, method=4)
        buf.seek(0)

        # Nom de fichier : remplacer l'extension par .webp
        original_name = getattr(django_file, 'name', 'image.webp')
        base = original_name.rsplit('.', 1)[0] if '.' in original_name else original_name
        new_name = base + '.webp'

        return ContentFile(buf.read(), name=new_name)

    except Exception as e:
        logger.warning("compress_image failed: %s — using original", e)
        django_file.seek(0)
        return django_file


def compress_video(django_file):
    """
    Reçoit un django InMemoryUploadedFile / TemporaryUploadedFile.
    Retourne un ContentFile MP4 H.264 recompressé, ou le fichier original si erreur.
    """
    tmp_in_path  = None
    tmp_out_path = None
    try:
        django_file.seek(0)
        suffix_in = '.' + (_ext(django_file.name) or 'mp4')
        with tempfile.NamedTemporaryFile(suffix=suffix_in, delete=False) as tmp_in:
            for chunk in django_file.chunks():
                tmp_in.write(chunk)
            tmp_in_path = tmp_in.name

        tmp_out_path = tmp_in_path + '_out.mp4'

        cmd = [
            'ffmpeg', '-y',
            '-i', tmp_in_path,
            '-vf', f'scale=-2:{VIDEO_MAX_DIM}:flags=lanczos',
            '-c:v', 'libx264',
            '-crf', str(VIDEO_CRF),
            '-preset', VIDEO_PRESET,
            '-c:a', 'aac',
            '-b:a', VIDEO_AUDIO_BR,
            '-movflags', '+faststart',
            '-max_muxing_queue_size', '1024',
            tmp_out_path,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=300,   # 5 min max
        )

        if result.returncode != 0:
            logger.warning("ffmpeg error: %s", result.stderr.decode('utf-8', errors='replace')[-500:])
            raise RuntimeError("ffmpeg failed")

        with open(tmp_out_path, 'rb') as f:
            data = f.read()

        original_name = getattr(django_file, 'name', 'video.mp4')
        base = original_name.rsplit('.', 1)[0] if '.' in original_name else original_name
        new_name = base + '.mp4'

        return ContentFile(data, name=new_name)

    except Exception as e:
        logger.warning("compress_video failed: %s — using original", e)
        django_file.seek(0)
        return django_file

    finally:
        # Nettoyage des fichiers temporaires (tmp_in_path peut être None si exception précoce)
        for p in [tmp_in_path, tmp_out_path]:
            if p:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass


def compress_media(django_file):
    """
    Point d'entrée unique : détecte image ou vidéo et compresse.
    """
    name = getattr(django_file, 'name', '')
    ext = _ext(name)
    if ext in VIDEO_EXTS:
        return compress_video(django_file), 'video'
    else:
        return compress_image(django_file), 'image'


def ffmpeg_available():
    import shutil
    return shutil.which('ffmpeg') is not None


def recompress_video_media(media_id):
    """Recompresse en arrière-plan la vidéo d'un PostMedia déjà enregistré.

    L'original est servi tout de suite ; dès que ffmpeg a fini, le fichier
    est remplacé par la version 720p H.264 (beaucoup plus légère en 3G/4G).
    """
    from django.core.files.base import File
    from .models import PostMedia

    if not ffmpeg_available():
        return
    try:
        media = PostMedia.objects.get(pk=media_id)
    except PostMedia.DoesNotExist:
        return
    if media.media_type != 'video' or not media.file:
        return

    media.file.open('rb')
    try:
        original = File(media.file, name=os.path.basename(media.file.name))
        compressed = compress_video(original)
    finally:
        media.file.close()
    if compressed is original:
        return  # échec de ffmpeg : on garde l'original
    old_name = media.file.name
    media.file.save(compressed.name, compressed, save=True)
    if old_name != media.file.name:
        try:
            media.file.storage.delete(old_name)
        except Exception:
            logger.warning("Impossible de supprimer l'original %s", old_name)


def generate_video_poster(media_id):
    """Extrait une image (1re seconde) de la vidéo d'un PostMedia, en WebP."""
    from .models import PostMedia

    if not ffmpeg_available():
        return
    try:
        media = PostMedia.objects.get(pk=media_id)
    except PostMedia.DoesNotExist:
        return
    if media.media_type != 'video' or not media.file or media.poster:
        return

    tmp_in = tmp_out = None
    try:
        suffix = '.' + (_ext(media.file.name) or 'mp4')
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            media.file.open('rb')
            for chunk in media.file.chunks():
                f.write(chunk)
            media.file.close()
            tmp_in = f.name
        tmp_out = tmp_in + '_poster.jpg'
        result = subprocess.run(
            ['ffmpeg', '-y', '-ss', '1', '-i', tmp_in, '-frames:v', '1',
             '-vf', f'scale=-2:{VIDEO_MAX_DIM}', '-q:v', '4', tmp_out],
            capture_output=True, timeout=60,
        )
        if result.returncode != 0 or not os.path.exists(tmp_out):
            # Vidéo plus courte qu'une seconde : prendre la première image
            result = subprocess.run(
                ['ffmpeg', '-y', '-i', tmp_in, '-frames:v', '1', '-q:v', '4', tmp_out],
                capture_output=True, timeout=60,
            )
        if result.returncode != 0:
            return
        with open(tmp_out, 'rb') as f:
            poster = compress_image(ContentFile(f.read(), name='poster.jpg'))
        base = os.path.splitext(os.path.basename(media.file.name))[0]
        media.poster.save(f'{base}.webp', poster, save=True)
    except Exception as e:
        logger.warning("generate_video_poster failed: %s", e)
    finally:
        for path in (tmp_in, tmp_out):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass


def process_video_media(media_id):
    """Tâche de fond d'une vidéo de post : aperçu, puis recompression 720p."""
    generate_video_poster(media_id)
    recompress_video_media(media_id)


def store_post_media(post, django_file, order):
    """Crée le PostMedia d'un fichier uploadé, compressé.

    Image : redimensionnée et convertie en WebP tout de suite (quelques
    dizaines de ms). Vidéo : enregistrée telle quelle puis recompressée en
    tâche de fond, pour ne pas bloquer la publication.
    """
    from ZOOT.background import run_in_background
    from .models import PostMedia

    if _ext(getattr(django_file, 'name', '')) in VIDEO_EXTS:
        media = PostMedia.objects.create(post=post, file=django_file, media_type='video', order=order)
        run_in_background(process_video_media, media.pk)
        return media
    return PostMedia.objects.create(post=post, file=compress_image(django_file), media_type='image', order=order)
