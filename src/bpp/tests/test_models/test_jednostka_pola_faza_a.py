import pytest
from model_bakery import baker

from bpp.models import Jednostka


def test_defaulty_nowych_pol():
    # baker losowo wypełnia BooleanField — default testujemy przez _meta.
    assert Jednostka._meta.get_field("zezwalaj_na_ranking_autorow").default is True
    assert Jednostka._meta.get_field("poprzednie_nazwy").default == ""


@pytest.mark.django_db
def test_pola_nullowalne_domyslnie_puste():
    # Faza C (#438): ``legacy_wydzial_id`` usunięty (migracja 0468); zostaje
    # ``skrot_nazwy`` jako nullowalne pole Fazy A.
    j = baker.make(Jednostka, skrot_nazwy=None)
    j.refresh_from_db()
    assert j.skrot_nazwy is None


@pytest.mark.django_db
def test_slug_przyjmuje_dluga_nazwe():
    # Projekt ma globalny custom generator baker dla AutoSlugField
    # (BAKER_CUSTOM_FIELDS_GEN w settings/base.py), który zawsze losuje
    # gotowy 50-znakowy slug — a autoslug populate_from działa tylko, gdy
    # pole jest w chwili zapisu puste. Podajemy więc slug="" jawnie, żeby
    # wymusić realne wyliczenie sluga z (długiej) nazwy.
    dluga = "Wydział " + "x" * 200
    j = baker.make(Jednostka, nazwa=dluga, slug="")
    j.refresh_from_db()
    assert len(j.slug) > 50  # nie ucięte do 50
