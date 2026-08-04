"""Znak towarowy poza eksportem CERIF + mapowanie charakteru „Fragment".

Dwie rzeczy, które wyszły po recenzji migracji 0480 — świadomie w NOWEJ
migracji, bo tamtej (już zastosowanej) nie wolno modyfikować.

**Znak towarowy.** ``Patent/Type`` jest w profilu obowiązkowy i ograniczony
do gałęzi „patent" słownika COAR, w której nie ma znaku towarowego. Samo
pominięcie mapowania NIE dawało więc „braku typu", tylko fallback na
``c_15cd patent`` — czyli deklarowanie znaku towarowego patentem. Jedyne
uczciwe wyjście to nie eksportować takich rekordów; służy do tego jawne
pole, a nie dopasowanie po nazwie (``nazwa`` jest edytowalna w adminie).

**Fragment.** W baseline ``frg`` ma ``charakter_sloty=2`` i ``rodzaj_pbn=2``,
czyli dokładnie to samo co ``ROZ``/``ROZS`` zmapowane na *book part* — BPP
samo raportuje fragment do PBN jako rozdział. To istniejąca klasyfikacja
systemu, nie interpretacja.

``Supl`` celowo zostaje bez typu: jedyną przesłanką jest etykieta
``nazwa_w_primo="Artykuł"``, podczas gdy ``charakter_ogolny`` to ``xxx``,
a nie ``art``. Suplement bywa też zbiorem streszczeń zjazdowych.
"""

from django.db import migrations, models

FRAGMENT_BOOK_PART = "http://purl.org/coar/resource_type/c_3248"

# Nazwy rodzajów praw, które NIE są patentami w rozumieniu COAR.
NIE_PATENTY = ("znak towarowy",)


def wypelnij(apps, schema_editor):
    model = apps.get_model("bpp", "Rodzaj_Prawa_Patentowego")
    # `iexact`, nie `in`: `nazwa` jest edytowalna w adminie, a exact-match
    # przepuściłby „Znak towarowy" — i znak towarowy dalej wychodziłby jako
    # patent, czyli dokładnie ten błąd, który ta migracja naprawia.
    for nazwa in NIE_PATENTY:
        model.objects.filter(nazwa__iexact=nazwa).update(eksportuj_jako_patent=False)

    apps.get_model("bpp", "Charakter_Formalny").objects.filter(skrot="frg").filter(
        coar_type__in=["", None]
    ).update(coar_type=FRAGMENT_BOOK_PART)


def cofnij(apps, schema_editor):
    """Bez odwracania — patrz uzasadnienie w migracji 0480."""


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0482_alter_jednostka_ror_id_alter_uczelnia_ror_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="rodzaj_prawa_patentowego",
            name="eksportuj_jako_patent",
            field=models.BooleanField(
                default=True,
                help_text="Odznacz dla praw, które nie są patentami w rozumieniu "
                "słownika COAR (np. znak towarowy). Takie rekordy nie trafią do "
                "eksportu CERIF/OpenAIRE — profil wymaga dla każdego rekordu typu "
                "z gałęzi „patent”, więc jedyną alternatywą byłoby zadeklarowanie "
                "ich patentami wbrew prawdzie.",
                verbose_name="Eksportuj do CERIF jako patent",
            ),
        ),
        migrations.RunPython(wypelnij, cofnij),
    ]
