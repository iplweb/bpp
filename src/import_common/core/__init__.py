"""Wspólny rdzeń logiki matchowania dla wszystkich importerów BPP.

Pakiet powstał z podziału jednoplikowego `import_common/core.py` (~880 linii)
na tematyczne podmoduły, ale zachowuje pełne API publiczne pod starym
namespace -- wszystkie symbole importowane z `import_common.core` zachowują
swoją ścieżkę.

Podział na podmoduły:

- `tytul_funkcja`  -- matchery dla słownikowych encji (Wydzial, Tytul,
  Funkcja_Autora, Grupa_Pracownicza, Wymiar_Etatu)
- `jednostka`      -- matchowanie jednostek + helper `wytnij_skrot`
- `autor`          -- matchowanie autorów (po identyfikatorach + imieniu)
- `zrodlo`         -- matchowanie czasopism (ISSN, mniswId, tytuł)
- `dyscyplina`     -- matchowanie dyscyplin BPP i PBN
- `wydawca`        -- matchowanie wydawców
- `uczelnia`       -- matchowanie uczelni (PBN Institution)
- `publikacja`     -- matchowanie rekordów publikacji + pomocnicze stałe
- `normalize_db`   -- wyrażenia ORM do znormalizowanych pól + ich pythonowe
  odpowiedniki + `normalize_date`
"""

from .autor import (
    _build_autor_name_query,
    _try_get_autor_by_bpp_id,
    _try_get_autor_by_orcid,
    _try_get_autor_by_pbn_id,
    _try_get_autor_by_pbn_uid_id,
    _try_get_autor_by_system_kadrowy_id,
    _try_match_autor_by_direct_ids,
    _try_match_autor_by_name,
    _try_match_autor_in_jednostka,
    _try_match_autor_with_orcid_or_tytul,
    matchuj_autora,
)
from .dyscyplina import (
    matchuj_aktualna_dyscypline_pbn,
    matchuj_dyscypline,
    matchuj_nieaktualna_dyscypline_pbn,
    normalize_kod_dyscypliny_pbn,
)
from .jednostka import matchuj_jednostke, wytnij_skrot
from .normalize_db import (
    normalize_date,
    normalize_zrodlo_nazwa_for_db_lookup,
    normalize_zrodlo_skrot_for_db_lookup,
    normalized_db_isbn,
    normalized_db_title,
    normalized_db_zrodlo_nazwa,
    normalized_db_zrodlo_skrot,
)
from .publikacja import (
    MATCH_SIMILARITY_THRESHOLD,
    MATCH_SIMILARITY_THRESHOLD_LOW,
    MATCH_SIMILARITY_THRESHOLD_VERY_LOW,
    TITLE_LIMIT_MANY_WORDS,
    TITLE_LIMIT_SINGLE_WORD,
    _build_isbn_query,
    _check_candidate,
    _is_title_long_enough,
    _isbn_matches,
    _part_numbers_compatible,
    _try_match_pub_by_doi,
    _try_match_pub_by_isbn,
    _try_match_pub_by_title,
    _try_match_pub_by_uri,
    _try_match_pub_by_zrodlo,
    matchuj_publikacje,
)
from .tytul_funkcja import (
    matchuj_funkcja_autora,
    matchuj_grupa_pracownicza,
    matchuj_tytul,
    matchuj_wydzial,
    matchuj_wymiar_etatu,
)
from .uczelnia import matchuj_uczelnie
from .wydawca import matchuj_wydawce
from .zrodlo import (
    _try_match_zrodlo_by_issn,
    _try_match_zrodlo_by_mnisw_id,
    _try_match_zrodlo_by_title_single,
    matchuj_zrodlo,
)

__all__ = [
    # autor
    "matchuj_autora",
    "_build_autor_name_query",
    "_try_get_autor_by_bpp_id",
    "_try_get_autor_by_orcid",
    "_try_get_autor_by_pbn_id",
    "_try_get_autor_by_pbn_uid_id",
    "_try_get_autor_by_system_kadrowy_id",
    "_try_match_autor_by_direct_ids",
    "_try_match_autor_by_name",
    "_try_match_autor_in_jednostka",
    "_try_match_autor_with_orcid_or_tytul",
    # dyscyplina
    "matchuj_dyscypline",
    "matchuj_aktualna_dyscypline_pbn",
    "matchuj_nieaktualna_dyscypline_pbn",
    "normalize_kod_dyscypliny_pbn",
    # jednostka
    "matchuj_jednostke",
    "wytnij_skrot",
    # normalize_db
    "normalize_date",
    "normalize_zrodlo_nazwa_for_db_lookup",
    "normalize_zrodlo_skrot_for_db_lookup",
    "normalized_db_isbn",
    "normalized_db_title",
    "normalized_db_zrodlo_nazwa",
    "normalized_db_zrodlo_skrot",
    # publikacja
    "matchuj_publikacje",
    "MATCH_SIMILARITY_THRESHOLD",
    "MATCH_SIMILARITY_THRESHOLD_LOW",
    "MATCH_SIMILARITY_THRESHOLD_VERY_LOW",
    "TITLE_LIMIT_MANY_WORDS",
    "TITLE_LIMIT_SINGLE_WORD",
    "_build_isbn_query",
    "_check_candidate",
    "_is_title_long_enough",
    "_isbn_matches",
    "_part_numbers_compatible",
    "_try_match_pub_by_doi",
    "_try_match_pub_by_isbn",
    "_try_match_pub_by_title",
    "_try_match_pub_by_uri",
    "_try_match_pub_by_zrodlo",
    # tytul_funkcja
    "matchuj_funkcja_autora",
    "matchuj_grupa_pracownicza",
    "matchuj_tytul",
    "matchuj_wydzial",
    "matchuj_wymiar_etatu",
    # uczelnia
    "matchuj_uczelnie",
    # wydawca
    "matchuj_wydawce",
    # zrodlo
    "matchuj_zrodlo",
    "_try_match_zrodlo_by_issn",
    "_try_match_zrodlo_by_mnisw_id",
    "_try_match_zrodlo_by_title_single",
]
