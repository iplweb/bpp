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


def _zakolejkuj(instance, operacja, user=None, uczelnia=None, **dodatkowe):
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
            **dodatkowe,
        )
    except AlreadyEnqueuedError:
        # Rekord czeka już w kolejce — idempotencja, nie błąd.
        return None

    tasks.task_sprobuj_wyslac_do_pbn.delay(wpis.pk)
    return wpis


def zakolejkuj_wysylke(instance, user=None, uczelnia=None, po_przywroceniu=False):
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
        po_przywroceniu=po_przywroceniu,
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
# Proste reguły (decyzja właściciela, listopad 2026):
#
# - „W TRAKCIE" = worker trzyma sesyjną blokadę doradczą rekordu
#   (``klucz_blokady_rekordu``) przez całą próbę wysyłki/wycofania. Kosz
#   i przywrócenie biorą ``pg_try_advisory_xact_lock`` na tym samym kluczu —
#   zajęty → „trwa wysyłka/wycofywanie w PBN, spróbuj za chwilę".
# - KOSZ: aktywny wpis rekordu blokuje kosz, dopóki kolejka z nim nie
#   skończy. Wyjątek: czekającą WYSYŁKĘ operator może jawnie ANULOWAĆ
#   (``anuluj_wysylke_pbn=True``) — wtedy rekord idzie do kosza, a receiver
#   zleca wycofanie. Wysyłka zlecona przy PRZYWRÓCENIU blokuje do końca.
# - PRZYWRÓCENIE: aktywne wycofanie blokuje przywrócenie do jego końca;
#   potem receiver zleca wysyłkę — tylko gdy rekord ma PBN UID.
# - WORKER tuż przed wysyłką (pod blokadą) czyta stan rekordu od nowa:
#   wysyłka rekordu z kosza / wycofanie rekordu żywego kończą się bez
#   rozmowy z PBN (``PBN_Export_Queue._stan_rekordu_wyklucza``).


class RekordWKolejcePBN(Exception):
    """Rekordu nie można teraz przenieść do kosza / przywrócić z powodu
    kolejki PBN. ``powod``: ``oczekuje`` (czekająca wysyłka — można ją
    anulować), ``w_trakcie`` (worker właśnie wysyła/wycofuje),
    ``po_przywroceniu`` (wysyłka po przywróceniu z kosza — trzeba poczekać),
    ``wycofanie`` (czeka wycofanie z PBN — trzeba poczekać).
    """

    def __init__(self, wpis, powod, rekord=None):
        self.wpis = wpis
        self.powod = powod
        rekord = rekord if rekord is not None else wpis.rekord_do_wysylki
        komunikaty = {
            "oczekuje": (
                f"Rekord „{rekord}” jest w kolejce wysyłki do PBN — trzeba go "
                f"z niej wycofać, zanim trafi do kosza."
            ),
            "w_trakcie": (
                f"Trwa wysyłka/wycofywanie rekordu „{rekord}” w PBN — spróbuj "
                f"za chwilę."
            ),
            "po_przywroceniu": (
                f"Rekord „{rekord}” czeka na ponowną wysyłkę do PBN po "
                f"przywróceniu z kosza — można go usunąć dopiero, gdy ta "
                f"wysyłka się zakończy."
            ),
            "wycofanie": (
                f"Rekord „{rekord}” jest wycofywany z PBN — operacja będzie "
                f"możliwa po zakończeniu wycofania (kolejka eksportu do PBN)."
            ),
        }
        super().__init__(komunikaty[powod])

    @property
    def w_toku(self):
        return self.powod == "w_trakcie"


def _klucz(instance):
    from django.contrib.contenttypes.models import ContentType

    from pbn_export_queue.models import klucz_blokady_rekordu

    ct = ContentType.objects.get_for_model(instance)
    return klucz_blokady_rekordu(ct.pk, instance.pk)


def rekord_w_trakcie_pbn(instance):
    """Czy worker właśnie wysyła/wycofuje ten rekord (bez efektów ubocznych
    — sprawdza ``pg_locks``)."""
    from django.db import connection

    klucz = _klucz(instance)
    with connection.cursor() as cur:
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype = 'advisory' "
            "AND objsubid = 1 AND granted "
            "AND ((classid::bigint << 32) | objid::bigint) = %s)",
            [klucz],
        )
        return cur.fetchone()[0]


def _zablokuj_rekord_pbn(instance, wpis):
    """``pg_try_advisory_xact_lock`` na kluczu rekordu — zajęty znaczy, że
    worker właśnie go wysyła/wycofuje."""
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_xact_lock(%s)", [_klucz(instance)])
        if not cur.fetchone()[0]:
            raise RekordWKolejcePBN(wpis, "w_trakcie", rekord=instance)


def _aktywny_wpis(instance, zablokuj=False):
    qs = PBN_Export_Queue.objects.filter_rekord_do_wysylki(instance)
    if zablokuj:
        qs = qs.select_for_update()
    return qs.first()


def aktywny_wpis(instance):
    """Aktywny (niezakończony) wpis kolejki dla rekordu albo ``None``."""
    return _aktywny_wpis(instance)


def stan_kolejki_przed_koszem(instance):
    """Bez efektów ubocznych (strona potwierdzenia): ``(wpis, powod)`` —
    ``powod`` jak w ``RekordWKolejcePBN`` albo ``None``."""
    wpis = _aktywny_wpis(instance)
    if rekord_w_trakcie_pbn(instance):
        return wpis, "w_trakcie"
    if wpis is None:
        return None, None
    if wpis.operacja == PBN_Export_Queue.Operacja.WYCOFANIE:
        return wpis, "wycofanie"
    if wpis.po_przywroceniu:
        return wpis, "po_przywroceniu"
    return wpis, "oczekuje"


def przygotuj_kolejke_do_kosza(instance, anuluj_wysylke_pbn=False, user=None):
    """Przed przeniesieniem do kosza (wołać w transakcji zapisu kosza)."""
    wpis = _aktywny_wpis(instance, zablokuj=True)
    _zablokuj_rekord_pbn(instance, wpis)
    if wpis is None:
        return
    if wpis.operacja == PBN_Export_Queue.Operacja.WYCOFANIE:
        raise RekordWKolejcePBN(wpis, "wycofanie")
    if wpis.po_przywroceniu:
        raise RekordWKolejcePBN(wpis, "po_przywroceniu")
    if not anuluj_wysylke_pbn:
        raise RekordWKolejcePBN(wpis, "oczekuje")
    kto = f" przez: {user}" if user is not None else ""
    wpis.anuluj(f"Anulowano: rekord przeniesiony do kosza{kto}. ")


def przygotuj_kolejke_do_przywrocenia(instance, user=None):
    """Przed przywróceniem (wołać w transakcji przywracania): worker
    w trakcie albo aktywny wpis (wycofanie) → ``RekordWKolejcePBN``."""
    wpis = _aktywny_wpis(instance, zablokuj=True)
    _zablokuj_rekord_pbn(instance, wpis)
    if wpis is None:
        return
    if wpis.operacja == PBN_Export_Queue.Operacja.WYCOFANIE:
        raise RekordWKolejcePBN(wpis, "wycofanie")
    raise RekordWKolejcePBN(wpis, "oczekuje")
