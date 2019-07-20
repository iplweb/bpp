import pytest
from django.urls import reverse

from bpp.models import Autor_Dyscyplina
from rozbieznosci_dyscyplin.models import RozbieznosciView


@pytest.mark.django_db
def test_lista_autorow(client, autor_jan_kowalski, autor_jan_nowak, dyscyplina1,
                       wydawnictwo_ciagle, rok, jednostka):
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1)

    wydawnictwo_ciagle.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    url = reverse("przypisywanie_dyscyplin:main-view")
    res = client.get(url)

    assert ('Nowak' not in res.rendered_content)
    assert ('Kowalski' in res.rendered_content)


@pytest.mark.django_db
def test_znajdz_rozbieznosci(autor_jan_kowalski, jednostka, dyscyplina1, dyscyplina2, dyscyplina3,
                             wydawnictwo_ciagle, rok):
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2
    )

    wca = wydawnictwo_ciagle.dodaj_autora(
        autor_jan_kowalski,
        jednostka,
        dyscyplina_naukowa=dyscyplina1)

    assert RozbieznosciView.objects.count() == 0

    wca.dyscyplina_naukowa = dyscyplina2
    wca.save()

    assert RozbieznosciView.objects.count() == 0

    wca.dyscyplina_naukowa = dyscyplina3
    wca.save()

    assert RozbieznosciView.objects.first().autor == autor_jan_kowalski

    wca.dyscyplina_naukowa = None
    wca.save()

    assert RozbieznosciView.objects.first().autor == autor_jan_kowalski
