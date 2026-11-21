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


# --- kosz a kolejka PBN ---------------------------------------------------


class RekordWKolejcePBN(Exception):
    """Rekord ma aktywne zlecenie WYSYŁKI do PBN — nie trafi do kosza bez
    świadomej decyzji operatora (``anuluj_wysylke_pbn=True``).

    Bez tej bramki zlecenie wycofania przy kasowaniu odbijałoby się od
    „rekord już jest w kolejce" (jeden aktywny wpis na rekord) i ginęło po
    cichu, a wysyłka i tak by się nie odbyła (rekord w koszu) — oświadczenia
    wysłane wcześniej zostałyby w PBN.

    ``w_toku=True``: wysyłka już trwa (worker ją podjął) — tej nie da się
    bezpiecznie przerwać; trzeba poczekać, aż się skończy.
    """

    def __init__(self, wpis, w_toku=False):
        self.wpis = wpis
        self.w_toku = w_toku
        if w_toku:
            komunikat = (
                f"Rekord „{wpis.rekord_do_wysylki}” jest właśnie wysyłany do PBN "
                f"— poczekaj, aż wysyłka się zakończy, i usuń go ponownie."
            )
        else:
            komunikat = (
                f"Rekord „{wpis.rekord_do_wysylki}” jest w kolejce wysyłki do PBN "
                f"— trzeba go z niej wycofać, zanim trafi do kosza."
            )
        super().__init__(komunikat)


def aktywny_wpis(instance):
    """Aktywny (niezakończony) wpis kolejki dla rekordu albo ``None``."""
    return PBN_Export_Queue.objects.filter_rekord_do_wysylki(instance).first()


def aktywna_wysylka(instance):
    """Aktywny wpis WYSYŁKI rekordu albo ``None``."""
    wpis = aktywny_wpis(instance)
    if wpis is not None and wpis.operacja == PBN_Export_Queue.Operacja.WYSYLKA:
        return wpis
    return None


def przygotuj_kolejke_do_kosza(instance, anuluj_wysylke_pbn=False, user=None):
    """Przed przeniesieniem rekordu do kosza: rozstrzyga aktywne zlecenia.

    - aktywna WYSYŁKA i brak zgody → ``RekordWKolejcePBN`` (rekord zostaje);
    - aktywna WYSYŁKA, zgoda, wysyłka jeszcze nie podjęta → wpis zamknięty
      jako wykluczony z komunikatem „anulowano"; wycofanie zleci receiver;
    - aktywna WYSYŁKA już w toku → ``RekordWKolejcePBN(w_toku=True)``;
    - aktywne WYCOFANIE z flagą ponownej wysyłki (rekord był przywrócony
      i znów idzie do kosza) → flaga zdjęta.
    """
    wpis = aktywny_wpis(instance)
    if wpis is None:
        return
    if wpis.operacja == PBN_Export_Queue.Operacja.WYCOFANIE:
        if wpis.wyslij_ponownie_po_zakonczeniu:
            wpis.wyslij_ponownie_po_zakonczeniu = False
            wpis.save(update_fields=["wyslij_ponownie_po_zakonczeniu"])
        return
    if wpis.wysylke_podjeto is not None:
        raise RekordWKolejcePBN(wpis, w_toku=True)
    if not anuluj_wysylke_pbn:
        raise RekordWKolejcePBN(wpis)
    kto = f" przez: {user}" if user is not None else ""
    wpis.exclude(f"Anulowano: rekord przeniesiony do kosza{kto}. ")


def zakolejkuj_wysylke_po_przywroceniu(instance, user=None, uczelnia=None):
    """Przywrócenie z kosza → ponowna wysyłka do PBN.

    Gdy wycofanie oświadczeń (zlecone przy kasowaniu) jeszcze się nie
    zakończyło, NIE przerywamy go — wpis dostaje flagę
    ``wyslij_ponownie_po_zakonczeniu`` i po jego zakończeniu system sam zleca
    świeżą wysyłkę. Kolejność jest istotna: wysyłka przed wycofaniem
    skończyłaby się wycofaniem właśnie wysłanych oświadczeń.

    Zwraca wpis (nowy WYSYLKA albo oflagowane WYCOFANIE) albo ``None``.
    """
    wpis = zakolejkuj_wysylke(instance, user=user, uczelnia=uczelnia)
    if wpis is not None:
        return wpis
    aktywny = aktywny_wpis(instance)
    if aktywny is not None and aktywny.operacja == PBN_Export_Queue.Operacja.WYCOFANIE:
        aktywny.wyslij_ponownie_po_zakonczeniu = True
        aktywny.save(update_fields=["wyslij_ponownie_po_zakonczeniu"])
    return aktywny


def wyslij_ponownie_po_wycofaniu(pk):
    """Wołane po commicie zakończenia wpisu z flagą ponownej wysyłki.

    Flagę zdejmujemy atomowym ``UPDATE ... WHERE flaga`` — tylko ten, kto ją
    zdjął, zleca wysyłkę (ochrona przed podwójnym zleceniem). Rekord, który
    w międzyczasie znów trafił do kosza, nie jest wysyłany.
    """
    zdjeto = PBN_Export_Queue.objects.filter(
        pk=pk, wyslij_ponownie_po_zakonczeniu=True
    ).update(wyslij_ponownie_po_zakonczeniu=False)
    if not zdjeto:
        return None
    wpis = PBN_Export_Queue.objects.get(pk=pk)
    rekord = wpis.rekord_do_wysylki
    if rekord is None or getattr(rekord, "deleted_at", None) is not None:
        return None
    return zakolejkuj_wysylke(rekord, user=wpis.zamowil, uczelnia=wpis.uczelnia)
