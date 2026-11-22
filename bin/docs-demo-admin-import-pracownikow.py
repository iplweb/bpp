"""Demo state for the screenshots of docs/administrator/import-pracownikow.md.

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-admin-import-pracownikow.py

The scenario uploads a small staff file for one unit (plik_pracownikow_demo
in bin/docs-screenshots.py). Jednostkę i osoby pliku bierzemy z bazy, a nie
po nazwie (nazwy losuje generator danych demo) — reguły w
bpp.demo_data.zrzuty.import_pracownikow, wspólne ze scenariuszem: jednostka
to obecna jednostka autorki Margarity Merigold, pierwszej osoby z pliku.
Skrypt wypisuje wybór. The "odpięcia" proposal lists
every active author+unit link that is missing from the file, but only in units
with "Zarządzaj automatycznie" set. In the demo every unit has it set, so a
seven-person file would propose unlinking the whole university. This keeps the
flag only on that one unit, so the proposal shows the two people of the unit
left out of the file.

It also creates the editor account ``vesemir`` (is_staff + "wprowadzanie
danych").

The scenario really imports the file (new unit, new author, ended employment,
staff numbers stored on the matched authors), so re-run it on a fresh demo DB
(``run-site run --from-dump ...``), not on one it has already been run on.
"""

from django.contrib.auth.models import Group
from password_policies.models import PasswordHistory

from bpp.demo_data.zrzuty import import_pracownikow
from bpp.models import BppUser, Jednostka

# Jednostka i osoby pliku z bazy, a nie po nazwie (nazwy losuje generator
# danych demo): reguły w bpp.demo_data.zrzuty.import_pracownikow — te same,
# z których scenariusz ``import-pracownikow`` składa plik.
OSOBY = import_pracownikow()
JEDNOSTKA = OSOBY["jednostka"]

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

# --- only one unit is managed automatically -------------------------------
Jednostka.objects.exclude(pk=JEDNOSTKA.pk).update(zarzadzaj_automatycznie=False)
Jednostka.objects.filter(pk=JEDNOSTKA.pk).update(zarzadzaj_automatycznie=True)
print("zarzadzaj_automatycznie: only", JEDNOSTKA.nazwa)
print("w pliku:", ", ".join(str(a) for a in [OSOBY["margarita"], *OSOBY["w_pliku"]]))
print("po BPP ID:", OSOBY["po_id"], "| wielu kandydatów:", OSOBY["wielu"])
print("spoza pliku (propozycja odpięcia):", ", ".join(map(str, OSOBY["spoza_pliku"])))
