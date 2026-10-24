"""System checki aplikacji ``bpp``.

- ``bpp.W001``: konta staff bez przypisanych uczelni (instalacja
  wielouczelniana).
- ``bpp.W101``–``bpp.W104``: szyfrowanie sekretów integracji
  (EncryptedTextField).
- ``bpp.W201``: logowanie Microsoft bez konkretnego katalogu (tenanta).

Wszystkie są ostrzeżeniami (Warning) — nie blokują startu, ``migrate`` ani
buildu. Checki zaglądające do bazy mają tag ``Tags.database`` i działają
tylko, gdy Django przekaże listę baz (``migrate``,
``check --database default``), więc zwykłe ``check``/``runserver``/
``collectstatic`` nie dotykają bazy.
"""

import logging

from django.core import checks
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction

logger = logging.getLogger(__name__)

W001_ID = "bpp.W001"

MAKS_LOGINOW = 10


@checks.register(checks.Tags.database)
def konta_staff_bez_uczelni_check(app_configs, databases=None, **kwargs):
    """Ostrzeż o kontach staff bez przypisanych uczelni w instalacji
    wielouczelnianej.

    Pusta relacja ``accessible_uczelnie`` oznacza dostęp do panelu
    administracyjnego wszystkich uczelni (kompatybilność wsteczna). Przy
    więcej niż jednej uczelni operator powinien o tym wiedzieć.
    """
    if not databases:
        return []

    from bpp.konta_bez_uczelni import jest_wiele_uczelni, konta_staff_bez_uczelni

    try:
        if not jest_wiele_uczelni():
            return []

        konta = (
            konta_staff_bez_uczelni()
            .order_by("username")
            .values_list("username", flat=True)
        )
        liczba = konta.count()
        if not liczba:
            return []
        loginy = list(konta[:MAKS_LOGINOW])
    except DatabaseError:
        # Tabele mogą jeszcze nie istnieć (check przed pierwszym ``migrate``)
        # — wtedy nie ma czego sprawdzać.
        return []

    lista = ", ".join(loginy)
    if liczba > len(loginy):
        lista += f" (i {liczba - len(loginy)} innych)"

    return [
        checks.Warning(
            f"W systemie jest więcej niż jedna uczelnia, a {liczba} aktywnych "
            f"kont z dostępem do panelu (is_staff, bez superusera) nie ma "
            f"przypisanych dostępnych uczelni: {lista}.",
            hint="Konta bez przypisanych uczelni mają dostęp do panelu "
            "administracyjnego WSZYSTKICH uczelni. Przypisz im uczelnie "
            "w adminie (edycja użytkownika → sekcja „Dostęp do uczelni”).",
            id=W001_ID,
        )
    ]


W_BRAK_KLUCZA = "bpp.W101"
W_ZLY_KLUCZ = "bpp.W102"
W_NIEODSZYFROWALNE = "bpp.W103"
W_JAWNE = "bpp.W104"

_PODPOWIEDZ_KLUCZ = (
    'Wygeneruj: python -c "from cryptography.fernet import Fernet; '
    'print(Fernet.generate_key().decode())" i ustaw jako env '
    "DJANGO_BPP_FIELD_ENCRYPTION_KEY (zrób kopię zapasową klucza)."
)


@checks.register(checks.Tags.security)
def klucz_szyfrowania_check(app_configs, **kwargs):
    from bpp.fields import multifernet

    try:
        mf = multifernet()
    except ImproperlyConfigured as e:
        return [checks.Warning(str(e), hint=_PODPOWIEDZ_KLUCZ, id=W_ZLY_KLUCZ)]
    if mf is None:
        return [
            checks.Warning(
                "Brak klucza DJANGO_BPP_FIELD_ENCRYPTION_KEY — sekrety "
                "integracji (tokeny PBN, hasła Clarivate/DSpace, sekret ORCID) "
                "są zapisywane w bazie bez szyfrowania.",
                hint=_PODPOWIEDZ_KLUCZ,
                id=W_BRAK_KLUCZA,
            )
        ]
    return []


@checks.register(checks.Tags.database)
def sekrety_w_bazie_check(app_configs, databases=None, **kwargs):
    if not databases or "default" not in databases:
        return []

    from bpp.fields import multifernet
    from bpp.sekrety import kolumny_szyfrowane, stan_kolumny

    try:
        jest_klucz = multifernet() is not None
    except ImproperlyConfigured:
        return []  # zgłasza to klucz_szyfrowania_check

    connection = connections["default"]
    nieodszyfrowalne = []
    jawne = []
    try:
        with transaction.atomic(using="default"):
            for tabela, kolumna in kolumny_szyfrowane():
                stan = stan_kolumny(connection, tabela, kolumna)
                if stan.nieodszyfrowalne:
                    nieodszyfrowalne.append(
                        f"{tabela}.{kolumna} ({stan.nieodszyfrowalne})"
                    )
                if stan.jawne:
                    jawne.append(f"{tabela}.{kolumna} ({stan.jawne})")
    except DatabaseError as e:
        # Baza niedostępna albo jeszcze niezmigrowana — nic do sprawdzenia.
        logger.debug("Pomijam sprawdzenie sekretów w bazie: %s", e)
        return []

    wynik = []
    if nieodszyfrowalne:
        wynik.append(
            checks.Warning(
                "W bazie są zaszyfrowane sekrety integracji, których nie da "
                "się odszyfrować aktualnym kluczem: "
                + ", ".join(nieodszyfrowalne)
                + ". Integracje będą traktować je jak puste.",
                hint="Przywróć poprzedni klucz (można podać kilka, po "
                "przecinku, w DJANGO_BPP_FIELD_ENCRYPTION_KEY) albo wpisz "
                "sekrety ponownie w module Redagowania (użytkownicy ponownie "
                "autoryzują się w PBN).",
                id=W_NIEODSZYFROWALNE,
            )
        )
    if jawne and jest_klucz:
        wynik.append(
            checks.Warning(
                "Klucz szyfrowania jest ustawiony, ale w bazie są jeszcze "
                "niezaszyfrowane sekrety integracji: " + ", ".join(jawne) + ".",
                hint="Uruchom: python src/manage.py zaszyfruj_sekrety "
                "(przy pierwszym migrate z kluczem zrobi to też migracja "
                "0496 — wtedy ostrzeżenie można zignorować).",
                id=W_JAWNE,
            )
        )
    return wynik


@checks.register(checks.Tags.security)
def microsoft_tenant_check(app_configs, **kwargs):
    """Ostrzeż, gdy logowanie Microsoft nie wskazuje konkretnego katalogu."""
    from django.conf import settings

    from bpp.auth.microsoft_conf import (
        TENANT_HINT,
        W_TENANT_ID,
        microsoft_tenant_warning,
    )

    tresc = microsoft_tenant_warning(
        getattr(settings, "MICROSOFT_AUTH_CLIENT_ID", None),
        getattr(settings, "MICROSOFT_AUTH_TENANT_ID", None),
    )
    if not tresc:
        return []
    return [checks.Warning(tresc, hint=TENANT_HINT, id=W_TENANT_ID)]
