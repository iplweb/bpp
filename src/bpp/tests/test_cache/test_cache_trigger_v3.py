"""Testy triggera bpp_refresh_cache() v3 (spec-optymalizacje-wydajnosci-2026-06).

Trzy zachowania:

1. UPDATE publikacji NIE przepisuje wierszy bpp_autorzy_mat (poprzednio
   DELETE na bpp_rekord_mat kaskadował przez FK i wymuszał wipe + re-insert
   wszystkich autorów; v3 robi czysty upsert ON CONFLICT). Sprawdzane po
   xmin — przepisany wiersz dostaje nowe xmin.

2. UPDATE wiersza *_autor zmieniający autor_id in-place aktualizuje
   bpp_autorzy_mat (poprzednio trigger czytał TD["old"] i filtrował widok
   po STARYM autor_id — pusty SELECT, wiersz mat ginął bez następcy).

3. DELETE jednego z dwóch wierszy *_autor tego samego autora (dwie role,
   np. aut. + red.) usuwa z bpp_autorzy_mat tylko ten jeden wiersz
   (poprzednio DELETE po (rekord_id, autor_id) kasował OBA).
"""

import pytest
from django.db import connection
from model_bakery import baker

from bpp.models import (
    Autor,
    Jednostka,
    Praca_Doktorska,
    Rekord,
    Wydawnictwo_Ciagle,
)


def _xmin_autorzy_mat(rekord):
    """Mapa {id_wiersza_mat: xmin} dla wszystkich autorów rekordu."""
    with connection.cursor() as c:
        c.execute(
            "SELECT id, xmin::text FROM bpp_autorzy_mat WHERE rekord_id = %s",
            [list(rekord.pk)],
        )
        return {tuple(row[0]): row[1] for row in c.fetchall()}


@pytest.mark.django_db
def test_update_publikacji_nie_przepisuje_wierszy_autorzy_mat(standard_data, denorms):
    wc = baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="STARY", szczegoly="sz", uwagi="u"
    )
    j = baker.make(Jednostka)
    wc.dodaj_autora(baker.make(Autor, imiona="Jan", nazwisko="Pierwszy"), j)
    wc.dodaj_autora(baker.make(Autor, imiona="Jan", nazwisko="Drugi"), j)
    denorms.flush()

    rekord = Rekord.objects.get_for_model(wc)
    przed = _xmin_autorzy_mat(rekord)
    assert len(przed) == 2

    # surowy UPDATE — izoluje sam trigger (bez denorm / sygnałów Django)
    with connection.cursor() as c:
        c.execute(
            "UPDATE bpp_wydawnictwo_ciagle SET tytul_oryginalny = 'NOWY' WHERE id = %s",
            [wc.pk],
        )

    assert Rekord.objects.get_for_model(wc).tytul_oryginalny == "NOWY"

    po = _xmin_autorzy_mat(rekord)
    assert po == przed, (
        "edycja publikacji przepisała wiersze bpp_autorzy_mat "
        f"(xmin przed={przed}, po={po})"
    )


@pytest.mark.django_db
def test_zmiana_autor_id_in_place_aktualizuje_autorzy_mat(standard_data, denorms):
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="T", szczegoly="sz", uwagi="u")
    j = baker.make(Jednostka)
    a = baker.make(Autor, imiona="Jan", nazwisko="Stary")
    b = baker.make(Autor, imiona="Jan", nazwisko="Nowy")
    wca = wc.dodaj_autora(a, j)
    denorms.flush()

    rekord = Rekord.objects.get_for_model(wc)
    assert rekord.autorzy_set.filter(autor=a).exists()

    with connection.cursor() as c:
        c.execute(
            "UPDATE bpp_wydawnictwo_ciagle_autor SET autor_id = %s WHERE id = %s",
            [b.pk, wca.pk],
        )

    assert rekord.autorzy_set.filter(autor=b).exists(), (
        "po zmianie autor_id in-place wiersz bpp_autorzy_mat nie wskazuje nowego autora"
    )
    assert not rekord.autorzy_set.filter(autor=a).exists()


@pytest.mark.django_db
def test_usuniecie_jednej_z_dwoch_rol_autora_zostawia_druga(standard_data, denorms):
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="T", szczegoly="sz", uwagi="u")
    j = baker.make(Jednostka)
    a = baker.make(Autor, imiona="Jan", nazwisko="Dwurolowy")
    wca_aut = wc.dodaj_autora(a, j, typ_odpowiedzialnosci_skrot="aut.", kolejnosc=0)
    wca_red = wc.dodaj_autora(a, j, typ_odpowiedzialnosci_skrot="red.", kolejnosc=1)
    denorms.flush()

    rekord = Rekord.objects.get_for_model(wc)
    assert rekord.autorzy_set.filter(autor=a).count() == 2

    wca_red.delete()

    pozostale = rekord.autorzy_set.filter(autor=a)
    assert pozostale.count() == 1, (
        "usunięcie jednej roli autora skasowało z bpp_autorzy_mat oba wiersze"
    )
    assert tuple(pozostale.get().pk) == (rekord.pk[0], wca_aut.pk)


@pytest.mark.django_db
def test_doktorska_zmiana_autora_aktualizuje_autorzy_mat(standard_data, denorms):
    """Strażnik: dla prac doktorskich autor leży na wierszu publikacji
    (widok autorzy z INNER JOIN do bpp_autor) — edycja publikacji musi
    nadal odświeżać bpp_autorzy_mat."""
    j = baker.make(Jednostka)
    a = baker.make(Autor, imiona="Jan", nazwisko="Doktorant")
    b = baker.make(Autor, imiona="Jan", nazwisko="Inny")
    pd = baker.make(Praca_Doktorska, autor=a, jednostka=j, tytul_oryginalny="Dr")
    denorms.flush()

    rekord = Rekord.objects.get_for_model(pd)
    assert rekord.autorzy_set.filter(autor=a).exists()

    pd.autor = b
    pd.save()
    denorms.flush()

    assert rekord.autorzy_set.filter(autor=b).exists()
    assert not rekord.autorzy_set.filter(autor=a).exists()
