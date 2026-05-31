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
def test_render_author_row_pokazuje_orcid_i_badge_kandydatow(session, rf):
    """Wiersz pokazuje ORCID wybranego autora pod nazwiskiem oraz badge
    'X kandydatów' (oba w kolumnie 'Autor w BPP'). Kolumna 'Dopasowanie'
    zostaje czysta — tylko status, żeby DataTables filter mógł
    pogrupować po unikalnych wartościach."""
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
    # Badge "X kandydatów" w komórce "Autor w BPP" (nie w kolumnie
    # "Dopasowanie")
    assert "2 kandydatów" in html
    # ORCID wybranego autora pod nazwiskiem
    assert "0000-0001-2345-6789" in html
    # Wybrany autor widoczny
    assert str(z_orcid) in html
    # Edytuj button + klik na cały wiersz
    assert "btn-edit-author" in html
    assert "author-row-clickable" in html
    # Dropdown w wierszu nie istnieje (modal-based wybór)
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
def test_auto_match_ustawia_default_zapisany_jako(session):
    """`zapisany_jako` jest pre-fillowane z family_name + given_name."""
    _auto_match_authors(
        session, [{"given": "Eva", "family": "Lech-Maranda"}], year=None
    )
    imp = session.authors.get()
    assert imp.zapisany_jako == "Lech-Maranda Eva"


@pytest.mark.django_db
def test_author_match_view_zapisuje_zapisany_jako(session, importer_client):
    """POST na author-match z polem `zapisany_jako` aktualizuje rekord."""
    from django.urls import reverse

    autor = baker.make(Autor, imiona="Ewa", nazwisko="Lech-Marańda")
    imp = baker.make(
        ImportedAuthor,
        session=session,
        order=0,
        family_name="Lech-Maranda",
        given_name="Eva",
        zapisany_jako="Lech-Maranda Eva",
    )
    url = reverse(
        "importer_publikacji:author-match",
        args=[session.pk, imp.pk],
    )
    response = importer_client.post(
        url,
        {"autor": autor.pk, "zapisany_jako": "Lech-Maranda E."},
    )
    assert response.status_code == 200
    imp.refresh_from_db()
    assert imp.zapisany_jako == "Lech-Maranda E."


@pytest.mark.django_db
def test_author_candidates_modal_view_renderuje_kandydatow(session, importer_client):
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
    # Pewność pokazana jako procent (85%) zamiast 0.85,
    # powód strategii user-friendly (wariant PL/EN) zamiast polish_english
    assert "85%" in html
    assert "wariant PL/EN" in html
    assert "polish_english" not in html
