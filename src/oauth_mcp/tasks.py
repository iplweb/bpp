"""Zadania cykliczne serwera MCP — retencja rejestracji DCR (#656).

Otwarta rejestracja klientów (RFC 7591, `POST /o/register/`) tworzy wiersz
`oauth2_provider_application` przy KAŻDYM udanym żądaniu — anonimowo, bez
uwierzytelnienia. Tak ma działać DCR i tak wymaga tego MCP, więc to nie jest
błąd. Brakowało natomiast drugiej połowy cyklu życia: klient, który
zarejestrował się i nigdy nie dokończył flow (zamknięta karta, narzędzie
testowe, skaner, przerwany `bpp-mcp login`), zostawiał `Application` na
zawsze. Ten moduł domyka pętlę.
"""

from datetime import timedelta

from celery.utils.log import get_task_logger
from django.db.models import Q
from django.utils import timezone

from django_bpp.celery_tasks import app

logger = get_task_logger(__name__)

# Znacznik rejestracji utworzonej przez DCR, doklejany do `client_id` w
# `views_dcr.py`. Nie potrzebuje migracji (pole istnieje) i jest
# ROZSTRZYGALNY, a nie probabilistyczny: `ClientIdGenerator` z DOT losuje z
# `UNICODE_ASCII_CHARACTER_SET`, czyli samych alfanumeryków — bez myślnika.
# Domyślnie wygenerowany `client_id` NIE MOŻE więc zacząć się od `dcr-`.
# `client_id` jest generowany po stronie serwera, więc znacznika nie da się
# podstawić z zewnątrz (inaczej niż `client_name` sterowanej przez klienta).
DCR_CLIENT_ID_PREFIX = "dcr-"

# Po ilu dniach nietknięta rejestracja jest uznana za porzuconą. 7 dni to
# świadomy sufit: `Grant` żyje minuty, a `REFRESH_TOKEN_EXPIRE_SECONDS`
# (settings/base.py) to dokładnie 7 dni — krótszy próg mógłby trafić w klienta,
# który wciąż ma szansę odświeżyć token.
DCR_RETENCJA_DNI = 7

# Kasujemy partiami: `.delete()` po całym queryssecie ściąga do pamięci PK
# wszystkich pasujących wierszy (Django rozwija kaskady po stronie ORM-a).
# Sufit dla jednego IP to 20 rejestracji/h, a rozproszony botnet obchodzi
# limit per-IP — pierwszy przebieg na zaniedbanej instancji może więc zastać
# spory backlog. Partiami: stałe zużycie pamięci, krótkie transakcje,
# przerwanie w połowie zostawia bazę spójną.
DCR_DELETE_BATCH = 1000


def _osierocone_qs(*, dni, uwzglednij_nieoznaczone):
    """Queryset rejestracji, które NIGDY nie doszły do skutku.

    Kryteria bezpieczeństwa (kolejność ma znaczenie dla czytania SQL-a):

    * brak `AccessToken`, `RefreshToken`, `Grant` i `IDToken` — cokolwiek z
      tego istnieje, ktoś realnie zaczął albo dokończył flow. To jest jedyny
      warunek chroniący przed najgroźniejszym regresem: `Application` kaskaduje
      na tokeny, więc skasowanie używanej aplikacji wylogowałoby użytkownika;
    * `created` starsze niż próg retencji.

    Świadoma konserwatywność: wygasły, ale wciąż obecny w bazie token BLOKUJE
    kasowanie. DOT usuwa wygasłe tokeny osobną komendą (`cleartokens`), więc
    aplikacja staje się kwalifikowalna dopiero po jej przebiegu. Te dwa
    mechanizmy się komponują, a błąd w którymkolwiek daje pozostawiony wiersz
    (odwracalne), nie wylogowanie (nieodwracalne).
    """
    from oauth2_provider.models import get_application_model

    Application = get_application_model()

    jest_dcr = Q(client_id__startswith=DCR_CLIENT_ID_PREFIX)
    if uwzglednij_nieoznaczone:
        # Rejestracje sprzed wprowadzenia prefiksu nie mają jak się przyznać —
        # zostaje heurystyka po kształcie (public + authorization-code + brak
        # właściciela, bo DCR nigdy nie ustawia `user`). Krucha, dlatego
        # wyłączona domyślnie i dostępna wyłącznie pod jawną flagą.
        jest_dcr |= Q(
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            user__isnull=True,
        )

    return Application.objects.filter(
        jest_dcr,
        created__lt=timezone.now() - timedelta(days=dni),
        accesstoken__isnull=True,
        refreshtoken__isnull=True,
        grant__isnull=True,
        idtoken__isnull=True,
    )


def usun_osierocone_aplikacje_dcr(
    dni=DCR_RETENCJA_DNI, dry_run=False, uwzglednij_nieoznaczone=False
):
    """Kasuje osierocone rejestracje DCR. Zwraca liczbę `Application`.

    `dry_run=True` liczy to samo, czego dotknęłoby realne uruchomienie, ale
    niczego nie usuwa — do audytu wolumenu przed pierwszym przebiegiem.
    """
    from oauth2_provider.models import get_application_model

    Application = get_application_model()

    if dry_run:
        n = _osierocone_qs(
            dni=dni, uwzglednij_nieoznaczone=uwzglednij_nieoznaczone
        ).count()
        logger.info(
            "oauth_mcp: [dry-run] do skasowania %d osieroconych rejestracji "
            "DCR starszych niż %d dni",
            n,
            dni,
        )
        return n

    skasowano = 0
    while True:
        # Partia PK — LIMIT po stronie bazy, bez ściągania całości. Queryset
        # przeliczamy w każdej iteracji, bo poprzednia partia właśnie zniknęła.
        batch = list(
            _osierocone_qs(
                dni=dni, uwzglednij_nieoznaczone=uwzglednij_nieoznaczone
            ).values_list("pk", flat=True)[:DCR_DELETE_BATCH]
        )
        if not batch:
            break
        Application.objects.filter(pk__in=batch).delete()
        # Liczymy Application, nie sumę z `.delete()` — ta obejmuje kaskady.
        skasowano += len(batch)
        # Partia krótsza niż limit = to była ostatnia porcja.
        if len(batch) < DCR_DELETE_BATCH:
            break

    logger.info(
        "oauth_mcp: skasowano %d osieroconych rejestracji DCR starszych niż %d dni",
        skasowano,
        dni,
    )
    return skasowano


@app.task(ignore_result=True)
def usun_osierocone_aplikacje_oauth():
    """Wrapper Celery dla retencji rejestracji DCR (CELERYBEAT_SCHEDULE).

    Celowo bez parametrów: beat woła wariant domyślny, czyli wyłącznie
    rejestracje oznaczone prefiksem `dcr-`. Sprzątanie wierszy legacy
    (`--uwzglednij-nieoznaczone`) zostaje decyzją człowieka przy komendzie
    zarządzającej — heurystyka nie ma prawa działać bez nadzoru.
    """
    return usun_osierocone_aplikacje_dcr()
