from django.db import migrations, models


def convert_null_title_to_empty_string(apps, schema_editor):
    OsobaZInstytucji = apps.get_model("pbn_api", "OsobaZInstytucji")
    OsobaZInstytucji.objects.filter(title__isnull=True).update(title="")


class Migration(migrations.Migration):
    dependencies = [
        ("pbn_api", "0066_add_duplicate_scan_models"),
    ]

    operations = [
        # First convert all NULL values to empty strings
        migrations.RunPython(
            convert_null_title_to_empty_string,
            reverse_code=migrations.RunPython.noop,
        ),
        # Then alter the field to not allow NULL
        migrations.AlterField(
            model_name="osobazinstytucji",
            name="title",
            field=models.TextField(blank=True, default=""),
        ),
    ]
