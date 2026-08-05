"""Mapowania słowników BPP na wartości kontrolowane profilu OpenAIRE CRIS.

Wypełnia tylko wiersze, w których wartość jest PUSTA — decyzja redakcji ma
zawsze pierwszeństwo i migracja nigdy jej nie nadpisze. Dzięki temu jest
idempotentna i bezpieczna przy ponownym uruchomieniu.

Mapowane są wyłącznie przypadki jednoznaczne. Charaktery formalne, których
nie da się przypisać bez decyzji merytorycznej (np. „Broszura", „Fragment",
„inne"), zostają puste — wyłapie je `manage.py cerif_raport_mapowan`
i uzupełni redakcja. Zgadywanie byłoby gorsze niż brak: typ zbyt ogólny
degraduje metadane, typ nieprawdziwy je fałszuje.
"""

from django.db import migrations

COAR = "http://purl.org/coar/resource_type/"

# skrót charakteru formalnego -> URI COAR Resource Type.
#
# Świadomie POMINIĘTE (zostają puste, do decyzji redakcji):
#   BR   Broszura              — COAR nie ma odpowiednika
#   DE   Dokument elektroniczny— nośnik, nie typ treści
#   frg  Fragment              — za ogólne
#   IN   inne                  — z definicji nieokreślone
#   PZ   Poradnik zawodowy     — na granicy książki i raportu
#   Supl Publikacja w suplemencie — zależy od tego, co jest w suplemencie
#   TŁ   Tłumaczenie           — COAR opisuje typ, nie fakt przekładu
#   PAT  Patent                — patenty idą jako encja Patent, nie Publication
#   WYN  Projekt wynalazczy    — jw.
CHARAKTERY = {
    "AC": COAR + "c_6501",  # journal article
    "CZ": COAR + "c_0640",  # journal (kanał wydawniczy)
    "D": COAR + "c_db06",  # doctoral thesis
    "H": COAR + "c_46ec",  # thesis (COAR nie zna habilitacji)
    "KOM": COAR + "D97F-VB57",  # commentary
    "KS": COAR + "c_2f33",  # book
    "KSP": COAR + "c_2f33",  # book
    "KSZ": COAR + "c_2f33",  # book
    "L": COAR + "c_545b",  # letter to the editor
    "PA": COAR + "c_2f33",  # book (podręcznik akademicki)
    "PRZ": COAR + "c_5794",  # conference paper
    "PSZ": COAR + "c_c94f",  # conference output (streszczenie zjazdowe)
    "R": COAR + "c_efa0",  # review
    "ROZ": COAR + "c_3248",  # book part
    "ROZS": COAR + "c_3248",  # book part
    "SKR": COAR + "c_2f33",  # book (skrypt)
    "ZRZ": COAR + "c_5794",  # conference paper
    "ZSZ": COAR + "c_c94f",  # conference output
}

# nazwa rodzaju prawa patentowego -> URI COAR Patent Type.
#
# POMINIĘTE: „znak towarowy" — znak towarowy nie jest patentem i COAR nie ma
# dla niego terminu w gałęzi `patent`.
PRAWA_PATENTOWE = {
    "wynalazek": COAR + "c_15cd",  # patent
    "wzór użytkowy": COAR + "9DKX-KSAF",  # utility model
    "wzór przemysłowy": COAR + "C53B-JCY5",  # design patent
    "odmiana rośliny": COAR + "GPQ7-G5VE",  # plant variety protection
}

# skrót języka -> kod BCP 47.
#
# POMINIĘTE: „b/d" (brak danych) i „in." (inny) — oba znaczą „nie wiemy",
# a wtedy poprawnie jest NIE emitować atrybutu xml:lang.
JEZYKI = {
    "ang.": "en",
    "fr.": "fr",
    "hiszp.": "es",
    "niem.": "de",
    "pol.": "pl",
    "ros.": "ru",
    "wł.": "it",
}

DOSTEP_OTWARTY = "http://purl.org/coar/access_right/c_abf2"

# Skróty trybów Open Access, które jednoznacznie znaczą „otwarty dostęp".
# „OTHER" pomijamy — z samej nazwy nie wynika, czy praca jest otwarta.
TRYBY_OTWARTE = ("OPEN_JOURNAL", "OPEN_REPOSITORY", "PUBLISHER_WEBSITE")


def _uzupelnij(model, pole, mapowanie, klucz="skrot"):
    """Wypełnij ``pole`` wg ``mapowania``, pomijając wiersze już wypełnione."""
    for wartosc_klucza, wartosc in mapowanie.items():
        model.objects.filter(**{klucz: wartosc_klucza}).filter(
            **{f"{pole}__in": ["", None]}
        ).update(**{pole: wartosc})


def wypelnij(apps, schema_editor):
    _uzupelnij(apps.get_model("bpp", "Charakter_Formalny"), "coar_type", CHARAKTERY)
    _uzupelnij(
        apps.get_model("bpp", "Rodzaj_Prawa_Patentowego"),
        "coar_type",
        PRAWA_PATENTOWE,
        klucz="nazwa",
    )
    _uzupelnij(apps.get_model("bpp", "Jezyk"), "kod_bcp47", JEZYKI)

    for nazwa_modelu in (
        "Tryb_OpenAccess_Wydawnictwo_Ciagle",
        "Tryb_OpenAccess_Wydawnictwo_Zwarte",
    ):
        apps.get_model("bpp", nazwa_modelu).objects.filter(
            skrot__in=TRYBY_OTWARTE
        ).filter(coar_access_right__in=["", None]).update(
            coar_access_right=DOSTEP_OTWARTY
        )


def cofnij(apps, schema_editor):
    """Bez odwracania.

    Nie da się odróżnić wartości wstawionej przez tę migrację od takiej
    samej, wpisanej świadomie przez redakcję — kasowanie ryzykowałoby
    skasowanie tej drugiej.
    """


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0479_cerif_export_pola"),
    ]

    operations = [
        migrations.RunPython(wypelnij, cofnij),
    ]
