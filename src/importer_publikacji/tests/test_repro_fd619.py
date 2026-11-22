"""FD#619: importer po DOI nie zaciągał redaktorów monografii.

CrossRef dla monografii redagowanej zwraca osoby w polu ``editor`` (bez
``author``) — importer czytał tylko ``author``, więc krok „Autorzy" był
pusty. Fikstura poniżej odtwarza dane DOI z sesji 115 na APOŻ
(10.70402/apoz.2026.wasb.9788398070447, typ ``monograph``, 3 redaktorów).
"""

import pytest
from model_bakery import baker

from bpp import const
from importer_publikacji.models import ImportSession
from importer_publikacji.providers import dolacz_redaktorow
from importer_publikacji.providers.bibtex import BibTeXProvider
from importer_publikacji.providers.crossref import CrossRefProvider
from importer_publikacji.providers.dspace import _autorzy_i_redaktorzy
from importer_publikacji.providers.pbn import PBN_TYPE_MAP, _extract_authors
from importer_publikacji.tasks import fetch_session_task


def _osoba(family, given, orcid="", sequence="additional"):
    ret = {
        "role": [{"role": "editor", "vocabulary": "crossref"}],
        "given": given,
        "family": family,
        "sequence": sequence,
        "affiliation": [{"name": "Akademia Pożarnicza"}],
    }
    if orcid:
        ret["ORCID"] = f"https://orcid.org/{orcid}"
    return ret


# Fragment odpowiedzi api.crossref.org/works/<DOI> dla monografii
# redagowanej (typ ``monograph``, tylko ``editor``, brak ``author``).
CROSSREF_MONOGRAFIA_REDAGOWANA = {
    "DOI": "10.70402/apoz.2026.wasb.9788398070447",
    "type": "monograph",
    "title": ["Współczesna architektura środowiska bezpieczeństwa"],
    "publisher": "Akademia Pożarnicza",
    "published": {"date-parts": [[2026]]},
    "ISBN": ["9788398070447"],
    "editor": [
        _osoba("Kułakowska", "Aneta", "0000-0003-1829-568X", "first"),
        _osoba("Jakubczak", "Weronika", "0000-0003-1501-5064"),
        _osoba("Żurawski", "Sławomir", "0000-0001-9527-3391"),
    ],
}


class _FakeCache:
    def __init__(self, data):
        self.data = data

    def get_by_doi(self, doi):
        return self.data


@pytest.fixture
def crossref_dane(monkeypatch):
    from importer_publikacji.providers import crossref as crossref_mod

    def _ustaw(data):
        monkeypatch.setattr(crossref_mod.CrossrefAPICache, "objects", _FakeCache(data))

    return _ustaw


def test_crossref_monografia_redagowana_daje_redaktorow(crossref_dane):
    crossref_dane(CROSSREF_MONOGRAFIA_REDAGOWANA)

    result = CrossRefProvider().fetch("10.70402/apoz.2026.wasb.9788398070447")

    assert [a["family"] for a in result.authors] == [
        "Kułakowska",
        "Jakubczak",
        "Żurawski",
    ]
    assert all(a["typ_ogolny"] == const.TO_REDAKTOR for a in result.authors)
    assert result.authors[0]["orcid"] == "0000-0003-1829-568X"


def test_crossref_autorzy_i_redaktorzy_najpierw_redaktorzy(crossref_dane):
    """Kolejność jak w BPP (import z PBN, istniejące rekordy): redaktorzy,
    potem autorzy."""
    data = {
        **CROSSREF_MONOGRAFIA_REDAGOWANA,
        "type": "edited-book",
        "editor": [_osoba("Redaktorska", "Ewa")],
        "author": [{"family": "Autorski", "given": "Jan"}],
    }
    crossref_dane(data)

    result = CrossRefProvider().fetch(data["DOI"])

    assert [(a["family"], a.get("typ_ogolny")) for a in result.authors] == [
        ("Redaktorska", const.TO_REDAKTOR),
        ("Autorski", None),
    ]


def test_crossref_rozdzial_pomija_redaktorow_ksiazki(crossref_dane):
    """Strażnik: w rozdziale ``editor`` to redaktorzy książki nadrzędnej —
    nie dopisujemy ich do rozdziału."""
    data = {
        **CROSSREF_MONOGRAFIA_REDAGOWANA,
        "type": "book-chapter",
        "author": [{"family": "Autorski", "given": "Jan"}],
    }
    crossref_dane(data)

    result = CrossRefProvider().fetch(data["DOI"])

    assert [a["family"] for a in result.authors] == ["Autorski"]
    assert "typ_ogolny" not in result.authors[0]


@pytest.mark.django_db
def test_fetch_task_tworzy_redaktorow_w_kroku_autorzy(crossref_dane, django_user_model):
    """Pełna ścieżka pobrania: redaktorzy lądują w kroku „Autorzy" jako
    „redaktor" i dopasowują się do autorów BPP (tu: po ORCID)."""
    from bpp.models import Autor

    crossref_dane(CROSSREF_MONOGRAFIA_REDAGOWANA)
    kulakowska = baker.make(
        Autor, nazwisko="Kułakowska", imiona="Aneta", orcid="0000-0003-1829-568X"
    )
    session = baker.make(
        ImportSession,
        created_by=baker.make(django_user_model),
        provider_name="CrossRef",
        identifier="10.70402/apoz.2026.wasb.9788398070447",
        status=ImportSession.Status.FETCHING,
    )

    fetch_session_task.apply(args=[session.pk, session.created_by_id]).get()

    session.refresh_from_db()
    assert session.status == ImportSession.Status.FETCHED
    autorzy = list(session.authors.order_by("order"))
    assert [(a.family_name, a.typ_ogolny) for a in autorzy] == [
        ("Kułakowska", const.TO_REDAKTOR),
        ("Jakubczak", const.TO_REDAKTOR),
        ("Żurawski", const.TO_REDAKTOR),
    ]
    assert autorzy[0].matched_autor == kulakowska


def test_dolacz_redaktorow_nieznany_typ_pomija():
    assert dolacz_redaktorow([], [{"family": "X", "given": "Y"}], None) == []


# --- inne źródła z analogicznym polem ---------------------------------------

BIBTEX_KSIAZKA = """@book{k1,
  title     = {Monografia redagowana},
  editor    = {Kowalska, Anna and Nowak, Piotr},
  year      = {2026},
  publisher = {Akademia Pożarnicza}
}"""

BIBTEX_ROZDZIAL = """@incollection{k2,
  author    = {Autorski, Jan},
  title     = {Rozdział},
  booktitle = {Monografia redagowana},
  editor    = {Kowalska, Anna and Nowak, Piotr},
  year      = {2026}
}"""


def test_bibtex_book_z_editor():
    result = BibTeXProvider().fetch(BIBTEX_KSIAZKA)
    assert [(a["family"], a["typ_ogolny"]) for a in result.authors] == [
        ("Kowalska", const.TO_REDAKTOR),
        ("Nowak", const.TO_REDAKTOR),
    ]


def test_bibtex_collection_z_editor():
    """biblatex ``@collection`` = książka redagowana."""
    result = BibTeXProvider().fetch(BIBTEX_KSIAZKA.replace("@book", "@collection"))
    assert result.publication_type == "edited-book"
    assert [a["typ_ogolny"] for a in result.authors] == [const.TO_REDAKTOR] * 2


def test_bibtex_incollection_pomija_redaktorow_ksiazki():
    result = BibTeXProvider().fetch(BIBTEX_ROZDZIAL)
    assert [a["family"] for a in result.authors] == ["Autorski"]


def test_pbn_edited_book_z_editors():
    obj = {
        "type": "EDITED_BOOK",
        "editors": {"uid1": {"lastName": "Kowalska", "name": "Anna"}},
        "authors": {"uid2": {"lastName": "Autorski", "name": "Jan"}},
    }
    osoby = dolacz_redaktorow(
        _extract_authors(obj),
        _extract_authors(obj, "editors"),
        PBN_TYPE_MAP[obj["type"]],
    )
    assert [(a["family"], a.get("typ_ogolny")) for a in osoby] == [
        ("Kowalska", const.TO_REDAKTOR),
        ("Autorski", None),
    ]


def test_dspace_contributor_editor():
    meta = [
        {"key": "dc.contributor.editor", "value": "Kowalska, Anna"},
        {"key": "dc.contributor.author", "value": "Autorski, Jan"},
    ]
    assert [
        (a["family"], a.get("typ_ogolny")) for a in _autorzy_i_redaktorzy(meta, "book")
    ] == [("Kowalska", const.TO_REDAKTOR), ("Autorski", None)]
    assert [a["family"] for a in _autorzy_i_redaktorzy(meta, "book-chapter")] == [
        "Autorski"
    ]


# --- ta sama osoba jako redaktor i autor ------------------------------------


@pytest.mark.django_db
def test_utworz_niedopasowanych_jeden_autor_dla_redaktora_i_autora():
    """Osoba, która jest i redaktorem, i autorem (bez ORCID), nie może dać
    dwóch rekordów ``Autor`` przy „Utwórz niedopasowanych autorów"."""
    from bpp.models import Autor, Jednostka
    from importer_publikacji.models import ImportedAuthor
    from importer_publikacji.views.authors import _create_unmatched_authors

    session = baker.make(ImportSession)
    for order, typ in enumerate((const.TO_REDAKTOR, const.TO_AUTOR)):
        baker.make(
            ImportedAuthor,
            session=session,
            order=order,
            family_name="Zupełnienowa",
            given_name="Ewa",
            orcid="",
            typ_ogolny=typ,
        )
    obca = baker.make(Jednostka)

    _create_unmatched_authors(session, obca)

    assert Autor.objects.filter(nazwisko="Zupełnienowa").count() == 1
    assert session.authors.values("matched_autor").distinct().count() == 1


@pytest.mark.django_db
def test_orcid_do_ustawienia_dla_redaktora_i_autora_z_tym_samym_orcid():
    from bpp.models import Autor
    from importer_publikacji.models import ImportedAuthor
    from importer_publikacji.views.authors import _orcid_settable_qs

    autor = baker.make(Autor, orcid=None)
    session = baker.make(ImportSession)
    for order, typ in enumerate((const.TO_REDAKTOR, const.TO_AUTOR)):
        baker.make(
            ImportedAuthor,
            session=session,
            order=order,
            orcid="0000-0003-1829-568X",
            matched_autor=autor,
            typ_ogolny=typ,
        )

    assert _orcid_settable_qs(session).count() == 2


@pytest.mark.django_db
def test_orcid_konflikt_roznych_orcid_nadal_wykluczony():
    """Strażnik: ten sam autor BPP dopasowany do dwóch różnych ORCID-ów to
    konflikt — ORCID nie jest proponowany."""
    from bpp.models import Autor
    from importer_publikacji.models import ImportedAuthor
    from importer_publikacji.views.authors import _orcid_settable_qs

    autor = baker.make(Autor, orcid=None)
    session = baker.make(ImportSession)
    for order, orcid in enumerate(("0000-0003-1829-568X", "0000-0001-9527-3391")):
        baker.make(
            ImportedAuthor,
            session=session,
            order=order,
            orcid=orcid,
            matched_autor=autor,
        )

    assert _orcid_settable_qs(session).count() == 0
