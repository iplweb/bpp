"""Merge dwóch leaves po merge'u origin/dev w branch feature/multi-hosted-config.

- 0416_rename_dynamic_columns_to_admin: extrakcja django-dynamic-admin-columns
  (z dev, gałąź refactoringowa).
- 0417_ensure_uczelnia_site_not_null: utwardzenie Uczelnia.site (z naszej
  multi-hosted, gałąź feature).

Merge-only — bez operacji.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0416_rename_dynamic_columns_to_admin"),
        ("bpp", "0417_ensure_uczelnia_site_not_null"),
    ]

    operations = []
