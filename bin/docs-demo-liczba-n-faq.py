"""Demo state for the screenshots of docs/redaktor/liczba-n-faq.md.

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-liczba-n-faq.py

In the demo dump every author is "N", on a full-time contract, with one
discipline at 100% in each year 2022-2025 - so the N number is just a head
count and none of the usual reasons for a difference shows up. This script
introduces one example of each reason (by author id, stable in the dump):

- 8 authors of "nauki teologiczne" split 60/40 with "historia", so a
  second, small discipline lands in "Dyscypliny nieraportowane",
- part-time contracts (0.50 and 0.75),
- one author with data only for 2024-2025 (hired in 2024),
- one doctoral student (D) and one record without an author type,
- one record without a contract size,
- one author with one discipline but 75% (the hidden "75 + 25 = 100" case),
- one author who left: current unit moved to a unit that does not
  "skupia pracowników".

It also creates the editor account ``vesemir`` (is_staff + "wprowadzanie
danych") and computes the N number. Meant for a disposable demo DB.
"""

from decimal import Decimal

from django.contrib.auth.models import Group
from password_policies.models import PasswordHistory

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    BppUser,
    Dyscyplina_Naukowa,
    Jednostka,
    Uczelnia,
)
from ewaluacja_common.models import Rodzaj_Autora
from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_ewaluacji_2022_2025

LATA = range(2022, 2026)
TEOLOGIA_Z_HISTORIA = [225, 213, 141, 229, 169, 209, 133, 145]
POL_ETATU = 132  # Bonhart Lambert, filozofia
TRZY_CZWARTE_ETATU = 220  # Merigold Emhyr, filozofia
OD_2024 = 138  # Bonhart Regis, biotechnologia
DOKTORANT = 166  # Bonhart Geralt, biotechnologia
BEZ_RODZAJU_2025 = 167  # Bonhart Jaskier, archeologia
BEZ_ETATU_2023 = 215  # Merigold Leo, archeologia
PROCENT_75 = 160  # O'Dimm Triss, filozofia
ODESZLA = 187  # Merigold Margarita, archeologia

historia = Dyscyplina_Naukowa.objects.get(nazwa="historia")
N = Rodzaj_Autora.objects.get(skrot="N")
D = Rodzaj_Autora.objects.get(skrot="D")


def ad(autor_id):
    return Autor_Dyscyplina.objects.filter(autor_id=autor_id, rok__in=LATA)


# start from the dump's state, so re-running gives the same result
Autor_Dyscyplina.objects.filter(rok__in=LATA).update(
    rodzaj_autora=N,
    wymiar_etatu=Decimal("1.00"),
    procent_dyscypliny=Decimal("100.00"),
    subdyscyplina_naukowa=None,
    procent_subdyscypliny=None,
)

Autor_Dyscyplina.objects.filter(autor_id__in=TEOLOGIA_Z_HISTORIA, rok__in=LATA).update(
    procent_dyscypliny=Decimal("60.00"),
    subdyscyplina_naukowa=historia,
    procent_subdyscypliny=Decimal("40.00"),
)
ad(POL_ETATU).update(wymiar_etatu=Decimal("0.50"))
ad(TRZY_CZWARTE_ETATU).update(wymiar_etatu=Decimal("0.75"))
ad(DOKTORANT).update(rodzaj_autora=D)
ad(PROCENT_75).update(
    procent_dyscypliny=Decimal("75.00"), procent_subdyscypliny=Decimal("25.00")
)
Autor_Dyscyplina.objects.filter(autor_id=BEZ_RODZAJU_2025, rok=2025).update(
    rodzaj_autora=None
)
Autor_Dyscyplina.objects.filter(autor_id=BEZ_ETATU_2023, rok=2023).update(
    wymiar_etatu=None
)

# hired in 2024: no data for 2022-2023
Autor_Dyscyplina.objects.filter(autor_id=OD_2024, rok__in=[2022, 2023]).delete()

# left the university: current unit no longer "skupia pracowników"
uczelnia = Uczelnia.objects.get()
emeryci, _ = Jednostka.objects.get_or_create(
    nazwa="Pracownicy emerytowani",
    defaults=dict(
        skrot="Emer.",
        uczelnia=uczelnia,
        skupia_pracownikow=False,
        parent=Jednostka.objects.get(nazwa="Wydział Bestiariuszu"),
    ),
)
Autor.objects.filter(pk=ODESZLA).update(aktualna_jednostka=emeryci)

# editor account
u, _ = BppUser.objects.get_or_create(
    username="vesemir",
    defaults=dict(email="vesemir@example.com", first_name="Vesemir"),
)
u.is_staff = True
u.set_password("vesemir")  # demo DB only; password == login
u.save()
u.groups.add(Group.objects.get(name="wprowadzanie danych"))
if not PasswordHistory.objects.filter(user=u).exists():
    PasswordHistory.objects.create(user=u, password=u.password)

oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia)
print("liczba-n-faq demo state ready")
