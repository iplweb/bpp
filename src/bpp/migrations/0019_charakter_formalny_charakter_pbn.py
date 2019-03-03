# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0018_auto_20150824_1233'),
    ]

    operations = [
        migrations.AddField(
            model_name='charakter_formalny',
            name='charakter_pbn',
            field=models.ForeignKey(on_delete=models.CASCADE, default=None, blank=True, to='bpp.Charakter_PBN', null=True),
            preserve_default=True,
        ),
    ]
