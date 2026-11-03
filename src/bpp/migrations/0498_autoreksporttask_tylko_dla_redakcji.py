from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0497_uczelnia_bppuser_szyfrowanie_sekretow"),
    ]

    operations = [
        migrations.AddField(
            model_name="autoreksporttask",
            name="tylko_dla_redakcji",
            field=models.BooleanField(default=False),
        ),
    ]
