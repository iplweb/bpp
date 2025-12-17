from django.db import migrations, models


def populate_ostatnio_zmieniony(apps, schema_editor):
    Zgloszenie_Publikacji_Autor = apps.get_model(
        "zglos_publikacje", "Zgloszenie_Publikacji_Autor"
    )
    for autor in Zgloszenie_Publikacji_Autor.objects.select_related("rekord").iterator():
        autor.ostatnio_zmieniony = autor.rekord.ostatnio_zmieniony
        autor.save(update_fields=["ostatnio_zmieniony"])


class Migration(migrations.Migration):
    dependencies = [
        ("zglos_publikacje", "0018_alter_zgloszenie_publikacji_rodzaj_zglaszanej_publikacji"),
    ]

    operations = [
        migrations.AddField(
            model_name="zgloszenie_publikacji_autor",
            name="ostatnio_zmieniony",
            field=models.DateTimeField(auto_now=True, db_index=True, null=True),
        ),
        migrations.RunPython(populate_ostatnio_zmieniony, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="zgloszenie_publikacji_autor",
            name="ostatnio_zmieniony",
            field=models.DateTimeField(auto_now=True, db_index=True),
        ),
    ]
