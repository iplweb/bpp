import autoslug.fields
from django.db import migrations

import bpp.util.text


class Migration(migrations.Migration):
    """Krok 3/3: slug wydawcy jako ``AutoSlugField`` — NOT NULL + UNIQUE."""

    dependencies = [
        ("bpp", "0504_wydawca_slug_dane"),
    ]

    operations = [
        migrations.AlterField(
            model_name="wydawca",
            name="slug",
            field=autoslug.fields.AutoSlugField(
                editable=False,
                max_length=512,
                populate_from="nazwa",
                slugify=bpp.util.text.slugify_wydawca,
                unique=True,
            ),
        ),
    ]
