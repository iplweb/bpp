"""PBN integrator utils module.

This module provides utilities for integrating with the Polish Bibliography Network (PBN).
The code has been refactored into logical submodules while maintaining backwards compatibility.

Submodules:
- constants: Constants used throughout the module
- django_imports: Deferred Django imports
- mongodb_ops: MongoDB save operations
- dictionaries: Languages, countries, disciplines integration
- institutions: Institution operations
- conferences: Conference operations
- journals: Journal/source operations
- publishers: Publisher operations
- offline_data: Offline data operations
- publications: Publication operations
- scientists: Scientist/author operations
- synchronization: Publication synchronization
- integration: Publication integration
- statements: Statement operations
- multiprocessing_utils: Multiprocessing utilities
- cleanup: Cleanup operations
"""

from __future__ import annotations

# Re-export from istarmap for backwards compatibility
from pbn_integrator.utils import istarmap  # noqa

# Cleanup
from pbn_integrator.utils.cleanup import (  # noqa
    clear_all,
    clear_match_publications,
    clear_publications,
)

# Conferences
from pbn_integrator.utils.conferences import pobierz_konferencje  # noqa

# Constants
from pbn_integrator.utils.constants import (  # noqa
    CPU_COUNT,
    DEFAULT_CONTEXT,
    MODELE_Z_PBN_UID,
    PBN_KOMUNIKAT_DOI_ISTNIEJE,
    PBN_KOMUNIKAT_ISBN_ISTNIEJE,
)

# Dictionaries (languages, countries, disciplines)
from pbn_integrator.utils.dictionaries import (  # noqa
    integruj_dyscypliny,
    integruj_jezyki,
    integruj_kraje,
)

# Django imports
from pbn_integrator.utils.django_imports import (  # noqa
    _ensure_django_imports,
    matchuj_autora,
    matchuj_wydawce,
    normalize_doi,
    normalize_isbn,
    normalize_tytul_publikacji,
)

# Institutions
from pbn_integrator.utils.institutions import (  # noqa
    InstitutionGetter,
    integruj_instytucje,
    integruj_uczelnie,
    pobierz_instytucje,
    pobierz_instytucje_polon,
)

# Integration
from pbn_integrator.utils.integration import (  # noqa
    _integruj_publikacje,
    _integruj_publikacje_threaded,
    _integruj_single_part,
    integruj_publikacje_instytucji,
    integruj_wszystkie_publikacje,
    ustaw_pbn_uid_jesli_brak,
)

# Backwards compatibility alias
zweryfikuj_lub_stworz_match = ustaw_pbn_uid_jesli_brak

# Journals
from pbn_integrator.utils.journals import (  # noqa
    ZrodlaGetter,
    integruj_zrodla,
    pobierz_zrodla,
    pobierz_zrodla_mnisw,
)

# MongoDB operations
from pbn_integrator.utils.mongodb_ops import (  # noqa
    ensure_institution_exists,
    ensure_person_exists,
    ensure_publication_exists,
    pobierz_mongodb,
    zapisz_mongodb,
    zapisz_oswiadczenie_instytucji,
    zapisz_publikacje_instytucji,
)

# Multiprocessing utils
from pbn_integrator.utils.multiprocessing_utils import (  # noqa
    _bede_uzywal_bazy_danych_z_multiprocessing_z_django,
    _init,
    initialize_pool,
    split_list,
    wait_for_results,
)

# Offline data
from pbn_integrator.utils.offline_data import (  # noqa
    _pobierz_offline,
    _single_unit_offline,
    _single_unit_wgraj,
    _wgraj_z_offline_do_bazy,
    pbn_file_path,
    pobierz_ludzi_offline,
    pobierz_prace_offline,
    wgraj_ludzi_z_offline_do_bazy,
    wgraj_prace_z_offline_do_bazy,
)

# Publications
from pbn_integrator.utils.publications import (  # noqa
    OswiadczeniaInstytucjiGetter,
    PublikacjeInstytucjiGetter,
    _pobierz_pojedyncza_prace,
    _pobierz_prace_po_elemencie,
    pobierz_brakujace_publikacje_batch,
    pobierz_oswiadczenia_z_instytucji,
    pobierz_prace,
    pobierz_prace_po_doi,
    pobierz_prace_po_isbn,
    pobierz_publikacje_z_instytucji,
    pobierz_publikacje_z_instytucji_v2,
    pobierz_rekordy_publikacji_instytucji,
    zapisz_publikacje_instytucji_v2,
)

# Publishers
from pbn_integrator.utils.publishers import (  # noqa
    PublisherGetter,
    integruj_wydawcow,
    pobierz_wydawcow_mnisw,
    pobierz_wydawcow_wszystkich,
)

# Scientists
from pbn_integrator.utils.scientists import (  # noqa
    integruj_autorow_z_uczelni,
    integruj_wszystkich_niezintegrowanych_autorow,
    matchuj_autora_po_stronie_pbn,
    pbn_json_wez_pbn_id_stare,
    pobierz_i_zapisz_dane_jednej_osoby,
    pobierz_ludzi_z_uczelni,
    utworz_wpis_dla_jednego_autora,
    weryfikuj_orcidy,
)

# Statements
from pbn_integrator.utils.statements import (  # noqa
    integruj_oswiadczenia_pbn_first_import,
    integruj_oswiadczenia_z_instytucji,
    integruj_oswiadczenia_z_instytucji_pojedyncza_praca,
    sprawdz_ilosc_autorow_przy_zmatchowaniu,
    usun_wszystkie_oswiadczenia,
    usun_zerowe_oswiadczenia,
    wyswietl_niezmatchowane_ze_zblizonymi_tytulami,
)

# Synchronization
from pbn_integrator.utils.synchronization import (  # noqa
    _synchronizuj_pojedyncza_publikacje,
    synchronizuj_publikacje,
    wydawnictwa_ciagle_do_synchronizacji,
    wydawnictwa_zwarte_do_synchronizacji,
    wyslij_informacje_o_platnosciach,
)

# Re-export from threaded_page_getter for backwards compatibility
from pbn_integrator.utils.threaded_page_getter import (  # noqa
    ThreadedMongoDBSaver,
    ThreadedPageGetter,
    threaded_page_getter,
)

# Expose all public names for backwards compatibility
__all__ = [
    # Constants
    "CPU_COUNT",
    "DEFAULT_CONTEXT",
    "MODELE_Z_PBN_UID",
    "PBN_KOMUNIKAT_DOI_ISTNIEJE",
    "PBN_KOMUNIKAT_ISBN_ISTNIEJE",
    # Django imports
    "_ensure_django_imports",
    "matchuj_autora",
    "matchuj_wydawce",
    "normalize_doi",
    "normalize_isbn",
    "normalize_tytul_publikacji",
    # Multiprocessing utils
    "_bede_uzywal_bazy_danych_z_multiprocessing_z_django",
    "_init",
    "initialize_pool",
    "split_list",
    "wait_for_results",
    # MongoDB operations
    "ensure_institution_exists",
    "ensure_person_exists",
    "ensure_publication_exists",
    "pobierz_mongodb",
    "zapisz_mongodb",
    "zapisz_oswiadczenie_instytucji",
    "zapisz_publikacje_instytucji",
    # Dictionaries
    "integruj_dyscypliny",
    "integruj_jezyki",
    "integruj_kraje",
    # Institutions
    "InstitutionGetter",
    "integruj_instytucje",
    "integruj_uczelnie",
    "pobierz_instytucje",
    "pobierz_instytucje_polon",
    # Conferences
    "pobierz_konferencje",
    # Journals
    "ZrodlaGetter",
    "integruj_zrodla",
    "pobierz_zrodla",
    "pobierz_zrodla_mnisw",
    # Publishers
    "PublisherGetter",
    "integruj_wydawcow",
    "pobierz_wydawcow_mnisw",
    "pobierz_wydawcow_wszystkich",
    # Offline data
    "_pobierz_offline",
    "_single_unit_offline",
    "_single_unit_wgraj",
    "_wgraj_z_offline_do_bazy",
    "pbn_file_path",
    "pobierz_ludzi_offline",
    "pobierz_prace_offline",
    "wgraj_ludzi_z_offline_do_bazy",
    "wgraj_prace_z_offline_do_bazy",
    # Publications
    "OswiadczeniaInstytucjiGetter",
    "PublikacjeInstytucjiGetter",
    "_pobierz_pojedyncza_prace",
    "_pobierz_prace_po_elemencie",
    "pobierz_brakujace_publikacje_batch",
    "pobierz_oswiadczenia_z_instytucji",
    "pobierz_prace",
    "pobierz_prace_po_doi",
    "pobierz_prace_po_isbn",
    "pobierz_publikacje_z_instytucji",
    "pobierz_publikacje_z_instytucji_v2",
    "pobierz_rekordy_publikacji_instytucji",
    "zapisz_publikacje_instytucji_v2",
    # Scientists
    "integruj_autorow_z_uczelni",
    "integruj_wszystkich_niezintegrowanych_autorow",
    "matchuj_autora_po_stronie_pbn",
    "pbn_json_wez_pbn_id_stare",
    "pobierz_i_zapisz_dane_jednej_osoby",
    "pobierz_ludzi_z_uczelni",
    "utworz_wpis_dla_jednego_autora",
    "weryfikuj_orcidy",
    # Synchronization
    "_synchronizuj_pojedyncza_publikacje",
    "synchronizuj_publikacje",
    "wydawnictwa_ciagle_do_synchronizacji",
    "wydawnictwa_zwarte_do_synchronizacji",
    "wyslij_informacje_o_platnosciach",
    # Integration
    "_integruj_publikacje",
    "_integruj_publikacje_threaded",
    "_integruj_single_part",
    "integruj_publikacje_instytucji",
    "integruj_wszystkie_publikacje",
    "ustaw_pbn_uid_jesli_brak",
    "zweryfikuj_lub_stworz_match",  # Backwards compatibility alias
    # Statements
    "integruj_oswiadczenia_pbn_first_import",
    "integruj_oswiadczenia_z_instytucji",
    "integruj_oswiadczenia_z_instytucji_pojedyncza_praca",
    "sprawdz_ilosc_autorow_przy_zmatchowaniu",
    "usun_wszystkie_oswiadczenia",
    "usun_zerowe_oswiadczenia",
    "wyswietl_niezmatchowane_ze_zblizonymi_tytulami",
    # Cleanup
    "clear_all",
    "clear_match_publications",
    "clear_publications",
    # Threaded page getter
    "ThreadedMongoDBSaver",
    "ThreadedPageGetter",
    "threaded_page_getter",
]
