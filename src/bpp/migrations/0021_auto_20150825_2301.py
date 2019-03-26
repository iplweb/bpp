# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0020_auto_20150824_1609'),
    ]

    operations = [
        migrations.AddField(
            model_name='jezyk',
            name='skrot_dla_pbn',
            field=models.CharField(help_text=b'\n    Skr\xc3\xb3t nazwy j\xc4\x99zyka u\xc5\xbcywany w plikach eksportu do PBN.', max_length=10, verbose_name=b'Skr\xc3\xb3t dla PBN', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='zrodlo',
            name='jezyk',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='bpp.Jezyk', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='zrodlo',
            name='wydawca',
            field=models.CharField(max_length=250, blank=True),
            preserve_default=True,
        ),
    ]
