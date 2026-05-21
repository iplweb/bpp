from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("deduplikator_autorow", "0008_add_priority_field"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="IgnoredAuthor",
            new_name="IgnoredScientist",
        ),
        migrations.AlterModelOptions(
            name="ignoredscientist",
            options={
                "ordering": ["-created_on"],
                "verbose_name": "Ignorowany Scientist (PBN)",
                "verbose_name_plural": "Ignorowani Scientist (PBN)",
            },
        ),
    ]
