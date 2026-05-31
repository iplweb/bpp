import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.struktura import Jednostka
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from nowe_raporty.views import (
    GenerujRaportDlaAutora,
    zastosuj_filtry_zaawansowane,
)


@pytest.fixture
def autor_z_pracami(typy_odpowiedzialnosci):
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor = baker.make(Autor)
    wc_low = baker.make(Wydawnictwo_Ciagle, punkty_kbn=5, rok=2020)
    wc_high = baker.make(Wydawnictwo_Ciagle, punkty_kbn=20, rok=2020)
    wc_low.dodaj_autora(autor, jednostka, zapisany_jako="A")
    wc_high.dodaj_autora(autor, jednostka, zapisany_jako="A")
    return autor


@pytest.mark.django_db
def test_zastosuj_filtry_zaawansowane(autor_z_pracami):
    qs = Rekord.objects.prace_autora(autor_z_pracami)
    assert qs.count() == 2

    assert zastosuj_filtry_zaawansowane(qs, {}).count() == 2
    assert zastosuj_filtry_zaawansowane(qs, {"punkty_mnisw_od": "10"}).count() == 1
    assert zastosuj_filtry_zaawansowane(qs, {"punkty_mnisw_do": "10"}).count() == 1
    assert zastosuj_filtry_zaawansowane(qs, {"tylko_punktowane": "True"}).count() == 2
    # bledne/puste wartosci ignorowane
    assert zastosuj_filtry_zaawansowane(qs, {"punkty_mnisw_od": ""}).count() == 2
    assert zastosuj_filtry_zaawansowane(qs, {"punkty_mnisw_od": "abc"}).count() == 2


@pytest.mark.django_db
def test_filtr_zaawansowany_zaweza_raport(rf, autor_z_pracami):
    baker.make("flexible_reports.Report", slug="raport-autorow")
    v = GenerujRaportDlaAutora(kwargs=dict(od_roku=2020, do_roku=2020))
    v.object = autor_z_pracami
    v.request = rf.get("/", data={"_tzju": "False", "punkty_mnisw_od": "10"})

    ret = v.get_context_data()
    assert ret["report"].base_queryset.count() == 1


@pytest.mark.django_db
def test_eksport_bez_definicji_raportu_nie_500(generuj_raporty_app, jednostka):
    # Brak Report + ?_export=docx nie moze konczyc sie 500 (zaleglosc tematu 1).
    url = reverse("nowe_raporty:jednostka_generuj", args=(jednostka.pk, 2020, 2020))
    res = generuj_raporty_app.get(url + "?_export=docx")
    assert res.status_code == 200
    assert "Nie znaleziono definicji" in res.text
