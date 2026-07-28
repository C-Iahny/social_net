from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0004_group_dina'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='category',
            field=models.CharField(
                blank=True,
                choices=[
                    ('sport',      '🏃 Sport'),
                    ('musique',    '🎵 Musique'),
                    ('cuisine',    '🍳 Cuisine'),
                    ('tech',       '💻 Technologie'),
                    ('art',        '🎨 Art & Culture'),
                    ('education',  '📚 Éducation'),
                    ('voyage',     '✈️ Voyage'),
                    ('business',   '💼 Business'),
                    ('gaming',     '🎮 Gaming'),
                    ('bienetre',   '🧘 Bien-être'),
                    ('nature',     '🌱 Nature'),
                    ('humour',     '😄 Humour'),
                    ('madagascar', '🇲🇬 Madagascar'),
                    ('famille',    '👨‍👩‍👧 Famille'),
                    ('religion',   '🙏 Religion & Spiritualité'),
                    ('autre',      '💬 Autre'),
                ],
                db_index=True,
                default='',
                max_length=20,
                verbose_name='Catégorie',
            ),
        ),
    ]
