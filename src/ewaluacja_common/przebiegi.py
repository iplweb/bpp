"""Strażnik przebiegów w tle: wykrywa przebieg, który padł, i go anuluje.

Statusy długich zadań (generowanie metryk, moduł optymalizacji ewaluacji)
trzymają w bazie flagę ``w_trakcie``. Zdejmuje ją samo zadanie albo widok,
który widzi jego wynik — więc gdy zadanie przepadnie (restart workera przy
wdrożeniu, ubity proces, niedziałająca usługa zadań w tle), flaga zostaje
na zawsze: strona statusu kręci się bez końca, a ponowne uruchomienie
przekierowuje z powrotem na nią.

Strażnik pyta Celery, czy ktokolwiek jeszcze pracuje nad przebiegiem:

* żaden worker nie wykonuje, nie trzyma w rezerwie ani nie ma zaplanowanego
  zadania przebiegu, i żadne nie czeka w kolejce brokera → ``MARTWY``,
* żaden worker nie odpowiada → ``BRAK_WORKERA``,
* nie da się ustalić (broker niedostępny, kolejka za długa do przejrzenia,
  broker inny niż Redis) → ``NIE_WIADOMO``.

Zadania przebiegu rozpoznajemy po NAZWACH (``ZADANIA_PRZEBIEGU``), nie tylko
po ``task_id``: przebiegi rozgałęziają się w grupy/chordy o własnych
identyfikatorach. Skutek uboczny jest po bezpiecznej stronie — przebieg
innej uczelni o tych samych zadaniach podtrzymuje status przy życiu, nigdy
odwrotnie.

Anulujemy dopiero stan POTWIERDZONY w czasie (dwa odczyty w odstępie),
nigdy pojedynczy odczyt: między zakończeniem jednego zadania a podjęciem
następnego z łańcucha bywa chwila, w której nic nie jest „aktywne”.
"""

import json
import logging

from django.conf import settings
from django.utils import timezone
from kombu.exceptions import OperationalError
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

ZYJE = "zyje"
MARTWY = "martwy"
BRAK_WORKERA = "brak_workera"
NIE_WIADOMO = "nie_wiadomo"
#: Powód anulowania, gdy stanu nie dało się ustalić, a minął limit przebiegu.
PRZEKROCZONY_LIMIT = "przekroczony_limit"

#: Ile sekund czekamy na odpowiedź workerów. Żądanie HTTP czeka tyle
#: w całości, więc krótko; pytamy najwyżej raz na ``ODSTEP_SPRAWDZEN``.
LIMIT_ODPOWIEDZI_WORKERA_SEKUNDY = 2.0
#: Świeżo zleconego przebiegu nie sprawdzamy: widok zapisuje status tuż po
#: wysłaniu zadania, a zadanie potrzebuje chwili, żeby trafić do workera.
KARENCJA_PO_STARCIE_SEKUNDY = 60
ODSTEP_SPRAWDZEN_SEKUNDY = 20
#: Tyle musi trwać stan „martwy” w kolejnych odczytach, żeby anulować.
POTWIERDZENIE_MARTWEGO_SEKUNDY = 45
#: Tyle musi trwać brak odpowiedzi workerów, żeby anulować. Dłużej niż
#: restart usługi przy wdrożeniu; zmienia ustawienie
#: ``PRZEBIEGI_LIMIT_BEZ_WORKERA_SEKUNDY``.
DOMYSLNY_LIMIT_BEZ_WORKERA_SEKUNDY = 300
#: Dłuższej kolejki nie przeglądamy (żądanie HTTP) — stan „nie wiadomo”.
MAKS_ZADAN_W_KOLEJCE = 20000


def limit_bez_workera_sekundy():
    return getattr(
        settings,
        "PRZEBIEGI_LIMIT_BEZ_WORKERA_SEKUNDY",
        DOMYSLNY_LIMIT_BEZ_WORKERA_SEKUNDY,
    )


def _czeka_w_kolejce(app, nazwy_zadan, task_id):
    """Czy zadanie przebiegu czeka w kolejce brokera (jeszcze niepodjęte
    przez workera). ``None`` — nie da się ustalić."""
    with app.connection_for_read() as conn:
        if conn.transport.driver_type != "redis":
            return None
        klient = conn.default_channel.client
        kolejki = {app.conf.task_default_queue, *app.amqp.queues.keys()}
        for kolejka in kolejki:
            if klient.llen(kolejka) > MAKS_ZADAN_W_KOLEJCE:
                return None
            for surowe in klient.lrange(kolejka, 0, -1):
                try:
                    naglowki = json.loads(surowe).get("headers") or {}
                except ValueError:
                    continue  # wiadomość w innym formacie — nie nasze zadanie
                if naglowki.get("task") in nazwy_zadan or (
                    naglowki.get("id") == task_id
                ):
                    return True
    return False


def stan_zadan_w_celery(nazwy_zadan, task_id):
    """Czy Celery jeszcze pracuje nad przebiegiem: ``ZYJE`` / ``MARTWY`` /
    ``BRAK_WORKERA`` / ``NIE_WIADOMO`` (patrz docstring modułu)."""
    from django_bpp.celery_tasks import app

    nazwy_zadan = frozenset(nazwy_zadan)
    try:
        aktywne = app.control.inspect(timeout=LIMIT_ODPOWIEDZI_WORKERA_SEKUNDY).active()
        if not aktywne:
            return BRAK_WORKERA
        # Wiemy już, ilu jest workerów — kolejne pytania kończą się po tylu
        # odpowiedziach, bez czekania pełnego limitu.
        inspekcja = app.control.inspect(
            timeout=LIMIT_ODPOWIEDZI_WORKERA_SEKUNDY, limit=len(aktywne)
        )
        odpowiedzi = [aktywne, inspekcja.reserved(), inspekcja.scheduled()]
        czeka = _czeka_w_kolejce(app, nazwy_zadan, task_id)
    except (OperationalError, RedisError, OSError):
        # Broker niedostępny / zerwane połączenie: strona statusu ma działać
        # dalej, a o przebiegu nic nie wiemy.
        logger.exception("Nie udało się sprawdzić w Celery, czy przebieg żyje")
        return NIE_WIADOMO

    for odpowiedz in odpowiedzi:
        for zadania in (odpowiedz or {}).values():
            for zadanie in zadania:
                # ``scheduled`` opakowuje zadanie w {"eta": ..., "request": {}}
                zadanie = zadanie.get("request", zadanie)
                if zadanie.get("name") in nazwy_zadan or zadanie.get("id") == task_id:
                    return ZYJE
    if czeka:
        return ZYJE
    # Któryś worker nie zdążył odpowiedzieć na jedno z pytań — nie wolno
    # z tego wnioskować, że zadania nie ma.
    if czeka is None or any(
        odpowiedz is None or len(odpowiedz) < len(aktywne) for odpowiedz in odpowiedzi
    ):
        return NIE_WIADOMO
    return MARTWY


def powod_przerwania(
    klucz, nazwy_zadan, task_id, data_rozpoczecia, limit_przebiegu=None
):
    """Czy przebieg należy uznać za przerwany. Zwraca powód (``MARTWY``,
    ``BRAK_WORKERA``, ``PRZEKROCZONY_LIMIT``) albo ``None`` — żyje, za
    wcześnie na ocenę albo stan jeszcze niepotwierdzony.

    ``klucz`` identyfikuje status w pamięci odczytów (``OdczytPrzebiegu``).
    """
    teraz = timezone.now()
    wiek = (teraz - data_rozpoczecia).total_seconds()
    if wiek < KARENCJA_PO_STARCIE_SEKUNDY:
        return None

    from .models import OdczytPrzebiegu

    odczyt = OdczytPrzebiegu.objects.filter(klucz=klucz, task_id=task_id).first()
    if odczyt is not None and (
        (teraz - odczyt.sprawdzono).total_seconds() < ODSTEP_SPRAWDZEN_SEKUNDY
    ):
        return None

    stan = stan_zadan_w_celery(nazwy_zadan, task_id)
    od = odczyt.od if odczyt is not None and odczyt.stan == stan else teraz
    OdczytPrzebiegu.objects.update_or_create(
        klucz=klucz,
        defaults={"task_id": task_id, "stan": stan, "od": od, "sprawdzono": teraz},
    )
    trwa = (teraz - od).total_seconds()

    if stan == MARTWY and trwa >= POTWIERDZENIE_MARTWEGO_SEKUNDY:
        return MARTWY
    if stan == BRAK_WORKERA and trwa >= limit_bez_workera_sekundy():
        return BRAK_WORKERA
    if stan == NIE_WIADOMO and limit_przebiegu and wiek > limit_przebiegu:
        return PRZEKROCZONY_LIMIT
    return None


def komunikat_przerwania(nazwa, powod):
    """Komunikat dla użytkownika (trafia do ``ostatni_komunikat``)."""
    if powod == BRAK_WORKERA:
        minuty = max(1, round(limit_bez_workera_sekundy() / 60))
        return (
            f"{nazwa}: zadanie zostało anulowane, bo usługa przetwarzania "
            f"zadań w tle nie działa od co najmniej {minuty} min. Zgłoś to "
            "administratorowi systemu — dopóki usługa nie zostanie "
            "uruchomiona, ponowne uruchomienie zadania nic nie da."
        )
    if powod == PRZEKROCZONY_LIMIT:
        return (
            f"{nazwa}: zadanie trwało dłużej, niż może trwać, i nie udało "
            "się potwierdzić, że nadal pracuje — zostało anulowane. "
            "Uruchom je ponownie, a jeśli sytuacja się powtórzy, zgłoś to "
            "administratorowi systemu."
        )
    return (
        f"{nazwa}: zadanie zostało przerwane przed zakończeniem (np. przez "
        "restart usługi przetwarzania zadań w tle podczas aktualizacji "
        "systemu) i nie zostanie dokończone. Uruchom je ponownie."
    )


class PilnowanyPrzebiegMixin:
    """Domieszka dla modeli statusu z polami ``w_trakcie``, ``task_id``,
    ``data_rozpoczecia``, ``data_zakonczenia``, ``ostatni_komunikat``.

    Widoki pokazujące status albo decydujące „czy już trwa” biorą go przez
    ``aktualny()`` — przerwany przebieg zostaje wtedy przy okazji anulowany.
    Zadania w tle używają ``get_or_create`` — one niczego nie anulują.
    """

    #: Pełne nazwy zadań Celery, które mogą pracować w ramach przebiegu.
    ZADANIA_PRZEBIEGU = ()
    #: Początek komunikatu dla użytkownika, np. „Analiza zamiany dyscyplin”.
    NAZWA_PRZEBIEGU = "Zadanie w tle"
    #: Twardy limit (sekundy) — stosowany tylko, gdy stanu nie da się
    #: ustalić w Celery. ``None`` = bez limitu.
    LIMIT_PRZEBIEGU_SEKUNDY = None

    @classmethod
    def aktualny(cls, *args, **kwargs):
        status = cls.get_or_create(*args, **kwargs)
        status.anuluj_jesli_martwy()
        return status

    @property
    def przerwany(self):
        """Ostatni przebieg przerwano przed końcem: nie trwa i nigdy się
        nie zakończył (zakończenie — także błędem — ustawia datę)."""
        return bool(
            not self.w_trakcie
            and self.data_rozpoczecia is not None
            and self.data_zakonczenia is None
        )

    def komunikat_przerwania_dla(self, task_id):
        """Komunikat, jeśli to przebieg ``task_id`` został przerwany przez
        strażnika; inaczej ``None``."""
        if self.przerwany and self.task_id and self.task_id == str(task_id):
            return self.ostatni_komunikat
        return None

    def _przebieg_juz_zakonczony(self):
        """Zadanie skończyło pracę (wynik jest gotowy), tylko nikt jeszcze
        nie zdjął flagi — to robota widoków, nie strażnika. Statusy, których
        ``task_id`` wskazuje zadanie-rodzica kończące się od razu po
        rozesłaniu podzadań, nadpisują tę metodę."""
        from celery.result import AsyncResult

        return AsyncResult(self.task_id).ready()

    def _po_przerwaniu(self):
        """Sprzątanie po anulowaniu (np. oznaczenie rekordów „w toku”)."""

    def anuluj_jesli_martwy(self):
        """Anuluj przebieg, nad którym nikt już nie pracuje. Zwraca
        ``True``, gdy anulowano."""
        if not (self.w_trakcie and self.task_id and self.data_rozpoczecia):
            return False
        wiek = (timezone.now() - self.data_rozpoczecia).total_seconds()
        if wiek < KARENCJA_PO_STARCIE_SEKUNDY or self._przebieg_juz_zakonczony():
            return False

        powod = powod_przerwania(
            f"przebieg-w-tle:{self._meta.label_lower}:{self.pk}",
            self.ZADANIA_PRZEBIEGU,
            self.task_id,
            self.data_rozpoczecia,
            self.LIMIT_PRZEBIEGU_SEKUNDY,
        )
        if powod is None:
            return False

        # Warunkowy UPDATE: jeśli w międzyczasie przebieg się zakończył albo
        # zlecono nowy — nic nie robimy.
        zmienione = (
            type(self)
            .objects.filter(
                pk=self.pk,
                w_trakcie=True,
                task_id=self.task_id,
                data_rozpoczecia=self.data_rozpoczecia,
            )
            .update(
                w_trakcie=False,
                data_zakonczenia=None,
                ostatni_komunikat=komunikat_przerwania(self.NAZWA_PRZEBIEGU, powod),
            )
        )
        self.refresh_from_db()
        if zmienione:
            logger.warning(
                "%s: przebieg task_id=%s anulowany przez strażnika (%s)",
                type(self).__name__,
                self.task_id,
                powod,
            )
            self._po_przerwaniu()
        return bool(zmienione)
