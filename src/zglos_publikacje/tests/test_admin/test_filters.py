import pytest
from model_bakery import baker

from bpp.models import Jednostka, Typ_Odpowiedzialnosci, Uczelnia
from zglos_publikacje.admin.filters import WydzialJednostkiPierwszegoAutora
from zglos_publikacje.models import Zgloszenie_Publikacji


@pytest.mark.django_db
def test_WydzialJednostkiPierwszegoAutora_lapie_autora_przy_samym_korzeniu(
    autor_jan_kowalski,
    typy_odpowiedzialnosci,
    rf,
):
    """F3 (#438): pierwszy autor siedzi w SAMEJ jednostce-korzeniu
    (``wydzial=NULL``). Filtr „wydział 1-go autora" = ten korzeń MUSI złapać
    zgłoszenie. Przed fixem ``Jednostka.objects.filter(wydzial_id=v)`` (bez
    ``| pk=v``) nie zawierał samego korzenia → zgłoszenie CICHO znikało."""
    from denorm import denorms

    u = baker.make(Uczelnia)
    korzen = baker.make(Jednostka, uczelnia=u, parent=None, skupia_pracownikow=True)
    denorms.flush()
    korzen.refresh_from_db()
    assert korzen.wydzial_id is None

    zgloszenie = baker.make(Zgloszenie_Publikacji)
    zgloszenie.zgloszenie_publikacji_autor_set.create(
        autor=autor_jan_kowalski,
        jednostka=korzen,
        kolejnosc=0,
        typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.first(),
        rok=2022,
    )

    params = {"wydz1a": [str(korzen.pk)]}
    req = rf.get("/", {"wydz1a": str(korzen.pk)})
    filtr = WydzialJednostkiPierwszegoAutora(req, params, Zgloszenie_Publikacji, None)
    qs = filtr.queryset(req, Zgloszenie_Publikacji.objects.all())
    assert qs.count() == 1


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

    drugi_root = drugi_wydzial
    params = {"wydz1a": [str(drugi_root.pk)]}
    req = rf.get("/", {"wydz1a": str(drugi_root.pk)})
    filtr = WydzialJednostkiPierwszegoAutora(req, params, Zgloszenie_Publikacji, None)
    qs = filtr.queryset(req, Zgloszenie_Publikacji.objects.all())
    assert qs.count() == 0
