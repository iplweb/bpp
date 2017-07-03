# -*- coding: utf-8 -*-


from datetime import date

from django.db import migrations
from django.db.models.functions import Coalesce


def utworz_jednostka_wydzial(apps, schema_editor):
    Jednostka = apps.get_model("bpp", "Jednostka")
    Jednostka_Wydzial = apps.get_model("bpp", "Jednostka_Wydzial")
    db_alias = schema_editor.connection.alias

    for j in Jednostka.objects.using(db_alias).all():
        if Jednostka_Wydzial.objects.using(db_alias).filter(
                jednostka_id=j.pk,
                wydzial_id=j.wydzial_id).count() == 0:
            Jednostka_Wydzial.objects.using(db_alias).create(
                jednostka_id=j.pk,
                wydzial_id=j.wydzial_id,
            )


def usun_jednostka_wydzial(apps, schema_editor):
    Jednostka = apps.get_model("bpp", "Jednostka")

    Jednostka_Wydzial = apps.get_model("bpp", "Jednostka_Wydzial")
    db_alias = schema_editor.connection.alias

    for j in Jednostka.objects.using(db_alias).all():
        q = Jednostka_Wydzial.objects.using(db_alias).filter(
            jednostka_jd=j.pk,
            wydzial_id=j.wydzial_id)
        jw = q.annotate(
            od_not_null=Coalesce("od", date(1, 1, 1)),
        ).order_by("-od_not_null").first()
        q.delete()
        j.wydzial_id = jw.wydzial_id
        j.save()


class Migration(migrations.Migration):
    dependencies = [
        ('bpp', '0060_auto_20161114_1905'),
    ]

    operations = [
        migrations.RunPython(utworz_jednostka_wydzial, usun_jednostka_wydzial)
    ]
