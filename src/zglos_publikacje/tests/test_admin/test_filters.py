from model_bakery import baker

from zglos_publikacje.admin.filters import WydzialJednostkiPierwszegoAutora
from zglos_publikacje.models import Zgloszenie_Publikacji

from bpp.models import Typ_Odpowiedzialnosci


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
