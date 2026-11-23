"""Publiczny kontrakt kolejkowania operacji PBN.

Funkcje MODUŁOWE (nie metody managera) — tak woła je faza 06 z receiverów
sygnałów: ``post_soft_delete`` → ``zakolejkuj_wycofanie``, ``post_restore``
→ ``zakolejkuj_wysylke``. Jedno miejsce prawdy: wpisy powstają wyłącznie
przez ``sprobuj_utowrzyc_wpis``, żeby nie omijać zabezpieczenia TOCTOU,
FK ``uczelnia`` ani pola ``operacja``.
"""

from django.db import transaction

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
    from pbn_export_queue.bezpiecznik import automaty_wstrzymane

    if automaty_wstrzymane():
        # Lokalna kopia produkcji: kosz/przywrócenie nie zleca niczego w PBN
        # (inaczej przeniesienie pracy do kosza na maszynie dewelopera
        # wycofałoby oświadczenia w prawdziwym PBN).
        return None

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

    # Po COMMIT: worker nie może dostać wpisu, którego jeszcze nie widzi
    # (albo który zniknie z wycofaną transakcją kosza/przywrócenia).
    pk = wpis.pk
    transaction.on_commit(lambda: tasks.task_sprobuj_wyslac_do_pbn.delay(pk))
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


# --- kosz a kolejka PBN ---------------------------------------------------
#
# JEDNA reguła (decyzja właściciela, listopad 2026): rekord z JAKIMKOLWIEK
# niezakończonym wpisem kolejki (czeka, podjęty, czeka na ponowienie —
# wysyłka czy wycofanie) NIE może trafić do kosza ani z niego wrócić.
# Wiszącą wysyłkę operator może usunąć z kolejki ręcznie (wpisy wysyłki są
# usuwalne; wpisy wycofania — nie).
#
# Serializacja: zakolejkowanie (każda ścieżka — przez
# ``sprobuj_utowrzyc_wpis`` / ``prepare_for_resend``) i kosz/przywrócenie
# biorą TĘ SAMĄ blokadę transakcyjną rekordu
# (``PBN_Export_Queue.objects.zablokuj_rekord``) i sprawdzają stan pod nią.


KOMUNIKAT_REKORD_W_KOLEJCE = (
    "Rekord jest w kolejce PBN — poczekaj, aż kolejka zakończy jego przetwarzanie."
)


class RekordWKolejcePBN(Exception):
    """Rekord ma niezakończony wpis kolejki PBN — kosz/przywrócenie
    niemożliwe, dopóki kolejka go nie przetworzy."""

    def __init__(self, wpis=None):
        self.wpis = wpis
        super().__init__(KOMUNIKAT_REKORD_W_KOLEJCE)


def aktywny_wpis(instance):
    """Niezakończony wpis kolejki dla rekordu albo ``None``."""
    return PBN_Export_Queue.objects.filter_rekord_do_wysylki(instance).first()


def grupa_blokady_kolejki(instance):
    """Niezakończone wpisy kolejki rekordu jako ``GrupaBlokady`` (do strony
    „Nie można przenieść do kosza") albo ``None``."""
    from django.utils.timezone import localtime

    from bpp.models.soft_delete import GrupaBlokady, PozycjaBlokady

    wpisy = list(PBN_Export_Queue.objects.filter_rekord_do_wysylki(instance))
    if not wpisy:
        return None
    return GrupaBlokady(
        etykieta="Rekordy w kolejce PBN",
        liczba=len(wpisy),
        pozycje=[
            PozycjaBlokady(
                obj=wpis,
                wiersz=wpis,
                opis=(
                    f"{wpis.get_operacja_display()} — zlecono "
                    f"{localtime(wpis.zamowiono):%Y-%m-%d %H:%M}"
                    + (", w trakcie wysyłki" if wpis.wysylke_podjeto else "")
                ),
            )
            for wpis in wpisy
        ],
    )


def sprawdz_kolejke_przed_koszem(instance):
    """Kosz/przywrócenie: blokada rekordu, potem reguła i świeży ``pbn_uid``.

    Wołać w transakcji kosza/przywrócenia. Pod blokadą żadna ścieżka nie
    zakolejkuje rekordu, a ``pbn_uid`` czytamy z bazy — o wycofaniu (kosz)
    i wysyłce (przywrócenie) decyduje receiver na podstawie tej wartości,
    nie nieaktualnej instancji (np. sprzed pierwszej udanej wysyłki).
    """
    PBN_Export_Queue.objects.zablokuj_rekord(instance)
    wpis = aktywny_wpis(instance)
    if wpis is not None:
        raise RekordWKolejcePBN(wpis)
    if hasattr(instance, "pbn_uid_id"):
        instance.pbn_uid_id = (
            type(instance)
            ._base_manager.filter(pk=instance.pk)
            .values_list("pbn_uid_id", flat=True)
            .get()
        )
