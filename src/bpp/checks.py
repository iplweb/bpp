"""System-checki aplikacji ``bpp`` wymagające dostępu do bazy danych.

Rejestrowane z tagiem ``Tags.database`` — Django uruchamia je tylko przy
``manage.py check --database default`` (oraz w ``migrate``), więc zwykłe
``check``/``runserver``/``collectstatic`` nie dotykają bazy.
"""

from django.core import checks
from django.db import DatabaseError

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
