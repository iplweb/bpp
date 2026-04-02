"""Data migration: populate forma_dostepu from existing records
and move single plik to Zgloszenie_Publikacji_Zalacznik."""

from django.db import migrations


def migruj_forme_dostepu_i_pliki(apps, schema_editor):
    Zgloszenie_Publikacji = apps.get_model(
        "zglos_publikacje", "Zgloszenie_Publikacji"
    )
    Zalacznik = apps.get_model(
        "zglos_publikacje", "Zgloszenie_Publikacji_Zalacznik"
    )

    OTWARTY = 1
    OGRANICZONY = 2

    for zp in Zgloszenie_Publikacji.objects.all():
        zmieniono = False

        # Ustal formę dostępu na podstawie istniejących danych
        if zp.strona_www:
            zp.forma_dostepu = OTWARTY
            zmieniono = True
        elif zp.plik:
            zp.forma_dostepu = OGRANICZONY
            zmieniono = True

        if zmieniono:
            zp.save(update_fields=["forma_dostepu"])

        # Przenieś istniejący plik do modelu Zalacznik
        if zp.plik:
            Zalacznik.objects.create(
                zgloszenie=zp,
                plik=zp.plik,
                oryginalna_nazwa_pliku=(
                    zp.oryginalna_nazwa_pliku
                ),
                kolejnosc=0,
            )


def migruj_wymagaj_oplatach(apps, schema_editor):
    """Migracja starego pola wymagaj_informacji_o_oplatach
    na nowe pola per typ."""
    Uczelnia = apps.get_model("bpp", "Uczelnia")

    for uczelnia in Uczelnia.objects.all():
        # Stare zachowanie: opłaty wymagane dla artykułów
        # i monografii (ARTYKUL_LUB_MONOGRAFIA),
        # NIE dla rozdziałów i pozostałych
        wymaga = uczelnia.wymagaj_informacji_o_oplatach
        uczelnia.wymagaj_oplatach_artykul = wymaga
        uczelnia.wymagaj_oplatach_monografia = wymaga
        uczelnia.wymagaj_oplatach_rozdzial = False
        uczelnia.wymagaj_oplatach_inne = False
        uczelnia.save(
            update_fields=[
                "wymagaj_oplatach_artykul",
                "wymagaj_oplatach_monografia",
                "wymagaj_oplatach_rozdzial",
                "wymagaj_oplatach_inne",
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        (
            "zglos_publikacje",
            "0023_nowy_formularz_zgloszenia",
        ),
        ("bpp", "0411_nowy_formularz_zgloszenia"),
    ]

    operations = [
        migrations.RunPython(
            migruj_forme_dostepu_i_pliki,
            migrations.RunPython.noop,
        ),
        migrations.RunPython(
            migruj_wymagaj_oplatach,
            migrations.RunPython.noop,
        ),
    ]
