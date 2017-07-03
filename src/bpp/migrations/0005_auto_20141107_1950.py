# -*- coding: utf-8 -*-


from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0004_auto_20141107_1101'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='patent_autor',
            unique_together=set([('rekord', 'autor', 'typ_odpowiedzialnosci'), ('rekord', 'kolejnosc')]),
        ),
        migrations.AlterUniqueTogether(
            name='wydawnictwo_ciagle_autor',
            unique_together=set([('rekord', 'autor', 'typ_odpowiedzialnosci'), ('rekord', 'kolejnosc')]),
        ),
        migrations.AlterUniqueTogether(
            name='wydawnictwo_zwarte_autor',
            unique_together=set([('rekord', 'autor', 'typ_odpowiedzialnosci'), ('rekord', 'kolejnosc')]),
        ),
    ]
