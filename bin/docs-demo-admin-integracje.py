"""Demo state for the administrator integration pages (PBN, DSpace, CERIF, groups).

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-admin-integracje.py

Used by the screenshots of docs/administrator/konfiguracja-pbn.md,
integracja-dspace.md, eksport-cerif.md and grupy-uprawnien.md. What it does:

- creates the superuser ``regis`` and the editor ``vesemir``
  (is_staff + "wprowadzanie danych", "eksport do DSpace"),
- fills the PBN, DSpace and CERIF sections of the university with obviously
  fake values. Nothing here ever talks to PBN or DSpace: the values are
  written straight to the database (the admin form would resolve the host
  names), and the screenshots never press "Zapisz".

Idempotent.
"""

from django.contrib.auth.models import Group
from password_policies.models import PasswordHistory

from bpp.const import GR_EKSPORT_DSPACE
from bpp.models import BppUser, Uczelnia


def konto(username, first_name, last_name, grupy=(), staff=False, superuser=False):
    u, _ = BppUser.objects.get_or_create(
        username=username,
        defaults=dict(
            email=f"{username}@example.com",
            first_name=first_name,
            last_name=last_name,
        ),
    )
    u.set_password(u.username)  # demo DB only: password == login
    u.is_staff = staff or superuser
    u.is_superuser = superuser
    u.save()
    for nazwa in grupy:
        u.groups.add(Group.objects.get(name=nazwa))
    if not PasswordHistory.objects.filter(user=u).exists():
        PasswordHistory.objects.create(user=u, password=u.password)
    return u


regis = konto("regis", "Emiel", "Regis", superuser=True)
konto(
    "vesemir",
    "Vesemir",
    "z Kaer Morhen",
    grupy=["wprowadzanie danych", GR_EKSPORT_DSPACE],
    staff=True,
)

ucz = Uczelnia.objects.get()

# --- PBN: fake application, no server behind it ---------------------------
ucz.pbn_integracja = True
ucz.pbn_aktualizuj_na_biezaco = True
ucz.pbn_api_root = "https://pbn-micro-alpha.opi.org.pl"
ucz.pbn_app_name = "BPP-demo"
ucz.pbn_app_token = "demo-token-0000"
ucz.pbn_api_user = regis

# --- DSpace: a made-up repository (example.org never answers) -------------
ucz.dspace_aktywny = True
ucz.dspace_api_endpoint = "https://repozytorium.example.org/server/api"
ucz.dspace_api_username = "bpp-demo"
ucz.dspace_api_password = "demo-token-0000"
ucz.dspace_domyslny_jezyk_dc = "pl"

# --- CERIF / OpenAIRE ------------------------------------------------------
ucz.eksport_cerif_wlaczony = True
ucz.eksport_cerif_osoby = True
ucz.eksport_cerif_kwoty = False
ucz.ror_id = ""  # no made-up ROR: it would point at a real institution
ucz.oai_identyfikator_repozytorium = "bpp.twoja-uczelnia.pl"

# save() runs clean(), which validates *changed* integration URLs offline
# (no DNS) - fine for these values.
ucz.save()

print("admin-integracje demo ready:", ucz, "| superuser:", regis.username)
