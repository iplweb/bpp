"""Demo state for docs/administrator/metody-logowania.md (login methods).

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-logowanie-metody.py

What it does:

- creates the superuser ``regis`` and the editor ``vesemir``,
- fills the "ORCID" section of the university with obviously fake
  credentials, so the "logowanie ORCID" buttons appear (nothing ever talks
  to ORCID: the screenshots never click them),
- adds one made-up locked-out login attempt (documentation IP range
  192.0.2.0/24), so the "Access attempts" admin list is not empty.

The OIDC (Keycloak) buttons are switched on by the environment, not by the
database: start run-site with fake DJANGO_BPP_OIDC_* variables whose issuer
points at a closed local port, e.g.

    DJANGO_BPP_OIDC_CLIENT_ID=bpp-demo \\
    DJANGO_BPP_OIDC_CLIENT_SECRET=demo-token-0000 \\
    DJANGO_BPP_OIDC_ISSUER=http://127.0.0.1:9/realms/uczelnia \\
    uv run run-site run --from-dump ... --no-browser --no-celery

At start-up BPP tries ``.well-known`` on the issuer once; a closed local port
fails at once and no external service is contacted.

Idempotent.
"""

from axes.models import AccessAttempt
from django.contrib.auth.models import Group
from password_policies.models import PasswordHistory

from bpp.models import BppUser, Uczelnia

DEMO_USER_REDAKTOR = "vesemir"  # demo editor: is_staff + "wprowadzanie danych"
DEMO_USER_ADMIN = "regis"  # demo superuser for administrator pages


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


regis = konto(DEMO_USER_ADMIN, "Emiel", "Regis", superuser=True)
konto(
    DEMO_USER_REDAKTOR,
    "Vesemir",
    "z Kaer Morhen",
    grupy=["wprowadzanie danych"],
    staff=True,
)

ucz = Uczelnia.objects.get()
ucz.orcid_client_id = "APP-DEMO0000DEMO0000"
ucz.orcid_client_secret = "demo-token-0000"
ucz.orcid_sandbox = True
ucz.orcid_tylko_dla_pracownikow = False
ucz.save()

AccessAttempt.objects.filter(username="geralt").delete()
AccessAttempt.objects.create(
    username="geralt",
    ip_address="192.0.2.15",
    user_agent="Mozilla/5.0 (X11; Linux x86_64)",
    http_accept="text/html",
    path_info="/accounts/login/local/",
    get_data="",
    post_data="username=geralt",
    failures_since_start=10,
)

print("logowanie-metody demo ready:", ucz, "| superuser:", regis.username)
