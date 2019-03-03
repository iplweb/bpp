# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0019_charakter_formalny_charakter_pbn'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='charakter_pbn',
            options={'ordering': ['identyfikator'], 'verbose_name': 'Charakter PBN', 'verbose_name_plural': 'Charaktery PBN'},
        ),
        migrations.AlterField(
            model_name='charakter_formalny',
            name='charakter_pbn',
            field=models.ForeignKey(on_delete=models.CASCADE, default=None, blank=True, to='bpp.Charakter_PBN', null=True, verbose_name=b'Charakter PBN'),
            preserve_default=True,
        ),
    ]
