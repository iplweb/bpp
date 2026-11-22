"""Seed the Witcher demo DB with author and source duplicates, for the
screenshots of docs/redaktor/duplikaty.md (scenario ``duplikaty``).

Run on the ready demo DB (docs/deweloper/zrzuty-ekranu.md), once:

    uv run python src/manage.py shell < bin/docs-demo-duplikaty.py
    uv run python src/manage.py denorm_flush

What it does:

- creates the demo editor ``vesemir`` (password == login, ``is_staff``,
  group "wprowadzanie danych"),
- turns one demo author into "Geralt z Rivii" (ORCID, title, unit) and adds
  two duplicates of him, as an import would: "G. z Rivii" (2 works, filed
  under a wrong unit) and "Geralt z Rivii" (3 works, no ORCID/title),
- puts one journal on the ministerial list (a local PBN journal record
  with an MNiSW ID; nothing is sent to PBN) and splits off 4 of its
  publications into a duplicate source with the same name in capitals
  ("ACTA …") and the same ISSN.

Autora i źródło wybieramy z bazy, a nie po pk/nazwie (nazwy losuje generator
danych demo, a pk zależą od tego, czy baza była już zapełniana): autor to
pierwsza alfabetycznie osoba z aktualną jednostką i co najmniej 3 pracami
w czasopismach, źródło — to z największą liczbą prac. Skrypt wypisuje wybór.

The scenario changes the data (merges, remaps), so take screenshots on a
fresh copy of the DB each time.
"""

from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Count, F
from password_policies.models import PasswordHistory

from bpp.models import (
    Autor,
    BppUser,
    Jednostka,
    Tytul,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
    Zrodlo,
)
from pbn_api.models import Journal


def brak(co):
    raise SystemExit(
        f"Brak w bazie demo: {co} — wygeneruj dane wg docs/deweloper/zrzuty-ekranu.md."
    )


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

    # demo author -> "Geralt z Rivii"
    g = (
        Autor.objects.filter(aktualna_jednostka__isnull=False)
        .annotate(prac=Count("wydawnictwo_ciagle_autor"))
        .filter(prac__gte=3)
        .order_by("nazwisko", "imiona", "pk")
        .first()
    )
    if g is None:
        brak("autor z aktualną jednostką i co najmniej 3 pracami")
    print(f"Geralt z Rivii: dawniej {g} (pk {g.pk})")
    g.nazwisko, g.imiona = "z Rivii", "Geralt"
    g.orcid = "0000-0002-1825-0097"  # ORCID's own fictional example record
    g.tytul = Tytul.objects.filter(skrot="dr").first()
    g.save()
    for klass in (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor):
        klass.objects.filter(autor=g).update(zapisany_jako="Geralt z Rivii")
    jedn = g.aktualna_jednostka
    # a wrong unit: first other unit without subunits, alphabetically
    inna = (
        Jednostka.objects.filter(rght=F("lft") + 1)
        .exclude(pk=jedn.pk)
        .order_by("nazwa")
        .first()
    )
    if inna is None:
        brak("druga jednostka bez podjednostek")

    jego = Wydawnictwo_Ciagle.objects.filter(autorzy_set__autor=g)
    wolne = list(
        Wydawnictwo_Ciagle.objects.exclude(pk__in=jego.values("pk"))
        .filter(rok__gte=2023)
        .order_by("pk")[:5]
    )
    d1 = Autor.objects.create(nazwisko="z Rivii", imiona="G.")
    d2 = Autor.objects.create(nazwisko="z Rivii", imiona="Geralt")
    for d, prace, jednostka in ((d1, wolne[:2], inna), (d2, wolne[2:], jedn)):
        jednostka.dodaj_autora(d)
        for p in prace:
            p.dodaj_autora(d, jednostka)

    main = (
        Zrodlo.objects.exclude(issn=None)
        .exclude(issn="")
        .annotate(prac=Count("wydawnictwo_ciagle"))
        .order_by("-prac", "nazwa", "pk")
        .first()
    )
    if main is None:
        brak("źródło z ISSN")
    print(f"źródło: {main.nazwa} (ISSN {main.issn}), duplikat: {main.nazwa.upper()}")
    main.pbn_uid = Journal.objects.create(
        mongoId="5e709189878c28a04737dc6f",
        status="ACTIVE",
        versions=[
            {
                "current": True,
                "object": {"title": main.nazwa, "issn": main.issn, "mniswId": 31337},
            }
        ],
    )
    main.save()
    dup = Zrodlo.objects.create(
        nazwa=main.nazwa.upper(),
        skrot=f"{main.skrot} (dup.)",
        issn=main.issn,
        rodzaj=main.rodzaj,
    )
    for p in Wydawnictwo_Ciagle.objects.filter(zrodlo=main).order_by("-pk")[:4]:
        p.zrodlo = dup
        p.save()
