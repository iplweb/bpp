"""Publiczny kontrakt kolejkowania operacji PBN.

Funkcje MODUŁOWE (nie metody managera) — tak woła je faza 06 z receiverów
sygnałów: ``post_soft_delete`` → ``zakolejkuj_wycofanie``, ``post_restore``
→ ``zakolejkuj_wysylke``. Jedno miejsce prawdy: wpisy powstają wyłącznie
przez ``sprobuj_utowrzyc_wpis``, żeby nie omijać zabezpieczenia TOCTOU,
FK ``uczelnia`` ani pola ``operacja``.
"""

from pbn_export_queue.models import PBN_Export_Queue

#: Login konta używanego jako ``zamowil`` przy operacjach systemowych.
NAZWA_KONTA_TECHNICZNEGO = "bpp-system"


def pobierz_konto_techniczne():
    """Konto ``zamowil`` dla operacji bez zalogowanego użytkownika.

    ``PBN_Export_Queue.zamowil`` jest NOT NULL, a soft-delete zlecony
    sygnałem, celery albo scalaniem duplikatów nie ma requestu. Świadomie
    NIE robimy ``zamowil`` nullable (spec §4.2) — psułoby to założenia
    kolejki i raportów, w których „kto zlecił" jest kolumną.

    Konto jest nieaktywne i bez hasła: ma istnieć jako podmiot audytu,
    nie jako sposób logowania.

    ⚠️ Konto nie ma własnego ``pbn_token``, więc samo z siebie nie wyśle
    nic do PBN — ``_pozyskaj_klienta_pbn`` skończy się wtedy
    ``WillNotExportError`` i wpis dostanie ``FINISHED_ERROR`` z błędem
    merytorycznym. To celowo GŁOŚNA porażka, nie ciche pominięcie.
    Obejście produkcyjne bez zmiany kodu: administrator ustawia temu kontu
    ``przedstawiaj_w_pbn_jako`` na konto z ważnym tokenem PBN
    (``get_pbn_user()`` samo podmieni użytkownika).
    """
    from django.contrib.auth import get_user_model

    user, utworzono = get_user_model().objects.get_or_create(
        username=NAZWA_KONTA_TECHNICZNEGO,
        defaults={
            "first_name": "Konto",
            "last_name": "systemowe BPP",
            "is_active": False,
            "is_staff": False,
            "is_superuser": False,
        },
    )
    if utworzono:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def _zakolejkuj(instance, operacja, user=None, uczelnia=None):
    from pbn_api.exceptions import AlreadyEnqueuedError

    # `tasks` importuje `models`, więc import na poziomie modułu zrobiłby
    # cykl — stąd import lokalny.
    from pbn_export_queue import tasks

    try:
        wpis = PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(
            user or pobierz_konto_techniczne(),
            instance,
            uczelnia=uczelnia,
            operacja=operacja,
        )
    except AlreadyEnqueuedError:
        # Rekord czeka już w kolejce — idempotencja, nie błąd.
        return None

    tasks.task_sprobuj_wyslac_do_pbn.delay(wpis.pk)
    return wpis


def zakolejkuj_wysylke(instance, user=None, uczelnia=None):
    """Tworzy wpis WYSYLKA i uruchamia wysyłkę w tle.

    Wołane m.in. przy przywróceniu publikacji z kosza (faza 06).

    **BEZ gate'u na ``pbn_uid``** — rekord bez PBN UID też ma prawo
    pojechać do PBN, bo wysyłka dopiero go nadaje. (Kontrakt planu fazy 06
    opisywał „None gdy brak pbn_uid" dla obu funkcji; to świadome odejście
    — nie „naprawiaj" go pod tamten opis, bo zablokowałoby wysyłkę rekordu,
    który nigdy w PBN nie był.)

    Idempotentne: gdy rekord już czeka w kolejce → ``None``.
    ``user=None`` → konto techniczne (``zamowil`` jest NOT NULL).
    """
    return _zakolejkuj(
        instance,
        PBN_Export_Queue.Operacja.WYSYLKA,
        user=user,
        uczelnia=uczelnia,
    )


def zakolejkuj_wycofanie(instance, user=None, uczelnia=None):
    """Tworzy wpis WYCOFANIE i uruchamia wycofanie oświadczeń w tle.

    Gate: tylko gdy rekord ma PBN UID — bez niego nic do PBN nie poszło,
    więc nie ma czego wycofywać (``None``, no-op).

    Idempotentne: gdy rekord już czeka w kolejce → ``None``.
    ``user=None`` → konto techniczne. NIGDY nie przekazujemy ``None`` do
    ``zamowil``: naruszenie NOT NULL udawałoby wtedy „już w kolejce"
    i wycofanie zniknęłoby po cichu.
    """
    if not getattr(instance, "pbn_uid_id", None):
        return None

    return _zakolejkuj(
        instance,
        PBN_Export_Queue.Operacja.WYCOFANIE,
        user=user,
        uczelnia=uczelnia,
    )
