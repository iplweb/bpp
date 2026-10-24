"""System checki szyfrowania sekretów integracji (EncryptedTextField).

Wszystkie są ostrzeżeniami (Warning), nie błędami — nie blokują startu,
``migrate`` ani buildu. Checki zaglądające do bazy mają tag ``database``
i działają tylko, gdy Django przekaże listę baz (``migrate``,
``check --database default``).
"""

import logging

from django.core import checks
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction

logger = logging.getLogger(__name__)

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
