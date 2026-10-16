"""Shim naprawiający ``django-easy-audit`` na modelach soft-delete.

Pełne uzasadnienie w ``src/bpp/easyaudit_shim.py``. Tu pilnujemy trzech
rzeczy: że shim jest wpięty, że naprawia realny objaw i że zniknie, gdy
przestanie być potrzebny.
"""

import inspect
import weakref

import pytest
from django.apps import apps
from django.db.models import signals
from model_bakery import baker

from bpp.easyaudit_shim import DISPATCH_UID, WERSJA_UPSTREAM
from bpp.easyaudit_shim import pre_save as nasz_pre_save
from bpp.models import Wydawnictwo_Ciagle

pytestmark = pytest.mark.skipif(
    not apps.is_installed("easyaudit"),
    reason="easyaudit wchodzi tylko w local.py/production.py",
)


def _odbiorcy_pod_uid():
    """Funkcje podpięte pod ``pre_save`` naszym ``dispatch_uid``.

    ``Signal.receivers`` (Django 5.2) trzyma krotki
    ``((dispatch_uid, id_nadawcy), odbiorca, is_async)``, a ``odbiorca`` bywa
    słabą referencją (``connect(weak=True)`` jest domyślne) — stąd
    rozpakowanie i ewentualne rozwinięcie ``weakref``.
    """
    znalezione = []
    for klucz, odbiorca, *_ in signals.pre_save.receivers:
        if klucz[0] != DISPATCH_UID:
            continue
        if isinstance(odbiorca, weakref.ReferenceType):
            odbiorca = odbiorca()
        znalezione.append(odbiorca)
    return znalezione


def test_shim_jest_wpiety_zamiast_handlera_upstreamu():
    """Nasz handler zajmuje ``dispatch_uid`` easyauditu, nie stoi obok niego.

    Gdyby stał obok, oba by się wykonywały i audyt dublowałby wpisy.
    """
    odbiorcy = _odbiorcy_pod_uid()
    assert odbiorcy, "nikt nie jest podpiety pod dispatch_uid easyauditu"
    assert len(odbiorcy) == 1, (
        f"handler podpiety {len(odbiorcy)} razy — zainstaluj() nie jest "
        f"idempotentne albo obok naszego stoi handler upstreamu"
    )
    assert odbiorcy[0] is nasz_pre_save, (
        f"pod {DISPATCH_UID} siedzi {odbiorcy[0]!r}, a nie nasz shim — "
        "sprawdz kolejnosc ready() aplikacji"
    )


@pytest.mark.django_db
def test_restore_publikacji_nie_wywala_sie_na_audycie():
    """OBJAW, dla którego shim powstał.

    Bez niego ``restore()`` leci ``DoesNotExist``: easyaudit szuka
    poprzedniej wersji wiersza przez ``objects``, a ten w trakcie
    przywracania jest jeszcze odfiltrowany jako skasowany.
    """
    wc = baker.make(Wydawnictwo_Ciagle)
    pk = wc.pk
    wc.delete()

    wc.restore()

    assert Wydawnictwo_Ciagle.objects.filter(pk=pk).exists(), (
        "po restore publikacja nie wrocila do objects"
    )


@pytest.mark.django_db
def test_restore_zgloszenia_publikacji_czyli_blad_ZASTANY():
    """``Zgloszenie_Publikacji`` jest ``SoftDeleteModel`` OD DAWNA i również
    figuruje w ``DJANGO_EASY_AUDIT_REGISTERED_CLASSES``.

    Ten test dowodzi, że naprawiamy błąd ZASTANY, a nie wyłącznie skutek
    uboczny fazy 02: na ``dev`` (bez shimu) przywrócenie skasowanego
    zgłoszenia jest niemożliwe.

    ``strict=False`` jest tu potrzebne z INNEGO powodu — pakietowy
    ``restore()`` domyślnie wymaga, żeby każdy model powiązany też był
    ``SoftDeleteModel`` (``Zgloszenie_Publikacji_Autor`` nie jest). To ten
    sam inwariant, który dla naszych modeli domyka ``soft_delete.py``.
    """
    from zglos_publikacje.models import Zgloszenie_Publikacji

    z = baker.make(Zgloszenie_Publikacji)
    pk = z.pk
    z.delete()

    Zgloszenie_Publikacji.global_objects.get(pk=pk).restore(strict=False)

    assert Zgloszenie_Publikacji.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_audyt_dalej_dziala_czyli_shim_niczego_nie_wycisza(admin_user, rf, settings):
    """Shim ma naprawiać lookup, a nie wyłączać audyt.

    Bez tego testu „zielono" znaczyłoby tylko tyle, że nic nie wybucha —
    a najprostszym sposobem, żeby nic nie wybuchało, byłoby przestać
    audytować.

    Zanim ten test cokolwiek mierzył, trzeba było zdjąć DWIE bramki, z
    których żadna nie ma związku z shimem — obie po kolei dawały „zero
    zdarzeń", czyli objaw nieodróżnialny od zepsutego shimu:

    1. **Request z użytkownikiem.** BPP ma
       ``DJANGO_EASY_AUDIT_CRUD_DIFFERENCE_CALLBACKS =
       ["bpp.util.dont_log_anonymous_crud_events"]``, który świadomie
       odrzuca zdarzenia bez zalogowanego użytkownika.
    2. **``settings.TEST``.** Bez niego easyaudit odkłada zapis zdarzenia
       na ``transaction.on_commit``, a w teście transakcja jest
       rollbackowana — callback nigdy nie odpala. To własny przełącznik
       pakietu, przewidziany dokładnie na tę sytuację.
    """
    from easyaudit.middleware.easyaudit import _thread_locals
    from easyaudit.models import CRUDEvent

    settings.TEST = True
    request = rf.get("/")
    request.user = admin_user
    _thread_locals.request = request
    try:
        wc = baker.make(Wydawnictwo_Ciagle)
        przed = CRUDEvent.objects.count()

        wc.tytul_oryginalny = "Zmieniony tytul dla audytu"
        wc.save()

        assert CRUDEvent.objects.count() > przed, (
            "zapis nie wygenerowal zdarzenia audytu — shim wycisza easyaudit"
        )
    finally:
        del _thread_locals.request


def test_upstream_nadal_ma_blad_czyli_shim_jest_potrzebny():
    """STRAŻNIK ODWROTNY: pada, gdy shim przestanie być potrzebny.

    Sprawdza, czy ``easyaudit`` NADAL pobiera poprzedni wiersz przez
    ``objects``. Gdy upstream scali poprawkę (issue #175, otwarte od 2021),
    ten test spadnie na czerwono — i to jest sygnał, żeby skasować
    ``bpp/easyaudit_shim.py`` razem z wywołaniem w ``BppConfig.ready()``,
    a nie żeby test „naprawić".

    Bez tego strażnika shim zostałby w kodzie na zawsze, cicho duplikując
    logikę, którą pakiet już by miał poprawną.
    """
    from easyaudit.signals import model_signals

    zrodlo = inspect.getsource(model_signals.pre_save)

    assert "sender.objects.get(pk=instance.pk)" in zrodlo, (
        f"easyaudit (kopiowano z {WERSJA_UPSTREAM}) NIE uzywa juz "
        f"`sender.objects` — poprawka prawdopodobnie weszla upstream. "
        f"SKASUJ bpp/easyaudit_shim.py i wywolanie zainstaluj() "
        f"w BppConfig.ready(), zamiast poprawiac ten test."
    )
