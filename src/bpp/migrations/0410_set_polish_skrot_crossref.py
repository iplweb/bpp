from django.db import migrations


def set_polish_skrot_crossref(apps, schema_editor):
    Jezyk = apps.get_model("bpp", "Jezyk")
    Jezyk.objects.filter(skrot="pol.").update(skrot_crossref="pl")


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0409_set_default_jest_wydawnictwem_zwartym"),
    ]

    operations = [
        migrations.RunPython(
            set_polish_skrot_crossref,
            migrations.RunPython.noop,
        ),
    ]
