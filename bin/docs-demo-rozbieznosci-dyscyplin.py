"""Demo state for the screenshots of docs/redaktor/rozbieznosci-dyscyplin.md.

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-rozbieznosci-dyscyplin.py

The dump already has plenty of "author has a discipline, the work has none"
rows (edited books). This adds the two other kinds, both in 2024, the way
they come from imported or old data (a database trigger remaps the works
when an author's discipline is edited in BPP, so the state has to be forced
afterwards):

- Regis z Cintry: 2024 discipline "filozofia" + second discipline
  "archeologia", while his 2024 articles carry "nauki teologiczne",
- Cahir z Aretuzy: no 2024 discipline assignment, while his 2024 articles
  carry "archeologia",
- two journals get a 2024 discipline, so "rozbieżności dyscyplin źródeł"
  has rows,
- creates the editor account ``vesemir`` (is_staff + "wprowadzanie danych").

Updates go through querysets on purpose: model validation would (correctly)
refuse to create such an inconsistent state by hand.
"""

from django.contrib.auth.models import Group
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

ROK = 2024

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

filozofia = Dyscyplina_Naukowa.objects.get(nazwa="filozofia")
archeologia = Dyscyplina_Naukowa.objects.get(nazwa="archeologia")

teologia = Dyscyplina_Naukowa.objects.get(nazwa="nauki teologiczne")

# --- work discipline differs from both author disciplines -----------------
regis = Autor.objects.get(imiona="Regis", nazwisko="z Cintry")
Autor_Dyscyplina.objects.filter(autor=regis, rok=ROK).update(
    dyscyplina_naukowa=filozofia, subdyscyplina_naukowa=archeologia
)
Wydawnictwo_Ciagle_Autor.objects.filter(autor=regis, rekord__rok=ROK).update(
    dyscyplina_naukowa=teologia
)

# --- work has a discipline, the author has no assignment for the year -----
cahir = Autor.objects.get(imiona="Cahir", nazwisko="z Aretuzy")
Autor_Dyscyplina.objects.filter(autor=cahir, rok=ROK).delete()
Wydawnictwo_Ciagle_Autor.objects.filter(autor=cahir, rekord__rok=ROK).update(
    dyscyplina_naukowa=archeologia
)

# --- journal disciplines -----------------------------------------------------
for nazwa, dyscyplina in [
    ("Acta Oxenfurcka", filozofia),
    ("Folia Kaedwenica", archeologia),
]:
    for zrodlo in Zrodlo.objects.filter(nazwa=nazwa):
        Dyscyplina_Zrodla.objects.get_or_create(
            zrodlo=zrodlo, rok=ROK, dyscyplina=dyscyplina
        )

print("OK: rozbieżności dyscyplin seeded")
