# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.db.models import CASCADE


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0022_auto_20150825_2303'),
        ('eksport_pbn', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='plikeksportupbn',
            name='rok',
            field=models.IntegerField(default=1),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='plikeksportupbn',
            name='wydzial',
            field=models.ForeignKey(default=1, to='bpp.Wydzial', on_delete=CASCADE),
            preserve_default=False,
        ),
    ]
