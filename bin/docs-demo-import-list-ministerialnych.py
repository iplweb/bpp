"""Demo state for the screenshots of docs/redaktor/import-list-ministerialnych.md.

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-import-list-ministerialnych.py

What this does:

- creates the editor account ``vesemir`` (is_staff + "wprowadzanie danych"),
- wipes the points and disciplines of the demo journals for the demo year
  (``WYKAZ_DEMO_ROK`` in bin/docs-screenshots.py) and the editor's earlier
  ministerial-list imports,
- makes sure the BPP journals of the made-up list (WYKAZ_DEMO_WIERSZE in
  bin/docs-screenshots.py) exist: generator danych demo losuje nazwy i ISSN-y
  czasopism, więc brakujące dostają nazwę i ISSN z wykazu — kolejne
  alfabetycznie czasopisma spoza wykazu,
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
# Czasopisma z wykazu, które mają być w BPP (nazwa, ISSN) — zgodnie
# z WYKAZ_DEMO_WIERSZE w bin/docs-screenshots.py (bez „Zoologii Brokilońskiej”,
# której celowo w BPP nie ma).
ZRODLA_Z_WYKAZU = [
    ("Acta Wiedźmińska", "6746-8071"),
    ("Annales Aretuzańska", "9770-3482"),
    ("Folia Temerska", "7109-3248"),
    ("Studia Aretuzańska", "4990-913X"),
    ("Acta Oxenfurcka", "4936-183X"),
    ("Przegląd Temerska", "9938-6774"),
]

u, _ = BppUser.objects.get_or_create(
    username="vesemir",
    defaults=dict(
        email="vesemir@example.com", first_name="Vesemir", last_name="z Kaer Morhen"
    ),
)
u.is_staff = True
u.set_password(u.username)
u.save()
u.groups.add(Group.objects.get(name="wprowadzanie danych"))
if not PasswordHistory.objects.filter(user=u).exists():
    PasswordHistory.objects.create(user=u, password=u.password)

for op in ImportListMinisterialnych.objects.filter(owner=u):
    op.plik.delete(save=False)  # keeps file names (and breadcrumbs) suffix-free
    op.delete()

# Generator danych demo losuje nazwy i ISSN-y czasopism (po rozszerzeniu puli
# nazw motywu w commicie 4be76d7aa ten sam --seed daje inne), więc czasopisma
# z wykazu, których brakuje, tworzymy z kolejnych alfabetycznie czasopism
# spoza wykazu — deterministycznie i z ich dotychczasowymi pracami.
issny = [issn for _, issn in ZRODLA_Z_WYKAZU]
wolne = iter(Zrodlo.objects.exclude(issn__in=issny).order_by("nazwa", "pk"))
for nazwa, issn in ZRODLA_Z_WYKAZU:
    if Zrodlo.objects.filter(issn=issn).exists():
        continue
    z = next(wolne, None)
    if z is None:
        raise SystemExit(
            "Za mało czasopism w bazie demo — wygeneruj dane wg "
            "docs/deweloper/zrzuty-ekranu.md."
        )
    print(f"{z.nazwa} ({z.issn}) -> {nazwa} ({issn})")
    z.nazwa, z.issn = nazwa, issn
    z.save()

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
