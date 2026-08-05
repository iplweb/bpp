"""Mapowanie typów BPP na słownik COAR Resource Types.

``Publication/Type`` i ``Patent/Type`` są w profilu **obowiązkowe**
(``mandatory (1)``), więc każdy eksportowany rekord musi mieć wartość
z tego słownika.

Fallback dla niezmapowanego typu to korzeń odpowiedniej gałęzi hierarchii.
Jest to legalna wartość słownika, więc walidator przechodzi, a rekord nie
znika po cichu z eksportu. Alternatywa — pomijanie niezmapowanych — cicho
gubiłaby publikacje z bibliografii, co przy eksporcie do OpenAIRE jest
gorsze niż typ zbyt ogólny.

Zawartość obu słowników jest przepisana 1:1 z plików schematu profilu
OpenAIRE CRIS 1.2:

- ``https://www.openaire.eu/schema/cris/1.2/vocabularies/
  coar_publication_types.xsd`` (poddrzewo ``text``),
- ``https://www.openaire.eu/schema/cris/1.2/vocabularies/
  coar_patent_types.xsd`` (poddrzewo ``patent``).

To one, a nie bieżący stan słownika COAR, wyznaczają zbiór wartości
przechodzących walidację XSD — profil zamraża wersję słownika, więc terminy
oznaczone w nim jako *deprecated* nadal są legalne i zostają tutaj.
"""

BAZA = "http://purl.org/coar/resource_type/"

TEKST_ROOT = BAZA + "c_18cf"
PATENT_ROOT = BAZA + "c_15cd"
JOURNAL = BAZA + "c_0640"
DOCTORAL_THESIS = BAZA + "c_db06"
# COAR nie zna habilitacji. `doctoral thesis` byłoby bliższe praktyce, ale
# formalnie nieprawdziwe — bierzemy nadrzędne `thesis`.
THESIS = BAZA + "c_46ec"

# URI → angielski termin ze schematu. Termin nie jest używany do walidacji
# (ta idzie po kluczach), służy dokumentacji i raportowi mapowań.
TYPY_TEKSTOWE = {
    BAZA + "c_1162": "annotation",
    BAZA + "c_7a1f": "bachelor thesis",
    BAZA + "c_86bc": "bibliography",
    BAZA + "c_6947": "blog post",
    BAZA + "c_2f33": "book",
    BAZA + "c_3248": "book part",
    BAZA + "c_ba08": "book review",
    BAZA + "c_7877": "clinical study",
    BAZA + "D97F-VB57": "commentary",
    BAZA + "c_c94f": "conference output",
    BAZA + "c_5794": "conference paper",
    BAZA + "c_18cp": "conference paper not in proceedings",
    BAZA + "c_6670": "conference poster",
    BAZA + "c_18co": "conference poster not in proceedings",
    BAZA + "R60J-J5BD": "conference presentation",
    BAZA + "c_f744": "conference proceedings",
    BAZA + "c_3e5a": "contribution to journal (deprecated since 2021-03-12)",
    BAZA + "c_7acd": "corrigendum",
    BAZA + "c_ab20": "data management plan",
    BAZA + "c_beb9": "data paper",
    BAZA + "c_db06": "doctoral thesis",
    BAZA + "c_b239": "editorial",
    BAZA + "c_18ww": "internal report (deprecated since 2021-03-12)",
    BAZA + "c_0640": "journal",
    BAZA + "c_6501": "journal article",
    BAZA + "c_8544": "lecture",
    BAZA + "c_0857": "letter",
    BAZA + "c_545b": "letter to the editor",
    BAZA + "c_2cd9": "magazine",
    BAZA + "c_0040": "manuscript",
    BAZA + "c_bdcc": "master thesis",
    BAZA + "c_18wz": "memorandum",
    BAZA + "c_18cw": "musical notation",
    BAZA + "c_2fe3": "newspaper",
    BAZA + "c_998f": "newspaper article",
    BAZA + "QX5C-AR31": "other periodical",
    BAZA + "c_18wq": "other type of report (deprecated since 2021-03-12)",
    BAZA + "H9BQ-739P": "peer review",
    BAZA + "c_2659": "periodical (deprecated since 2021-03-12)",
    BAZA + "c_186u": "policy report (deprecated)",
    BAZA + "c_816b": "preprint (deprecated)",
    BAZA + "c_18op": "project deliverable",
    BAZA + "c_93fc": "report",
    BAZA + "c_ba1f": "report part (deprecated since 2021-03-12)",
    BAZA + "c_18hj": "report to funding agency (deprecated since 2021-03-12)",
    BAZA + "c_2df8fbb1": "research article",
    BAZA + "c_baaf": "research proposal",
    BAZA + "YZ1N-ZFT9": "research protocol",
    BAZA + "c_18ws": "research report",
    BAZA + "c_efa0": "review",
    BAZA + "c_dcae04bc": "review article",
    BAZA + "c_7bab": "software paper",
    BAZA + "c_71bd": "technical documentation",
    BAZA + "c_18gh": "technical report",
    BAZA + "c_18cf": "text",
    BAZA + "c_46ec": "thesis",
    BAZA + "6NC7-GK9S": "transcription",
    BAZA + "c_8042": "working paper",
}

TYPY_PATENTOWE = {
    BAZA + "SB3Y-W4EH": "PCT application",
    BAZA + "C53B-JCY5": "design patent",
    BAZA + "c_15cd": "patent",
    BAZA + "Z907-YMBB": "plant patent",
    BAZA + "GPQ7-G5VE": "plant variety protection",
    BAZA + "MW8G-3CR8": "software patent",
    BAZA + "9DKX-KSAF": "utility model",
}

WSZYSTKIE = frozenset(TYPY_TEKSTOWE) | frozenset(TYPY_PATENTOWE)


def _z_galezi(coar_type, dozwolone, korzen):
    """Wartość z podanej gałęzi hierarchii albo jej korzeń.

    Wartość z **innej** gałęzi (np. URI patentu wpisany przy charakterze
    formalnym) jest tu tak samo zła jak wartość spoza słownika: profil
    ogranicza ``Publication/Type`` i ``Patent/Type`` do rozłącznych
    enumeracji, więc przepuszczona wprost wywaliłaby walidację XSD.
    """
    if not coar_type:
        return korzen

    uri = coar_type.strip()
    return uri if uri in dozwolone else korzen


def typ_publikacji(coar_type):
    """URI typu publikacji; ``TEKST_ROOT`` gdy brak mapowania."""
    return _z_galezi(coar_type, TYPY_TEKSTOWE, TEKST_ROOT)


def typ_patentu(coar_type):
    """URI typu patentu; ``PATENT_ROOT`` gdy brak mapowania."""
    return _z_galezi(coar_type, TYPY_PATENTOWE, PATENT_ROOT)


def znany(uri) -> bool:
    """Czy URI należy do słownika COAR obsługiwanego przez profil?"""
    if not uri:
        return False

    return uri.strip() in WSZYSTKIE
