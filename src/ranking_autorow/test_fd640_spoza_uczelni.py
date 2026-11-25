"""FD#640 — ranking autorów pomija autorów spoza uczelni (strona i eksport)."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Wydawnictwo_Ciagle
from ranking_autorow.views import RankingAutorow


@pytest.fixture
def ranking_z_obcym(
    uczelnia_z_obca_jednostka, obca_jednostka, jednostka, typy_odpowiedzialnosci
):
    # typy_odpowiedzialnosci PRZED dodaj_autora: słowniki z post_migrate
    # bywają wyczyszczone przez TRUNCATE wcześniejszych testów transakcyjnych.
    # Domyślnie (``Jednostka.wchodzi_do_rankingu_autorow=True``) obca jednostka
    # wchodzi do widoku sum rankingu — redakcja rzadko to odznacza. Fixture
    # testów ma tę flagę wyłączoną, co maskowało wyciek.
    obca_jednostka.wchodzi_do_rankingu_autorow = True
    obca_jednostka.save()
    nasz = baker.make(Autor, imiona="Jan", nazwisko="Naszrankingowy")
    Autor_Jednostka.objects.create(autor=nasz, jednostka=jednostka)
    obcy = baker.make(Autor, imiona="Ewa", nazwisko="Obcarankingowa")
    Autor_Jednostka.objects.create(autor=obcy, jednostka=obca_jednostka)

    praca = baker.make(Wydawnictwo_Ciagle, rok=2022, impact_factor=10, punkty_kbn=20)
    praca.dodaj_autora(nasz, jednostka)
    praca.dodaj_autora(obcy, obca_jednostka, afiliuje=False)
    return nasz, obcy


def _ranking(rf, **get):
    request = rf.get("/", {"bez_nieaktualnych": "False", **get})
    return RankingAutorow(request=request, kwargs=dict(od_roku=2022, do_roku=2022))


@pytest.mark.django_db
@pytest.mark.parametrize("rozbij", ["True", "False"])
def test_fd640_ranking_pomija_autora_spoza_uczelni(rf, ranking_z_obcym, rozbij):
    nasz, obcy = ranking_z_obcym
    autorzy = {
        row.autor.pk for row in _ranking(rf, rozbij_na_jednostki=rozbij).get_queryset()
    }
    assert nasz.pk in autorzy  # strażnik: autor uczelni bez zmian
    assert obcy.pk not in autorzy


@pytest.mark.django_db
def test_fd640_eksport_rankingu_bez_autora_spoza_uczelni(admin_client, ranking_z_obcym):
    url = reverse("bpp:ranking-autorow", args=(2022, 2022))
    res = admin_client.get(url, {"bez_nieaktualnych": "False", "_export": "csv"})
    assert res.status_code == 200
    tresc = b"".join(res.streaming_content) if res.streaming else res.content
    tresc = tresc.decode("utf-8")
    assert "Naszrankingowy" in tresc
    assert "Obcarankingowa" not in tresc
