"""Seed the Witcher demo DB with duplicate publications, for the screenshots
of docs/redaktor/duplikaty-publikacji.md (scenario ``duplikaty_publikacji``).

Run on the ready demo DB (docs/deweloper/zrzuty-ekranu.md), once, with a
Celery worker running (the scenario starts a real scan):

    uv run python src/manage.py shell < bin/docs-demo-duplikaty-publikacji.py

What it does:

- creates the demo editor ``vesemir`` (password == login, ``is_staff``,
  group "wprowadzanie danych"),
- enters three demo publications from 2024 a second time, the way it
  happens after an import or when two people add the same work:
  - an article with the same title and source, DOI typed as a link
    (``https://doi.org/…``) and only the first two authors,
  - an article entered again as a chapter (wydawnictwo zwarte), without the
    "(nr …)" suffix in the title,
  - a book entered twice with an identical title and only one author.
- removes earlier scan results, so the scenario starts from an empty page.

Rekordy to pierwsze alfabetycznie (po tytule) prace z 2024 r. spełniające
warunek — nie po pk, bo pk zależą od danych demo. Skrypt wypisuje wybór.
"""

from django.contrib.auth.models import Group
from django.db import transaction
from password_policies.models import PasswordHistory

from bpp.demo_data.zrzuty import duplikaty_publikacji
from bpp.models import BppUser, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from deduplikator_publikacji.models import PublicationDuplicateScanRun

# Rekordy wybiera bpp.demo_data.zrzuty.duplikaty_publikacji (pierwsze
# alfabetycznie z 2024 r. spełniające warunek, a nie po pk) — tę samą regułę
# stosuje scenariusz ``duplikaty-publikacji``.
WYBOR = duplikaty_publikacji()
for co, rekord in WYBOR.items():
    print(f"{co}: {rekord.tytul_oryginalny} (pk {rekord.pk})")
ARTYKUL_DOI = WYBOR["artykul_doi"].pk
ARTYKUL_ROZDZIAL = WYBOR["artykul_rozdzial"].pk
KSIAZKA = WYBOR["ksiazka"].pk


def kopiuj_autorow(z, do, ile):
    for wa in z.autorzy_set.order_by("kolejnosc")[:ile]:
        do.dodaj_autora(wa.autor, wa.jednostka, zapisany_jako=wa.zapisany_jako)


with transaction.atomic():
    u, _ = BppUser.objects.get_or_create(
        username="vesemir",
        defaults=dict(
            email="vesemir@example.com",
            first_name="Vesemir",
            last_name="z Kaer Morhen",
        ),
    )
    u.set_password(u.username)
    u.is_staff = True
    u.save()
    u.groups.add(Group.objects.get(name="wprowadzanie danych"))
    PasswordHistory.objects.create(user=u, password=u.password)

    # 1. the same article twice: DOI written as a link, two authors only
    org = Wydawnictwo_Ciagle.objects.get(pk=ARTYKUL_DOI)
    dup = Wydawnictwo_Ciagle.objects.get(pk=ARTYKUL_DOI)
    dup.pk = None
    dup.doi = f"https://doi.org/{org.doi}"
    dup.pbn_uid = None
    dup.save()
    kopiuj_autorow(org, dup, 2)

    # 2. the article entered again as a chapter, title without "(nr 10)"
    org = Wydawnictwo_Ciagle.objects.get(pk=ARTYKUL_ROZDZIAL)
    tytul = org.tytul_oryginalny.split(" (nr")[0]
    kopia = Wydawnictwo_Zwarte.objects.filter(rok=org.rok).order_by("pk").first()
    rozdzial = Wydawnictwo_Zwarte.objects.create(
        tytul_oryginalny=tytul,
        rok=org.rok,
        charakter_formalny=kopia.charakter_formalny,
        typ_kbn=kopia.typ_kbn,
        jezyk=kopia.jezyk,
        status_korekty=kopia.status_korekty,
        wydawca=kopia.wydawca,
        miejsce_i_rok=kopia.miejsce_i_rok,
    )
    kopiuj_autorow(org, rozdzial, 3)

    # 3. the same book twice, identical title, one author
    org = Wydawnictwo_Zwarte.objects.get(pk=KSIAZKA)
    dup = Wydawnictwo_Zwarte.objects.get(pk=KSIAZKA)
    dup.pk = None
    dup.pbn_uid = None
    dup.save()
    kopiuj_autorow(org, dup, 1)

    PublicationDuplicateScanRun.objects.all().delete()
