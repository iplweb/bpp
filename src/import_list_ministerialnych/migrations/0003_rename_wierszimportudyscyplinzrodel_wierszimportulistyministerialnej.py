# Generated by Django 4.2.16 on 2024-11-17 20:49

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0356_drop_kc_komisja_centralna"),
        (
            "import_list_ministerialnych",
            "0002_alter_wierszimportudyscyplinzrodel_nr_wiersza",
        ),
    ]

    operations = [
        migrations.RenameModel(
            old_name="WierszImportuDyscyplinZrodel",
            new_name="WierszImportuListyMinisterialnej",
        ),
    ]
