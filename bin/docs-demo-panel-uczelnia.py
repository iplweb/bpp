"""Demo state for the screenshots of the university settings pages:
docs/administrator/ogolna.md, docs/redaktor/uczelnia.md,
docs/redaktor/autorzy.md and docs/redaktor/wydawnictwa.md.

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-panel-uczelnia.py

- creates the editor account ``vesemir`` (is_staff + "wprowadzanie danych")
  and the superuser ``regis`` (the PBN/integration sections of the
  university form are shown to superusers only),
- gives Margarita Merigold three workplaces (a finished one, the main one
  and a second, current one), so "Aktualne miejsce pracy" has something
  to choose from,
- fills the PBN section of the university with obviously fake values.
"""

import datetime

from django.contrib.auth.models import Group
from django.db.models import F
from password_policies.models import PasswordHistory

from bpp.models import Autor, Autor_Jednostka, BppUser, Jednostka, Uczelnia


def konto(username, first_name, last_name, superuser=False):
    user, _ = BppUser.objects.get_or_create(
        username=username,
        defaults=dict(
            email=f"{username}@example.com",
            first_name=first_name,
            last_name=last_name,
        ),
    )
    user.set_password(user.username)  # demo DB only: password == login
    user.is_staff = True
    user.is_superuser = superuser
    user.save()
    if not PasswordHistory.objects.filter(user=user).exists():
        PasswordHistory.objects.create(user=user, password=user.password)
    return user


redaktor = konto("vesemir", "Vesemir", "z Kaer Morhen")
redaktor.groups.add(Group.objects.get(name="wprowadzanie danych"))
konto("regis", "Emiel Regis", "Rohellec Terzieff-Godefroy", superuser=True)

# --- several workplaces of one author -------------------------------------
autor = Autor.objects.get(imiona="Margarita", nazwisko="Merigold")
# Jednostki bierzemy z bazy, a nie po nazwie: nazwy losuje generator danych
# demo z puli motywu, a po rozszerzeniu puli (commit 4be76d7aa) ten sam
# --seed daje inne jednostki — np. „Klinika Mutacji” już nie powstaje.
# Główne miejsce pracy = dotychczasowa jednostka autorki; dwie pozostałe =
# pierwsze alfabetycznie jednostki bez podjednostek (bez wydziałów).
glowna = autor.aktualna_jednostka
pozostale = list(
    Jednostka.objects.filter(rght=F("lft") + 1)
    .exclude(pk=glowna.pk)
    .order_by("nazwa")[:2]
)
if len(pozostale) < 2:
    raise SystemExit(
        "Za mało jednostek w bazie demo — wygeneruj dane wg "
        "docs/deweloper/zrzuty-ekranu.md."
    )
Autor_Jednostka.objects.filter(autor=autor).delete()
for jednostka, od, do, podstawowe in [
    (
        pozostale[0],
        datetime.date(2014, 10, 1),
        datetime.date(2019, 9, 30),
        None,
    ),
    (glowna, datetime.date(2019, 10, 1), None, True),
    (pozostale[1], datetime.date(2021, 3, 1), None, None),
]:
    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=od,
        zakonczyl_prace=do,
        podstawowe_miejsce_pracy=podstawowe,
    )
autor.refresh_from_db()  # a DB trigger recomputes aktualna_jednostka

# --- PBN section: obviously fake values -------------------------------------
uczelnia = Uczelnia.objects.get()
uczelnia.pbn_integracja = True
uczelnia.pbn_aktualizuj_na_biezaco = True
uczelnia.pbn_api_root = "https://pbn.nauka.gov.pl"
uczelnia.pbn_app_name = "demo-aplikacja-0000"
uczelnia.pbn_app_token = "demo-token-0000"
uczelnia.pbn_api_user = redaktor
uczelnia.save()

print("OK:", autor, autor.aktualna_jednostka)
