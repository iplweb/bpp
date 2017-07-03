# -*- coding: utf-8 -*-


from django.db import models, migrations


def dodaj_dane(apps, schema_editor):
    Jezyk = apps.get_model('bpp', 'Jezyk')

    pl, created = Jezyk.objects.get_or_create(skrot='pol.', nazwa='polski')
    pl.skrot_dla_pbn = 'PL'
    pl.save()
    assert pl.pk == 1

    ang, created = Jezyk.objects.get_or_create(skrot='ang.', nazwa='angielski')
    ang.skrot_dla_pbn = 'EN'
    ang.save()
    assert ang.pk == 2

class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0021_auto_20150825_2301'),
    ]

    operations = [
        migrations.RunPython(dodaj_dane)
    ]
