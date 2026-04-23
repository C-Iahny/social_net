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
    try:
        # Écrire le fichier d'entrée dans un temp
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
        # Nettoyage des fichiers temporaires
        for p in [tmp_in_path, tmp_out_path]:
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
