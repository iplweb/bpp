"""Track 1 (audyt uczelnia 2026-06-04): profil użytkownika pokazuje metryki
TYLKO z uczelni oglądającego (tej z requestu).

``ProfilUzytkownikaView`` robił ``MetrykaAutora.objects.filter(autor=autor)``
bez zawężenia — autor afiliowany do >1 uczelni widział na profilu metryki ze
WSZYSTKICH uczelni (przeoczenie wątku D, który objął tylko ``ewaluacja_metryki/
views/``, nie profil w ``bpp/views/``).
"""

from decimal import Decimal

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

    # MetrykaAutora.save() PRZELICZA pola pochodne z pól slotów/punktów:
    #   srednia_za_slot_* = punkty_* / slot_*
    #   procent_wykorzystania_slotow = (slot_nazbierany / slot_maksymalny) * 100
    # Losowe wartości baker-a (DecimalField(10,4), niezależne) potrafią dać iloraz
    # przepełniający procent (DecimalField(5,2), < 10^3) albo średnią — stąd flaky
    # NumericValueOutOfRange zależny od seeda/sharda. Pinujemy pola WEJŚCIOWE do
    # zdrowych wartości; test i tak nie patrzy na liczby, tylko na zawężenie po
    # uczelni.
    metryka_pola = dict(
        slot_maksymalny=Decimal("10.0000"),
        slot_nazbierany=Decimal("5.0000"),
        punkty_nazbierane=Decimal("50.0000"),
        slot_wszystkie=Decimal("10.0000"),
        punkty_wszystkie=Decimal("50.0000"),
    )
    baker.make(
        MetrykaAutora,
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        uczelnia=uczelnia,
        **metryka_pola,
    )
    baker.make(
        MetrykaAutora,
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        uczelnia=druga_uczelnia_profile,
        **metryka_pola,
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
