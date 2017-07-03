# -*- coding: utf-8 -*-


from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0003_auto_20141023_1419'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='patent_autor',
            unique_together=set([('rekord', 'autor', 'typ_odpowiedzialnosci'), ('rekord', 'autor', 'kolejnosc')]),
        ),
        migrations.AlterUniqueTogether(
            name='wydawnictwo_ciagle_autor',
            unique_together=set([('rekord', 'autor', 'typ_odpowiedzialnosci'), ('rekord', 'autor', 'kolejnosc')]),
        ),
        migrations.AlterUniqueTogether(
            name='wydawnictwo_zwarte_autor',
            unique_together=set([('rekord', 'autor', 'typ_odpowiedzialnosci'), ('rekord', 'autor', 'kolejnosc')]),
        ),
    ]
