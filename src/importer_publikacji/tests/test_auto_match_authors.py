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
def test_render_author_row_z_dropdownem_kandydatow(session, rf):
    """Template author_row renderuje dropdown gdy są >1 kandydatów,
    pokazuje aktualna_jednostka per kandydat i wbudowane info w głównej
    komórce (po połączeniu kolumn Autor + Jednostka)."""
    from django.template.loader import render_to_string

    from bpp.models import Jednostka

    j_lekarska = baker.make(Jednostka, nazwa="Wydz. Lekarski-PROBE")
    z_orcid = baker.make(
        Autor,
        imiona="Ewa",
        nazwisko="Lech-Marańda",
        orcid="0000-0001-2345-6789",
    )
    z_orcid.dodaj_jednostke(j_lekarska)  # ustawia aktualna_jednostka
    baker.make(Autor, imiona="Ewa", nazwisko="Lech-Maranda")

    _auto_match_authors(
        session, [{"given": "Eva", "family": "Lech-Maranda"}], year=None
    )
    imported = session.authors.get()

    html = render_to_string(
        "importer_publikacji/partials/author_row.html",
        {"session": session, "author": imported},
    )
    assert "2 kandydatów" in html
    assert str(z_orcid) in html
    assert "ORCID" in html
    # Jednostka pokazana w głównej komórce (połączone kolumny)
    assert "Wydz. Lekarski-PROBE" in html
    # hx-post celuje w endpoint author-match (URL kończy się na /match/)
    assert "/match/" in html
    # Tylko alternatywny kandydat (nie matched_autor) ma hidden input z pk
    bez_orcid_pk = imported.candidates.exclude(autor=z_orcid).get().autor.pk
    assert f'name="autor" value="{bez_orcid_pk}"' in html
