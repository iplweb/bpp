"""Demo state for the screenshots of docs/administrator/zglaszanie-publikacji.md.

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-admin-zglaszanie-publikacji.py

- creates the editor account ``vesemir`` (is_staff + "wprowadzanie danych"
  + "zgłoszenia publikacji") and the superuser ``regis`` (the university
  settings and the Administracja menu are superuser screens),
- assigns ``vesemir`` to one faculty (pierwszy alfabetycznie) in "Obsługa zgłoszeń prac - wydziały",
  so that list is not empty,
- sets the submission form options to the values the page describes
  (button shown to everyone, no login required, fee questions for articles
  and monographs only).
"""

from django.contrib.auth.models import Group
from password_policies.models import PasswordHistory

from bpp.const import GR_WPROWADZANIE_DANYCH, GR_ZGLOSZENIA_PUBLIKACJI
from bpp.models import BppUser, Jednostka, Uczelnia
from zglos_publikacje.models import Obslugujacy_Zgloszenia_Wydzialow


def konto(username, email, first_name, last_name, **flags):
    u, _ = BppUser.objects.get_or_create(
        username=username,
        defaults=dict(email=email, first_name=first_name, last_name=last_name),
    )
    u.set_password(u.username)  # demo DB only: password == login
    for k, v in flags.items():
        setattr(u, k, v)
    u.save()
    if not PasswordHistory.objects.filter(user=u).exists():
        PasswordHistory.objects.create(user=u, password=u.password)
    return u


vesemir = konto(
    "vesemir", "vesemir@example.com", "Vesemir", "z Kaer Morhen", is_staff=True
)
vesemir.groups.add(
    Group.objects.get(name=GR_WPROWADZANIE_DANYCH),
    Group.objects.get(name=GR_ZGLOSZENIA_PUBLIKACJI),
)

konto(
    "regis",
    "regis@example.com",
    "Emiel",
    "Regis",
    is_staff=True,
    is_superuser=True,
)

# Wydział z bazy, a nie po nazwie (nazwy losuje generator danych demo):
# pierwszy alfabetycznie wydział (jednostka najwyższego poziomu).
wydzial = Jednostka.objects.filter(parent__isnull=True).order_by("nazwa").first()
if wydzial is None:
    raise SystemExit(
        "Brak wydziałów w bazie demo — wygeneruj dane wg "
        "docs/deweloper/zrzuty-ekranu.md."
    )
Obslugujacy_Zgloszenia_Wydzialow.objects.get_or_create(user=vesemir, wydzial=wydzial)

Uczelnia.objects.update(
    pokazuj_formularz_zglaszania_publikacji="always",
    wymagaj_logowania_zglos_publikacje=False,
    wymagaj_oplatach_artykul=True,
    wymagaj_oplatach_monografia=True,
    wymagaj_oplatach_rozdzial=False,
    wymagaj_oplatach_inne=False,
)
print("OK: vesemir, regis, obsługujący zgłoszenia dla:", wydzial)
