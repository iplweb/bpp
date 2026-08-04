"""Wspólne cegiełki serializerów CERIF.

Reguła obowiązująca cały pakiet ``cerif_export.cerif``: **serializer nie
dotyka bazy**. Wolno czytać pola załadowanego obiektu, pola ``*_id`` kluczy
obcych oraz relacje, które provider zadeklarował jako prefetchowane
(``obj.autorzy_set.all()`` na prefetchu jest odczytem z cache, nie zapytaniem).
Nie wolno wołać ``.filter()``/``.get()`` ani przechodzić po FK, których
provider nie wciągnął w ``select_related``.

Widoczność encji sąsiadujących rozstrzyga wyłącznie
:meth:`KontekstSerializacji.id_dla` — czyste sprawdzenie przynależności do
prekomputowanego zbioru.

Atrybut ``@id``
---------------

W ``@id`` idzie **człon lokalny** identyfikatora OAI (``Publications/wc-12``),
a nie cały ``oai:{namespace}:Publications/wc-12``. Tak wymaga
``openaire-cris-validator``: sprawdza, że nagłówkowy ``<identifier>`` jest
równy ``"oai:" + repoId + ":" + localName + "s/" + @id`` **albo**
``"oai:" + repoId + ":" + @id`` (``CRISValidator.wrapCheckOAIIdentifier``).
Wstawienie pełnego identyfikatora OAI w ``@id`` dałoby po sklejeniu
``oai:ns:oai:ns:…`` i wywaliłoby walidator.
"""

import datetime
import html
import re
from urllib.parse import urlsplit

from lxml import etree

from cerif_export import const, identyfikatory

NS = const.NS_CERIF
NS_XML = "http://www.w3.org/XML/1998/namespace"
XML_LANG = f"{{{NS_XML}}}lang"

# Mapa prefiksów używana przy budowaniu elementu-korzenia rekordu. Domyślny
# namespace to profil CERIF; słowniki COAR mają własne przestrzenie nazw i są
# deklarowane lokalnie na swoich elementach.
NSMAP_REKORDU = {None: NS}

# Schematy klasyfikacji używane w atrybucie ``scheme`` (wymagany przez
# ``cfGenericURIClassification__Type``). Atrybut ma nazwać słownik, z którego
# pochodzi wartość — dobieramy go do faktycznego URI licencji zamiast wpisywać
# na sztywno SPDX, bo w BPP ogromna większość licencji to Creative Commons.
SCHEMAT_LICENCJI_CC = "https://creativecommons.org/licenses/"
SCHEMAT_LICENCJI_SPDX = "https://spdx.org/licenses"


def schemat_licencji(uri):
    """Dobierz wartość atrybutu ``scheme`` do URI licencji.

    Porównujemy **host**, nie podciąg. ``Licencja_OpenAccess.uri`` jest polem
    edytowalnym w adminie, więc adres w rodzaju
    ``https://example.invalid/?x=creativecommons.org`` przechodziłby test
    ``"creativecommons.org" in uri`` i dostawał etykietę schematu CC.
    Skutek byłby łagodny (mylący atrybut ``scheme`` w XML-u), ale samo
    sprawdzenie jest po prostu niepoprawne — CodeQL zgłasza to jako
    ``py/incomplete-url-substring-sanitization``.
    """
    if not uri:
        return SCHEMAT_LICENCJI_SPDX

    host = (urlsplit(uri).hostname or "").lower()
    if host == "creativecommons.org" or host.endswith(".creativecommons.org"):
        return SCHEMAT_LICENCJI_CC
    return SCHEMAT_LICENCJI_SPDX


# Typy identyfikatorów CERIF dla elementu generycznego ``Identifier``.
TYP_ID_PBN = "https://pbn.nauka.gov.pl/core/#/scientist"
TYP_ID_ORCID = "https://w3id.org/cerif/vocab/IdentifierTypes#ORCID"

# Atrybut, pod którym provider MOŻE podwiesić listę plików repozytorium
# (``Element_Repozytorium``) danej publikacji. ``Element_Repozytorium`` jest
# powiązany przez ``GenericForeignKey`` bez odwrotnej ``GenericRelation``, więc
# serializer nie ma jak ich dociągnąć bez zapytania — a nie wolno mu.
# Gdy atrybutu nie ma, ``FileLocations`` po prostu nie powstaje.
ATRYBUT_PLIKI = "cerif_pliki"

# Atrybut, pod którym provider podaje gotowy URI typu COAR dla prac
# doktorskich i habilitacyjnych. ``Praca_Doktorska.charakter_formalny`` jest
# ``cached_property`` robiącym ``Charakter_Formalny.objects.get(skrot="D")``,
# czyli lazy DB hit wyzwalany z serializera (plus ``DoesNotExist``, gdy słownik
# przemianowano) — dlatego typ rozstrzyga provider, a nie my.
ATRYBUT_TYP_COAR = const.ATRYBUT_TYP_COAR

_WZORZEC_STRON = re.compile(r"^\s*(\d+)\s*[-–]\s*(\d+)\s*$")
_ZNACZNIK_HTML = re.compile(r"<[^>]*>")
_BIALE_ZNAKI = re.compile(r"\s+")

# Wzorce ze schematów profilu. Wartości, które do nich nie pasują, nie mogą
# trafić do dedykowanych elementów — dokument przestałby być poprawny wobec
# XSD, a OpenAIRE odrzuciłby cały rekord. Patrz includes/*-identifiers.xsd.
WZ_DOI = re.compile(r"^10\.\d{4,}(\.\d+)*/[^\s]+$")
WZ_ISSN = re.compile(r"^\d{4}-?\d{3}[\dX]$")
WZ_ORCID = re.compile(
    r"^https://orcid\.org/"
    r"(0000-000(1-[5-9]|2-[0-9]|3-[0-4])[0-9]{3}-[0-9]{3}[0-9X]"
    r"|0009-000[0-9]-[0-9]{4}-[0-9]{3}[0-9X])$"
)
WZ_ROR = re.compile(r"^https://ror\.org/0[\da-hj-km-np-tv-zA-HJ-KM-NP-TV-Z]{6}\d{2}$")
_WZ_ISBN = (
    re.compile(r"^(978-\d+-\d+-\d+-\d|979-[1-9]\d*-\d+-\d+-\d)$"),
    re.compile(r"^(978 \d+ \d+ \d+ \d|979 [1-9]\d* \d+ \d+ \d)$"),
    re.compile(r"^(978\d{10}|979[1-9]\d{9})$"),
    re.compile(r"^(\d+-\d+-\d+-[\dX]|\d+ \d+ \d+ [\dX])$"),
    re.compile(r"^\d{9}[\dX]$"),
)
_DLUGOSCI_ISBN = {17: 0, 13: 3, 10: 4}


# -- tekst ---------------------------------------------------------------


def tekst(wartosc):
    """Znormalizowany tekst albo ``None``, gdy pusto.

    Zdejmuje znaczniki HTML (tytuły i streszczenia przechodzą przez
    ``safe_tytul_html``, więc mogą zawierać ``<i>``, ``<sub>`` itp.),
    rozwija encje i skleja białe znaki. CERIF chce czysty tekst — zostawienie
    znaczników wpuściłoby do ``Title`` dosłowne ``&lt;i&gt;``.
    """
    if wartosc is None:
        return None
    if not isinstance(wartosc, str):
        wartosc = str(wartosc)
    wartosc = html.unescape(_ZNACZNIK_HTML.sub(" ", wartosc))
    wartosc = _BIALE_ZNAKI.sub(" ", wartosc).strip()
    return wartosc or None


def data_iso(wartosc):
    """``datetime.date``/``datetime`` → ``YYYY-MM-DD``; inaczej ``None``."""
    if isinstance(wartosc, datetime.datetime):
        wartosc = wartosc.date()
    if isinstance(wartosc, datetime.date):
        return wartosc.isoformat()
    return None


def rok_iso(wartosc):
    """Rok jako ``xs:gYear`` (dozwolony przez ``cfGenericDateTime__Type``)."""
    try:
        rok = int(wartosc)
    except (TypeError, ValueError):
        return None
    if rok < 1:
        return None
    return f"{rok:04d}"


def pasuje(wzorzec, wartosc):
    """Zwróć ``wartosc``, gdy pasuje do wzorca profilu; inaczej ``None``."""
    if wartosc is None:
        return None
    return wartosc if wzorzec.match(wartosc) else None


def poprawny_isbn(wartosc):
    """ISBN w jednej z postaci dopuszczonych przez ``ISBN__SimpleType``."""
    if wartosc is None:
        return None
    indeks = _DLUGOSCI_ISBN.get(len(wartosc))
    if indeks is None:
        return None
    # Długość 13 dopuszcza dwa warianty: ISBN-13 bez separatorów oraz
    # ISBN-10 z separatorami — sprawdzamy oba.
    kandydaci = (
        (_WZ_ISBN[3], _WZ_ISBN[indeks]) if len(wartosc) == 13 else (_WZ_ISBN[indeks],)
    )
    for wzorzec in kandydaci:
        if wzorzec.match(wartosc):
            return wartosc
    return None


def rozbij_strony(strony):
    """``"123-145"`` → ``("123", "145")``; gdy nie pasuje — ``(None, None)``.

    ``strony`` to w BPP jedno pole tekstowe o bardzo swobodnej zawartości
    (``"123-145"``, ``"e12345"``, ``"s. 4, 7-9"``). Wzorzec dopuszcza wyłącznie
    czysty zakres liczbowy; wszystko inne pomijamy, bo zgadywanie
    ``StartPage``/``EndPage`` produkowałoby dane nieprawdziwe.
    """
    if not strony:
        return None, None
    dopasowanie = _WZORZEC_STRON.match(strony)
    if dopasowanie is None:
        return None, None
    return dopasowanie.group(1), dopasowanie.group(2)


# -- budowanie XML -------------------------------------------------------


def element(nazwa, wartosc=None, ns=NS, nsmap=None, **atrybuty):
    """Nowy element w podanej przestrzeni nazw."""
    el = etree.Element(f"{{{ns}}}{nazwa}", nsmap=nsmap)
    if wartosc is not None:
        el.text = wartosc
    for klucz, war in atrybuty.items():
        if war is not None:
            el.set(klucz, war)
    return el


def dodaj(rodzic, nazwa, wartosc, ns=NS, jezyk=None, **atrybuty):
    """Dopisz element tekstowy; pusta wartość → nic się nie dzieje.

    Zwraca utworzony element albo ``None``. ``jezyk`` (kod BCP 47) trafia do
    ``xml:lang`` — profil używa go na typach ``cfMLangString__Type``.
    """
    if wartosc is None or wartosc == "":
        return None
    el = element(nazwa, wartosc, ns=ns, **atrybuty)
    if jezyk:
        el.set(XML_LANG, jezyk)
    rodzic.append(el)
    return el


def dodaj_kontener(rodzic, nazwa, ns=NS):
    """Dopisz pusty element-kontener (np. ``Authors``) i zwróć go."""
    el = element(nazwa, ns=ns)
    rodzic.append(el)
    return el


def czlon_lokalny(oai_id):
    """``oai:ns:Publications/wc-12`` → ``Publications/wc-12``.

    Namespace bywa domeną z kropkami, ale nigdy nie zawiera dwukropka
    (wymusza to wzorzec w ``identyfikatory``), więc rozcinamy po drugim.
    """
    if oai_id is None:
        return None
    czesci = oai_id.split(":", 2)
    if len(czesci) != 3:
        return None
    return czesci[2]


def ustaw_id(el, obj, ctx):
    """Nadaj ``@id`` encji **osadzonej**, o ile wyjdzie w swoim secie.

    Gdy nie wyjdzie — element zostaje bez identyfikatora. Profil pozwala na to
    wprost ("embedded entities without internal identifiers are permitted"),
    a wskazanie na rekord, którego harvester nigdy nie zobaczy, łamałoby
    integralność referencyjną (kontrola 5a walidatora).

    Do encji najwyższego poziomu służy :func:`ustaw_id_rekordu` — tam
    identyfikator jest obowiązkowy.
    """
    lokalny = czlon_lokalny(ctx.id_dla(obj))
    if lokalny is not None:
        el.set("id", lokalny)
    return lokalny


def ustaw_id_rekordu(el, obj, ctx):
    """Nadaj ``@id`` encji najwyższego poziomu — zawsze.

    Profil: „Internal Identifier — **mandatory (1) in top level entity**".
    Rekord jest właśnie wydawany, więc z definicji istnieje; przepuszczanie
    go przez zbiór widoczności (jak przy encjach osadzonych) produkowało
    rekordy bez identyfikatora. Walidator zgłaszał to dopiero pośrednio,
    jako „Record for OrgUnit[@id=...] not found" przy sprawdzaniu
    integralności referencyjnej — bo skoro rekord nie ma ``@id``, to nie da
    się go dopasować do odwołania z innej encji.
    """
    lokalny = czlon_lokalny(identyfikatory.zbuduj(ctx.namespace, obj))
    el.set("id", lokalny)
    return lokalny


# -- osadzone encje ------------------------------------------------------


def jednostka_ujawnialna(jednostka, ctx) -> bool:
    """Czy wolno w ogóle pokazać tę jednostkę w osadzonej encji?

    Samo pominięcie ``@id`` NIE wystarcza. ``Autor`` bywa zatrudniony
    w kilku uczelniach, a ``autor_jednostka_set`` nie jest filtrowany po
    tenancie — bez tego sprawdzenia eksport uczelni A ujawniał ``Name``
    jednostki uczelni B (i tak samo nazwy własnych jednostek z
    ``widoczna=False`` albo ``nie_eksportuj_przez_api=True``).
    """
    return jednostka is not None and ctx.widoczne.zawiera(jednostka)


def osadz_orgunit(rodzic, jednostka, ctx):
    """Dopisz skrócony ``OrgUnit`` (``Acronym`` + ``Name``).

    Kontrola 5b walidatora wymaga, żeby osadzona encja była **podzbiorem**
    swojego pełnego rekordu, więc oba elementy budujemy dokładnie tak samo
    jak :func:`cerif_export.cerif.orgunit.serializuj`.

    Jednostka spoza zbioru widoczności nie jest osadzana wcale — patrz
    :func:`jednostka_ujawnialna`.
    """
    if not jednostka_ujawnialna(jednostka, ctx):
        return None
    el = element("OrgUnit")
    ustaw_id(el, jednostka, ctx)
    dodaj(el, "Acronym", tekst(getattr(jednostka, "skrot", None)))
    dodaj(el, "Name", tekst(getattr(jednostka, "nazwa", None)))
    rodzic.append(el)
    return el


def osadz_osobe(rodzic, autor, ctx):
    """Dopisz skrócony ``Person`` (``PersonName`` + ``ORCID``).

    Nazwisko autora z ``pokazuj=False`` pozostaje — bez niego lista autorów
    publikacji byłaby po prostu nieprawdziwa, a to opis bibliograficzny,
    który i tak widnieje na okładce czasopisma.

    **ORCID już nie.** To trwały, globalny identyfikator osoby, a nie
    element opisu bibliograficznego: wystawienie go wiąże ukrytego autora
    z jego profilem w całym ekosystemie OpenAIRE i jest nieodwracalne.
    """
    from cerif_export.cerif import person

    el = element("Person")
    widoczny = ustaw_id(el, autor, ctx) is not None
    person.dodaj_person_name(el, autor)
    if widoczny:
        person.dodaj_orcid(el, autor)
    rodzic.append(el)
    return el


def dodaj_wklad_osoby(
    rodzic, nazwa, autor, ctx, nazwa_wyswietlana=None, jednostka=None
):
    """Dopisz ``Author``/``Editor``/``Inventor`` — osobę z afiliacją.

    Odpowiada typom ``cfLinkWithDisplayNameToPersonWithAffiliations*`` —
    sekwencja ``DisplayName?``, ``Person``, ``Affiliation*``. Afiliacja jest
    **rodzeństwem** ``Person`` wewnątrz wkładu, nie dzieckiem ``Person``.
    """
    if autor is None:
        return None
    el = dodaj_kontener(rodzic, nazwa)
    dodaj(el, "DisplayName", tekst(nazwa_wyswietlana), ns=NS)
    osadz_osobe(el, autor, ctx)
    # Kontener `Affiliation` tworzymy dopiero, gdy jednostkę wolno pokazać —
    # inaczej zostawiłby po sobie pusty element i ujawniał sam fakt
    # afiliacji do jednostki spoza eksportu.
    if jednostka_ujawnialna(jednostka, ctx):
        afiliacja = dodaj_kontener(el, "Affiliation")
        osadz_orgunit(afiliacja, jednostka, ctx)
    return el


def dodaj_slowa_kluczowe(rodzic, obj):
    """Dopisz ``Keyword`` z obu list słów kluczowych rekordu.

    ``slowa_kluczowe`` (taggit) wymaga prefetchu po stronie providera —
    ``.all()`` czyta wtedy z cache, bez zapytania. ``slowa_kluczowe_eng`` to
    ``ArrayField``, czyli zwykła lista na obiekcie.
    """
    tagi = getattr(obj, "slowa_kluczowe", None)
    if tagi is not None:
        for tag in tagi.all():
            dodaj(rodzic, "Keyword", tekst(tag.name), jezyk="pl")
    for slowo in getattr(obj, "slowa_kluczowe_eng", None) or []:
        dodaj(rodzic, "Keyword", tekst(slowo), jezyk="en")


def dodaj_pliki(rodzic, obj):
    """Dopisz ``FileLocations`` z listy podwieszonej przez provider.

    Patrz :data:`ATRYBUT_PLIKI`. Bierzemy wyłącznie elementy o jawnym trybie
    dostępu i z plikiem — reszta nie ma publicznego URL-a.
    """
    from bpp.const import TRYB_DOSTEPU

    pliki = getattr(obj, ATRYBUT_PLIKI, None)
    if not pliki:
        return None

    jawne = [
        plik
        for plik in pliki
        if plik.tryb_dostepu == TRYB_DOSTEPU.JAWNY.value and plik.plik
    ]
    if not jawne:
        return None

    lokacje = dodaj_kontener(rodzic, "FileLocations")
    for plik in jawne:
        medium = dodaj_kontener(lokacje, "Medium")
        dodaj(medium, "Title", tekst(plik.nazwa_pliku))
        dodaj(medium, "URI", plik.plik.url)
    return lokacje
