"""Seed the Witcher demo DB for the screenshots of the "Wyszukiwanie
precyzyjne" series (docs/uzytkownik/wyszukiwanie-precyzyjne*.md, scenarios
``wyszukiwanie-precyzyjne*``).

Run on the ready demo DB (docs/deweloper/zrzuty-ekranu.md), once:

    uv run python src/manage.py shell < bin/docs-demo-wyszukiwanie-precyzyjne.py

What it does, so that every example query on the pages returns something:

- creates the demo editor ``vesemir`` (password == login, ``is_staff``,
  group "wprowadzanie danych") — only staff accounts may save search forms,
- creates the demo superuser ``regis`` (password == login), for the admin
  list of saved forms,
- gives Impact Factor to the journal articles of 2024 (the demo generator
  leaves IF at zero everywhere),
- removes the DOI from every tenth journal article (the generator gives
  every record a DOI),
- creates two saved search forms owned by ``vesemir``: a public one (prace
  obecnej jednostki autorki konta „yennefer” — wybranej z bazy, bo nazwy
  jednostek losuje generator danych demo) and a private one.

Re-running this script is safe.
"""

from decimal import Decimal

from django.contrib.auth.models import Group
from django.db import transaction
from multiseek.logic import EQUAL_FEMALE, EQUAL_NONE, GREATER_OR_EQUAL, IN_RANGE
from multiseek.models import SearchForm
from multiseek.util import make_field
from password_policies.models import PasswordHistory

from bpp.demo_data import zrzuty
from bpp.models import BppUser, Wydawnictwo_Ciagle
from bpp.multiseek_registry.fields import (
    JednostkaQueryObject,
    NazwiskoIImieQueryObject,
    PunktyKBNQueryObject,
    ZakresLatQueryObject,
)
from bpp.views.browse import zrob_formularz

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

    admin, _ = BppUser.objects.get_or_create(
        username="regis",
        defaults=dict(
            email="regis@example.com",
            first_name="Regis",
            last_name="Terzieff-Godefroy",
        ),
    )
    admin.set_password(admin.username)
    admin.is_staff = admin.is_superuser = True
    admin.save()
    PasswordHistory.objects.create(user=admin, password=admin.password)

    # --- Impact Factor on the 2024 journal articles ---------------------------
    for n, wc in enumerate(Wydawnictwo_Ciagle.objects.filter(rok=2024).order_by("pk")):
        if n % 3 == 2:
            continue  # leave some at zero, so "IF > 0" really narrows the list
        wc.impact_factor = Decimal("0.5") + Decimal(n % 9) * Decimal("0.75")
        wc.save()

    # --- journal articles without DOI -----------------------------------------
    for n, wc in enumerate(Wydawnictwo_Ciagle.objects.order_by("pk")):
        if n % 10 == 0 and wc.doi:
            wc.doi = None
            wc.save()

    # --- saved search forms ---------------------------------------------------
    # Autorka konta „yennefer” i jej obecna jednostka — z bazy, nie po pk ani
    # nazwie (nazwy jednostek losuje generator danych demo).
    # Wspólne ze scenariuszami wyszukiwania (bpp.demo_data.zrzuty).
    yennefer = zrzuty.yennefer()
    klinika = zrzuty.aktualna_jednostka(yennefer)
    print("jednostka w formularzu:", klinika.nazwa)
    formularze = {
        f"{klinika.nazwa} — prace od 100 pkt": (
            True,
            zrob_formularz(
                [make_field(JednostkaQueryObject, EQUAL_FEMALE, klinika.pk)],
                [make_field(PunktyKBNQueryObject, GREATER_OR_EQUAL, "100")],
            ),
        ),
        "Yennefer — prace 2020–2024": (
            False,
            zrob_formularz(
                [make_field(NazwiskoIImieQueryObject, EQUAL_NONE, yennefer.pk)],
                [make_field(ZakresLatQueryObject, IN_RANGE, "[2020,2024]")],
            ),
        ),
    }
    for nazwa, (publiczny, dane) in formularze.items():
        SearchForm.objects.update_or_create(
            name=nazwa, defaults=dict(owner=u, public=publiczny, data=dane)
        )
