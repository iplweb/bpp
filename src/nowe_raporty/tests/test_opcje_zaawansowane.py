import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.struktura import Jednostka
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from nowe_raporty.seeding import seed_default_reports
from nowe_raporty.views import zastosuj_filtry_zaawansowane


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
    # Filtr zaawansowany (punkty_mnisw_od) zaweza queryset raportu - przez
    # generyczny RaportGenerujView + zaseedowana DefinicjaRaportu.
    from nowe_raporty.models import DefinicjaRaportu
    from nowe_raporty.views import RaportGenerujView

    seed_default_reports()
    definicja = DefinicjaRaportu.objects.get(slug="raport-autorow")

    v = RaportGenerujView()
    v.kwargs = dict(slug=definicja.slug, od_roku=2020, do_roku=2020)
    v.object = autor_z_pracami
    v.request = rf.get("/", data={"_tzju": "False", "punkty_mnisw_od": "10"})

    ret = v.get_context_data()
    assert ret["report"].base_queryset.count() == 1


@pytest.mark.django_db
def test_walidatory_zakresu_lat_dopiete(autor_z_pracami):
    # Regresja: walidatory rok-min/rok-max muszą być faktycznie dopięte do pól
    # (były martwym kodem po return w _wiersze_zaawansowane).
    from nowe_raporty.forms import form_class_dla
    from nowe_raporty.models import DefinicjaRaportu

    definicja = baker.make(
        DefinicjaRaportu, slug="r-walidacja", poziom=DefinicjaRaportu.POZIOM_AUTOR
    )
    form = form_class_dla(definicja)(
        data={
            "obiekt": autor_z_pracami.pk,
            "od_roku": 1900,  # poniżej min (rekordy są z 2020)
            "do_roku": 2020,
            "_export": "html",
            "tylko_z_jednostek_uczelni": False,
        }
    )
    assert not form.is_valid()
    assert "od_roku" in form.errors


@pytest.mark.django_db
def test_eksport_raportu_nie_500(generuj_raporty_app, autor, rok):
    # Eksport zaseedowanego raportu (?_export=docx) renderuje sie bez 500.
    seed_default_reports()
    url = reverse(
        "nowe_raporty:raport_generuj", args=("raport-autorow", autor.pk, rok, rok)
    )
    res = generuj_raporty_app.get(url + "?_export=docx")
    assert res.status_code == 200
