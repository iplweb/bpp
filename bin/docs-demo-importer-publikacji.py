"""Stan demo do zrzutów docs/redaktor/importer-publikacji.md (scenariusz
``importer-publikacji``).

Uruchom na bazie demo (docs/deweloper/zrzuty-ekranu.md), po
bin/docs-demo-import-list-ministerialnych.py (punktacja „Acta Wiedźmińskiej”
za 2025 r.):

    uv run python src/manage.py shell < bin/docs-demo-importer-publikacji.py

Skrypt:

- mapuje rodzaj CrossRef „journal-article” na charakter formalny „Artykuł
  w czasopismie” (inaczej importer zostawia charakter formalny pusty),
- ustawia obcą jednostkę uczelni, jeśli jej brak (importer przypisuje do niej
  autorów spoza uczelni),
- tworzy redaktora ``vesemir`` (is_staff + „wprowadzanie danych”).

Autorów wpisu BibTeX (osoba z imiennikiem, osoba spoza BPP) wybiera scenariusz
— bpp.demo_data.zrzuty.imiennicy_importera i NIEOBECNI_IMPORTER. Ponowne
uruchomienie daje ten sam stan.
"""

from django.contrib.auth.models import Group
from django.core.management import call_command
from password_policies.models import PasswordHistory

from bpp.models import BppUser, Charakter_Formalny, Uczelnia
from bpp.models.system.crossref_mapper import Crossref_Mapper

artykul = Charakter_Formalny.objects.get(skrot="AC")  # „Artykuł w czasopismie”
Crossref_Mapper.objects.update_or_create(
    charakter_crossref=Crossref_Mapper.CHARAKTER_CROSSREF.JOURNAL_ARTICLE,
    defaults=dict(charakter_formalny_bpp=artykul),
)

if Uczelnia.objects.get().obca_jednostka_id is None:
    call_command("create_obca_jednostka")

u, _ = BppUser.objects.get_or_create(
    username="vesemir",
    defaults=dict(
        email="vesemir@example.com", first_name="Vesemir", last_name="z Kaer Morhen"
    ),
)
u.is_staff = True
u.set_password(u.username)  # demo DB only: password == login
u.save()
u.groups.add(Group.objects.get(name="wprowadzanie danych"))
if not PasswordHistory.objects.filter(user=u).exists():
    PasswordHistory.objects.create(user=u, password=u.password)

print("importer-publikacji: journal-article -> Artykuł w czasopismie")
