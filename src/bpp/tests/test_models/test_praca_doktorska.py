import pytest
from model_bakery import baker

from bpp.models import Autor, Praca_Doktorska, Praca_Habilitacyjna, Tytul


@pytest.mark.django_db
@pytest.mark.parametrize("klass", [Praca_Doktorska, Praca_Habilitacyjna])
def test_autor_bez_tytulu(klass, typy_odpowiedzialnosci):
    "Upewnij się, że tytuł autora nie wchodzi do opisu pracy doktorskiej"
    t = baker.make(Tytul, nazwa="profesor doktor", skrot="prof. dr")
    a = baker.make(Autor, imiona="Test", nazwisko="Foo", tytul=t)
    p = baker.make(klass, autor=a)
    assert "prof. dr" not in p.opis_bibliograficzny().lower()
