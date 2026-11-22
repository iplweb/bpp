"""Seed the Witcher demo DB for the screenshots of
docs/uzytkownik/tabela-krzyzowa.md (scenario ``tabela-krzyzowa``).

Run on the ready demo DB (docs/deweloper/zrzuty-ekranu.md), then flush:

    uv run python src/manage.py shell < bin/docs-demo-tabela-krzyzowa.py
    uv run python src/manage.py denorm_flush

In the dump all 50 works of Yennefer Merigold are from 2020-2026, in one
unit, spread over ~20 kinds of work. A cross table "unit x kind of work"
would then be one row and twenty narrow columns. This script turns her
works into a career that reads well in the table:

- years spread over 2002-2025 (three works stay in 2026, outside the
  2000-2025 range used on the page),
- three units in turn (until 2009, 2010-2017, from 2018), with matching
  employment history. Jednostki są wybierane z bazy, a nie po nazwie (nazwy
  losuje generator danych demo): ostatnia to obecna jednostka autorki, dwie
  wcześniejsze to pierwsze alfabetycznie inne jednostki bez podjednostek.
  Skrypt wypisuje, które jednostki wybrał,
- four kinds of work (article, letter to the editor, book, book chapter)
  with plausible MNiSW points.

It also makes sure the demo user ``yennefer`` exists (password == login),
for the export screenshot. Re-running the script gives the same result.
"""

import datetime

from django.db import transaction
from django.db.models import F
from password_policies.models import PasswordHistory

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Autor_Jednostka,
    BppUser,
    Charakter_Formalny,
    Jednostka,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)

YENNEFER = Autor.objects.get(imiona="Yennefer", nazwisko="Merigold")

# Jednostki z bazy, a nie po nazwie: nazwy losuje generator danych demo z puli
# motywu, a po rozszerzeniu puli (commit 4be76d7aa) ten sam --seed daje inne
# jednostki. Ostatnia = obecna jednostka autorki; dwie wcześniejsze = pierwsze
# alfabetycznie jednostki bez podjednostek (bez wydziałów).
OBECNA = YENNEFER.aktualna_jednostka
if OBECNA is None:
    raise SystemExit("Yennefer Merigold nie ma aktualnej jednostki w bazie demo.")
WCZESNIEJSZE = list(
    Jednostka.objects.filter(rght=F("lft") + 1)
    .exclude(pk=OBECNA.pk)
    .order_by("nazwa")[:2]
)
if len(WCZESNIEJSZE) < 2:
    raise SystemExit(
        "Za mało jednostek w bazie demo — wygeneruj dane wg "
        "docs/deweloper/zrzuty-ekranu.md."
    )

JEDNOSTKI = [
    # (last year, unit)
    (2009, WCZESNIEJSZE[0]),
    (2017, WCZESNIEJSZE[1]),
    (9999, OBECNA),
]


def jednostka_w_roku(rok):
    for do_roku, jednostka in JEDNOSTKI:
        if rok <= do_roku:
            return jednostka
    raise ValueError(rok)


CF = {
    n: Charakter_Formalny.objects.get(nazwa=n)
    for n in (
        "Artykuł w czasopismie",
        "List do redakcji",
        "Książka",
        "Rozdział książki",
    )
}
PUNKTY_ART = [20, 40, 70, 100, 140, 200, 70, 40, 100]

with transaction.atomic():
    u, _ = BppUser.objects.get_or_create(
        username="yennefer",
        defaults=dict(
            email="yennefer@example.com",
            first_name="Yennefer",
            last_name="z Vengerbergu",
        ),
    )
    if u.autor_id is None:
        u.autor = YENNEFER
    u.set_password(u.username)
    u.save()
    PasswordHistory.objects.create(user=u, password=u.password)

    # (kind, through-row) sorted by record pk: deterministic order
    powiazania = [
        ("ciagle", wa)
        for wa in Wydawnictwo_Ciagle_Autor.objects.filter(autor=YENNEFER)
        .select_related("rekord")
        .order_by("rekord_id")
    ] + [
        ("zwarte", wa)
        for wa in Wydawnictwo_Zwarte_Autor.objects.filter(autor=YENNEFER)
        .select_related("rekord")
        .order_by("rekord_id")
    ]
    # interleave articles and books so every period has both
    powiazania.sort(key=lambda p: (p[1].rekord_id * 7919) % 101)

    n = len(powiazania)
    w_zakresie = n - 3
    for i, (rodzaj, wa) in enumerate(powiazania):
        rok = 2002 + (i * 24) // w_zakresie if i < w_zakresie else 2026
        rekord = wa.rekord
        rekord.rok = rok
        if rodzaj == "ciagle":
            if i % 7 == 3:
                rekord.charakter_formalny = CF["List do redakcji"]
                rekord.punkty_kbn = 5
            else:
                rekord.charakter_formalny = CF["Artykuł w czasopismie"]
                rekord.punkty_kbn = PUNKTY_ART[i % len(PUNKTY_ART)]
        else:
            if i % 3 == 0:
                rekord.charakter_formalny = CF["Książka"]
                rekord.punkty_kbn = 80 if i % 2 else 200
            else:
                rekord.charakter_formalny = CF["Rozdział książki"]
                rekord.punkty_kbn = 20 if i % 2 else 50
        rekord.save()
        wa.jednostka = jednostka_w_roku(rok)
        wa.afiliuje = True
        # a discipline must match the author's discipline in that year
        ad = Autor_Dyscyplina.objects.filter(autor=YENNEFER, rok=rok).first()
        wa.dyscyplina_naukowa = ad.dyscyplina_naukowa if ad else None
        wa.save()

    # employment history matching the units above
    okresy = [
        (WCZESNIEJSZE[0], datetime.date(2001, 10, 1), datetime.date(2009, 12, 31)),
        (WCZESNIEJSZE[1], datetime.date(2010, 1, 1), datetime.date(2017, 12, 31)),
        (OBECNA, datetime.date(2018, 1, 1), None),
    ]
    for jednostka, od, do in okresy:
        aj, _ = Autor_Jednostka.objects.get_or_create(
            autor=YENNEFER, jednostka=jednostka
        )
        aj.rozpoczal_prace = od
        aj.zakonczyl_prace = do
        aj.save()

print("prace Yennefer:", n)
for do_roku, jednostka in JEDNOSTKI:
    print(f"do {do_roku}: {jednostka.nazwa} (/bpp/jednostka/{jednostka.slug}/)")
