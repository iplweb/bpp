from django.db import migrations

import bpp.fields

#: Kolumny przenoszone na EncryptedTextField w tej migracji.
KOLUMNY = (
    ("bpp_bppuser", "pbn_token"),
    ("bpp_uczelnia", "clarivate_password"),
    ("bpp_uczelnia", "orcid_client_secret"),
    ("bpp_uczelnia", "pbn_app_token"),
)


def zaszyfruj(apps, schema_editor):
    from bpp.fields import multifernet
    from bpp.sekrety import zaszyfruj_jawne

    if multifernet() is None:
        print(
            "\n  Brak klucza DJANGO_BPP_FIELD_ENCRYPTION_KEY — sekrety integracji "
            "pozostają w bazie jawne. Po ustawieniu klucza uruchom: "
            "manage.py zaszyfruj_sekrety"
        )
        return
    for tabela, kolumna in KOLUMNY:
        zaszyfruj_jawne(schema_editor.connection, tabela, kolumna)


def odszyfruj(apps, schema_editor):
    from bpp.sekrety import odszyfruj_wszystkie

    for tabela, kolumna in KOLUMNY:
        odszyfruj_wszystkie(schema_editor.connection, tabela, kolumna)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0496_autoreksporttask_ukryte_statusy"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bppuser",
            name="pbn_token",
            field=bpp.fields.EncryptedTextField(blank=True, default="", max_length=128),
        ),
        migrations.AlterField(
            model_name="uczelnia",
            name="clarivate_password",
            field=bpp.fields.EncryptedTextField(
                blank=True, default="", max_length=50, verbose_name="Hasło"
            ),
        ),
        migrations.AlterField(
            model_name="uczelnia",
            name="orcid_client_secret",
            field=bpp.fields.EncryptedTextField(
                blank=True,
                default="",
                max_length=128,
                verbose_name="ORCID Client Secret",
            ),
        ),
        migrations.AlterField(
            model_name="uczelnia",
            name="pbn_app_token",
            field=bpp.fields.EncryptedTextField(
                blank=True,
                default="",
                max_length=128,
                verbose_name="Token aplikacji w PBN",
            ),
        ),
        migrations.RunPython(zaszyfruj, odszyfruj),
    ]
