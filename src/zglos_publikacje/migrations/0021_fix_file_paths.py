import os

from django.conf import settings
from django.db import migrations, models


def fix_file_paths(apps, schema_editor):
    """Naprawia ścieżki plików, które nie wskazują na istniejące pliki."""
    Zgloszenie_Publikacji = apps.get_model(
        "zglos_publikacje", "Zgloszenie_Publikacji"
    )
    protected_dir = os.path.join(
        settings.MEDIA_ROOT, "protected", "zglos_publikacje"
    )

    for obj in Zgloszenie_Publikacji.objects.exclude(plik="").exclude(plik=None):
        if not obj.plik:
            continue

        current_path = os.path.join(settings.MEDIA_ROOT, obj.plik.name)

        if os.path.exists(current_path):
            # Plik istnieje pod zapisaną ścieżką - OK
            continue

        # Plik nie istnieje - sprawdź czy jest w protected/zglos_publikacje/
        filename = os.path.basename(obj.plik.name)
        protected_path = os.path.join(protected_dir, filename)

        if os.path.exists(protected_path):
            # Plik znaleziony w protected - napraw ścieżkę
            new_name = f"protected/zglos_publikacje/{filename}"
            print(f"Naprawiam ścieżkę: {obj.plik.name} -> {new_name}")
            obj.plik = new_name
            obj.save(update_fields=["plik"])
        else:
            # Plik nie istnieje nigdzie
            print(
                f"UWAGA: Plik nie istnieje: {obj.plik.name} "
                f"(id={obj.pk}, email={obj.email})"
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("zglos_publikacje", "0020_move_files_to_protected"),
    ]

    operations = [
        # First: Ensure max_length is large enough (3x of original 255)
        migrations.AlterField(
            model_name="zgloszenie_publikacji",
            name="plik",
            field=models.FileField(
                blank=True,
                help_text=(
                    "Jeżeli zgłaszana publikacja nie jest dostępna nigdzie "
                    "w sieci internet,\n        prosimy o dodanie załącznika"
                ),
                max_length=765,
                null=True,
                upload_to="protected/zglos_publikacje/",
                verbose_name="Plik załącznika",
            ),
        ),
        # Then: Fix file paths
        migrations.RunPython(fix_file_paths, noop),
    ]
