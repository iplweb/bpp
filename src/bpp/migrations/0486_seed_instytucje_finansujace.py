"""Seed słownika instytucji finansujących.

Identyfikatory NIE są przepisane z pamięci — każdy został odpytany w rejestrze
przy pisaniu tej migracji i potwierdzony **krzyżowo**: Crossref Funder Registry
(``https://api.crossref.org/funders?query=…``) podaje FundRef ID, a rekord ROR
(``https://api.ror.org/organizations/<id>``) wymienia ten sam FundRef ID
w ``external_ids``. Zgodność obu rejestrów jest tu jedynym dowodem, że
identyfikator należy do TEJ instytucji, a nie do innej o podobnej nazwie
(w rejestrach siedzą obok siebie np. NCN i NCBJ, ABM i AMED).

Instytucja bez potwierdzonego identyfikatora weszłaby bez niego: pusty
identyfikator jest brakiem danych, a zmyślony jest błędem, który wycieknie do
OpenAIRE i sklei nasze publikacje z cudzym profilem grantodawcy. Dla całego
zakresu tej migracji potwierdzenie udało się uzyskać, więc pustych nie ma.

Dwie decyzje wymagające komentarza:

* **MNiSW.** Crossref prowadzi ten rekord pod nazwą „Ministerstwo Edukacji
  i Nauki" (nazwa z okresu połączenia resortów), a ROR — pod „Ministry of
  Science and Higher Education". To ten sam podmiot: ROR ``05dwvd537``
  wymienia FundRef ``501100004569`` i ma alias „Ministerstwo Nauki
  i Szkolnictwa Wyższego". W seedzie zostaje aktualna polska nazwa resortu,
  bo to ona pojawia się w umowach grantowych.
* **Komisja Europejska** dostaje ``kraj="BE"`` za rejestrem ROR (siedziba
  w Brukseli). Pole jest wewnętrzne i nie wychodzi w CERIF — profil OpenAIRE
  nie ma elementu ``Country`` w encji ``OrgUnit`` — więc nie ma powodu
  naciągać go do kodu rezerwowego ``EU``.

Adresy WWW pochodzą z pola ``links`` rekordów ROR; dwa poprawiono, bo
rejestrowy adres nie działa (``nauka.gov.pl`` MNiSW-u nie odpowiada — resort
siedzi dziś na ``gov.pl/web/nauka``) albo prowadzi do wersji angielskiej po
``http`` (NCBR). Oba zastępniki sprawdzone: HTTP 200.

Idempotentna: ``get_or_create`` po ``fundref_id`` (wszystkie pozycje go mają;
gdyby doszła instytucja bez FundRef-a, kluczem zostaje ``nazwa``). Operacja
odwrotna jest no-opem — kasowanie grantodawców przy cofaniu migracji zerwałoby
``PROTECT`` z ``Finansowanie`` i wywaliłoby migrację wstecz na wierszach,
których ta migracja nie tworzyła.
"""

from django.db import migrations

#: (nazwa, nazwa_en, akronim, kraj, fundref_id, ror_id, strona_www)
INSTYTUCJE = [
    (
        "Narodowe Centrum Nauki",
        "National Science Centre",
        "NCN",
        "PL",
        "501100004281",
        "https://ror.org/03ha2q922",
        "https://www.ncn.gov.pl",
    ),
    (
        "Narodowe Centrum Badań i Rozwoju",
        "National Centre for Research and Development",
        "NCBR",
        "PL",
        "501100005632",
        "https://ror.org/05pwfyy15",
        "https://www.ncbr.gov.pl/",
    ),
    (
        "Ministerstwo Nauki i Szkolnictwa Wyższego",
        "Ministry of Science and Higher Education",
        "MNiSW",
        "PL",
        "501100004569",
        "https://ror.org/05dwvd537",
        "https://www.gov.pl/web/nauka",
    ),
    (
        "Fundacja na rzecz Nauki Polskiej",
        "Foundation for Polish Science",
        "FNP",
        "PL",
        "501100001870",
        "https://ror.org/048zd9m77",
        "https://fnp.org.pl",
    ),
    (
        "Narodowa Agencja Wymiany Akademickiej",
        "National Agency for Academic Exchange",
        "NAWA",
        "PL",
        "501100014434",
        "https://ror.org/02jf81j23",
        "https://nawa.gov.pl",
    ),
    (
        "Agencja Badań Medycznych",
        "Medical Research Agency",
        "ABM",
        "PL",
        "501100023181",
        "https://ror.org/026nedj88",
        "https://abm.gov.pl",
    ),
    (
        "Komisja Europejska",
        "European Commission",
        "EC",
        "BE",
        "501100000780",
        "https://ror.org/00k4n6c32",
        "https://commission.europa.eu",
    ),
]


def seed(apps, schema_editor):
    Instytucja_Finansujaca = apps.get_model("bpp", "Instytucja_Finansujaca")
    for nazwa, nazwa_en, akronim, kraj, fundref_id, ror_id, www in INSTYTUCJE:
        klucz = {"fundref_id": fundref_id} if fundref_id else {"nazwa": nazwa}
        Instytucja_Finansujaca.objects.get_or_create(
            defaults={
                "nazwa": nazwa,
                "nazwa_en": nazwa_en,
                "akronim": akronim,
                "kraj": kraj,
                "fundref_id": fundref_id,
                "ror_id": ror_id,
                "strona_www": www,
            },
            **klucz,
        )


class Migration(migrations.Migration):
    dependencies = [("bpp", "0485_projekt_finansowanie")]

    # Reverse to jawny no-op — uzasadnienie w docstringu modułu.
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
