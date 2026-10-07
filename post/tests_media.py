"""Compression des médias de posts (post/media_utils.py)."""
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from account.models import Account
from post.media_utils import store_post_media
from post.models import Post


class StorePostMediaTests(TestCase):
    def setUp(self):
        self.user = Account.objects.create_user(email='m@test.mg', username='media', password='pw12345678')
        self.post = Post.objects.create(author=self.user, body='photo')

    def test_image_is_resized_and_converted_to_webp(self):
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', (3000, 2000), (200, 50, 50)).save(buf, format='PNG')
        upload = SimpleUploadedFile('grande.png', buf.getvalue(), content_type='image/png')

        media = store_post_media(self.post, upload, order=0)

        self.assertEqual(media.media_type, 'image')
        self.assertTrue(media.file.name.endswith('.webp'))
        with media.file.open('rb') as f:
            img = Image.open(f)
            self.assertLessEqual(max(img.size), 1280)
        self.assertLess(media.file.size, len(buf.getvalue()))
        media.file.delete(save=False)

    def test_video_is_stored_as_video(self):
        upload = SimpleUploadedFile('clip.mp4', b'\x00\x00\x00\x18ftypmp42', content_type='video/mp4')
        media = store_post_media(self.post, upload, order=0)
        self.assertEqual(media.media_type, 'video')
        media.file.delete(save=False)
