"""Track 3 (audyt uczelnia 2026-06-04): wydruk oświadczeń 2022-25 zawężony do
uczelni oglądającego.

``get_base_queryset`` / ``build_queryset_for_task`` budowały qs ``Autorzy`` tylko
po roku/autorze/tytule/dyscyplinie — bez ``jednostka__uczelnia`` → admin uczelni
U1 widział/eksportował oświadczenia autorów uczelni U2 (przeciek cross-uczelnia).
"""

import pytest
from django.contrib.sites.models import Site
from model_bakery import baker

from bpp.models import (
    Autor_Dyscyplina,
    Jednostka,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydzial,
)
from oswiadczenia.views import WydrukOswiadczen2022View


@pytest.fixture
def jednostka_drugiej_uczelni(db):
    site = baker.make(Site, domain="druga-osw.testserver", name="druga-osw")
    uczelnia2 = Uczelnia.objects.create(skrot="DR2", nazwa="Druga uczelnia", site=site)
    wydzial = Wydzial.objects.create(uczelnia=uczelnia2, skrot="W2", nazwa="Wydział II")
    return Jednostka.objects.create(
        nazwa="Jedn. Drugiej Ucz.", skrot="JDU2", wydzial=wydzial, uczelnia=uczelnia2
    )


@pytest.mark.django_db
def test_wydruk_oswiadczen_zaweza_do_uczelni_ogladajacego(
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    jednostka_drugiej_uczelni,
    dyscyplina1,
    denorms,
    typy_odpowiedzialnosci,
    charaktery_formalne,
    rf,
):
    uczelnia1 = jednostka.uczelnia

    # Kowalski → U1, Nowak → U2; obaj z dyscypliną, rok w zakresie 2022-25.
    for autor in (autor_jan_kowalski, autor_jan_nowak):
        Autor_Dyscyplina.objects.create(
            autor=autor, rok=2023, dyscyplina_naukowa=dyscyplina1
        )
    wc1 = baker.make(Wydawnictwo_Ciagle, rok=2023, punkty_kbn=5)
    wc1.dodaj_autora(autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina1)
    wc2 = baker.make(Wydawnictwo_Ciagle, rok=2023, punkty_kbn=5)
    wc2.dodaj_autora(
        autor_jan_nowak, jednostka_drugiej_uczelni, dyscyplina_naukowa=dyscyplina1
    )
    denorms.flush()

    request = rf.get("/")
    request._uczelnia = uczelnia1

    view = WydrukOswiadczen2022View()
    view.request = request

    autor_ids = set(view.get_queryset().values_list("autor_id", flat=True))

    assert autor_jan_kowalski.id in autor_ids  # U1 — widoczny
    assert autor_jan_nowak.id not in autor_ids  # U2 — NIE przecieka
