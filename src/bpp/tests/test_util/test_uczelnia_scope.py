import pytest
from model_bakery import baker

from bpp.models import Rekord
from bpp.util.uczelnia_scope import scope_rekord_do_uczelni, tylko_jedna_uczelnia


@pytest.mark.django_db
def test_tylko_jedna_uczelnia_true_dla_jednej(uczelnia1):
    assert tylko_jedna_uczelnia() is True


@pytest.mark.django_db
def test_tylko_jedna_uczelnia_false_dla_dwoch(uczelnia1, uczelnia2):
    assert tylko_jedna_uczelnia() is False


@pytest.mark.django_db
def test_scope_none_uczelnia_zwraca_qs_bez_zmian(uczelnia1):
    qs = Rekord.objects.all()
    assert scope_rekord_do_uczelni(qs, None) is qs


@pytest.mark.django_db
def test_scope_single_install_short_circuit(uczelnia1):
    qs = Rekord.objects.all()
    assert scope_rekord_do_uczelni(qs, uczelnia1) is qs


@pytest.mark.django_db
def test_scope_dwie_uczelnie_filtruje(
    uczelnia1,
    uczelnia2,
    jednostka_uczelnia1,
    jednostka_uczelnia2,
    autor_uczelnia1,
    autor_uczelnia2,
    typy_odpowiedzialnosci,
):
    w1 = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="MOJA")
    w1.dodaj_autora(autor_uczelnia1, jednostka_uczelnia1)
    w2 = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="OBCA")
    w2.dodaj_autora(autor_uczelnia2, jednostka_uczelnia2)

    tytuly = set(
        scope_rekord_do_uczelni(Rekord.objects.all(), uczelnia1).values_list(
            "tytul_oryginalny", flat=True
        )
    )
    assert "MOJA" in tytuly
    assert "OBCA" not in tytuly
