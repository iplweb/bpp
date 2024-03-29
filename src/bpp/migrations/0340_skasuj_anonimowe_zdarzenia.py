# Generated by Django 3.2.20 on 2023-07-09 19:45

from django.db import migrations


def forwards_func(apps, schema_editor):
    if apps.is_installed("easyaudit"):
        CRUDEvent = apps.get_model("easyaudit", "CRUDEvent")
        CRUDEvent.objects.filter(user_id=None).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0339_autor_opis"),
    ]

    operations = [migrations.RunPython(forwards_func, migrations.RunPython.noop)]
