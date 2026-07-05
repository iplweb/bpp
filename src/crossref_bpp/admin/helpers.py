import math

from crossref_bpp.core import Komparator
from import_common.normalization import normalize_title


def _komparator_pk(metoda, wartosc):
    """Zwróć ``pk`` rekordu BPP dopasowanego przez dany komparator albo None."""
    rekord = metoda(wartosc).rekord_po_stronie_bpp
    return rekord.pk if rekord is not None else None


def _extract_title(z: dict):
    """Tytuł: lista łączona ". ", a następnie normalizacja."""
    title = z.get("title")
    if isinstance(title, list):
        title = ". ".join(title)
    return normalize_title(title)


def _extract_zrodlo(z: dict):
    """PK źródła dopasowanego po container-title (albo None)."""
    try:
        tytul_kontenera = z.get("container-title")[0]
    except (IndexError, TypeError):
        # IndexError: pusta lista; TypeError: brak klucza (z.get(...) → None)
        return None

    if not tytul_kontenera:
        return None

    zrodlo = Komparator.porownaj_container_title(tytul_kontenera).rekord_po_stronie_bpp
    return zrodlo.pk if zrodlo is not None else None


def _extract_wydawca(z: dict):
    """(pk_wydawcy, opis_tekstowy). Opis ustawiany tylko gdy brak dopasowania."""
    wydawca_idx = Komparator.porownaj_publisher(
        z.get("publisher")
    ).rekord_po_stronie_bpp
    if wydawca_idx is None:
        return None, z.get("publisher")
    return wydawca_idx, ""


def _extract_issn_isbn_typed(z: dict, key: str):
    """Z listy ``issn-type`` / ``isbn-type`` wyciągnij (electronic, pozostały)."""
    e_value = None
    value = None
    for wpis in z.get(key, []) or []:
        if wpis.get("type") == "electronic":
            e_value = wpis.get("value")
        else:
            value = wpis.get("value")
    return e_value, value


def _fallback_identifier(z: dict, key: str, value, e_value):
    """Uzupełnij ISSN/ISBN z pola skalarnej-listy, jeśli różny od electronic.

    Odwzorowuje oryginalną logikę: jeśli ``value`` już jest ustawione z
    pętli ``*-type``, nie ruszaj. W przeciwnym razie weź pierwszy element
    listy ``z[key]``; ale wyzeruj, jeśli równy ``e_value`` (czyli pole
    zawierało wariant electronic).
    """
    if value is not None:
        return value
    if not z.get(key, None):
        return value
    try:
        value = z.get(key)[0]
    except IndexError:
        return None
    if value is not None and value == e_value:
        return None
    return value


def _extract_license(z: dict):
    """(pk_licencji, ilość_miesięcy) dla pierwszej dopasowanej licencji."""
    for _licencja in z.get("license", []):
        licencja = Komparator.porownaj_license(_licencja).rekord_po_stronie_bpp
        if licencja is None:
            continue
        ilosc_miesiecy = None
        try:
            ilosc_miesiecy = int(math.ceil(int(_licencja.get("delay-in-days")) / 30))
        except (TypeError, ValueError):
            pass
        return licencja.pk, ilosc_miesiecy
    return None, None


def convert_crossref_to_changeform_initial_data(z: dict) -> dict:
    """
    Funkcja, która przerabia słownik CrossRef API na słownik
    początkowych argumentów dla changeform. Używany wewnętrznie przez
    funkcje bpp django-admina, gdzie potrzeba skonwertować pobrany z
    CrossRef słownik do argumentów początkowych.
    """

    wydawca_idx, wydawca_txt = _extract_wydawca(z)

    e_issn, issn = _extract_issn_isbn_typed(z, "issn-type")
    e_isbn, isbn = _extract_issn_isbn_typed(z, "isbn-type")
    issn = _fallback_identifier(z, "ISSN", issn, e_issn)
    isbn = _fallback_identifier(z, "ISBN", isbn, e_isbn)

    licencja_pk, licencja_ilosc_miesiecy = _extract_license(z)

    rok = z.get("published", {}).get("date-parts", [[""]])[0][0]

    miejsce_i_rok = ""
    if z.get("publisher-location"):
        miejsce_i_rok = z.get("publisher-location") + " " + str(rok)

    return {
        "tytul_oryginalny": _extract_title(z),
        "zrodlo": _extract_zrodlo(z),
        "nr_zeszytu": z.get("issue", ""),
        "strony": z.get("page", ""),
        "slowa_kluczowe": ", ".join(f'"{x}"' for x in z.get("subject", [])),
        "wydawca": wydawca_idx,
        "wydawca_opis": wydawca_txt,
        "doi": z.get("DOI"),
        "charakter_formalny": _komparator_pk(Komparator.porownaj_type, z.get("type")),
        "jezyk": _komparator_pk(Komparator.porownaj_language, z.get("language")),
        "adnotacje": "Dodano na podstawie CrossRef API",
        "e_issn": e_issn,
        "e_isbn": e_isbn,
        "isbn": isbn,
        "oznaczenie_wydania": z.get("edition-number"),
        "miejsce_i_rok": miejsce_i_rok,
        "openaccess_licencja": licencja_pk,
        "openaccess_ilosc_miesiecy": licencja_ilosc_miesiecy,
        "issn": issn,
        "www": z.get("resource", {}).get("primary", {}).get("URL", ""),
        "tom": z.get("volume", ""),
        "rok": rok,
    }


def _merge_pbn_title(merged_data, data_sources, pbn_object):
    """Uzupełnij/poszerz tytuł danymi z PBN."""
    pbn_title = pbn_object.get("title")
    if not pbn_title:
        return
    if not merged_data.get("tytul_oryginalny"):
        merged_data["tytul_oryginalny"] = normalize_title(pbn_title)
        data_sources["tytul_oryginalny"] = "PBN"
    elif normalize_title(pbn_title) != merged_data.get("tytul_oryginalny"):
        # Jeśli tytuły się różnią, zachowaj oba z adnotacją
        merged_data["tytul_alternatywny"] = normalize_title(pbn_title)
        data_sources["tytul_alternatywny"] = "PBN"


def _merge_pbn_fill_or_conflict(merged_data, data_sources, field, pbn_value):
    """Uzupełnij puste pole z PBN albo oznacz konflikt CrossRef+PBN.

    Odwzorowuje powtarzający się wzorzec dla tom/nr_zeszytu/strony.
    """
    if not pbn_value:
        return
    if not merged_data.get(field):
        merged_data[field] = pbn_value
        data_sources[field] = "PBN"
    elif merged_data.get(field) != pbn_value:
        data_sources[field] = "CrossRef+PBN"


def _merge_pbn_uid(merged_data, data_sources, pbn_data):
    pbn_id = (
        pbn_data.get("pbnId") or pbn_data.get("objectId") or pbn_data.get("mongoId")
    )
    if pbn_id:
        # To pole będzie obsłużone osobno w widoku, ale zachowujemy informację
        merged_data["pbn_uid"] = pbn_id
        data_sources["pbn_uid"] = "PBN"


def _merge_pbn_charakter_formalny(merged_data, data_sources, pbn_object):
    pbn_type = pbn_object.get("type")
    if pbn_type and not merged_data.get("charakter_formalny"):
        # Mapowanie typu PBN na charakter formalny będzie przez Komparator
        cf = Komparator.porownaj_type(pbn_type).rekord_po_stronie_bpp
        if cf:
            merged_data["charakter_formalny"] = cf.pk
            data_sources["charakter_formalny"] = "PBN"


def _merge_pbn_simple_field(merged_data, data_sources, field, value):
    """Skopiuj proste, prawdziwe pole z PBN i oznacz jego źródło."""
    if value:
        merged_data[field] = value
        data_sources[field] = "PBN"


def merge_crossref_and_pbn_data(crossref_data: dict, pbn_data: dict) -> dict:
    """
    Funkcja łącząca dane z CrossRef API i PBN API.
    CrossRef jest bazą, PBN wzbogaca dane dodatkowymi polami.

    Strategia łączenia:
    - Podstawowe dane bibliograficzne z CrossRef
    - Uzupełnienie polami specyficznymi dla PBN (punktacja ministerialna, dyscypliny)
    - W przypadku konfliktów preferowane są bardziej kompletne dane
    - Pola specyficzne dla polskiego systemu nauki pochodzą z PBN
    """

    # Rozpocznij od danych CrossRef przekonwertowanych do formatu changeform
    merged_data = convert_crossref_to_changeform_initial_data(crossref_data)

    # Słownik przechowujący źródła danych dla każdego pola
    data_sources = {key: "CrossRef" for key in merged_data if merged_data[key]}

    # Jeśli nie ma danych PBN, zwróć tylko dane CrossRef
    if not pbn_data:
        merged_data["data_sources"] = data_sources
        merged_data["has_pbn_data"] = False
        return merged_data

    merged_data["has_pbn_data"] = True

    # Wyciągnij dane z obiektu PBN
    pbn_object = pbn_data.get("object", {}) if isinstance(pbn_data, dict) else {}

    _merge_pbn_title(merged_data, data_sources, pbn_object)

    _merge_pbn_simple_field(
        merged_data,
        data_sources,
        "punkty_kbn",
        pbn_object.get("mniswPointsForInstitution"),
    )

    _merge_pbn_fill_or_conflict(
        merged_data, data_sources, "tom", pbn_object.get("volume")
    )
    _merge_pbn_fill_or_conflict(
        merged_data, data_sources, "nr_zeszytu", pbn_object.get("issue")
    )
    _merge_pbn_fill_or_conflict(
        merged_data, data_sources, "strony", pbn_object.get("pages")
    )

    _merge_pbn_uid(merged_data, data_sources, pbn_data)
    _merge_pbn_charakter_formalny(merged_data, data_sources, pbn_object)

    # Liczba arkuszy wydawniczych (specyficzne dla PBN)
    _merge_pbn_simple_field(
        merged_data,
        data_sources,
        "liczba_arkuszy_wydawniczych",
        pbn_object.get("sheets"),
    )

    # Konferencja (jeśli jest w PBN)
    conference = pbn_object.get("conference")
    if conference:
        _merge_pbn_simple_field(
            merged_data,
            data_sources,
            "konferencja_nazwa",
            conference.get("name"),
        )

    # Dodaj informacje o autorach z PBN jeśli brakuje w CrossRef
    pbn_authors = pbn_object.get("authors", [])
    if pbn_authors and not crossref_data.get("author"):
        # To będzie obsłużone osobno w formularzu inline
        merged_data["pbn_authors"] = pbn_authors
        data_sources["pbn_authors"] = "PBN"

    # Zaktualizuj adnotacje
    adnotacje = ["Dodano na podstawie CrossRef API i PBN API"]
    if merged_data.get("tytul_alternatywny"):
        adnotacje.append(f"Tytuł w PBN: {merged_data['tytul_alternatywny']}")
    merged_data["adnotacje"] = "; ".join(adnotacje)
    data_sources["adnotacje"] = "CrossRef+PBN"

    # Dodaj informacje o źródłach danych
    merged_data["data_sources"] = data_sources

    return merged_data
