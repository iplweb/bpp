import math

from crossref_bpp.core import Komparator
from import_common.normalization import normalize_title


def convert_crossref_to_changeform_initial_data(z: dict) -> dict:
    """
    Funkcja, która przerabia słownik CrossRef API na słownik
    początkowych argumentów dla changeform. Używany wewnętrznie przez
    funkcje bpp django-admina, gdzie potrzeba skonwertować pobrany z
    CrossRef słownik do argumentów początkowych.
    """

    title = z.get("title")
    if isinstance(title, list):
        title = ". ".join(title)
    title = normalize_title(title)

    try:
        tytul_kontenera = z.get("container-title")[0]
    except IndexError:
        tytul_kontenera = None

    zrodlo = None
    if tytul_kontenera:
        zrodlo = Komparator.porownaj_container_title(
            tytul_kontenera
        ).rekord_po_stronie_bpp

    if zrodlo is not None:
        zrodlo = zrodlo.pk

    wydawca_txt = ""
    wydawca_idx = Komparator.porownaj_publisher(
        z.get("publisher")
    ).rekord_po_stronie_bpp
    if wydawca_idx is None:
        wydawca_txt = z.get("publisher")

    charakter_formalny_pk = None
    charakter_formalny = Komparator.porownaj_type(z.get("type")).rekord_po_stronie_bpp
    if charakter_formalny is not None:
        charakter_formalny_pk = charakter_formalny.pk

    jezyk_pk = None
    jezyk = Komparator.porownaj_language(z.get("language")).rekord_po_stronie_bpp
    if jezyk is not None:
        jezyk_pk = jezyk.pk

    issn = None
    e_issn = None
    if z.get("issn-type", []):
        for _issn in z.get("issn-type"):
            if _issn.get("type") == "electronic":
                e_issn = _issn.get("value")
            else:
                issn = _issn.get("value")

    isbn = None
    e_isbn = None
    if z.get("isbn-type", []):
        for _isbn in z.get("isbn-type"):
            if _isbn.get("type") == "electronic":
                e_isbn = _isbn.get("value")
            else:
                isbn = _isbn.get("value")

    # Jeżeli nie udało się pobrać ISSN w poprzedniej pętli przy analizie listy issn-type,
    # wobec tego pobierz ISSN z parametru ISSN po stronie crossref-api. ALE ustaw issn
    # jedynie wtedy gdy jest ono INNE niż e_issn (ustawiony w pętli powyżej):
    if issn is None:
        if z.get("ISSN", None):
            try:
                issn = z.get("ISSN")[0]
            except IndexError:
                issn = None

            if issn is not None:
                if issn == e_issn:
                    # Jeżeli ISSN jest RÓWNY e_issn czyli w polu ISSN w CrossRef API
                    # był podany ISSN typu "electronic", to w takim razie nie używaj tej
                    # wartości jako ISSN.
                    issn = None

    if isbn is None:
        if z.get("ISBN", None):
            try:
                isbn = z.get("ISBN")[0]
            except IndexError:
                isbn = None

            if isbn is not None:
                if isbn == e_isbn:
                    isbn = None

    licencja_pk = None
    licencja_ilosc_miesiecy = None
    for _licencja in z.get("license", []):
        licencja = Komparator.porownaj_license(_licencja).rekord_po_stronie_bpp
        if licencja is not None:
            licencja_pk = licencja.pk
            try:
                licencja_ilosc_miesiecy = int(
                    math.ceil(int(_licencja.get("delay-in-days")) / 30)
                )
            except (TypeError, ValueError):
                pass
            break

    rok = z.get("published", {}).get("date-parts", [[""]])[0][0]

    miejsce_i_rok = ""
    if z.get("publisher-location"):
        miejsce_i_rok = z.get("publisher-location") + " " + str(rok)

    ret = {
        "tytul_oryginalny": title,
        "zrodlo": zrodlo,
        "nr_zeszytu": z.get("issue", ""),
        "strony": z.get("page", ""),
        "slowa_kluczowe": ", ".join('"%s"' % x for x in z.get("subject", [])),
        "wydawca": wydawca_idx,
        "wydawca_opis": wydawca_txt,
        "doi": z.get("DOI"),
        "charakter_formalny": charakter_formalny_pk,
        "jezyk": jezyk_pk,
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

    return ret


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
    data_sources = {}

    # Oznacz wszystkie pola CrossRef
    for key in merged_data:
        if merged_data[key]:
            data_sources[key] = "CrossRef"

    # Jeśli nie ma danych PBN, zwróć tylko dane CrossRef
    if not pbn_data:
        merged_data["data_sources"] = data_sources
        merged_data["has_pbn_data"] = False
        return merged_data

    merged_data["has_pbn_data"] = True

    # Wyciągnij dane z obiektu PBN
    pbn_object = pbn_data.get("object", {}) if isinstance(pbn_data, dict) else {}

    # Uzupełnij tytuł jeśli brak w CrossRef lub różny
    pbn_title = pbn_object.get("title")
    if pbn_title:
        if not merged_data.get("tytul_oryginalny"):
            merged_data["tytul_oryginalny"] = normalize_title(pbn_title)
            data_sources["tytul_oryginalny"] = "PBN"
        elif normalize_title(pbn_title) != merged_data.get("tytul_oryginalny"):
            # Jeśli tytuły się różnią, zachowaj oba z adnotacją
            merged_data["tytul_alternatywny"] = normalize_title(pbn_title)
            data_sources["tytul_alternatywny"] = "PBN"

    # Dodaj punktację ministerialną z PBN
    mnisw_points = pbn_object.get("mniswPointsForInstitution")
    if mnisw_points:
        merged_data["punkty_kbn"] = mnisw_points
        data_sources["punkty_kbn"] = "PBN"

    # Uzupełnij numer tomu jeśli brak
    pbn_volume = pbn_object.get("volume")
    if pbn_volume and not merged_data.get("tom"):
        merged_data["tom"] = pbn_volume
        data_sources["tom"] = "PBN"
    elif pbn_volume and merged_data.get("tom") != pbn_volume:
        data_sources["tom"] = "CrossRef+PBN"

    # Uzupełnij numer wydania
    pbn_issue = pbn_object.get("issue")
    if pbn_issue and not merged_data.get("nr_zeszytu"):
        merged_data["nr_zeszytu"] = pbn_issue
        data_sources["nr_zeszytu"] = "PBN"
    elif pbn_issue and merged_data.get("nr_zeszytu") != pbn_issue:
        data_sources["nr_zeszytu"] = "CrossRef+PBN"

    # Uzupełnij strony
    pbn_pages = pbn_object.get("pages")
    if pbn_pages and not merged_data.get("strony"):
        merged_data["strony"] = pbn_pages
        data_sources["strony"] = "PBN"
    elif pbn_pages and merged_data.get("strony") != pbn_pages:
        data_sources["strony"] = "CrossRef+PBN"

    # Dodaj PBN UID jeśli dostępny
    pbn_id = (
        pbn_data.get("pbnId") or pbn_data.get("objectId") or pbn_data.get("mongoId")
    )
    if pbn_id:
        # To pole będzie obsłużone osobno w widoku, ale zachowujemy informację
        merged_data["pbn_uid"] = pbn_id
        data_sources["pbn_uid"] = "PBN"

    # Uzupełnij typ publikacji jeśli brak w CrossRef
    pbn_type = pbn_object.get("type")
    if pbn_type and not merged_data.get("charakter_formalny"):
        # Mapowanie typu PBN na charakter formalny będzie przez Komparator
        cf = Komparator.porownaj_type(pbn_type).rekord_po_stronie_bpp
        if cf:
            merged_data["charakter_formalny"] = cf.pk
            data_sources["charakter_formalny"] = "PBN"

    # Liczba arkuszy wydawniczych (specyficzne dla PBN)
    sheets = pbn_object.get("sheets")
    if sheets:
        merged_data["liczba_arkuszy_wydawniczych"] = sheets
        data_sources["liczba_arkuszy_wydawniczych"] = "PBN"

    # Konferencja (jeśli jest w PBN)
    conference = pbn_object.get("conference")
    if conference:
        conference_name = conference.get("name")
        if conference_name:
            merged_data["konferencja_nazwa"] = conference_name
            data_sources["konferencja_nazwa"] = "PBN"

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
