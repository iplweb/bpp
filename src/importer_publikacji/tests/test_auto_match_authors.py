"""Testy dla ``_auto_match_authors`` — zapis ``matched_autor`` i listy
``ImportedAuthor_Candidate`` w zależności od wyniku ``Komparator.porownaj_author``.
"""

import pytest
from model_bakery import baker

from bpp.models import Autor
from importer_publikacji.models import ImportedAuthor, ImportSession
from importer_publikacji.views.authors import _auto_match_authors


@pytest.fixture
def session():
    return baker.make(ImportSession)


@pytest.mark.django_db
def test_brak_dopasowania_nie_zapisuje_kandydatow(session):
    """Pusta baza autorów → UNMATCHED, brak kandydatów w M2M."""
    _auto_match_authors(
        session, [{"given": "Eva", "family": "Lech-Maranda"}], year=None
    )
    imported = session.authors.get()
    assert imported.matched_autor is None
    assert imported.match_status == ImportedAuthor.MatchStatus.UNMATCHED
    assert imported.candidates.count() == 0


@pytest.mark.django_db
def test_jednoznaczny_exact_match_zapisuje_kandydata(session):
    """1 kandydat z pewnosc=1.0 → AUTO_EXACT, 1 wpis kandydatów."""
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    _auto_match_authors(session, [{"given": "Jan", "family": "Kowalski"}], year=None)
    imported = session.authors.get()
    assert imported.matched_autor == autor
    assert imported.match_status == ImportedAuthor.MatchStatus.AUTO_EXACT
    candidates = list(imported.candidates.all())
    assert len(candidates) == 1
    assert candidates[0].autor == autor
    assert candidates[0].pewnosc == 1.0
    assert candidates[0].powod == "iexact"


@pytest.mark.django_db
def test_lech_maranda_ambiguity_sugeruje_z_orcid(session):
    """Reprodukcja zgłoszenia: 2 autorów w bazie → AUTO_LOOSE z sugerowanym.

    Eva Lech-Maranda (import) ↔ {Ewa Lech-Marańda, Ewa Lech-Maranda} (baza).
    Oba kandydaci po PL↔EN (pewnosc=0.85). Sugerowany — ten z ORCID.
    """
    z_orcid = baker.make(
        Autor,
        imiona="Ewa",
        nazwisko="Lech-Marańda",
        orcid="0000-0001-2345-6789",
    )
    bez_orcid = baker.make(Autor, imiona="Ewa", nazwisko="Lech-Maranda")

    _auto_match_authors(
        session, [{"given": "Eva", "family": "Lech-Maranda"}], year=None
    )
    imported = session.authors.get()
    assert imported.matched_autor == z_orcid
    assert imported.match_status == ImportedAuthor.MatchStatus.AUTO_LOOSE

    candidates = list(imported.candidates.order_by("-pewnosc", "-publikacji_count"))
    assert len(candidates) == 2
    assert {c.autor for c in candidates} == {z_orcid, bez_orcid}
    assert all(c.pewnosc == 0.85 for c in candidates)
    assert all(c.powod == "polish_english" for c in candidates)


@pytest.mark.django_db
def test_render_author_row_pokazuje_badge_kandydatow(session, rf):
    """Wiersz pokazuje badge 'X kandydatów' gdy są >1 — lista jest w
    modalu, nie inline."""
    from django.template.loader import render_to_string

    z_orcid = baker.make(
        Autor,
        imiona="Ewa",
        nazwisko="Lech-Marańda",
        orcid="0000-0001-2345-6789",
    )
    baker.make(Autor, imiona="Ewa", nazwisko="Lech-Maranda")

    _auto_match_authors(
        session, [{"given": "Eva", "family": "Lech-Maranda"}], year=None
    )
    imported = session.authors.get()

    html = render_to_string(
        "importer_publikacji/partials/author_row.html",
        {"session": session, "author": imported},
    )
    # Badge pokazuje liczbę kandydatów (link do modala)
    assert "2 kandydatów" in html
    # Wybrany autor widoczny w komórce "Autor w BPP"
    assert str(z_orcid) in html
    # Edytuj button do otwarcia modala
    assert "btn-edit-author" in html
    # Dropdown z kandydatami NIE jest już w wierszu (lista jest w modalu)
    assert "modal-candidate-button" not in html
    assert "candidates-dropdown" not in html


@pytest.mark.django_db
def test_author_info_view_zwraca_json(session, importer_client):
    """GET author-info zwraca JSON z pk/slug/orcid/pbn_uid_id autora BPP."""
    from django.urls import reverse

    autor = baker.make(
        Autor,
        imiona="Jan",
        nazwisko="Kowalski",
        orcid="0000-0001-2345-6789",
    )
    url = reverse(
        "importer_publikacji:author-info",
        args=[session.pk, autor.pk],
    )
    response = importer_client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data["pk"] == autor.pk
    assert data["orcid"] == "0000-0001-2345-6789"
    assert "slug" in data
    assert "display" in data


@pytest.mark.django_db
def test_author_candidates_modal_view_renderuje_kandydatow(
    session, importer_client
):
    """GET author-candidates-modal zwraca HTML partial z listą kandydatów."""
    from django.urls import reverse

    a1 = baker.make(Autor, imiona="Ewa", nazwisko="Lech-Marańda")
    a2 = baker.make(Autor, imiona="Ewa", nazwisko="Lech-Maranda")
    _auto_match_authors(
        session, [{"given": "Eva", "family": "Lech-Maranda"}], year=None
    )
    imp = session.authors.get()

    url = reverse(
        "importer_publikacji:author-candidates-modal",
        args=[session.pk, imp.pk],
    )
    response = importer_client.get(url)
    assert response.status_code == 200
    html = response.content.decode()
    assert "modal-candidate-button" in html
    assert str(a1) in html
    assert str(a2) in html
    # data-autor-pk pozwala JS-owi przepiąć select2
    assert f'data-autor-pk="{a1.pk}"' in html or f"data-autor-pk='{a1.pk}'" in html
