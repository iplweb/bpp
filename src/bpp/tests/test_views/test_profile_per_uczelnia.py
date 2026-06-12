"""Track 1 (audyt uczelnia 2026-06-04): profil użytkownika pokazuje metryki
TYLKO z uczelni oglądającego (tej z requestu).

``ProfilUzytkownikaView`` robił ``MetrykaAutora.objects.filter(autor=autor)``
bez zawężenia — autor afiliowany do >1 uczelni widział na profilu metryki ze
WSZYSTKICH uczelni (przeoczenie wątku D, który objął tylko ``ewaluacja_metryki/
views/``, nie profil w ``bpp/views/``).
"""

import pytest
from django.contrib.sites.models import Site
from model_bakery import baker

from bpp.models import Uczelnia
from bpp.views.profile import ProfilUzytkownikaView


@pytest.fixture
def druga_uczelnia_profile(db):
    site = baker.make(Site, domain="druga-prof.testserver", name="druga-prof")
    return Uczelnia.objects.create(skrot="DRP", nazwa="Druga", site=site)


@pytest.mark.django_db
def test_profil_metryki_zaweza_do_uczelni_ogladajacego(
    autor_jan_kowalski, uczelnia, druga_uczelnia_profile, dyscyplina1, rf
):
    from ewaluacja_metryki.models import MetrykaAutora

    baker.make(
        MetrykaAutora,
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        uczelnia=uczelnia,
    )
    baker.make(
        MetrykaAutora,
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        uczelnia=druga_uczelnia_profile,
    )

    user = baker.make("bpp.BppUser", autor=autor_jan_kowalski)
    request = rf.get("/")
    request._uczelnia = uczelnia
    request.user = user

    view = ProfilUzytkownikaView()
    view.request = request
    view.kwargs = {}

    ctx = view.get_context_data()
    uczelnia_ids = set(ctx["metryki"].values_list("uczelnia_id", flat=True))

    assert uczelnia_ids == {uczelnia.pk}
