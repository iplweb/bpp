import pytest
from model_bakery import baker

from bpp.models import Typ_Odpowiedzialnosci
from zglos_publikacje.admin.filters import WydzialJednostkiPierwszegoAutora
from zglos_publikacje.models import Zgloszenie_Publikacji


# Flake under xdist: passes 100% in isolation but occasionally hits a
# zombie Postgres connection when another xdist worker recycles the DB.
# Two reruns are cheap and turn a ~1/10 failure into ~1/1000.
@pytest.mark.flaky(reruns=2, reruns_delay=1)
def test_WydzialJednostkiPierwszegoAutora_queryset(
    aktualna_jednostka,
    druga_aktualna_jednostka,
    wydzial,
    drugi_wydzial,
    autor_jan_kowalski,
    autor_jan_nowak,
    typy_odpowiedzialnosci,
    rf,
):
    zgloszenie = baker.make(Zgloszenie_Publikacji)
    zgloszenie.zgloszenie_publikacji_autor_set.create(
        autor=autor_jan_kowalski,
        jednostka=aktualna_jednostka,
        kolejnosc=0,
        typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.first(),
        rok=2022,
    )
    zgloszenie.zgloszenie_publikacji_autor_set.create(
        autor=autor_jan_nowak,
        jednostka=druga_aktualna_jednostka,
        kolejnosc=1,
        typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.first(),
        rok=2022,
    )

    params = {"wydz1a": str(wydzial.pk)}
    req = rf.get("/", params)
    filtr = WydzialJednostkiPierwszegoAutora(req, params, Zgloszenie_Publikacji, None)
    qs = filtr.queryset(req, Zgloszenie_Publikacji.objects.all())
    assert qs.count() == 1

    params = {"wydz1a": str(drugi_wydzial.pk)}
    req = rf.get("/", params)
    filtr = WydzialJednostkiPierwszegoAutora(req, params, Zgloszenie_Publikacji, None)
    qs = filtr.queryset(req, Zgloszenie_Publikacji.objects.all())
    assert qs.count() == 0
