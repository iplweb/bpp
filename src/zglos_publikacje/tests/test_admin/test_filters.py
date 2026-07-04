from model_bakery import baker

from bpp.models import Typ_Odpowiedzialnosci
from zglos_publikacje.admin.filters import WydzialJednostkiPierwszegoAutora
from zglos_publikacje.models import Zgloszenie_Publikacji


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

    # Django 5.0+ SimpleListFilter expects params as dict[str, list]
    # (matches QueryDict.lists() from real requests). Passing a plain
    # string makes __init__ do `value[-1]`, which silently returns the
    # last character of the string instead of the last list element.
    # Faza B (#438): filtr listuje jednostki-korzenie; „wydział" 1-go autora to
    # korzeń jego jednostki (węzeł-lustro), nie obiekt Wydzial.
    root = aktualna_jednostka.wydzial
    params = {"wydz1a": [str(root.pk)]}
    req = rf.get("/", {"wydz1a": str(root.pk)})
    filtr = WydzialJednostkiPierwszegoAutora(req, params, Zgloszenie_Publikacji, None)
    qs = filtr.queryset(req, Zgloszenie_Publikacji.objects.all())
    assert qs.count() == 1

    # Wydział, w którym 1-szy autor NIE jest → 0 (węzeł-lustro pustego wydziału).
    from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu

    drugi_root = znajdz_lub_utworz_wezel_wydzialu(drugi_wydzial)[0]
    params = {"wydz1a": [str(drugi_root.pk)]}
    req = rf.get("/", {"wydz1a": str(drugi_root.pk)})
    filtr = WydzialJednostkiPierwszegoAutora(req, params, Zgloszenie_Publikacji, None)
    qs = filtr.queryset(req, Zgloszenie_Publikacji.objects.all())
    assert qs.count() == 0
