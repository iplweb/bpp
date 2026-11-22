"""Demo state for the screenshots of docs/redaktor/dwudyscyplinowcy.md.

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-dwudyscyplinowcy.py

The dump has no author with two disciplines and no journal disciplines, so
"Dwudyscyplinowcy" would be empty. This script:

- gives five authors a second discipline (``subdyscyplina``) for some of
  the years 2022-2025 (Renfri ze Stygga gets "historia", which no journal
  has, so she is deliberately NOT on the list). Trzy osoby to autorzy
  obowiązkowi motywu „wiedzmin” (zawsze istnieją); dwie pozostałe są
  wybierane z bazy — pierwsi alfabetycznie autorzy, którzy nie mają jeszcze
  tej dyscypliny (skrypt ich wypisuje),
- gives every journal its disciplines for 2022-2025 (po kolei, wg
  alfabetu — nazwy czasopism losuje generator), so part of each author's
  articles match the second discipline and part do not,
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
# Autorzy obowiązkowi motywu „wiedzmin” — zawsze są w danych demo.
OBOWIAZKOWI = [
    ("Yennefer", "Merigold", archeologia, LATA),
    ("Rience", "z Aretuzy", filozofia, LATA),
    ("Renfri", "ze Stygga", historia, LATA),
]
# Pozostali dwaj — z bazy, nie po nazwisku (te losuje generator danych demo).
WYBIERANI = [(teologia, range(2023, 2026)), (archeologia, range(2024, 2026))]


def autor_obowiazkowy(imiona, nazwisko):
    autor = (
        Autor.objects.filter(imiona=imiona, nazwisko=nazwisko).order_by("pk").first()
    )
    if autor is None:
        raise SystemExit(
            f"Brak autora {imiona} {nazwisko} — wygeneruj dane demo wg "
            "docs/deweloper/zrzuty-ekranu.md (motyw „wiedzmin”)."
        )
    return autor


DWUDYSCYPLINOWCY = [
    (autor_obowiazkowy(imiona, nazwisko), sub, lata)
    for imiona, nazwisko, sub, lata in OBOWIAZKOWI
]
for sub, lata in WYBIERANI:
    autor = (
        Autor.objects.filter(autor_dyscyplina__rok__in=list(lata))
        .exclude(autor_dyscyplina__dyscyplina_naukowa=sub)
        .exclude(pk__in=[a.pk for a, _, _ in DWUDYSCYPLINOWCY])
        .distinct()
        .order_by("nazwisko", "imiona", "pk")
        .first()
    )
    if autor is None:
        raise SystemExit(
            f"Brak autora bez dyscypliny „{sub.nazwa}” — wygeneruj dane demo wg "
            "docs/deweloper/zrzuty-ekranu.md."
        )
    DWUDYSCYPLINOWCY.append((autor, sub, lata))

for autor, sub, lata in DWUDYSCYPLINOWCY:
    print(f"{autor}: druga dyscyplina {sub.nazwa}, lata {lata.start}-{lata.stop - 1}")
    Autor_Dyscyplina.objects.filter(autor=autor, rok__in=list(lata)).update(
        subdyscyplina_naukowa=sub,
        procent_dyscypliny=Decimal("70.00"),
        procent_subdyscypliny=Decimal("30.00"),
    )

# --- journal disciplines --------------------------------------------------
# Po kolei wg alfabetu, a nie po pierwszym słowie nazwy: nazwy czasopism
# losuje generator danych demo z puli motywu, a ta się zmienia.
DYSCYPLINY_ZRODEL = [
    [filozofia, archeologia],
    [teologia],
    [archeologia, biotechnologia],
    [filozofia],
    [biotechnologia],
    [teologia, filozofia],
]
for i, zrodlo in enumerate(Zrodlo.objects.order_by("nazwa", "pk")):
    for d in DYSCYPLINY_ZRODEL[i % len(DYSCYPLINY_ZRODEL)]:
        for rok in LATA:
            Dyscyplina_Zrodla.objects.get_or_create(
                zrodlo=zrodlo, rok=rok, dyscyplina=d
            )

# --- a few articles already counted in the second discipline --------------
yennefer = DWUDYSCYPLINOWCY[0][0]
przeniesione = (
    Wydawnictwo_Ciagle_Autor.objects.filter(
        autor=yennefer,
        rekord__rok__in=[2023, 2024],
        rekord__zrodlo__dyscyplina_zrodla__dyscyplina=archeologia,
    )
    .distinct()
    .order_by("rekord__rok", "rekord__tytul_oryginalny")[:2]
)
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
