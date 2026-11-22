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
- creates "Jednostka Domyślna <skrót uczelni>" - the catch-all unit an
  import puts works in when it cannot tell the author's unit,
- files the 6 newest journal articles and 2 newest books of one demo author
  under "Jednostka Domyślna", as an import would. Autora wybieramy z bazy
  (nie po pk ani nazwisku — te zależą od danych demo): pierwsze alfabetycznie
  imię i nazwisko noszone przez co najmniej dwie osoby; z nich ta z największą
  liczbą prac. Druga osoba o tym samym nazwisku pokazuje się obok w
  wyszukiwarce autorów. Skrypt wypisuje wybranego autora i jego pk.

The scenario remaps and undoes, so take screenshots on a fresh copy of the DB.
"""

from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Count
from password_policies.models import PasswordHistory

from bpp.models import (
    Autor,
    BppUser,
    Jednostka,
    Uczelnia,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)


def autor_z_imiennikiem():
    """Autor, który ma w bazie imiennika (to samo imię i nazwisko).

    Pierwsze alfabetycznie takie imię i nazwisko; spośród osób, które je
    noszą, ta z największą liczbą prac w czasopismach (przy remisie: niższe pk).
    """
    imiennicy = (
        Autor.objects.values("nazwisko", "imiona")
        .annotate(ile=Count("pk"))
        .filter(ile__gte=2)
        .order_by("nazwisko", "imiona")
        .first()
    )
    if imiennicy is None:
        raise SystemExit(
            "W bazie demo nie ma dwóch autorów o tym samym imieniu i nazwisku "
            "— wygeneruj dane wg docs/deweloper/zrzuty-ekranu.md."
        )
    return (
        Autor.objects.filter(nazwisko=imiennicy["nazwisko"], imiona=imiennicy["imiona"])
        .annotate(prac=Count("wydawnictwo_ciagle_autor"))
        .order_by("-prac", "pk")
        .first()
    )


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

    # named like the current PBN import names it: "Jednostka Domyślna <skrót>"
    uczelnia = Uczelnia.objects.first()
    jd, _ = Jednostka.objects.get_or_create(
        nazwa=f"Jednostka Domyślna {uczelnia.skrot}",
        defaults=dict(skrot=f"JD-{uczelnia.skrot}", uczelnia=uczelnia),
    )

    eskel = autor_z_imiennikiem()
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

print(f"przemapowanie-prac-autora: demo data ready — autor {eskel} (pk {eskel.pk})")
