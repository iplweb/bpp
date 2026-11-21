"""Seed the Witcher demo DB for the screenshots of
docs/redaktor/wyszukiwanie-redagowanie.md (scenario
``redaktor-wyszukiwanie-redagowanie``).

Run on the ready demo DB (docs/deweloper/zrzuty-ekranu.md), once:

    uv run python src/manage.py shell < bin/docs-demo-redaktor-wyszukiwanie-redagowanie.py

What it does, so that every example DjangoQL query on the page returns
something on the demo data:

- creates the demo editor ``vesemir`` (password == login, ``is_staff``,
  group "wprowadzanie danych"),
- adds a student research club unit "SKN Alchemików" (unit kind
  "Koło naukowe") with three authors whose public profile is hidden, and
  files a few of their works under it,
- hides the public profile of two more (staff) authors,
- links six 2021 articles to (local, made-up) PBN publication records and
  marks three of them as free of charge (``opl_pub_cost_free``).

The scenario only reads data; re-running this script is safe.
"""

from django.contrib.auth.models import Group
from django.db import transaction
from password_policies.models import PasswordHistory

from bpp.models import (
    Autor,
    Autor_Jednostka,
    BppUser,
    Jednostka,
    RodzajJednostki,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
)
from pbn_api.models import Publication

UKRYJ = dict(
    pokazuj_w_wyszukiwaniu=False,
    pokazuj_w_indeksie=False,
    pokazuj_strone_autora=False,
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

    # --- student research club with hidden authors -------------------------
    rodzaj, _ = RodzajJednostki.objects.get_or_create(
        nazwa="Koło naukowe", defaults=dict(skrot="SKN", kolejnosc=90)
    )
    wydzial = Jednostka.objects.get(nazwa="Wydział Magii i Eliksirów")
    skn = Jednostka.objects.filter(nazwa="SKN Alchemików").first()
    if skn is None:
        skn = Jednostka.objects.create(
            nazwa="SKN Alchemików",
            skrot="SKN Alch.",
            parent=wydzial,
            wydzial=wydzial.wydzial,
            uczelnia=wydzial.uczelnia,
            rodzaj=rodzaj,
        )
    studenci = list(
        Autor.objects.filter(wydawnictwo_ciagle_autor__isnull=False)
        .distinct()
        .order_by("-pk")[:3]
    )
    for a in studenci:
        Autor_Jednostka.objects.get_or_create(autor=a, jednostka=skn)
        Autor.objects.filter(pk=a.pk).update(aktualna_jednostka=skn, **UKRYJ)
        for wca in Wydawnictwo_Ciagle_Autor.objects.filter(autor=a)[:2]:
            wca.jednostka = skn
            wca.save()

    # --- hidden staff authors ---------------------------------------------
    for a in (
        Autor.objects.exclude(aktualna_jednostka=None)
        .exclude(aktualna_jednostka=skn)
        .order_by("pk")[:2]
    ):
        Autor.objects.filter(pk=a.pk).update(**UKRYJ)

    # --- PBN counterparts + publication fee info for 2021 articles --------
    for n, rec in enumerate(
        Wydawnictwo_Ciagle.objects.filter(rok=2021).order_by("pk")[:6]
    ):
        if rec.pbn_uid_id is None:
            rec.pbn_uid = Publication.objects.create(
                mongoId=f"64f0cafe{n:016x}",
                status="ACTIVE",
                title=rec.tytul_oryginalny,
                year=rec.rok,
                versions=[
                    {
                        "current": True,
                        "object": {
                            "type": "ARTICLE",
                            "title": rec.tytul_oryginalny,
                            "year": rec.rok,
                        },
                    }
                ],
            )
        rec.opl_pub_cost_free = True if n % 2 else None
        rec.save()
