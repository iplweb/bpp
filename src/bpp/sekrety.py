"""Operacje na surowych wartościach kolumn ``EncryptedTextField``.

Wszystko tutaj działa na poziomie SQL (kursor), a NIE przez ORM: odczyt
przez model zamienia nieodszyfrowalny szyfrogram na pustą wartość, więc
„wczytaj i zapisz” przez ORM mogłoby nadpisać dane. Z tych funkcji
korzysta migracja szyfrująca, komenda ``zaszyfruj_sekrety`` oraz
system check.
"""

import logging
from dataclasses import dataclass

from cryptography.fernet import InvalidToken

from bpp.fields import (
    PREFIKS_SZYFROGRAMU,
    EncryptedTextField,
    multifernet,
    wyglada_na_szyfrogram,
)

logger = logging.getLogger(__name__)


@dataclass
class StanKolumny:
    jawne: int = 0
    zaszyfrowane: int = 0
    nieodszyfrowalne: int = 0


def kolumny_szyfrowane():
    """Lista ``(tabela, kolumna)`` dla wszystkich pól EncryptedTextField."""
    from django.apps import apps

    wynik = []
    for model in apps.get_models():
        for field in model._meta.concrete_fields:
            if isinstance(field, EncryptedTextField):
                wynik.append((model._meta.db_table, field.column))
    return sorted(wynik)


def _wiersze(connection, tabela, kolumna):
    qn = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT id, {qn(kolumna)} FROM {qn(tabela)} "
            f"WHERE {qn(kolumna)} IS NOT NULL AND {qn(kolumna)} <> ''"
        )
        return cursor.fetchall()


def _zapisz(connection, tabela, kolumna, pk, wartosc):
    qn = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {qn(tabela)} SET {qn(kolumna)} = %s WHERE id = %s",
            [wartosc, pk],
        )


def stan_kolumny(connection, tabela, kolumna) -> StanKolumny:
    mf = multifernet()
    stan = StanKolumny()
    for _pk, wartosc in _wiersze(connection, tabela, kolumna):
        if not wyglada_na_szyfrogram(wartosc):
            stan.jawne += 1
            continue
        try:
            if mf is None:
                raise InvalidToken
            mf.decrypt(wartosc.encode())
            stan.zaszyfrowane += 1
        except InvalidToken:
            stan.nieodszyfrowalne += 1
    return stan


def zaszyfruj_jawne(connection, tabela, kolumna, dry_run=False) -> int:
    """Szyfruje wartości jawne. Zwraca liczbę zaszyfrowanych wierszy.

    Wymaga klucza (wywołujący sprawdza ``multifernet() is not None``).
    Wartości wyglądające na szyfrogram są pomijane (idempotencja).
    """
    mf = multifernet()
    ile = 0
    for pk, wartosc in _wiersze(connection, tabela, kolumna):
        if wyglada_na_szyfrogram(wartosc):
            continue
        if not dry_run:
            _zapisz(
                connection,
                tabela,
                kolumna,
                pk,
                mf.encrypt(wartosc.encode()).decode(),
            )
        ile += 1
    return ile


def przeszyfruj(connection, tabela, kolumna, dry_run=False) -> tuple[int, int]:
    """Przepisuje szyfrogramy na pierwszy (główny) klucz MultiFernet.

    Zwraca ``(przeszyfrowane, nieodszyfrowalne)``; nieodszyfrowalnych
    wartości nie rusza.
    """
    mf = multifernet()
    ile = 0
    nieodszyfrowalne = 0
    for pk, wartosc in _wiersze(connection, tabela, kolumna):
        if not wyglada_na_szyfrogram(wartosc):
            continue
        try:
            nowa = mf.rotate(wartosc.encode()).decode()
        except InvalidToken:
            nieodszyfrowalne += 1
            continue
        if not dry_run:
            _zapisz(connection, tabela, kolumna, pk, nowa)
        ile += 1
    return ile, nieodszyfrowalne


def odszyfruj_wszystkie(connection, tabela, kolumna) -> tuple[int, int]:
    """Zamienia szyfrogramy z powrotem na wartości jawne (cofnięcie migracji).

    Szyfrogramy, których nie da się odczytać, są czyszczone (pusta wartość) —
    i tak są bezużyteczne bez klucza, a nie zmieściłyby się w kolumnie
    ``varchar`` po cofnięciu zmiany typu. Zwraca ``(odszyfrowane,
    wyczyszczone)``.
    """
    mf = multifernet()
    ile = 0
    wyczyszczone = 0
    for pk, wartosc in _wiersze(connection, tabela, kolumna):
        if not wartosc.startswith(PREFIKS_SZYFROGRAMU):
            continue
        try:
            if mf is None:
                raise InvalidToken
            jawna = mf.decrypt(wartosc.encode()).decode()
            ile += 1
        except InvalidToken:
            logger.warning(
                "Nie można odszyfrować %s.%s (id=%s) — wartość wyczyszczona.",
                tabela,
                kolumna,
                pk,
            )
            jawna = ""
            wyczyszczone += 1
        _zapisz(connection, tabela, kolumna, pk, jawna)
    return ile, wyczyszczone
