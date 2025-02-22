from .mixins import (  # noqa
    AdnotacjeZDatamiMixin,
    AdnotacjeZDatamiOrazPBNMixin,
    ZapiszZAdnotacjaMixin,
)

ADNOTACJE_FIELDSET = (
    "Adnotacje",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": (ZapiszZAdnotacjaMixin.readonly_fields + ("adnotacje",)),
    },
)

ADNOTACJE_Z_DATAMI_FIELDSET = (
    "Adnotacje",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": AdnotacjeZDatamiMixin.readonly_fields + ("adnotacje",),
    },
)

ADNOTACJE_Z_DATAMI_ORAZ_PBN_FIELDSET = (
    "Adnotacje",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": AdnotacjeZDatamiOrazPBNMixin.readonly_fields + ("adnotacje",),
    },
)

OPENACCESS_FIELDSET = (
    "OpenAccess",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": (
            "openaccess_tryb_dostepu",
            "openaccess_licencja",
            "openaccess_wersja_tekstu",
            "openaccess_czas_publikacji",
            "openaccess_ilosc_miesiecy",
        ),
    },
)

DWA_TYTULY = (
    "tytul_oryginalny",
    "tytul",
)

MODEL_ZE_SZCZEGOLAMI = (
    "informacje",
    "szczegoly",
    "uwagi",
    "slowa_kluczowe",
    "slowa_kluczowe_eng",
    "strony",
    "tom",
)

MODEL_Z_ISSN = (
    "issn",
    "e_issn",
)

MODEL_Z_PBN_UID = ("pbn_uid",)

MODEL_Z_OPLATA_ZA_PUBLIKACJE = (
    "opl_pub_cost_free",
    "opl_pub_research_potential",
    "opl_pub_research_or_development_projects",
    "opl_pub_other",
    "opl_pub_amount",
)

MODEL_Z_OPLATA_ZA_PUBLIKACJE_FIELDSET = (
    "Opłata za publikację",
    {"classes": ("grp-collapse grp-closed",), "fields": MODEL_Z_OPLATA_ZA_PUBLIKACJE},
)

MODEL_Z_ISBN = (
    "isbn",
    "e_isbn",
)

MODEL_Z_WWW = (
    "www",
    "dostep_dnia",
    "public_www",
    "public_dostep_dnia",
)

MODEL_Z_PUBMEDID = ("pubmed_id", "pmc_id")

MODEL_Z_DOI = ("doi",)

MODEL_Z_LICZBA_CYTOWAN = ("liczba_cytowan",)

MODEL_Z_MIEJSCEM_PRZECHOWYWANIA = ("numer_odbitki",)

MODEL_Z_ROKIEM = ("rok",)

MODEL_TYPOWANY = (
    "jezyk",
    "jezyk_alt",
    "jezyk_orig",
    "typ_kbn",
)

MODEL_PUNKTOWANY_BAZA = (
    "punkty_kbn",
    "impact_factor",
    "index_copernicus",
    "punktacja_snip",
    "punktacja_wewnetrzna",
)

MODEL_PUNKTOWANY = MODEL_PUNKTOWANY_BAZA + ("weryfikacja_punktacji",)

MODEL_PUNKTOWANY_Z_KWARTYLAMI_BAZA = MODEL_PUNKTOWANY_BAZA + (
    "kwartyl_w_scopus",
    "kwartyl_w_wos",
)

MODEL_PUNKTOWANY_Z_KWARTYLAMI = MODEL_PUNKTOWANY_Z_KWARTYLAMI_BAZA + (
    "weryfikacja_punktacji",
)

MODEL_Z_INFORMACJA_Z = ("informacja_z",)

MODEL_Z_LICZBA_ZNAKOW_WYDAWNICZYCH = ("liczba_znakow_wydawniczych",)

MODEL_ZE_STATUSEM = ("status_korekty",)

MODEL_RECENZOWANY = ("recenzowana",)

MODEL_TYPOWANY_BEZ_CHARAKTERU_FIELDSET = (
    "Typ",
    {"classes": ("",), "fields": MODEL_TYPOWANY},
)

MODEL_TYPOWANY_FIELDSET = (
    "Typ",
    {"classes": ("",), "fields": ("charakter_formalny",) + MODEL_TYPOWANY},
)

MODEL_PUNKTOWANY_FIELDSET = (
    "Punktacja",
    {"classes": ("",), "fields": MODEL_PUNKTOWANY},
)

MODEL_PUNKTOWANY_WYDAWNICTWO_CIAGLE_FIELDSET = (
    "Punktacja",
    {
        "classes": ("",),
        "fields": MODEL_PUNKTOWANY_Z_KWARTYLAMI + ("uzupelnij_punktacje",),
    },
)

MODEL_OPCJONALNIE_NIE_EKSPORTOWANY_DO_API_FIELDSET = (
    "Eksport do API",
    {"classes": ("grp-collapse grp-closed",), "fields": ("nie_eksportuj_przez_api",)},
)

POZOSTALE_MODELE_FIELDSET = (
    "Pozostałe informacje",
    {
        "classes": ("",),
        "fields": MODEL_Z_INFORMACJA_Z + MODEL_ZE_STATUSEM + MODEL_RECENZOWANY,
    },
)

POZOSTALE_MODELE_WYDAWNICTWO_CIAGLE_FIELDSET = (
    "Pozostałe informacje",
    {
        "classes": ("",),
        "fields": MODEL_Z_LICZBA_ZNAKOW_WYDAWNICZYCH
        + MODEL_Z_INFORMACJA_Z
        + MODEL_ZE_STATUSEM
        + MODEL_RECENZOWANY,
    },
)

POZOSTALE_MODELE_WYDAWNICTWO_ZWARTE_FIELDSET = (
    "Pozostałe informacje",
    {
        "classes": ("",),
        "fields": MODEL_Z_LICZBA_ZNAKOW_WYDAWNICZYCH
        + MODEL_Z_INFORMACJA_Z
        + MODEL_ZE_STATUSEM
        + MODEL_RECENZOWANY,
    },
)

SERIA_WYDAWNICZA_FIELDSET = (
    "Seria wydawnicza",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": ("seria_wydawnicza", "numer_w_serii"),
    },
)

PRACA_WYBITNA_FIELDSET = (
    "Praca wybitna",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": ("praca_wybitna", "uzasadnienie_wybitnosci"),
    },
)

PRZED_PO_LISCIE_AUTOROW_FIELDSET = (
    "Dowolny tekst przed lub po liście autorów",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": ("tekst_przed_pierwszym_autorem", "tekst_po_ostatnim_autorze"),
    },
)

EKSTRA_INFORMACJE_WYDAWNICTWO_CIAGLE_FIELDSET = (
    "Ekstra informacje",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": MODEL_Z_PBN_UID
        + MODEL_Z_ISSN
        + MODEL_Z_WWW
        + MODEL_Z_PUBMEDID
        + MODEL_Z_DOI
        + MODEL_Z_LICZBA_CYTOWAN
        + MODEL_Z_MIEJSCEM_PRZECHOWYWANIA,
    },
)

EKSTRA_INFORMACJE_WYDAWNICTWO_ZWARTE_FIELDSET = (
    "Ekstra informacje",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": MODEL_Z_PBN_UID
        + MODEL_Z_ISSN
        + MODEL_Z_WWW
        + MODEL_Z_PUBMEDID
        + MODEL_Z_DOI
        + MODEL_Z_LICZBA_CYTOWAN
        + MODEL_Z_MIEJSCEM_PRZECHOWYWANIA,
    },
)

EKSTRA_INFORMACJE_DOKTORSKA_HABILITACYJNA_FIELDSET = (
    "Ekstra informacje",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": MODEL_Z_WWW
        + MODEL_Z_PUBMEDID
        + MODEL_Z_DOI
        + MODEL_Z_LICZBA_CYTOWAN
        + MODEL_Z_MIEJSCEM_PRZECHOWYWANIA,
    },
)
