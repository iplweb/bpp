"""FD#620: podpowiedź dyscyplin dla autora bez przypisania na rok pracy —
autocomplete ``dyscyplina-naukowa-przypisanie-autocomplete`` i wspólna
funkcja „typowych dyscyplin uczelni"."""

import json

import pytest
from django.conf import settings
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina
from bpp.util.typowe_dyscypliny import (
    ZRODLO_ROK_AUTORA,
    ZRODLO_TYPOWE,
    ZRODLO_WSZYSTKIE,
    policz_typowe_dyscypliny,
    propozycja_dla_autora_bez_przypisania,
    typowe_dyscypliny,
)

URL = "bpp:dyscyplina-naukowa-przypisanie-autocomplete"


def _get(app, **forward):
    return app.get(reverse(URL), {"forward": json.dumps(forward)}).json


def _praca_z_dyscyplina(wydawnictwo_ciagle, jednostka, dyscyplina, rok, ile=1):
    """``ile`` autorów z przypisaniem ``dyscyplina`` w pracy z roku ``rok``."""
    wydawnictwo_ciagle.rok = rok
    wydawnictwo_ciagle.save()
    for i in range(ile):
        autor = baker.make(Autor, nazwisko=f"Typowy{rok}{i}", imiona="Jan")
        Autor_Dyscyplina.objects.create(
            autor=autor, rok=rok, dyscyplina_naukowa=dyscyplina
        )
        wydawnictwo_ciagle.dodaj_autora(
            autor,
            jednostka,
            zapisany_jako=f"Typowy{rok}{i} J.",
            dyscyplina_naukowa=dyscyplina,
        )


# --- przyczyna zgłoszenia: ID autora jako liczba JSON -----------------------


@pytest.mark.django_db
def test_repro_fd620_id_autora_jako_liczba(app, autor_jan_kowalski, dyscyplina1, rok):
    """Importer wysyła ``{"autor": 185, "rok": 2026}`` (liczby) — dotąd
    autocomplete odpowiadał „Podaj autora”, a lista w modalu była pusta,
    mimo że autor miał dyscyplinę na ten rok."""
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=rok, dyscyplina_naukowa=dyscyplina1
    )

    res = _get(app, autor=autor_jan_kowalski.pk, rok=rok)

    assert res["results"] == [{"id": dyscyplina1.pk, "text": dyscyplina1.nazwa}]


@pytest.mark.django_db
def test_id_autora_bool_nadal_odrzucane(app):
    assert _get(app, autor=True, rok=2020)["results"][0]["text"] == "Podaj autora"


# --- propozycja dla autora bez przypisania ---------------------------------


@pytest.mark.django_db
def test_bez_flagi_typowe_zachowanie_bez_zmian(app, autor_jan_kowalski, rok):
    res = _get(app, autor=str(autor_jan_kowalski.pk), rok=str(rok))
    assert res["results"] == [{"id": None, "text": f"Brak przypisania dla roku {rok}"}]
    assert "brak_przypisania" not in res


@pytest.mark.django_db
def test_autor_z_przypisaniem_na_rok_bez_zmian(
    app, autor_jan_kowalski, dyscyplina1, dyscyplina2, rok
):
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=rok, dyscyplina_naukowa=dyscyplina1
    )
    res = _get(app, autor=autor_jan_kowalski.pk, rok=rok, typowe=True)
    assert res["results"] == [{"id": dyscyplina1.pk, "text": dyscyplina1.nazwa}]
    assert "brak_przypisania" not in res


@pytest.mark.django_db
def test_dyscypliny_z_ubieglego_roku(
    app, autor_jan_kowalski, dyscyplina1, dyscyplina2, dyscyplina3, rok
):
    """Autor miał dyscypliny w roku poprzednim — tylko one, bez typowych."""
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=rok - 1,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
    )
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=rok - 2, dyscyplina_naukowa=dyscyplina3
    )

    res = _get(app, autor=autor_jan_kowalski.pk, rok=rok, typowe=True)

    (grupa,) = res["results"]
    assert grupa["text"] == (
        f"Autor nie ma dyscypliny na rok {rok} — dyscypliny autora z roku {rok - 1}"
    )
    assert {d["id"] for d in grupa["children"]} == {dyscyplina1.pk, dyscyplina2.pk}
    assert res["brak_przypisania"]["zrodlo"] == ZRODLO_ROK_AUTORA
    assert res["brak_przypisania"]["rok_zrodla"] == rok - 1


@pytest.mark.django_db
def test_dyscypliny_z_najblizszego_wczesniejszego_roku(
    app, autor_jan_kowalski, dyscyplina1, dyscyplina2, rok
):
    """Brak w roku poprzednim, ale był wcześniej — najbliższy wcześniejszy."""
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=rok - 3, dyscyplina_naukowa=dyscyplina1
    )
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=rok - 5, dyscyplina_naukowa=dyscyplina2
    )
    # Przypisanie z PRZYSZŁEGO roku nie jest brane pod uwagę.
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=rok + 1, dyscyplina_naukowa=dyscyplina2
    )

    res = _get(app, autor=autor_jan_kowalski.pk, rok=rok, typowe=True)

    (grupa,) = res["results"]
    assert [d["id"] for d in grupa["children"]] == [dyscyplina1.pk]
    assert f"dyscypliny autora z roku {rok - 3}" in grupa["text"]
    assert res["brak_przypisania"]["rok_zrodla"] == rok - 3


@pytest.mark.django_db
def test_autor_bez_dyscyplin_nigdy_typowe_dla_uczelni(
    app,
    autor_jan_kowalski,
    jednostka,
    wydawnictwo_ciagle,
    dyscyplina1,
    dyscyplina2,
    dyscyplina3,
    rok,
):
    """Autor nigdy nie miał dyscyplin — typowe dla uczelni, od najczęstszej."""
    _praca_z_dyscyplina(wydawnictwo_ciagle, jednostka, dyscyplina2, rok, ile=2)
    drugi = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        rok=rok - 1,
        charakter_formalny=wydawnictwo_ciagle.charakter_formalny,
        jezyk=wydawnictwo_ciagle.jezyk,
        typ_kbn=wydawnictwo_ciagle.typ_kbn,
        status_korekty=wydawnictwo_ciagle.status_korekty,
    )
    _praca_z_dyscyplina(drugi, jednostka, dyscyplina1, rok - 1, ile=1)
    # Praca sprzed okna (rok - 3) się nie liczy.
    stara = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        rok=rok - 3,
        charakter_formalny=wydawnictwo_ciagle.charakter_formalny,
        jezyk=wydawnictwo_ciagle.jezyk,
        typ_kbn=wydawnictwo_ciagle.typ_kbn,
        status_korekty=wydawnictwo_ciagle.status_korekty,
    )
    _praca_z_dyscyplina(stara, jednostka, dyscyplina3, rok - 3, ile=3)

    res = _get(app, autor=autor_jan_kowalski.pk, rok=rok, typowe=True)

    (grupa,) = res["results"]
    assert [d["id"] for d in grupa["children"]] == [dyscyplina2.pk, dyscyplina1.pk]
    assert grupa["text"] == (
        f"Autor nie ma dyscypliny na rok {rok} — typowe dla uczelni "
        f"(prace z lat {rok - 2}–{rok})"
    )
    assert res["brak_przypisania"]["zrodlo"] == ZRODLO_TYPOWE

    # Wyszukiwanie zawęża listę.
    res = app.get(
        reverse(URL),
        {
            "forward": json.dumps(
                {"autor": autor_jan_kowalski.pk, "rok": rok, "typowe": True}
            ),
            "q": dyscyplina1.nazwa[:5],
        },
    ).json
    assert [d["id"] for d in res["results"][0]["children"]] == [dyscyplina1.pk]


@pytest.mark.django_db
def test_brak_danych_wszystkie_dyscypliny(
    app, autor_jan_kowalski, dyscyplina1, dyscyplina2, rok
):
    res = _get(app, autor=autor_jan_kowalski.pk, rok=rok, typowe=True)

    (grupa,) = res["results"]
    ids = {d["id"] for d in grupa["children"]}
    assert {dyscyplina1.pk, dyscyplina2.pk} <= ids
    assert grupa["text"].endswith("— wszystkie dyscypliny")
    assert res["brak_przypisania"]["zrodlo"] == ZRODLO_WSZYSTKIE


# --- funkcja wspólna i harmonogram -----------------------------------------


@pytest.mark.django_db
def test_policz_typowe_per_uczelnia(
    jednostka, wydawnictwo_ciagle, dyscyplina1, rok, uczelnia
):
    _praca_z_dyscyplina(wydawnictwo_ciagle, jednostka, dyscyplina1, rok)

    dane = policz_typowe_dyscypliny(rok_do=rok)

    assert dane["rok_od"] == rok - 2
    assert dane["wszystkie_uczelnie"] == [dyscyplina1.pk]
    assert dane["uczelnie"][str(jednostka.uczelnia_id)] == [dyscyplina1.pk]
    assert typowe_dyscypliny(jednostka.uczelnia).dyscypliny == [dyscyplina1]


@pytest.mark.django_db
def test_propozycja_dyscypliny_ukrytej_nie_podaje(dyscyplina1, dyscyplina2, rok):
    dyscyplina2.widoczna = False
    dyscyplina2.save()
    autor = baker.make(Autor, nazwisko="Bezdyscyplinowy", imiona="Jan")

    propozycja = propozycja_dla_autora_bez_przypisania(autor.pk, rok)

    assert dyscyplina1 in propozycja.dyscypliny
    assert dyscyplina2 not in propozycja.dyscypliny


def test_zadanie_w_harmonogramie_beat():
    from bpp.tasks import odswiez_typowe_dyscypliny

    wpis = settings.CELERYBEAT_SCHEDULE["odswiez-typowe-dyscypliny"]
    assert wpis["task"] == odswiez_typowe_dyscypliny.name
