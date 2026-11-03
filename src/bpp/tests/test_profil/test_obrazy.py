"""Testy przetwarzania zdjęcia autora (Pillow → kwadrat WebP 400x400)."""

import io

import pytest
from PIL import Image

from bpp.util.obrazy import ROZMIAR_ZDJECIA_AUTORA, przetworz_zdjecie_autora


def _obraz(w, h, kolor=(10, 20, 30), format="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), kolor).save(buf, format=format)
    buf.seek(0)
    return buf


def test_skaluje_do_kwadratu():
    wynik = przetworz_zdjecie_autora(_obraz(600, 800))
    assert Image.open(wynik).size == (
        ROZMIAR_ZDJECIA_AUTORA,
        ROZMIAR_ZDJECIA_AUTORA,
    )


def test_zapisuje_jako_webp():
    wynik = przetworz_zdjecie_autora(_obraz(500, 500))
    assert Image.open(wynik).format == "WEBP"


def test_szeroki_obraz_przyciety_do_kwadratu():
    wynik = przetworz_zdjecie_autora(_obraz(1000, 200))
    assert Image.open(wynik).size == (
        ROZMIAR_ZDJECIA_AUTORA,
        ROZMIAR_ZDJECIA_AUTORA,
    )


def test_nazwa_pliku_konczy_sie_webp():
    wynik = przetworz_zdjecie_autora(_obraz(400, 400), nazwa="moje zdjecie.png")
    assert wynik.name.endswith(".webp")


def test_obraz_z_alfa_jest_obslugiwany():
    buf = io.BytesIO()
    Image.new("RGBA", (500, 500), (10, 20, 30, 128)).save(buf, format="PNG")
    buf.seek(0)
    wynik = przetworz_zdjecie_autora(buf)
    assert Image.open(wynik).size == (
        ROZMIAR_ZDJECIA_AUTORA,
        ROZMIAR_ZDJECIA_AUTORA,
    )


def test_niepoprawny_plik_rzuca_blad_walidacji():
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        przetworz_zdjecie_autora(io.BytesIO(b"to nie jest obraz"))
