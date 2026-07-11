import pytest
from model_bakery import baker
from rest_framework.test import APIRequestFactory

from api_v1.serializers.zapytanie import (
    AutorKompaktSerializer,
    AutorzyKompaktSerializer,
)
from bpp.models import Tytul


@pytest.mark.django_db
def test_autor_kompakt_ma_plaskie_pola():
    # "prof." istnieje już w danych referencyjnych baseline (bpp_tytul.skrot
    # ma unique=True) — get_or_create zamiast baker.make, żeby nie kolidować.
    tytul, _ = Tytul.objects.get_or_create(
        skrot="prof.", defaults={"nazwa": "profesor"}
    )
    jedn = baker.make("bpp.Jednostka", nazwa="Kardiologii")
    autor = baker.make(
        "bpp.Autor",
        nazwisko="Kowalski",
        imiona="Jan",
        tytul=tytul,
        aktualna_jednostka=jedn,
        orcid="0000-0001",
    )
    req = APIRequestFactory().get("/")
    data = AutorKompaktSerializer(autor, context={"request": req}).data
    assert data["nazwisko"] == "Kowalski"
    assert data["tytul"] == "prof."
    assert data["aktualna_jednostka"] == "Kardiologii"
    assert data["orcid"] == "0000-0001"
    assert data["autor_url"].endswith(f"/autor/{autor.pk}/")
    assert isinstance(data["absolute_url"], str)


@pytest.mark.django_db
def test_autor_kompakt_bez_tytulu_i_jednostki():
    autor = baker.make(
        "bpp.Autor", nazwisko="Nowak", tytul=None, aktualna_jednostka=None
    )
    req = APIRequestFactory().get("/")
    data = AutorKompaktSerializer(autor, context={"request": req}).data
    assert data["tytul"] == ""
    assert data["aktualna_jednostka"] is None
