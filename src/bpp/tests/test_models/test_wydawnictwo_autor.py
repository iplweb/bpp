import pytest
from django.core.exceptions import ValidationError
from model_bakery import baker

from bpp.models import (
    Patent,
    Patent_Autor,
    RodzajJednostki,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)


@pytest.fixture(params=["wydawnictwo_zwarte", "wydawnictwo_ciagle", "patent"])
def rekord_wydawniczy(request):
    return request.getfixturevalue(request.param)


@pytest.mark.django_db
def test_autor_jednostka_afiliuje_na_obca(
    autor_jan_kowalski, obca_jednostka, rekord_wydawniczy
):
    from django.conf import settings

    assert getattr(settings, "BPP_WALIDUJ_AFILIACJE_AUTOROW", True)

    with pytest.raises(ValidationError):
        rekord_wydawniczy.dodaj_autora(
            autor_jan_kowalski, obca_jednostka, afiliuje=True
        )

    obca_jednostka.skupia_pracownikow = True
    obca_jednostka.save()
    rekord_wydawniczy.dodaj_autora(autor_jan_kowalski, obca_jednostka, afiliuje=True)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "w,r",
    [
        (Wydawnictwo_Zwarte_Autor, Wydawnictwo_Zwarte),
        (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Ciagle),
        (Patent_Autor, Patent),
    ],
)
def test_autor_jednostka_afiliuje_bug(autor_jan_kowalski, obca_jednostka, w, r):
    ri = baker.make(r)
    wi = w(autor=autor_jan_kowalski, jednostka=None, rekord=ri)
    wi.clean()


@pytest.mark.django_db
def test_autor_afiliuje_na_rodzaj_bez_afiliacji(
    autor_jan_kowalski, jednostka, rekord_wydawniczy
):
    """#438: jednostka rodzaju z ``autor_moze_afiliowac=False`` (np. „Wydział")
    nie przyjmuje afiliacji — analogicznie do obcej jednostki; przypisanie
    BEZ afiliacji pozostaje dozwolone."""
    rodzaj = baker.make(RodzajJednostki, autor_moze_afiliowac=False)
    jednostka.rodzaj = rodzaj
    jednostka.save()

    with pytest.raises(ValidationError):
        rekord_wydawniczy.dodaj_autora(autor_jan_kowalski, jednostka, afiliuje=True)

    rekord_wydawniczy.dodaj_autora(autor_jan_kowalski, jednostka, afiliuje=False)


@pytest.mark.django_db
def test_autor_afiliuje_na_rodzaj_dopuszczajacy_afiliacje(
    autor_jan_kowalski, jednostka, rekord_wydawniczy
):
    rodzaj = baker.make(RodzajJednostki, autor_moze_afiliowac=True)
    jednostka.rodzaj = rodzaj
    jednostka.save()

    rekord_wydawniczy.dodaj_autora(autor_jan_kowalski, jednostka, afiliuje=True)
