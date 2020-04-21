from model_mommy import mommy

from bpp.models import Tytul, Autor, Praca_Doktorska, Praca_Habilitacyjna

import pytest


@pytest.mark.django_db
@pytest.mark.parametrize("klass", [Praca_Doktorska, Praca_Habilitacyjna])
def test_autor_bez_tytulu(klass, typy_odpowiedzialnosci):
    "Upewnij się, że tytuł autora nie wchodzi do opisu pracy doktorskiej"
    t = mommy.make(Tytul, nazwa="profesor doktor", skrot="prof. dr")
    a = mommy.make(Autor, imiona="Test", nazwisko="Foo", tytul=t)
    p = mommy.make(klass, autor=a)
    assert "prof. dr" not in p.opis_bibliograficzny().lower()
