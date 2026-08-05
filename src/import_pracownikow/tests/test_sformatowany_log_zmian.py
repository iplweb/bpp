"""#513 F1 / #508 M4: ``sformatowany_log_zmian`` musi renderować WSZYSTKIE
klucze audytu, nie tylko ``autor``/``autor_jednostka``.

Faza integracji zapisuje też ``utworzono`` (m.in. „nowy autor: …"),
``przepiecie`` (raport przepięcia prac) i ``przepiecie_pominiete``. Bez ich
renderu utworzenie nowego autora i przepięcie dorobku były NIEWIDOCZNE w
audycie UI (jedyny widok log_zmian po integracji — partial _wiersz_preview).
"""

from import_pracownikow.models import ImportPracownikowRow


def _linie(log_zmian):
    return list(ImportPracownikowRow(log_zmian=log_zmian).sformatowany_log_zmian())


def test_log_none_nic_nie_zwraca():
    assert _linie(None) == []


def test_renderuje_zmiany_autor_i_autor_jednostka():
    linie = _linie(
        {"autor": ["nazwisko -> Kowalski"], "autor_jednostka": ["funkcja na asystent"]}
    )
    assert any("Kowalski" in x for x in linie)
    assert any("asystent" in x for x in linie)


def test_renderuje_utworzono_nowego_autora():
    # #513 F1: nowy autor był niewidoczny w audycie.
    linie = _linie(
        {
            "autor": [],
            "autor_jednostka": [],
            "utworzono": ["nowy autor: Jan Kowalski", "powiązanie autor-jednostka"],
        }
    )
    tekst = " ".join(linie)
    assert "nowy autor: Jan Kowalski" in tekst
    assert "powiązanie autor-jednostka" in tekst


def test_renderuje_przepiecie():
    linie = _linie(
        {
            "autor": [],
            "autor_jednostka": [],
            "przepiecie": {
                "pk": 7,
                "prace_ciagle": 3,
                "prace_zwarte": 2,
                "z": "ST",
                "do": "NW",
            },
        }
    )
    tekst = " ".join(linie)
    assert "3" in tekst and "2" in tekst
    assert "ST" in tekst and "NW" in tekst


def test_renderuje_przepiecie_pominiete():
    linie = _linie(
        {
            "autor": [],
            "autor_jednostka": [],
            "przepiecie_pominiete": "pominięto — już przepięte w innym wierszu",
        }
    )
    assert any("już przepięte" in x for x in linie)


def test_wszystkie_klucze_naraz():
    linie = _linie(
        {
            "autor": ["tytuł naukowy -> dr"],
            "autor_jednostka": ["wymiar_etatu na pełny etat"],
            "utworzono": ["nowy autor: Anna Nowak"],
            "przepiecie": {
                "pk": 1,
                "prace_ciagle": 1,
                "prace_zwarte": 0,
                "z": "AA",
                "do": "BB",
            },
        }
    )
    tekst = " ".join(linie)
    for oczekiwane in ("dr", "pełny etat", "Anna Nowak", "AA", "BB"):
        assert oczekiwane in tekst
