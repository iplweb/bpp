"""Demo state for the screenshots of docs/redaktor/oswiadczenia.md.

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-oswiadczenia.py

There is no PBN behind the demo, and there must never be one: the API root is
set to an ``.invalid`` host and the editor account has no PBN token, so the
"send" button stops at "you are not logged in to PBN". What this does:

- creates the editor account ``vesemir`` (is_staff + "wprowadzanie danych"),
- gives one author a second discipline for 2023 (two statements per work),
  an ORCID and statement dates,
- "unpins" the disciplines of one work (for the "Tylko odpięte" filter),
- links a few 2023/2024 works to a local copy of PBN data (PBN UID),
- adds one finished statement-sending task with a log entry per outcome.
  Messages are copied from ``pbn_wysylka_oswiadczen/tasks.py``.

Idempotent: re-running wipes and recreates what it made.
"""

import datetime
import json
from datetime import timedelta

from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from password_policies.models import PasswordHistory

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    BppUser,
    Dyscyplina_Naukowa,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
)
from pbn_api.exceptions import HttpException
from pbn_api.models import Publication
from pbn_wysylka_oswiadczen.models import PbnWysylkaLog, PbnWysylkaOswiadczenTask

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

# --- PBN pointing nowhere ---------------------------------------------------
ucz = Uczelnia.objects.get()
ucz.pbn_integracja = True  # shows the "PBN" top menu
ucz.pbn_app_name = "BPP"
ucz.pbn_app_token = "demo-token"
ucz.pbn_api_root = "https://pbn.invalid"
ucz.drukuj_oswiadczenia = True
ucz.drukuj_alternatywne_oswiadczenia = True
ucz.save()

# --- an author with two disciplines in 2023 --------------------------------
regis = Autor.objects.get(nazwisko="z Cintry", imiona="Regis")
regis.orcid = "0000-0002-1825-0097"  # the ORCID documentation example iD
regis.save()
filozofia = Dyscyplina_Naukowa.objects.get(nazwa="filozofia")
ad = Autor_Dyscyplina.objects.get(autor=regis, rok=2023)
if ad.dyscyplina_naukowa_id != filozofia.pk:
    ad.subdyscyplina_naukowa = filozofia
    ad.save()

Wydawnictwo_Ciagle_Autor.objects.filter(
    autor=regis, rekord__rok=2023, dyscyplina_naukowa__isnull=False
).update(data_oswiadczenia=datetime.date(2024, 1, 15))

# --- PBN UIDs on a few works -------------------------------------------------
Wydawnictwo_Ciagle.objects.exclude(pbn_uid=None).update(pbn_uid=None)
Publication.objects.filter(mongoId__startswith="64f0c0de0sw").delete()

prace = list(
    Wydawnictwo_Ciagle.objects.filter(
        rok__in=[2023, 2024], autorzy_set__dyscyplina_naukowa__isnull=False
    )
    .distinct()
    .order_by("pk")[:12]
)
for n, rec in enumerate(prace):
    pub = Publication.objects.create(
        mongoId=f"64f0c0de0sw{n:013x}",
        status="ACTIVE",
        title=rec.tytul_oryginalny,
        year=rec.rok,
        versions=[
            {
                "current": True,
                "object": {
                    "type": "ARTICLE",
                    "title": rec.tytul_oryginalny,
                    "year": rec.rok,
                },
            }
        ],
    )
    rec.pbn_uid = pub
    rec.save(update_fields=["pbn_uid"])

# Restore pins everywhere, then unpin all disciplines of one work
Wydawnictwo_Ciagle_Autor.objects.filter(przypieta=False).update(przypieta=True)
odpieta = prace[5]
odpieta.autorzy_set.exclude(dyscyplina_naukowa=None).update(przypieta=False)

# --- one finished sending task with a log per outcome ------------------------
PbnWysylkaOswiadczenTask.objects.all().delete()
now = timezone.now()
task = PbnWysylkaOswiadczenTask.objects.create(
    user=user,
    status="completed",
    rok_od=2022,
    rok_do=2025,
    total_publications=len(prace),
    processed_publications=len(prace),
)
ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)


def statements(rec):
    ret = []
    for wca in rec.autorzy_set.filter(przypieta=True).exclude(dyscyplina_naukowa=None):
        s = {
            "personRole": "AUTHOR",
            "disciplineUuid": f"8f0e2a52-0000-4000-8000-{wca.dyscyplina_naukowa_id:012d}",
        }
        if wca.autor.orcid:
            s["personOrcidId"] = wca.autor.orcid
        else:  # a made-up PBN person id, one per author
            s["personObjectId"] = f"5e0fa0700000{wca.autor_id:012x}"
        if wca.data_oswiadczenia:
            s["statementDate"] = str(wca.data_oswiadczenia)
        ret.append(s)
    return {
        "publicationUuid": f"5e1f0b7a-0000-4000-8000-{rec.pk:012d}",
        "statements": ret,
    }


wyniki = {"success": 0, "error": 0, "synchronized": 0}
for n, rec in enumerate(prace):
    log = PbnWysylkaLog(
        task=task, content_type=ct, object_id=rec.pk, pbn_uid=str(rec.pbn_uid_id)
    )
    if rec == odpieta:
        log.status = "synchronized"
        log.error_message = (
            "Brak autorow z przypieta dyscyplina - oswiadczenia skasowane"
        )
    elif n == 8:
        log.status = "error"
        log.error_message = (
            "Dane lokalne wymagaja aktualizacji: Nie jestem w stanie ustalić "
            "lokalnie identyfikatora UUID dla publikacji "
            f"{rec.pbn_uid}. Pobierz dane z profilu instytucji o publikacjach "
            "przez API V2 przez CLI lub wyślij tą publikację w całości do PBN. "
        )
    elif n == 10:
        log.status = "error"
        log.json_sent = statements(rec)
        body = (
            '{"code":400,"message":"Bad Request","description":"Validation '
            'failed.","details":{"statements[0].personObjectId":"Nie znaleziono '
            'osoby o podanym identyfikatorze."}}'
        )
        exc = HttpException(400, "/api/v2/institution-profile/statements", body)
        log.json_response = json.loads(body)
        log.error_message = f"HTTP 400: {str(exc)}"
    else:
        log.status = "success"
        log.json_sent = statements(rec)
        log.json_response = {}
    log.save()
    wyniki[log.status] += 1

start = now - timedelta(minutes=14)
PbnWysylkaOswiadczenTask.objects.filter(pk=task.pk).update(
    created_at=start,
    started_at=start + timedelta(seconds=3),
    completed_at=start + timedelta(minutes=2, seconds=41),
    success_count=wyniki["success"],
    error_count=wyniki["error"],
    synchronized_count=wyniki["synchronized"],
)
for i, log in enumerate(PbnWysylkaLog.objects.filter(task=task).order_by("pk")):
    PbnWysylkaLog.objects.filter(pk=log.pk).update(
        created_at=start + timedelta(seconds=10 + 13 * i)
    )

print(
    "Oswiadczenia demo ready:",
    len(prace),
    "works with PBN UID; unpinned:",
    odpieta.pk,
    "; Regis 2023:",
    ad,
)
