"""Receivery sygnałów ``django-soft-delete`` → ``SoftDeleteLog``.

JEDEN punkt podpięcia dla WSZYSTKICH modeli soft-delete (publikacje,
``*_Autor``, ``Autor``, ``Element_Repozytorium``) — receivery są rejestrowane
bez ``sender=``, więc nowy model soft-delete jest logowany bez dopisywania
czegokolwiek tutaj. Rejestracja: ``BppConfig.ready()``.

Usera i powód wnosi thread-local ``soft_delete_context`` — sygnały pakietu
ich nie niosą (patrz ``bpp/models/soft_delete_context.py``).
"""

from django.contrib.contenttypes.models import ContentType

from bpp.models.soft_delete import BppPublikacjaSoftDeleteMixin, pk_dla_audytu
from bpp.models.soft_delete_context import (
    current_soft_delete_reason,
    current_soft_delete_user,
)
from bpp.models.soft_delete_log import SoftDeleteLog

#: Wartości ``SoftDeleteLog.pbn_status`` (kontrakt PINNED planu fazy 06).
#: To OSOBNY słownik od ``PBN_Export_Queue.Operacja`` (``"wysylka"`` /
#: ``"wycofanie"``) — tamten opisuje wpis kolejki, ten opisuje, co receiver
#: z tym wpisem zrobił.
STATUS_WYCOFANIE = "WYCOFANIE"
STATUS_WYSYLKA = "WYSYLKA"


def _kolejkuj_pbn(instance, zakolejkuj, status):
    """Zleca operację PBN dla PUBLIKACJI. Zwraca ``(wpis, status)``.

    GATE IDZIE PO TYPIE, nie po obecności ``pbn_uid``. Plan fazy 06
    proponował uniwersalne ``getattr(instance, "pbn_uid_id", None)``,
    opierając się na twierdzeniu, że „``Autor`` i ``*_Autor`` nie mają
    ``pbn_uid``". ``Autor.pbn_uid`` jednak ISTNIEJE (FK do
    ``pbn_api.Scientist``), więc tamten gate wstawiłby autora do kolejki
    eksportu PUBLIKACJI i odpalił dla niego wysyłkę.

    Sam ``pbn_uid`` nie wystarczyłby też od drugiej strony: przy RESTORE
    wołamy ``zakolejkuj_wysylke``, która świadomie NIE MA gate'u na
    ``pbn_uid`` (faza 05a) — przyjęłaby więc każdy wiersz ``*_Autor``
    przywracany kaskadą i publikacja z N autorami dałaby N zbędnych zleceń.

    ``uczelnia`` wyprowadzana z rekordu, bo receiver nie ma requestu —
    patrz ``BppPublikacjaSoftDeleteMixin.uczelnia_rekordu()``.
    """
    if not isinstance(instance, BppPublikacjaSoftDeleteMixin):
        return None, ""

    wpis = zakolejkuj(
        instance,
        user=current_soft_delete_user(),
        uczelnia=instance.uczelnia_rekordu(),
    )
    # ``None`` znaczy „gate niespełniony ALBO rekord już czeka w kolejce"
    # (idempotencja ``sprobuj_utowrzyc_wpis``). Obu przypadków nie da się
    # tu rozróżnić — obie funkcje kolejkujące zwracają ``None``.
    return wpis, (status if wpis is not None else "")


def _utworz_log(instance, akcja, pbn_queue_entry=None, pbn_status=""):
    return SoftDeleteLog.objects.create(
        content_type=ContentType.objects.get_for_model(instance),
        object_id=pk_dla_audytu(instance),
        akcja=akcja,
        user=current_soft_delete_user(),
        powod=current_soft_delete_reason(),
        pbn_queue_entry=pbn_queue_entry,
        pbn_status=pbn_status,
    )


def _wylicza_punktacje(instance):
    """Czy rekord wnosi wiersze do ``Cache_Punktacja_*``.

    Gate zawęża do ``Wydawnictwo_Ciagle``, ``Wydawnictwo_Zwarte``
    i ``Patent`` — tylko one dziedziczą ``ModelZPrzeliczaniemDyscyplin``.
    Prace dyplomowe, ``Autor``, ``*_Autor`` i ``Element_Repozytorium``
    nie mają nawet metody ``przelicz_punkty_dyscyplin()``, więc bez gate'u
    receiver wywracałby się na ``AttributeError``.

    Gate załatwia przy okazji drugą rzecz: kaskada ``*_Autor`` emituje
    własne sygnały, a te wiersze tego abstraktu nie dziedziczą — więc
    przeliczenie zachodzi RAZ, przy sygnale rodzica, a nie 1 + N razy.
    """
    from bpp.models.abstract import ModelZPrzeliczaniemDyscyplin

    return isinstance(instance, ModelZPrzeliczaniemDyscyplin)


def _skasuj_punktacje(instance):
    """Kosz zabiera rekordowi sloty i punkty w ewaluacji.

    ``Cache_Punktacja_*`` nie ma FK do publikacji (klucz to tablica
    ``rekord_id = [content_type_id, pk]``), więc nie sprząta jej ani
    kaskada Django, ani kaskada ``*_Autor`` z fazy 02, ani triggery
    denormalizacji. Bez tego praca w koszu nadal liczyłaby się do
    ewaluacji.
    """
    from bpp.models.sloty.core import IPunktacjaCacher

    IPunktacjaCacher(instance).removeEntries()


def on_post_soft_delete(sender, instance, **kwargs):
    """Kosz → zlecenie wycofania oświadczeń z PBN + wpis audytu."""
    from pbn_export_queue.operacje import zakolejkuj_wycofanie

    if _wylicza_punktacje(instance):
        _skasuj_punktacje(instance)

    wpis, status = _kolejkuj_pbn(instance, zakolejkuj_wycofanie, STATUS_WYCOFANIE)
    _utworz_log(
        instance,
        SoftDeleteLog.Akcja.DELETE,
        pbn_queue_entry=wpis,
        pbn_status=status,
    )


def on_post_restore(sender, instance, **kwargs):
    """Przywrócenie → ponowna wysyłka do PBN, punktacja i wpis audytu.

    Punktację PRZELICZAMY, a nie odtwarzamy z kopii: wiersze
    ``Cache_Punktacja_*`` zostały skasowane, a przez czas pobytu w koszu
    mogły się zmienić dyscypliny autorów albo progi punktowe. Odtworzenie
    starych wartości przywróciłoby nieaktualny stan.

    ⚠️ To operacja LICZĄCA, nie ``UPDATE``. Przy masowym przywracaniu
    z admina (faza 07) koszt rośnie liniowo — patrz notatka w handoffie.
    """
    from pbn_export_queue.operacje import zakolejkuj_wysylke

    if _wylicza_punktacje(instance):
        instance.przelicz_punkty_dyscyplin()

    wpis, status = _kolejkuj_pbn(instance, zakolejkuj_wysylke, STATUS_WYSYLKA)
    _utworz_log(
        instance,
        SoftDeleteLog.Akcja.RESTORE,
        pbn_queue_entry=wpis,
        pbn_status=status,
    )


def on_post_hard_delete(sender, instance, **kwargs):
    """Hard-delete: rekord fizycznie znika, więc bez operacji PBN.

    Wycofanie oświadczeń wymaga ``pbn_uid`` odczytanego z rekordu, a tego
    już nie ma — dług opisany w handoffie fazy 05a §6. Log powstaje mimo
    to i jest wtedy JEDYNYM śladem, że rekord istniał.
    """
    _utworz_log(instance, SoftDeleteLog.Akcja.HARD_DELETE)


def register():
    """Podłącza receivery. Woła to ``BppConfig.ready()``.

    ``dispatch_uid`` przy każdym połączeniu: ``ready()`` bywa wołane więcej
    niż raz (m.in. przy ``TransactionTestCase``), a bez uid-a receiver
    zostałby podpięty dwa razy i każdy soft-delete produkowałby dwa wpisy
    logu. Import sygnałów jest lokalny, żeby moduł dał się zaimportować
    poza kontekstem gotowej aplikacji.
    """
    from django_softdelete.signals import (
        post_hard_delete,
        post_restore,
        post_soft_delete,
    )

    post_soft_delete.connect(
        on_post_soft_delete, dispatch_uid="bpp.soft_delete.post_soft_delete"
    )
    post_restore.connect(on_post_restore, dispatch_uid="bpp.soft_delete.post_restore")
    post_hard_delete.connect(
        on_post_hard_delete, dispatch_uid="bpp.soft_delete.post_hard_delete"
    )
