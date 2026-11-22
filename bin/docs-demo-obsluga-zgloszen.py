"""Stan demo do zrzutów docs/redaktor/obsluga-zgloszen.md (scenariusz
``obsluga-zgloszen``).

Uruchom na bazie demo (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-obsluga-zgloszen.py

Zgłoszenia tworzy już ``create_demo_data`` (``--zgloszen``), ale bez plików
załączników. Scenariusz pokazuje zgłoszenie książki niedostępnej w sieci:
z plikiem PDF i bez adresu WWW. Skrypt bierze zgłoszenie monografii
„do obsługi” wybrane przez bpp.demo_data.zrzuty.zgloszenie_ksiazki (tę samą
regułę stosuje scenariusz), usuwa adres WWW, ustawia dostęp ograniczony
i dokłada mały plik PDF. Tworzy też redaktora ``vesemir`` w grupie
„zgłoszenia publikacji”. Ponowne uruchomienie daje ten sam stan.
"""

from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from password_policies.models import PasswordHistory

from bpp.demo_data.zrzuty import zgloszenie_ksiazki
from bpp.models import BppUser

# Najmniejszy poprawny PDF z jedną pustą stroną.
PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)

u, _ = BppUser.objects.get_or_create(
    username="vesemir",
    defaults=dict(
        email="vesemir@example.com", first_name="Vesemir", last_name="z Kaer Morhen"
    ),
)
u.is_staff = True
u.set_password(u.username)  # demo DB only: password == login
u.save()
for grupa in ("wprowadzanie danych", "zgłoszenia publikacji"):
    u.groups.add(Group.objects.get(name=grupa))
if not PasswordHistory.objects.filter(user=u).exists():
    PasswordHistory.objects.create(user=u, password=u.password)

z = zgloszenie_ksiazki()
z.strona_www = ""
z.forma_dostepu = type(z).FormyDostepu.OGRANICZONY
if z.plik:
    z.plik.delete(save=False)
z.plik.save("pelny-tekst.pdf", ContentFile(PDF), save=False)
z.oryginalna_nazwa_pliku = "pelny-tekst.pdf"
z.save()
print(f"obsluga-zgloszen: książka „{z.tytul_oryginalny}” — plik PDF, bez adresu WWW")
