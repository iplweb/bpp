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
Autor_Jednostka.objects.filter(autor=autor).delete()
for nazwa, od, do, podstawowe in [
    (
        "Zakład Szlaku Wiedźmińskiego",
        datetime.date(2014, 10, 1),
        datetime.date(2019, 9, 30),
        None,
    ),
    ("Klinika Mutacji", datetime.date(2019, 10, 1), None, True),
    ("Katedra i Zakład Mutacji", datetime.date(2021, 3, 1), None, None),
]:
    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=Jednostka.objects.get(nazwa=nazwa),
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
