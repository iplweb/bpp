"""Demo state for the screenshots of docs/redaktor/import-list-ministerialnych.md.

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-import-list-ministerialnych.py

What this does:

- creates the editor account ``vesemir`` (is_staff + "wprowadzanie danych"),
- wipes the points and disciplines of the demo journals for the demo year
  (``WYKAZ_DEMO_ROK`` in bin/docs-screenshots.py) and the editor's earlier
  ministerial-list imports,
- seeds a few values the made-up ministerial list then compares against:
  one journal with different points, one with identical points and
  disciplines, one with a discipline the list no longer has.

Idempotent: re-running restores the same state, so the scenario
``import-list-ministerialnych`` (which saves an import) can be re-run.
"""

from django.contrib.auth.models import Group
from password_policies.models import PasswordHistory

from bpp.models import BppUser, Dyscyplina_Naukowa, Zrodlo
from import_list_ministerialnych.models import ImportListMinisterialnych

ROK = 2025  # keep in sync with WYKAZ_DEMO_ROK in bin/docs-screenshots.py

u, _ = BppUser.objects.get_or_create(
    username="vesemir",
    defaults=dict(
        email="vesemir@example.com", first_name="Vesemir", last_name="z Kaer Morhen"
    ),
)
u.is_staff = True
u.set_password("vesemir")
u.save()
u.groups.add(Group.objects.get(name="wprowadzanie danych"))
if not PasswordHistory.objects.filter(user=u).exists():
    PasswordHistory.objects.create(user=u, password=u.password)

for op in ImportListMinisterialnych.objects.filter(owner=u):
    op.plik.delete(save=False)  # keeps file names (and breadcrumbs) suffix-free
    op.delete()

for z in Zrodlo.objects.all():
    z.punktacja_zrodla_set.filter(rok=ROK).delete()
    z.dyscyplina_zrodla_set.filter(rok=ROK).delete()


def ustaw(issn, punkty, dyscypliny):
    z = Zrodlo.objects.get(issn=issn)
    z.punktacja_zrodla_set.create(rok=ROK, punkty_kbn=punkty)
    for nazwa in dyscypliny:
        z.dyscyplina_zrodla_set.create(
            rok=ROK, dyscyplina=Dyscyplina_Naukowa.objects.get(nazwa=nazwa)
        )


# Acta Wiedźmińska: 70 in BPP, 100 in the list; one discipline more in the list.
ustaw("6746-8071", 70, ["filozofia"])
# Folia Temerska: identical points and disciplines.
ustaw("7109-3248", 40, ["archeologia", "historia"])
# Przegląd Temerska: a discipline the list no longer assigns.
ustaw("9938-6774", 100, ["historia", "nauki teologiczne"])

print(f"Demo import-list-ministerialnych ready (rok {ROK}).")
