"""Wycofanie oświadczeń dyscyplin publikacji z profilu instytucji w PBN.

Jedno miejsce prawdy dla obu wejść: asynchronicznego (kolejka
``pbn_export_queue``, operacja ``WYCOFANIE``) i synchronicznego (wysyłka
poza kolejką). Dzięki temu stan ``SentData`` i rozumienie sukcesu są
identyczne niezależnie od tego, którędy przyszło zlecenie.
"""

from dataclasses import dataclass

from django.db import models

from pbn_api.exceptions import CannotDeleteStatementsException
from pbn_api.models import SentData


class StatusWycofania(models.TextChoices):
    WYCOFANO = "wycofano", "Wycofano oświadczenia"
    BRAK_OSWIADCZEN = "brak", "Brak oświadczeń do wycofania"
    POMINIETO = "pominieto", "Pominięto (rekord bez PBN UID)"


@dataclass
class WynikWycofania:
    status: StatusWycofania
    komunikat: str


def wycofaj_oswiadczenia(publikacja, client, uczelnia=None) -> WynikWycofania:
    """Wycofuje oświadczenia dyscyplin publikacji z profilu instytucji PBN.

    Gate: publikacja bez ``pbn_uid`` → ``POMINIETO`` (nie błąd), bez
    dotykania ``SentData`` i bez wołania klienta.

    **Obiektu publikacji w PBN NIE kasujemy.** Publikacja w PBN jest
    współdzielona między instytucjami — usuwamy wyłącznie oświadczenia
    dyscyplin NASZEJ instytucji, czyli to, co faktycznie deklarowaliśmy.

    Po sukcesie aktualizuje ``SentData`` WIERSZA TEJ UCZELNI:
    ``submitted_successfully=False`` + ``withdrawn_at``. Brak wiersza
    (``SentData.DoesNotExist``) nie jest błędem — rekord mógł dostać PBN
    UID z importu, a nie z wysyłki; nie ma wtedy czego oznaczać.

    Wyjątki PBN (``PraceSerwisowe`` / ``ResourceLocked`` / ``Http`` / …)
    PROPAGUJE — klasyfikuje je wywołujący (kolejka przez wspólne
    ``_handle_pbn_exception``, ścieżka synchroniczna własną obsługą).
    Prymityw odpowiada za semantykę „co znaczy sukces" i za stan
    ``SentData``, NIE za politykę ponawiania. Rozdzielenie jest celowe:
    wspólna klasyfikacja w jednym miejscu nie rozjedzie się między
    wejściami.

    :param publikacja: rekord BPP (soft-skasowany — to normalny przypadek)
    :param client: klient PBN uczelni (``uczelnia.pbn_client(token)``)
    :param uczelnia: właściciel wiersza ``SentData``; w multi-hosted
        obowiązkowa, bo przy ≥2 wierszach lookup bez niej rzuci
        ``MultipleObjectsReturned``
    """
    if not getattr(publikacja, "pbn_uid_id", None):
        return WynikWycofania(
            status=StatusWycofania.POMINIETO,
            komunikat=(
                "Rekord nie ma PBN UID — nic nie zostało wysłane do PBN, "
                "więc nie ma czego wycofywać."
            ),
        )

    try:
        client.delete_all_publication_statements(publikacja.pbn_uid_id)
    except CannotDeleteStatementsException as exc:
        # PBN mówi: nie ma czego usuwać. Dla NAS to stan docelowy, nie
        # błąd — oświadczeń tej publikacji w profilu instytucji już nie
        # ma. (Uwaga: pbn-client w _delete_statements_with_retry ponawia
        # na tym samym wyjątku, bo tam kasowanie poprzedza wysyłkę i brak
        # oświadczeń jest przeszkodą. Tu jest odwrotnie.)
        status = StatusWycofania.BRAK_OSWIADCZEN
        komunikat = f"PBN: brak oświadczeń do wycofania ({exc})."
    else:
        status = StatusWycofania.WYCOFANO
        komunikat = (
            f"Wycofano oświadczenia dyscyplin z profilu instytucji w PBN "
            f"(PBN UID={publikacja.pbn_uid_id})."
        )

    try:
        SentData.objects.mark_as_withdrawn(publikacja, uczelnia=uczelnia)
    except SentData.DoesNotExist:
        komunikat += " Brak wiersza SentData — nie ma czego oznaczać."

    return WynikWycofania(status=status, komunikat=komunikat)
