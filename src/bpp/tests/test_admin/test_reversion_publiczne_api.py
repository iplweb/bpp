"""BPP korzysta wyłącznie z publicznego API django-reversion.

Prywatne nazwy (``reversion.revisions._stack``, ``_get_options``) mogą
zniknąć w dowolnym wydaniu reversion. Akcje masowe z historią nie
potrzebują już odkładania stosu rewizji: ``HistoriaWersjiMixin`` nie
otwiera rewizji ``changelist_view`` dla akcji oznaczonych
``zapisuje_historie``, a pozostałe ścieżki admina działają jak dotąd.
"""

import re
from pathlib import Path
from unittest import mock

import pytest
import reversion
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from django.urls import resolve
from model_bakery import baker
from reversion.models import Version

from bpp.admin import actions
from bpp.admin.autor import AutorAdmin
from bpp.admin.uczelnia import UczelniaAdmin
from bpp.models import Autor, Uczelnia
from bpp.wersjonowanie import FOLLOW_REVERSION, sledzone_relacje

SRC = Path(__file__).resolve().parents[3]

#: ``reversion.revisions._cos`` albo ``from reversion.revisions import _cos``
#: (także w nawiasach / po przecinku).
PRYWATNE_REVERSION = re.compile(
    r"reversion\.revisions\._\w"
    r"|from\s+reversion(\.\w+)*\s+import\s+\(?[^\n]*\b_\w"
)

AKCJE_Z_HISTORIA = (
    "ustaw_pokazuj_true",
    "ustaw_pokazuj_false",
    "pokaz_autorow_wszedzie",
    "ukryj_autorow_wszedzie",
)


def test_src_nie_uzywa_prywatnego_api_reversion():
    ten_plik = Path(__file__).resolve()
    naruszenia = [
        f"{plik.relative_to(SRC)}:{nr}: {linia.strip()}"
        for plik in SRC.rglob("*.py")
        if plik.resolve() != ten_plik
        for nr, linia in enumerate(plik.read_text(encoding="utf-8").splitlines(), 1)
        if PRYWATNE_REVERSION.search(linia)
    ]
    assert naruszenia == []


@pytest.mark.parametrize(
    "linia,prywatna",
    [
        ("from reversion.revisions import _stack as _s", True),
        ("from reversion.revisions import is_active, _get_options", True),
        ("opcje = reversion.revisions._get_options(Autor)", True),
        ("from reversion.revisions import create_revision", False),
        ("import reversion", False),
        ("reversion.is_registered(model)", False),
    ],
)
def test_wzorzec_prywatnego_api(linia, prywatna):
    assert bool(PRYWATNE_REVERSION.search(linia)) is prywatna


def test_follow_reversion_autora_i_brak_wpisu():
    assert sledzone_relacje(Autor) == ("wybrane_publikacje",)
    # Model nieznany BPP: brak prefetchu, nigdy błąd.
    assert sledzone_relacje(object) == ()


def test_follow_modeli_rejestrowanych_przez_version_admin():
    """``VersionAdmin`` rejestruje ``Uczelnia`` sam (z inline'ami jako
    ``follow``) — mixin zapamiętuje to w ``FOLLOW_REVERSION``."""
    UczelniaAdmin(Uczelnia, AdminSite())
    assert reversion.is_registered(Uczelnia)
    assert Uczelnia in FOLLOW_REVERSION
    assert isinstance(FOLLOW_REVERSION[Uczelnia], tuple)


@pytest.mark.parametrize("nazwa", AKCJE_Z_HISTORIA)
def test_akcje_autora_z_historia_sa_oznaczone(nazwa):
    assert getattr(actions, nazwa).zapisuje_historie is True


@pytest.mark.parametrize(
    "nazwa", ["ustaw_przed_korekta", "ustaw_po_korekcie", "ustaw_w_trakcie_korekty"]
)
def test_akcje_statusu_korekty_sa_oznaczone(nazwa):
    assert getattr(actions, nazwa).zapisuje_historie is True


def _czy_rewizja_aktywna(admin_user, metoda, dane=None, url="/admin/bpp/autor/"):
    rf = RequestFactory()
    request = rf.post(url, dane or {}) if metoda == "post" else rf.get(url)
    request.user = admin_user
    request.resolver_match = resolve(url)
    with AutorAdmin(Autor, AdminSite()).create_revision(request):
        return reversion.is_active()


@pytest.mark.django_db
@pytest.mark.parametrize("nazwa", AKCJE_Z_HISTORIA)
def test_changelist_bez_rewizji_dla_akcji_z_historia(admin_user, nazwa):
    dane = {"action": nazwa, "_selected_action": [1], "index": 0}
    assert _czy_rewizja_aktywna(admin_user, "post", dane) is False


@pytest.mark.django_db
def test_changelist_bez_rewizji_dla_nieoznaczonych_akcji(admin_user):
    """FD#587: także akcja NIEoznaczona (wbudowane usuwanie) nie dostaje
    wspólnej rewizji — przywrócenie wersji jednego rekordu cofnęłoby
    wszystkie zmienione tą akcją."""
    dane = {"action": "delete_selected", "_selected_action": [1], "index": 0}
    assert _czy_rewizja_aktywna(admin_user, "post", dane) is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "metoda,dane,url",
    [
        # Zwykłe wyświetlenie listy.
        ("get", None, "/admin/bpp/autor/"),
        # POST listy bez akcji (np. list_editable / wyszukiwanie).
        ("post", {"q": "x"}, "/admin/bpp/autor/"),
        # Nieznana akcja albo zły indeks — decyduje Django, rewizja jak dotąd.
        ("post", {"action": "nie_ma_takiej", "index": 0}, "/admin/bpp/autor/"),
        ("post", {"action": "ukryj_autorow_wszedzie", "index": 5}, "/admin/bpp/autor/"),
        # Formularz dodawania z polem ``action`` to NIE lista rekordów.
        (
            "post",
            {"action": "ukryj_autorow_wszedzie", "index": 0},
            "/admin/bpp/autor/add/",
        ),
    ],
)
def test_pozostale_sciezki_admina_nadal_w_rewizji(admin_user, metoda, dane, url):
    assert _czy_rewizja_aktywna(admin_user, metoda, dane, url) is True


@pytest.mark.django_db
def test_akcja_z_historia_przed_i_po_w_osobnych_rewizjach(admin_client, admin_user):
    autorzy = baker.make(Autor, pokazuj_w_api=True, _quantity=2)
    res = admin_client.post(
        "/admin/bpp/autor/",
        {
            "action": "ukryj_autorow_wszedzie",
            "_selected_action": [a.pk for a in autorzy],
            "index": 0,
        },
    )
    assert res.status_code == 302

    przed = {Version.objects.get_for_object(a).last().revision_id for a in autorzy}
    po = {Version.objects.get_for_object(a).first().revision_id for a in autorzy}
    # FD#587: każdy autor we własnej rewizji „przed” i „po” — cofnięcie
    # jednego nie cofa drugiego.
    assert len(przed) == 2
    assert len(po) == 2
    assert not przed & po
    for rewizja in przed | po:
        assert Version.objects.filter(revision_id=rewizja).count() == 1
    uzytkownicy_po = set(
        Version.objects.filter(revision_id__in=po).values_list(
            "revision__user", flat=True
        )
    )
    assert uzytkownicy_po == {admin_user.pk}

    for autor in autorzy:
        Version.objects.get_for_object(autor).last().revert()
        autor.refresh_from_db()
        assert autor.pokazuj_w_api is True


@pytest.mark.django_db
@pytest.mark.parametrize("oznaczona,oczekiwana", [(False, False), (True, False)])
def test_changelist_nie_otwiera_rewizji_dla_akcji(admin_client, oznaczona, oczekiwana):
    """Przez prawdziwy ``changelist_view``: żadna akcja masowa nie wykonuje
    się we wspólnej rewizji reversion (FD#587) — oznaczone
    ``zapisuje_historie`` zapisują wersje same, osobno dla rekordów."""
    stan = []

    def akcja_testowa(modeladmin, request, queryset):
        stan.append(reversion.is_active())

    if oznaczona:
        actions.zapisuje_historie(akcja_testowa)
    autor = baker.make(Autor)
    with mock.patch.object(AutorAdmin, "actions", [akcja_testowa]):
        res = admin_client.post(
            "/admin/bpp/autor/",
            {"action": "akcja_testowa", "_selected_action": [autor.pk], "index": 0},
        )
    assert res.status_code == 302
    assert stan == [oczekiwana]
