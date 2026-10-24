from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0498_autoreksporttask_tylko_dla_redakcji"),
    ]

    operations = [
        migrations.AddField(
            model_name="autoreksporttask",
            name="zlecone_anonimowo",
            field=models.BooleanField(default=False),
        ),
    ]
