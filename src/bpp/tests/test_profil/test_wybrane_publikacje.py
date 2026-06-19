"""Testy self-service pickera wyróżnionych publikacji autora (§3.4).

Zalogowany autor zarządza listą WŁASNYCH wyróżnionych prac (dodaj, usuń,
zmień kolejność). Operuje wyłącznie na ``request.user.autor.wybrane_publikacje``
i może wskazać tylko pracę, która faktycznie należy do jego dorobku
(``Rekord.objects.prace_autora``). Bezpieczeństwo jest tu krytyczne — autor
A nie może wyróżnić pracy autora B ani usunąć/przesunąć cudzego wiersza.
"""

import json

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Rekord, Wydawnictwo_Zwarte
from bpp.models.wybrana_publikacja import WybranaPublikacjaAutora

pytestmark = pytest.mark.django_db


def _zaloguj_jako_autora(client, django_user_model, autor, username="picker-user"):
    user = django_user_model.objects.create_user(username=username, password="x")
    user.autor = autor
    user.save(update_fields=["autor"])
    client.force_login(user)
    return user


def _rekord_autora(autor):
    """Zwróć pierwszy ``Rekord`` z dorobku autora (po flush denorm)."""
    return Rekord.objects.prace_autora(autor).first()


def _ct_obj(rekord):
    """(content_type_id, object_id) rekordu — ``content_type`` to obiekt CT."""
    return rekord.content_type.id, rekord.object_id


def _identyfikator(rekord):
    """Zakodowany identyfikator rekordu używany w formularzu: ``ct-obj``."""
    ct, obj = _ct_obj(rekord)
    return f"{ct}-{obj}"


def _wpa(autor, rekord, kolejnosc=0):
    ct, obj = _ct_obj(rekord)
    return WybranaPublikacjaAutora.objects.create(
        autor=autor, content_type_id=ct, object_id=obj, kolejnosc=kolejnosc
    )


# --- kontrola dostępu ------------------------------------------------------


def test_anonim_widok_przekierowany_na_login(client):
    resp = client.get(reverse("bpp:profil-wybrane-publikacje"))
    assert resp.status_code == 302
    assert "login" in resp.url


def test_anonim_akcja_przekierowana_na_login(client):
    resp = client.post(reverse("bpp:profil-wybrane-publikacje-akcja"))
    assert resp.status_code == 302
    assert "login" in resp.url


def test_anonim_autocomplete_przekierowany_na_login(client):
    resp = client.get(reverse("bpp:profil-wybrane-publikacje-autocomplete"))
    assert resp.status_code == 302
    assert "login" in resp.url


def test_user_bez_autora_przekierowany_na_profil(client, django_user_model):
    user = django_user_model.objects.create_user(username="bez-autora", password="x")
    client.force_login(user)
    for nazwa in (
        "bpp:profil-wybrane-publikacje",
        "bpp:profil-wybrane-publikacje-akcja",
        "bpp:profil-wybrane-publikacje-autocomplete",
    ):
        resp = client.get(reverse(nazwa))
        assert resp.status_code == 302
        assert resp.url == reverse("bpp:profil-uzytkownika")


# --- widok zarządzania -----------------------------------------------------


def test_widok_pokazuje_wybrane_publikacje(
    client,
    django_user_model,
    transactional_db,
    standard_data,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    jednostka,
    denorms,
):
    wydawnictwo_zwarte.tytul_oryginalny = "Praca wyróżniona testowa"
    wydawnictwo_zwarte.save()
    wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)
    denorms.flush()

    _wpa(autor_jan_nowak, _rekord_autora(autor_jan_nowak))

    _zaloguj_jako_autora(client, django_user_model, autor_jan_nowak)
    resp = client.get(reverse("bpp:profil-wybrane-publikacje"))
    assert resp.status_code == 200
    assert "Praca wyróżniona testowa" in resp.content.decode()


# --- dodawanie -------------------------------------------------------------


def test_dodaj_wlasna_prace(
    client,
    django_user_model,
    transactional_db,
    standard_data,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    jednostka,
    denorms,
):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)
    denorms.flush()
    rekord = _rekord_autora(autor_jan_nowak)

    _zaloguj_jako_autora(client, django_user_model, autor_jan_nowak)
    resp = client.post(
        reverse("bpp:profil-wybrane-publikacje-akcja"),
        {"akcja": "dodaj", "rekord": _identyfikator(rekord)},
    )
    assert resp.status_code == 200
    dane = json.loads(resp.content)
    assert dane["ok"] is True

    ct, obj = _ct_obj(rekord)
    wpa = WybranaPublikacjaAutora.objects.get(autor=autor_jan_nowak)
    assert wpa.content_type_id == ct
    assert wpa.object_id == obj
    assert autor_jan_nowak.wybrane_publikacje.count() == 1


def test_dodaj_duplikat_nie_wybucha(
    client,
    django_user_model,
    transactional_db,
    standard_data,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    jednostka,
    denorms,
):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)
    denorms.flush()
    rekord = _rekord_autora(autor_jan_nowak)

    _zaloguj_jako_autora(client, django_user_model, autor_jan_nowak)
    url = reverse("bpp:profil-wybrane-publikacje-akcja")
    payload = {"akcja": "dodaj", "rekord": _identyfikator(rekord)}

    resp1 = client.post(url, payload)
    assert resp1.status_code == 200
    resp2 = client.post(url, payload)
    # Duplikat = friendly no-op, NIE 500.
    assert resp2.status_code == 200
    assert autor_jan_nowak.wybrane_publikacje.count() == 1


def test_dodaj_cudza_prace_odrzucone(
    client,
    django_user_model,
    transactional_db,
    standard_data,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    autor_jan_kowalski,
    jednostka,
    denorms,
):
    # Praca A — autora Nowaka (zalogowanego).
    wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)
    # Praca B — należy WYŁĄCZNIE do Kowalskiego.
    praca_b = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Praca Kowalskiego")
    praca_b.dodaj_autora(autor_jan_kowalski, jednostka)
    denorms.flush()

    rekord_b = _rekord_autora(autor_jan_kowalski)

    _zaloguj_jako_autora(client, django_user_model, autor_jan_nowak)
    resp = client.post(
        reverse("bpp:profil-wybrane-publikacje-akcja"),
        {"akcja": "dodaj", "rekord": _identyfikator(rekord_b)},
    )
    # Odrzucone bezpiecznie (400), NIE 500.
    assert resp.status_code == 400
    ct, obj = _ct_obj(rekord_b)
    assert not WybranaPublikacjaAutora.objects.filter(
        autor=autor_jan_nowak, content_type_id=ct, object_id=obj
    ).exists()


# --- usuwanie --------------------------------------------------------------


def test_usun_wlasny_wiersz(
    client,
    django_user_model,
    transactional_db,
    standard_data,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    jednostka,
    denorms,
):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)
    denorms.flush()
    wpa = _wpa(autor_jan_nowak, _rekord_autora(autor_jan_nowak))

    _zaloguj_jako_autora(client, django_user_model, autor_jan_nowak)
    resp = client.post(
        reverse("bpp:profil-wybrane-publikacje-akcja"),
        {"akcja": "usun", "pk": wpa.pk},
    )
    assert resp.status_code == 200
    assert not WybranaPublikacjaAutora.objects.filter(pk=wpa.pk).exists()


def test_usun_cudzy_wiersz_odrzucone(
    client,
    django_user_model,
    transactional_db,
    standard_data,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    autor_jan_kowalski,
    jednostka,
    denorms,
):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
    denorms.flush()
    # Wiersz NALEŻY do Kowalskiego.
    wpa = _wpa(autor_jan_kowalski, _rekord_autora(autor_jan_kowalski))

    # Zalogowany jako Nowak — próbuje usunąć cudzy wiersz.
    _zaloguj_jako_autora(client, django_user_model, autor_jan_nowak)
    resp = client.post(
        reverse("bpp:profil-wybrane-publikacje-akcja"),
        {"akcja": "usun", "pk": wpa.pk},
    )
    assert resp.status_code == 404
    assert WybranaPublikacjaAutora.objects.filter(pk=wpa.pk).exists()


# --- zmiana kolejności -----------------------------------------------------


def test_przesun_zmienia_kolejnosc_i_kolejnosc_w_sekcji(
    client,
    django_user_model,
    transactional_db,
    standard_data,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    jednostka,
    denorms,
):
    wydawnictwo_zwarte.tytul_oryginalny = "Pierwsza praca"
    wydawnictwo_zwarte.save()
    wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)
    praca2 = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Druga praca")
    praca2.dodaj_autora(autor_jan_nowak, jednostka)
    denorms.flush()

    r1 = Rekord.objects.get_for_model(wydawnictwo_zwarte)
    r2 = Rekord.objects.get_for_model(praca2)
    w1 = _wpa(autor_jan_nowak, r1, kolejnosc=0)
    w2 = _wpa(autor_jan_nowak, r2, kolejnosc=1)

    _zaloguj_jako_autora(client, django_user_model, autor_jan_nowak)
    # Nowa kolejność: w2, w1.
    resp = client.post(
        reverse("bpp:profil-wybrane-publikacje-akcja"),
        {"akcja": "przesun", "kolejnosc": [str(w2.pk), str(w1.pk)]},
    )
    assert resp.status_code == 200

    w1.refresh_from_db()
    w2.refresh_from_db()
    assert w2.kolejnosc == 0
    assert w1.kolejnosc == 1

    # Builder sekcji zwraca prace w nowej kolejności.
    from bpp.profil_autora_dane import _wybrane_publikacje

    dane = _wybrane_publikacje(autor_jan_nowak, limit=10, request=None)
    tytuly = [p.tytul_oryginalny for p in dane["prace"]]
    assert tytuly == ["Druga praca", "Pierwsza praca"]


def test_przesun_cudzych_wierszy_ignorowane(
    client,
    django_user_model,
    transactional_db,
    standard_data,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    autor_jan_kowalski,
    jednostka,
    denorms,
):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
    denorms.flush()
    cudzy = _wpa(autor_jan_kowalski, _rekord_autora(autor_jan_kowalski), kolejnosc=5)

    _zaloguj_jako_autora(client, django_user_model, autor_jan_nowak)
    resp = client.post(
        reverse("bpp:profil-wybrane-publikacje-akcja"),
        {"akcja": "przesun", "kolejnosc": [str(cudzy.pk)]},
    )
    assert resp.status_code == 200
    # Cudzy wiersz NIE został dotknięty.
    cudzy.refresh_from_db()
    assert cudzy.kolejnosc == 5


# --- autocomplete ----------------------------------------------------------


def test_autocomplete_zwraca_wlasne_prace(
    client,
    django_user_model,
    transactional_db,
    standard_data,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    autor_jan_kowalski,
    jednostka,
    denorms,
):
    wydawnictwo_zwarte.tytul_oryginalny = "Unikalny tytul nowaka"
    wydawnictwo_zwarte.save()
    wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)
    praca_k = baker.make(
        Wydawnictwo_Zwarte, tytul_oryginalny="Unikalny tytul kowalskiego"
    )
    praca_k.dodaj_autora(autor_jan_kowalski, jednostka)
    denorms.flush()

    _zaloguj_jako_autora(client, django_user_model, autor_jan_nowak)
    resp = client.get(
        reverse("bpp:profil-wybrane-publikacje-autocomplete"),
        {"q": "Unikalny tytul"},
    )
    assert resp.status_code == 200
    dane = json.loads(resp.content)
    etykiety = [w["label"] for w in dane["results"]]
    assert any("nowaka" in e for e in etykiety)
    # Praca Kowalskiego NIE pojawia się w wynikach Nowaka.
    assert not any("kowalskiego" in e for e in etykiety)
