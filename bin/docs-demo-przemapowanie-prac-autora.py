"""Seed the Witcher demo DB for the screenshots of
docs/redaktor/przemapowanie-prac-autora.md (scenario
``przemapowanie-prac-autora``).

Run on the ready demo DB (docs/deweloper/zrzuty-ekranu.md), once:

    uv run python src/manage.py shell < bin/docs-demo-przemapowanie-prac-autora.py
    uv run python src/manage.py denorm_flush

What it does:

- creates the demo editor ``vesemir`` (password == login, ``is_staff``,
  group "wprowadzanie danych") and the demo superuser ``regis`` (for the
  remap history in the editing module, which only a superuser can open),
- creates "Jednostka Domyślna" - the catch-all unit an import puts works in
  when it cannot tell the author's unit,
- files the 6 newest journal articles and 2 newest books of the demo author
  "Eskel z Cintry" (pk 136, unit "Katedra i Zakład Mutacji") under
  "Jednostka Domyślna", as an import would. The demo DB already has a second,
  unrelated author with the same name (pk 240, "Klinika Mutacji"), which the
  author search shows next to him.

The scenario remaps and undoes, so take screenshots on a fresh copy of the DB.
"""

from django.contrib.auth.models import Group
from django.db import transaction
from password_policies.models import PasswordHistory

from bpp.models import (
    Autor,
    BppUser,
    Jednostka,
    Uczelnia,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)

ESKEL = 136  # "Eskel z Cintry", Katedra i Zakład Mutacji


def konto(username, first_name, last_name, superuser=False):
    u, _ = BppUser.objects.get_or_create(
        username=username,
        defaults=dict(
            email=f"{username}@example.com",
            first_name=first_name,
            last_name=last_name,
        ),
    )
    u.set_password(u.username)
    u.is_staff = True
    u.is_superuser = superuser
    u.save()
    PasswordHistory.objects.create(user=u, password=u.password)
    return u


with transaction.atomic():
    red = konto("vesemir", "Vesemir", "z Kaer Morhen")
    red.groups.add(Group.objects.get(name="wprowadzanie danych"))
    konto("regis", "Emiel", "Regis", superuser=True)

    jd, _ = Jednostka.objects.get_or_create(
        nazwa="Jednostka Domyślna",
        defaults=dict(skrot="JD", uczelnia=Uczelnia.objects.first()),
    )

    eskel = Autor.objects.get(pk=ESKEL)
    for model, ile in (
        (Wydawnictwo_Ciagle_Autor, 6),
        (Wydawnictwo_Zwarte_Autor, 2),
    ):
        pks = list(
            model.objects.filter(autor=eskel)
            .order_by("-rekord__rok", "-rekord__pk")
            .values_list("pk", flat=True)[:ile]
        )
        # queryset update, like an import: no Autor_Jednostka side effects
        model.objects.filter(pk__in=pks).update(jednostka=jd)

print("przemapowanie-prac-autora: demo data ready")
