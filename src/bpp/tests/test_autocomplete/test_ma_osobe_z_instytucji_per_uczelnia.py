"""Track 7a: wskaźnik ``ma_osobe_z_instytucji`` zawężony do uczelni z requestu.

Adnotacja ``Exists(OsobaZInstytucji.objects.filter(personId=...))`` w
autocomplete autorów powinna odzwierciedlać instytucję PBN OGLĄDAJĄCEJ
uczelni (``request._uczelnia.pbn_uid``), nie dowolnej instytucji.
"""

import pytest
from model_bakery import baker

from fixtures.conftest_multisite import make_request_for_site


@pytest.mark.django_db
def test_ma_osobe_z_instytucji_scoped_to_viewing_uczelnia(
    uczelnia1, uczelnia2, settings
):
    settings.ALLOWED_HOSTS = ["*"]
    from bpp.views.autocomplete.authors import AutorAutocompleteBase
    from pbn_api.models import Institution, OsobaZInstytucji, Scientist

    inst1 = baker.make(Institution, name="Inst U1")
    inst2 = baker.make(Institution, name="Inst U2")
    uczelnia1.pbn_uid = inst1
    uczelnia1.save()
    uczelnia2.pbn_uid = inst2
    uczelnia2.save()

    sci_in_u2 = baker.make(Scientist)
    sci_in_u1_only = baker.make(Scientist)

    autor_u2 = baker.make("bpp.Autor", pbn_uid_id=sci_in_u2.pk)
    autor_u1_only = baker.make("bpp.Autor", pbn_uid_id=sci_in_u1_only.pk)

    # OsobaZInstytucji autora U2 jest w instytucji U2, autora "U1-only" w U1.
    baker.make(OsobaZInstytucji, personId=sci_in_u2, institutionId=inst2)
    baker.make(OsobaZInstytucji, personId=sci_in_u1_only, institutionId=inst1)

    # Request oglądany jako uczelnia2 (jej site).
    view = AutorAutocompleteBase()
    view.request = make_request_for_site(uczelnia2.site)
    view.q = ""

    qs = view.get_queryset()
    by_pk = {a.pk: a for a in qs}

    # Autor w instytucji U2 → oznaczony; autor tylko w U1 → NIE oznaczony.
    assert by_pk[autor_u2.pk].ma_osobe_z_instytucji is True
    assert by_pk[autor_u1_only.pk].ma_osobe_z_instytucji is False


@pytest.mark.django_db
def test_ma_osobe_z_instytucji_global_without_pbn_uid(uczelnia, settings):
    """Bez ``pbn_uid`` uczelni → subquery globalne (dawne zachowanie)."""
    settings.ALLOWED_HOSTS = ["*"]
    from django.test import RequestFactory

    from bpp.views.autocomplete.authors import AutorAutocompleteBase
    from pbn_api.models import Institution, OsobaZInstytucji, Scientist

    inst = baker.make(Institution)
    sci = baker.make(Scientist)
    autor = baker.make("bpp.Autor", pbn_uid_id=sci.pk)
    baker.make(OsobaZInstytucji, personId=sci, institutionId=inst)

    request = RequestFactory().get("/")
    request._uczelnia = uczelnia  # uczelnia bez pbn_uid

    view = AutorAutocompleteBase()
    view.request = request
    view.q = ""

    qs = view.get_queryset()
    by_pk = {a.pk: a for a in qs}
    # Brak pbn_uid → subquery globalne → autor oznaczony.
    assert by_pk[autor.pk].ma_osobe_z_instytucji is True
