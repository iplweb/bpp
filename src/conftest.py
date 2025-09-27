from datetime import timedelta
from uuid import uuid4

import pytest
from django.apps import apps
from model_bakery import baker

from django.utils import timezone

# Fix for VCR.py compatibility with urllib3
# This resolves the AttributeError: 'VCRHTTPConnection' has no attribute 'debuglevel'


def pytest_configure(config):
    try:
        import http.client

        import vcr

        # Patch VCR's HTTP connection classes to include required attributes
        original_vcr_stubs_init = (
            vcr.stubs.VCRHTTPConnection.__init__ if hasattr(vcr, "stubs") else None
        )

        def patched_init(self, *args, **kwargs):
            # Set default debuglevel before calling original init
            self.debuglevel = getattr(http.client.HTTPConnection, "debuglevel", 0)
            if original_vcr_stubs_init:
                original_vcr_stubs_init(self, *args, **kwargs)

        if hasattr(vcr, "stubs"):
            vcr.stubs.VCRHTTPConnection.__init__ = patched_init
            vcr.stubs.VCRHTTPSConnection.__init__ = patched_init

            # Ensure the class has all required attributes from http.client
            if not hasattr(vcr.stubs.VCRHTTPConnection, "debuglevel"):
                vcr.stubs.VCRHTTPConnection.debuglevel = 0
            if not hasattr(vcr.stubs.VCRHTTPSConnection, "debuglevel"):
                vcr.stubs.VCRHTTPSConnection.debuglevel = 0

            # Add _http_vsn and _http_vsn_str attributes required by urllib3
            if not hasattr(vcr.stubs.VCRHTTPConnection, "_http_vsn"):
                vcr.stubs.VCRHTTPConnection._http_vsn = 11
            if not hasattr(vcr.stubs.VCRHTTPConnection, "_http_vsn_str"):
                vcr.stubs.VCRHTTPConnection._http_vsn_str = "HTTP/1.1"
            if not hasattr(vcr.stubs.VCRHTTPSConnection, "_http_vsn"):
                vcr.stubs.VCRHTTPSConnection._http_vsn = 11
            if not hasattr(vcr.stubs.VCRHTTPSConnection, "_http_vsn_str"):
                vcr.stubs.VCRHTTPSConnection._http_vsn_str = "HTTP/1.1"

    except ImportError:
        # VCR not installed, skip configuration
        pass


pytest.mark.uruchom_tylko_bez_microsoft_auth = pytest.mark.skipif(
    apps.is_installed("microsoft_auth"),
    reason="działa wyłącznie bez django_microsoft_auth. Ta "
    "funkcja prawdopodobnie potrzebuje zalogowac do systemu zwykłego "
    "użytkownika i nie potrzebuje autoryzacji do niczego więcej. "
    "Możesz ją spokojnie przetestować z wyłączonym modułem microsoft_auth",
)


@pytest.fixture
def pbn_dyscyplina2(db, pbn_discipline_group):
    from pbn_api.models import Discipline

    return Discipline.objects.get_or_create(
        parent_group=pbn_discipline_group,
        uuid=uuid4(),
        code="202",
        name="druga dyscyplina",
        scientificFieldName="Dziedzina drugich dyscyplin",
    )[0]


@pytest.fixture
def pbn_discipline_group(db):
    from pbn_api.models import DisciplineGroup

    n = timezone.now().date()
    try:
        return DisciplineGroup.objects.get_or_create(
            validityDateTo=None,
            validityDateFrom=n - timedelta(days=7),
            defaults=dict(uuid=uuid4()),
        )[0]
    except DisciplineGroup.MultipleObjectsReturned:
        return DisciplineGroup.objects.filter(
            validityDateTo=None,
            validityDateFrom=n - timedelta(days=7),
        ).first()


@pytest.fixture
def pbn_dyscyplina1(db, pbn_discipline_group):
    from pbn_api.models import Discipline

    return Discipline.objects.get_or_create(
        parent_group=pbn_discipline_group,
        code="301",
        name="memetyka stosowana",
        scientificFieldName="Dziedzina memetyk",
        defaults=dict(uuid=uuid4()),
    )[0]


@pytest.fixture
@pytest.mark.django_db
def zwarte_z_dyscyplinami(
    wydawnictwo_zwarte,
    autor_jan_nowak,
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    dyscyplina2,
    charaktery_formalne,
    wydawca,
    typy_odpowiedzialnosci,
    rok,
):
    from bpp.models import Autor_Dyscyplina, Charakter_Formalny

    # Żeby eksportować oświadczenia, autor musi mieć swój odpowiednik w PBNie:
    autor_jan_nowak.pbn_uid = baker.make("pbn_api.Scientist")
    autor_jan_nowak.save()

    autor_jan_kowalski.pbn_uid = baker.make("pbn_api.Scientist")
    autor_jan_kowalski.save()

    # Musi miec też przypisania do dyscyplin
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak, dyscyplina_naukowa=dyscyplina1, rok=rok
    )
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina2, rok=rok
    )
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina2
    )

    # domyslnie: ksiazka/autorstwo/wydawca spoza wykazu
    wydawnictwo_zwarte.punkty_kbn = 20
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.charakter_formalny = Charakter_Formalny.objects.get(skrot="KSP")
    wydawnictwo_zwarte.save()

    return wydawnictwo_zwarte


def _dyscyplina_maker(nazwa, kod, dyscyplina_pbn):
    """Produkuje dyscypliny naukowe WRAZ z odpowiednim wpisem tłumacza
    dyscyplin"""
    from pbn_api.models import TlumaczDyscyplin

    from bpp.models import Dyscyplina_Naukowa

    d = Dyscyplina_Naukowa.objects.get_or_create(nazwa=nazwa, kod=kod)[0]
    TlumaczDyscyplin.objects.get_or_create(
        dyscyplina_w_bpp=d,
        pbn_2017_2021=dyscyplina_pbn,
        pbn_2022_2023=dyscyplina_pbn,
        pbn_2024_now=dyscyplina_pbn,
    )
    return d


@pytest.fixture
def dyscyplina1(db, pbn_dyscyplina1):
    return _dyscyplina_maker(
        nazwa="memetyka stosowana", kod="3.1", dyscyplina_pbn=pbn_dyscyplina1
    )


@pytest.fixture
def dyscyplina1_hst(db, pbn_dyscyplina1_hst):
    return _dyscyplina_maker(
        nazwa="nauka teologiczna", kod="7.1", dyscyplina_pbn=pbn_dyscyplina1_hst
    )


@pytest.fixture
def dyscyplina2(db, pbn_dyscyplina2):
    return _dyscyplina_maker(
        nazwa="druga dyscyplina", kod="2.2", dyscyplina_pbn=pbn_dyscyplina2
    )


# Import Playwright fixtures
from fixtures.playwright_fixtures import (  # noqa
    admin_page,
    preauth_asgi_page,
    preauth_page,
)
