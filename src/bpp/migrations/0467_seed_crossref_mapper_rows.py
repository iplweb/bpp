"""Zaseeduj wszystkie wiersze Crossref_Mapper z poprawnym
``jest_wydawnictwem_zwartym``.

Dotychczas wiersze Crossref_Mapper powstawały wyłącznie leniwie
(``get_or_create`` przy pierwszym imporcie danego typu), a migracja 0409
ustawiała ``jest_wydawnictwem_zwartym=True`` tylko dla wierszy JUŻ
istniejących. W efekcie pierwszy import ``book-chapter`` tworzył świeży
wiersz z modelowym defaultem ``False`` — ptaszek „jest wydawnictwem
zwartym" w importerze się nie zaznaczał.

Ta migracja jawnie tworzy komplet 16 wierszy (idempotentnie) z właściwą
wartością, tak by tabela była w pełni zainicjowana i edytowalna w adminie
(``charakter_formalny_bpp`` pozostaje do konfiguracji przez uczelnię).
"""

from django.db import migrations

# Wartości enum CHARAKTER_CROSSREF, które są wydawnictwami zwartymi.
# Zsynchronizowane z Crossref_Mapper.BOOK_TYPES (hardcode tutaj, bo migracje
# muszą być odporne na przyszłe zmiany kodu modelu).
BOOK_TYPES = {3, 4, 5, 7, 8, 9, 10, 11, 12, 13}
ALL_TYPES = range(1, 17)


def seed_crossref_mapper_rows(apps, schema_editor):
    Crossref_Mapper = apps.get_model("bpp", "Crossref_Mapper")
    for charakter_crossref in ALL_TYPES:
        Crossref_Mapper.objects.get_or_create(
            charakter_crossref=charakter_crossref,
            defaults={
                "jest_wydawnictwem_zwartym": charakter_crossref in BOOK_TYPES,
            },
        )


def reverse_seed(apps, schema_editor):
    """Nie usuwamy wierszy — mogły zostać skonfigurowane (charakter_formalny)."""


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0466_bppuser_zwijaj_dlugie_listy_autorow_and_more"),
    ]

    operations = [
        migrations.RunPython(
            seed_crossref_mapper_rows,
            reverse_seed,
        ),
    ]
