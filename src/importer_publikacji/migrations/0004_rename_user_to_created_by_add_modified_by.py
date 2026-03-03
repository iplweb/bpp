import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        (
            "importer_publikacji",
            "0003_importedauthor_dyscyplina_source",
        ),
    ]

    operations = [
        migrations.RenameField(
            model_name="importsession",
            old_name="user",
            new_name="created_by",
        ),
        migrations.AddField(
            model_name="importsession",
            name="modified_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="importer_modified_sessions",
                to=settings.AUTH_USER_MODEL,
                verbose_name="ostatnio zmodyfikował",
            ),
        ),
    ]
