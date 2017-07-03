# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0007_charakter_formalny_nazwa_w_primo'),
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
