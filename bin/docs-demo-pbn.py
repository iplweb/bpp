"""PBN demo state for the screenshots of docs/redaktor/pbn-wysylka-i-synchronizacja.md.

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md), after the demo
accounts exist:

    uv run python src/manage.py shell < bin/docs-demo-pbn.py

There is no PBN behind the demo, and there must never be one: the API root is
set to an ``.invalid`` host, which never resolves. What this does:

- creates the editor account ``vesemir`` (is_staff + "wprowadzanie danych"),
- turns on the PBN integration (menu "PBN", "Zapisz i wyślij do PBN" buttons),
- maps "Artykuł w czasopismie" to the PBN type "article" (otherwise every
  article would be "excluded" from export),
- fills a small local copy of PBN data (a few publications, one deleted),
- seeds the export queue with one entry per state. Every error goes through
  the real handler (``_handle_pbn_exception``), so the stored messages have
  exactly the shape a real failed send produces.

Idempotent: re-running wipes and recreates the queue and the local PBN copy.
"""

from datetime import timedelta

from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.utils import timezone
from password_policies.models import PasswordHistory

from bpp import const
from bpp.demo_data.zrzuty import PBN_PRACA_Z_BLEDEM, prace_pbn
from bpp.models import (
    BppUser,
    Charakter_Formalny,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from pbn_api.exceptions import (
    CharakterFormalnyNieobslugiwanyError,
    DOIorWWWMissing,
    HttpException,
    NeedsPBNAuthorisationException,
    PBNValidationError,
    ResourceLockedException,
    StatementsMissing,
)
from pbn_api.models import Publication, SentData
from pbn_export_queue.models import PBN_Export_Queue

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

# --- PBN integration on, but pointing nowhere ------------------------------
ucz = Uczelnia.objects.get()
ucz.pbn_integracja = True
ucz.pbn_aktualizuj_na_biezaco = True
ucz.pbn_app_name = "BPP"
ucz.pbn_app_token = "demo-token"
ucz.pbn_api_root = "https://pbn.invalid"
ucz.save()
if ucz.obca_jednostka_id is None:
    call_command("create_obca_jednostka")

Charakter_Formalny.objects.filter(skrot="AC").update(
    rodzaj_pbn=const.RODZAJ_PBN_ARTYKUL
)

# --- reset ------------------------------------------------------------------
PBN_Export_Queue.objects.all().delete()
SentData.objects.all().delete()
# Tylko własne rekordy PBN (mongoId 64f0c0de + 16 cyfr szesnastkowych) — nie
# te z bin/docs-demo-oswiadczenia.py (64f0c0de0sw…) ani z innych skryptów,
# które mogły już działać na tej bazie.
WLASNE = Publication.objects.filter(mongoId__regex=r"^64f0c0de[0-9a-f]{16}$")
Wydawnictwo_Ciagle.objects.filter(pbn_uid__in=WLASNE).update(pbn_uid=None)
Wydawnictwo_Zwarte.objects.filter(pbn_uid__in=WLASNE).update(pbn_uid=None)
WLASNE.delete()

now = timezone.now()
# Prace kolejki: bpp.demo_data.zrzuty.prace_pbn — ta sama reguła, z której
# scenariusz bierze pracę z błędem wysyłki (PBN_PRACA_Z_BLEDEM).
ciagle, zwarte = prace_pbn()


def pbn_publication(n, rec=None, title=None, year=2024, status="ACTIVE"):
    title = title or rec.tytul_oryginalny
    year = rec.rok if rec else year
    return Publication.objects.create(
        mongoId=f"64f0c0de{n:016x}",
        status=status,
        title=title,
        year=year,
        doi=(rec.doi or "") if rec else "",
        versions=[
            {
                "current": True,
                "object": {"type": "ARTICLE", "title": title, "year": year},
            }
        ],
    )


def wpis(rec, minut_temu, proby=1):
    q = PBN_Export_Queue.objects.create(
        rekord_do_wysylki=rec, zamowil=user, uczelnia=ucz
    )
    t = now - timedelta(minutes=minut_temu)
    PBN_Export_Queue.objects.filter(pk=q.pk).update(zamowiono=t)
    q.refresh_from_db()
    q.wysylke_podjeto = t + timedelta(seconds=20)
    q.ilosc_prob = proby
    q.save()
    return q


def sent(rec, exception="", pub=None):
    return SentData.objects.create(
        content_type=ContentType.objects.get_for_model(rec),
        object_id=rec.pk,
        uczelnia=ucz,
        data_sent={
            "type": "ARTICLE",
            "title": rec.tytul_oryginalny,
            "year": rec.rok,
            "doi": rec.doi or None,
        },
        uploaded_okay=not exception,
        submitted_successfully=not exception,
        submitted_at=now,
        exception=exception,
        api_url="https://pbn.invalid/api/v1/publications",
        pbn_uid=pub,
    )


def blad(q, exc):
    try:
        raise exc
    except Exception as e:
        return q._handle_pbn_exception(e)


def zakoncz_po(q, sekund=6):
    """Finished a few seconds after it started, not "now" (looks real)."""
    q.refresh_from_db()
    if q.wysylke_zakonczono:
        PBN_Export_Queue.objects.filter(pk=q.pk).update(
            wysylke_zakonczono=q.wysylke_podjeto + timedelta(seconds=sekund)
        )


# 1-3: sent fine, now linked to their PBN copy
for i, rec in enumerate(ciagle[:3]):
    pub = pbn_publication(i + 1, rec)
    rec.pbn_uid = pub
    rec.save(update_fields=["pbn_uid"])
    q = wpis(rec, 300 - i * 20)
    q._handle_successful_send(sent(rec, pub=pub), [])
    zakoncz_po(q)

# Local PBN copy: two works PBN has and BPP doesn't, one deleted in PBN
pbn_publication(101, title="Bestiariusz Temerii: przegląd krytyczny", year=2023)
pbn_publication(102, title="Wiedźmińskie znaki w praktyce terenowej", year=2024)
rec = ciagle[12]
rec.pbn_uid = pbn_publication(103, rec, status="DELETED")
rec.save(update_fields=["pbn_uid"])

# 4: PBN validation (400, details) -> merytoryczny
rec = ciagle[PBN_PRACA_Z_BLEDEM]
q = wpis(rec, 95)
body = (
    '{"code":400,"message":"Bad Request","description":"Validation failed.",'
    '"details":{"openAccess.releaseDate":'
    '"Data udostępnienia w otwartym dostępie jest wymagana!"}}'
)
exc = PBNValidationError(400, "/api/v1/publications", body)
sent(rec, exception=f"pbn_api.exceptions.PBNValidationError: {exc}")
blad(q, exc)
zakoncz_po(q)

# 5: PBN validation, list format (duplicate ISBN) -> merytoryczny
q = wpis(zwarte[0], 80)
blad(
    q,
    PBNValidationError(
        400,
        "/api/v1/publications",
        '[{"requestPosition":0,"code":"NOT_UNIQUE_PUBLICATION_ISBN_ISMN",'
        '"description":"Publikacja o identycznym ISBN już istnieje!"}]',
    ),
)
zakoncz_po(q)

# 6: no DOI / WWW -> merytoryczny
q = wpis(ciagle[4], 70)
blad(q, DOIorWWWMissing("Musi być DOI lub adres WWW"))
zakoncz_po(q, 2)

# 7: no statements -> merytoryczny
q = wpis(ciagle[5], 60)
blad(
    q,
    StatementsMissing(
        "Nie wyślę rekordu artykułu lub rozdziału bez zadeklarowanych "
        "oświadczeń autorów (dyscyplin). "
    ),
)
zakoncz_po(q, 2)

# 8: PBN server error -> techniczny
q = wpis(ciagle[6], 50)
blad(
    q,
    HttpException(
        500,
        "/api/v1/publications",
        '{"code":500,"message":"Internal Server Error",'
        '"description":"Unexpected error"}',
    ),
)
zakoncz_po(q)

# 9: waiting for the user to authorise in PBN
q = wpis(ciagle[7], 40)
blad(
    q,
    NeedsPBNAuthorisationException(
        403,
        "/api/v1/publications",
        '{"code":403,"message":"Forbidden","description":"W celu poprawnej '
        'autentykacji należy podać poprawny token użytkownika aplikacji."}',
    ),
)

# 10: locked in PBN -> retried in a few minutes (still pending)
q = wpis(ciagle[8], 12, proby=2)
blad(q, ResourceLockedException(423, "/api/v1/publications", "Locked"))

# 11: excluded by design (document type not sent to PBN)
q = wpis(ciagle[9], 30)
blad(q, CharakterFormalnyNieobslugiwanyError())
zakoncz_po(q, 1)

# 12-13: just ordered, not attempted yet
for i, rec in enumerate(ciagle[10:12]):
    q = PBN_Export_Queue.objects.create(
        rekord_do_wysylki=rec, zamowil=user, uczelnia=ucz
    )
    PBN_Export_Queue.objects.filter(pk=q.pk).update(
        zamowiono=now - timedelta(minutes=3 + i)
    )

print("PBN demo ready:", PBN_Export_Queue.objects.count(), "queue entries")
