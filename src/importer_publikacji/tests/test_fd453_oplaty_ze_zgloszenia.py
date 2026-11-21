"""FD#453 -- fee declaration from a submission reaches the imported record.

The author declares in the "Zgłoś publikację" form that the work was
cost-free (or which funds paid for it and how much). When the operator
creates the record with the publication importer from a session bound to
that submission, the declaration must end up on the created
``Wydawnictwo_Ciagle``/``Wydawnictwo_Zwarte``.
"""

from decimal import Decimal

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from importer_publikacji.models import ImportSession
from importer_publikacji.views import _create_publication
from zglos_publikacje.models import Zgloszenie_Publikacji

TYTUL = "Under the Salon Lights: Assessment of Occupational Exposure to PAHs"
DOI = "10.1234/fd453.oplaty"


def _zgl(**oplaty):
    return baker.make(
        Zgloszenie_Publikacji,
        doi=DOI,
        tytul_oryginalny=TYTUL,
        status=Zgloszenie_Publikacji.Statusy.NOWY,
        rok=2026,
        rodzaj_zglaszanej_publikacji=1,
        **oplaty,
    )


@pytest.fixture
def sesja(importer_user, jezyki, charaktery_formalne, typy_kbn, statusy_korekt):
    from bpp.models import Typ_KBN

    def _make(zgloszenie=None, zwarte=False):
        return ImportSession.objects.create(
            created_by=importer_user,
            provider_name="CrossRef",
            identifier=DOI,
            raw_data={},
            normalized_data={
                "title": TYTUL,
                "doi": DOI,
                "year": 2026,
                "authors": [],
                "keywords": [],
                "abstracts": [],
            },
            charakter_formalny=charaktery_formalne["AC"],
            typ_kbn=Typ_KBN.objects.get(skrot="PO"),
            jezyk=jezyki["pol."],
            jest_wydawnictwem_zwartym=zwarte,
            zgloszenie=zgloszenie,
        )

    return _make


@pytest.mark.django_db
def test_bezkosztowosc_ze_zgloszenia_trafia_do_rekordu(sesja):
    zgl = _zgl(
        opl_pub_cost_free=True,
        opl_pub_research_potential=False,
        opl_pub_research_or_development_projects=False,
        opl_pub_other=False,
        opl_pub_amount=None,
    )

    record = _create_publication(sesja(zgloszenie=zgl))

    record = Wydawnictwo_Ciagle.objects.get(pk=record.pk)
    assert record.opl_pub_cost_free is True
    assert record.opl_pub_research_potential is False
    assert record.opl_pub_research_or_development_projects is False
    assert record.opl_pub_other is False
    assert record.opl_pub_amount is None


@pytest.mark.django_db
def test_platna_publikacja_kwota_i_zrodla_trafiaja_do_rekordu(sesja):
    zgl = _zgl(
        opl_pub_cost_free=False,
        opl_pub_research_potential=True,
        opl_pub_research_or_development_projects=False,
        opl_pub_other=True,
        opl_pub_amount=Decimal("1234.56"),
    )

    record = _create_publication(sesja(zgloszenie=zgl))

    record = Wydawnictwo_Ciagle.objects.get(pk=record.pk)
    assert record.opl_pub_cost_free is False
    assert record.opl_pub_research_potential is True
    assert record.opl_pub_research_or_development_projects is False
    assert record.opl_pub_other is True
    assert record.opl_pub_amount == Decimal("1234.56")


@pytest.mark.django_db
def test_oplaty_ze_zgloszenia_dla_wydawnictwa_zwartego(sesja):
    zgl = _zgl(opl_pub_cost_free=True, opl_pub_amount=Decimal("0"))

    record = _create_publication(sesja(zgloszenie=zgl, zwarte=True))

    record = Wydawnictwo_Zwarte.objects.get(pk=record.pk)
    assert record.opl_pub_cost_free is True
    assert record.opl_pub_amount == Decimal("0")


@pytest.mark.django_db
def test_bez_zwiazanego_zgloszenia_oplaty_puste(sesja):
    """The title heuristic does NOT attach a fee declaration.

    A submission with the same title exists, but the session is not bound
    to it -- the record must not inherit someone else's fee declaration.
    """
    _zgl(opl_pub_cost_free=True)

    record = _create_publication(sesja(zgloszenie=None))

    record = Wydawnictwo_Ciagle.objects.get(pk=record.pk)
    assert record.opl_pub_cost_free is None
    assert record.opl_pub_amount is None


@pytest.mark.django_db
def test_soft_usuniete_zgloszenie_nie_przekazuje_oplat(sesja):
    zgl = _zgl(opl_pub_cost_free=True)
    session = sesja(zgloszenie=zgl)
    # The trash does not cascade: the session still points at the submission.
    zgl.delete(reason="test")
    session = ImportSession.objects.get(pk=session.pk)

    record = _create_publication(session)

    record = Wydawnictwo_Ciagle.objects.get(pk=record.pk)
    assert record.opl_pub_cost_free is None
