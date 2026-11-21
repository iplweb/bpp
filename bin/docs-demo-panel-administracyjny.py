"""Demo state for docs/administrator/panel-administracyjny.md (the admin dashboard).

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-panel-administracyjny.py

The dashboard ("Panel Sterowania", /admin/) draws its charts from data that a
freshly restored demo DB does not have, so every chart would be empty or flat.
This script, using demo users only:

- creates the superuser ``regis`` and the editor ``vesemir``,
- replaces the login history (easyaudit ``LoginEvent``) with realistic
  weekday logins of the demo accounts over the last six weeks,
- writes menu clicks (``MenuClick``) for ``regis`` and ``vesemir``, so the
  "Najczęściej używane" box has icons,
- writes admin edit history (``LogEntry``) over the last six months, weighted
  towards Monday-Thursday ("Edycje w dni tygodnia", "Aktywność w dniach
  miesiąca", "Ostatnio edytowane"),
- spreads the "utworzono" date of the demo publications over their year
  ("Nowo dodane prace" would otherwise be one spike on the day the demo DB
  was generated) and gives part of the articles a made-up impact factor
  ("Łączny Impact Factor" would be a flat zero line),
- clears the cached chart data (the chart views are cached for 24 hours).

Idempotent: re-running replaces what it wrote. Deterministic (fixed seed).
"""

import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.utils import timezone
from easyaudit.models import LoginEvent
from password_policies.models import PasswordHistory

from admin_dashboard.models import MenuClick
from bpp.models import Autor, BppUser, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

DEMO_USER_REDAKTOR = "vesemir"  # demo editor: is_staff + "wprowadzanie danych"
DEMO_USER_ADMIN = "regis"  # demo superuser for administrator pages

rnd = random.Random(42)
teraz = timezone.now()
tz = timezone.get_current_timezone()


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
vesemir = konto(
    DEMO_USER_REDAKTOR,
    "Vesemir",
    "z Kaer Morhen",
    grupy=["wprowadzanie danych"],
    staff=True,
)


def chwila_w_dniu(dzien, od=8, do=16):
    """A random moment during office hours of the given date."""
    t = time(rnd.randint(od, do - 1), rnd.randint(0, 59), rnd.randint(0, 59))
    return timezone.make_aware(datetime.combine(dzien, t), tz)


def dni_robocze(ile_dni):
    """Weekdays from `ile_dni` days ago up to yesterday, oldest first."""
    dzis = timezone.localdate()
    return [
        d
        for d in (dzis - timedelta(days=n) for n in range(ile_dni, 0, -1))
        if d.weekday() < 5
    ]


# --- login history: demo accounts only --------------------------------------
LoginEvent.objects.all().delete()
konta = {
    u.username: u
    for u in BppUser.objects.filter(
        username__in=["regis", "vesemir", "yennefer", "filippa", "jaskier"]
    )
}
# how likely each account logs in on a given weekday
czestosc = {
    "vesemir": 0.9,
    "regis": 0.6,
    "filippa": 0.35,
    "yennefer": 0.2,
    "jaskier": 0.1,
}
logowania = []
for dzien in dni_robocze(42):
    for nazwa, p in czestosc.items():
        if nazwa in konta and rnd.random() < p:
            logowania.append(
                LoginEvent(
                    login_type=LoginEvent.LOGIN,
                    username=nazwa,
                    user=konta[nazwa],
                    remote_ip=f"192.0.2.{rnd.randint(10, 200)}",  # TEST-NET-1
                    datetime=chwila_w_dniu(dzien),
                )
            )
# "datetime" is auto_now_add: bulk_create stores "now" (and overwrites the
# attribute), so remember the dates and put them back afterwards
daty = [ev.datetime for ev in logowania]
LoginEvent.objects.bulk_create(logowania)  # PostgreSQL returns the new pks
for ev, kiedy in zip(logowania, daty, strict=True):
    LoginEvent.objects.filter(pk=ev.pk).update(datetime=kiedy)

# --- menu clicks ------------------------------------------------------------
# (label as shown in the editing-module menu, URL, how often)
KLIKI = {
    "regis": [
        ("Wydawnictwa ciągłe", "/admin/bpp/wydawnictwo_ciagle/", 64),
        ("Autorzy", "/admin/bpp/autor/", 41),
        ("Wydawnictwa zwarte", "/admin/bpp/wydawnictwo_zwarte/", 33),
        ("Użytkownicy", "/admin/bpp/bppuser/", 22),
        ("Jednostki", "/admin/bpp/jednostka/", 17),
        ("Źródła", "/admin/bpp/zrodlo/", 15),
        ("Uczelnia", "/admin/bpp/uczelnia/", 11),
        ("Zgłoszenia publikacji", "/admin/zglos_publikacje/zgloszenie_publikacji/", 9),
        ("Grupy", "/admin/auth/group/", 7),
        ("Charaktery formalne", "/admin/bpp/charakter_formalny/", 5),
    ],
    "vesemir": [
        ("Wydawnictwa ciągłe", "/admin/bpp/wydawnictwo_ciagle/", 120),
        ("Autorzy", "/admin/bpp/autor/", 75),
        ("Wydawnictwa zwarte", "/admin/bpp/wydawnictwo_zwarte/", 52),
        ("Źródła", "/admin/bpp/zrodlo/", 30),
    ],
}
MenuClick.objects.filter(user__in=[regis, vesemir]).delete()
for nazwa, pozycje in KLIKI.items():
    u = konta[nazwa]
    for label, url, ile in pozycje:
        MenuClick.objects.bulk_create(
            [MenuClick(user=u, menu_label=label, menu_url=url) for _ in range(ile)]
        )
    # clicked_at is auto_now_add: spread the clicks over the last six weeks
    dni = dni_robocze(42)
    for pk in MenuClick.objects.filter(user=u).values_list("pk", flat=True):
        MenuClick.objects.filter(pk=pk).update(
            clicked_at=chwila_w_dniu(rnd.choice(dni))
        )

# --- edit history (django.contrib.admin LogEntry) ---------------------------
LogEntry.objects.filter(user__in=[regis, vesemir]).delete()
ct_ciagle = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
ct_zwarte = ContentType.objects.get_for_model(Wydawnictwo_Zwarte)
ct_autor = ContentType.objects.get_for_model(Autor)
ciagle = list(Wydawnictwo_Ciagle.objects.order_by("pk").only("pk", "tytul_oryginalny"))
zwarte = list(Wydawnictwo_Zwarte.objects.order_by("pk").only("pk", "tytul_oryginalny"))
autorzy = list(Autor.objects.order_by("pk").only("pk", "imiona", "nazwisko"))
# Monday..Friday weights: most editing early in the week, little on Friday
waga_dnia = [1.0, 0.9, 0.8, 0.75, 0.3]
wpisy = []
for dzien in dni_robocze(182):
    ile = rnd.randint(0, 6) if rnd.random() < waga_dnia[dzien.weekday()] else 0
    for _ in range(ile):
        u = vesemir if rnd.random() < 0.75 else regis
        los = rnd.random()
        if los < 0.6:
            obj, ct = rnd.choice(ciagle), ct_ciagle
        elif los < 0.85:
            obj, ct = rnd.choice(zwarte), ct_zwarte
        else:
            obj, ct = rnd.choice(autorzy), ct_autor
        wpisy.append(
            LogEntry(
                action_time=chwila_w_dniu(dzien),
                user=u,
                content_type=ct,
                object_id=str(obj.pk),
                object_repr=str(obj)[:200],
                action_flag=CHANGE if rnd.random() < 0.8 else ADDITION,
                change_message='[{"changed": {"fields": ["Strony"]}}]',
            )
        )
LogEntry.objects.bulk_create(wpisy)

# --- publication creation dates and impact factor ---------------------------
for model in (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte):
    for pk, rok in model.objects.values_list("pk", "rok"):
        start = timezone.make_aware(datetime(rok, 1, 15, 9), tz)
        koniec = min(timezone.make_aware(datetime(rok + 1, 6, 30, 15), tz), teraz)
        sek = int((koniec - start).total_seconds())
        model.objects.filter(pk=pk).update(
            utworzono=start + timedelta(seconds=rnd.randint(0, max(sek, 0)))
        )
for pk in Wydawnictwo_Ciagle.objects.values_list("pk", flat=True):
    if rnd.random() < 0.45:
        Wydawnictwo_Ciagle.objects.filter(pk=pk).update(
            impact_factor=Decimal(rnd.randint(300, 6500)) / 1000
        )

cache.clear()  # chart views are cached for 24 h

print(
    f"panel-administracyjny: {len(logowania)} logins, "
    f"{MenuClick.objects.filter(user__in=[regis, vesemir]).count()} menu clicks, "
    f"{len(wpisy)} edit-log entries"
)
