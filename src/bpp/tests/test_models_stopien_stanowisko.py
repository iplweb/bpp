import pytest
from model_bakery import baker

from bpp.models import (
    Autor,
    Autor_Jednostka,
    StanowiskoDydaktyczne,
    StopienSluzbowy,
)


@pytest.mark.django_db
def test_stopien_sluzbowy_str_i_verbose_name():
    s = baker.make(StopienSluzbowy, nazwa="kapitan", skrot="kpt.")
    assert str(s) == "kapitan"
    assert s._meta.verbose_name == "stopień służbowy"
    assert s._meta.verbose_name_plural == "stopnie służbowe"


@pytest.mark.django_db
def test_stanowisko_dydaktyczne_str_i_verbose_name():
    s = baker.make(StanowiskoDydaktyczne, nazwa="adiunkt", skrot="adiunkt")
    assert str(s) == "adiunkt"
    assert s._meta.verbose_name == "stanowisko dydaktyczne"
    assert s._meta.verbose_name_plural == "stanowiska dydaktyczne"


@pytest.mark.django_db
def test_autor_ma_stopien_sluzbowy():
    st = baker.make(StopienSluzbowy, nazwa="brygadier", skrot="bryg.")
    a = baker.make(Autor, stopien_sluzbowy=st)
    a.refresh_from_db()
    assert a.stopien_sluzbowy == st


@pytest.mark.django_db
def test_autor_jednostka_ma_stanowisko():
    sd = baker.make(StanowiskoDydaktyczne, nazwa="profesor", skrot="prof.")
    aj = baker.make(Autor_Jednostka, stanowisko=sd)
    aj.refresh_from_db()
    assert aj.stanowisko == sd


@pytest.mark.django_db
def test_stopien_set_null_po_skasowaniu_slownika():
    st = baker.make(StopienSluzbowy, nazwa="starszy strażak", skrot="st. str.")
    a = baker.make(Autor, stopien_sluzbowy=st)
    st.delete()
    a.refresh_from_db()
    assert a.stopien_sluzbowy is None
