# Horodatage complet des posts (dates relatives « il y a 5 min »).

from datetime import datetime, time

from django.db import migrations, models
from django.utils import timezone


def backfill(apps, schema_editor):
    Post = apps.get_model('post', 'Post')
    tz = timezone.get_default_timezone()
    batch = []
    for post in Post.objects.filter(created_at__isnull=True).only('id', 'post_date').iterator(chunk_size=500):
        if post.post_date is None:
            continue
        post.created_at = timezone.make_aware(datetime.combine(post.post_date, time.min), tz)
        batch.append(post)
        if len(batch) >= 500:
            Post.objects.bulk_update(batch, ['created_at'])
            batch = []
    if batch:
        Post.objects.bulk_update(batch, ['created_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('post', '0024_perf_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, blank=True, null=True),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
