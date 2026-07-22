from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("import_pracownikow", "0014_utworz_nowego_odpiecie"),
    ]

    operations = [
        migrations.AddField(
            model_name="importpracownikowrow",
            name="przepnij_prace",
            field=models.BooleanField(default=False),
        ),
    ]
