"""Demo state for the screenshots of docs/redaktor/dwudyscyplinowcy.md.

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-dwudyscyplinowcy.py

The dump has no author with two disciplines and no journal disciplines, so
"Dwudyscyplinowcy" would be empty. This script:

- gives five authors a second discipline (``subdyscyplina``) for some of
  the years 2022-2025 (Renfri ze Stygga gets "historia", which no journal
  has, so she is deliberately NOT on the list),
- gives every journal its disciplines for 2022-2025, so part of each
  author's articles match the second discipline and part do not,
- moves a few matching articles of Yennefer Merigold to her second
  discipline (so the "Sloty" column has values) and rebuilds the points
  cache of those records,
- computes the author metrics synchronously (``oblicz_metryki``), so the
  "Optymalizacja publikacji" page reached through the "Optymalizuj" button
  shows the author's slot usage instead of "Metryka autora nie istnieje",
- creates the editor account ``vesemir`` (is_staff + "wprowadzanie danych").

Updates go through querysets on purpose: database triggers would otherwise
remap the authors' works when their disciplines are edited.
"""

from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.management import call_command
from password_policies.models import PasswordHistory

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    BppUser,
    Dyscyplina_Naukowa,
    Dyscyplina_Zrodla,
    Wydawnictwo_Ciagle_Autor,
    Zrodlo,
)
from bpp.models.sloty.core import IPunktacjaCacher

LATA = range(2022, 2026)

# --- editor account -------------------------------------------------------
user, _ = BppUser.objects.get_or_create(
    username="vesemir",
    defaults=dict(
        email="vesemir@example.com", first_name="Vesemir", last_name="z Kaer Morhen"
    ),
)
user.set_password(user.username)  # demo DB only: password == login
user.is_staff = True
user.save()
user.groups.add(Group.objects.get(name="wprowadzanie danych"))
if not PasswordHistory.objects.filter(user=user).exists():
    PasswordHistory.objects.create(user=user, password=user.password)


def dyscyplina(nazwa):
    return Dyscyplina_Naukowa.objects.get(nazwa=nazwa)


filozofia = dyscyplina("filozofia")
archeologia = dyscyplina("archeologia")
teologia = dyscyplina("nauki teologiczne")
biotechnologia = dyscyplina("biotechnologia")
historia = dyscyplina("historia")

# --- second disciplines ---------------------------------------------------
# (first name, surname, second discipline, years)
DWUDYSCYPLINOWCY = [
    ("Yennefer", "Merigold", archeologia, LATA),
    ("Triss", "O'Dimm", teologia, range(2023, 2026)),
    ("Lambert", "z Roggeveen", archeologia, range(2024, 2026)),
    ("Rience", "z Aretuzy", filozofia, LATA),
    ("Renfri", "ze Stygga", historia, LATA),
]
for imiona, nazwisko, sub, lata in DWUDYSCYPLINOWCY:
    autor = Autor.objects.get(imiona=imiona, nazwisko=nazwisko)
    Autor_Dyscyplina.objects.filter(autor=autor, rok__in=list(lata)).update(
        subdyscyplina_naukowa=sub,
        procent_dyscypliny=Decimal("70.00"),
        procent_subdyscypliny=Decimal("30.00"),
    )

# --- journal disciplines --------------------------------------------------
DYSCYPLINY_ZRODEL = {
    "Acta": [filozofia, archeologia],
    "Annales": [teologia],
    "Folia": [archeologia, biotechnologia],
    "Przegląd": [filozofia],
    "Roczniki": [biotechnologia],
    "Studia": [teologia, filozofia],
}
for zrodlo in Zrodlo.objects.all():
    for d in DYSCYPLINY_ZRODEL[zrodlo.nazwa.split()[0]]:
        for rok in LATA:
            Dyscyplina_Zrodla.objects.get_or_create(
                zrodlo=zrodlo, rok=rok, dyscyplina=d
            )

# --- a few articles already counted in the second discipline --------------
yennefer = Autor.objects.get(imiona="Yennefer", nazwisko="Merigold")
przeniesione = Wydawnictwo_Ciagle_Autor.objects.filter(
    autor=yennefer,
    rekord__rok__in=[2023, 2024],
    rekord__zrodlo__nazwa__startswith="Folia",
).order_by("rekord__rok", "rekord__tytul_oryginalny")[:2]
rekordy = [wca.rekord for wca in przeniesione]
Wydawnictwo_Ciagle_Autor.objects.filter(pk__in=[w.pk for w in przeniesione]).update(
    dyscyplina_naukowa=archeologia
)
for rekord in rekordy:
    cacher = IPunktacjaCacher(rekord)
    cacher.removeEntries()
    cacher.rebuildEntries()

# --- author metrics (synchronously) ---------------------------------------
call_command("oblicz_metryki", nadpisz=True)

print("OK: dwudyscyplinowcy seeded")
