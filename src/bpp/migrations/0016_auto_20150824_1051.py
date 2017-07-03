# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0015_auto_20150617_2247'),
    ]

    operations = [
        migrations.AddField(
            model_name='autor',
            name='pbn_id',
            field=models.IntegerField(help_text=b'Identyfikator w systemie Polskiej Bibliografii Naukowej (PBN)', null=True, verbose_name=b'Identyfikator PBN', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='jednostka',
            name='pbn_id',
            field=models.IntegerField(help_text=b'Identyfikator w systemie Polskiej Bibliografii Naukowej (PBN)', null=True, verbose_name=b'Identyfikator PBN', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='uczelnia',
            name='pbn_id',
            field=models.IntegerField(help_text=b'Identyfikator w systemie Polskiej Bibliografii Naukowej (PBN)', null=True, verbose_name=b'Identyfikator PBN', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydzial',
            name='pbn_id',
            field=models.IntegerField(help_text=b'Identyfikator w systemie Polskiej Bibliografii Naukowej (PBN)', null=True, verbose_name=b'Identyfikator PBN', blank=True),
            preserve_default=True,
        ),
    ]
