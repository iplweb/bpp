"""Reguły widoczności encji w eksporcie CERIF.

Najważniejszy test w tym pliku to ``test_ukryty_autor_nie_wycieka_*``.
Przełącznik ``Uczelnia.eksport_cerif_wlaczony`` jest domyślnie WŁĄCZONY,
a set ``openaire_cris_persons`` wystawia imię, nazwisko, ORCID, płeć
i historię zatrudnienia do publicznego endpointu agregowanego przez
OpenAIRE. Jedynym zabezpieczeniem jest ``Autor.pokazuj`` — i ono musi
działać na OBU drogach: przez własny set i przez encję osadzoną
w publikacji.
"""

import pytest
from django.contrib.sites.models import Site
from lxml import etree
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia
from bpp.models.konferencja import Konferencja
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.models.zrodlo import Zrodlo
from cerif_export import const
from cerif_export.cerif import publication
from cerif_export.kontekst import KontekstSerializacji
from cerif_export.providers import provider_dla_setu
from cerif_export.slowniki import coar

NAMESPACE = "cerif.example.org"


def pki(provider, uczelnia):
    obiekty, _ = provider.strona(uczelnia, rozmiar=1000)
    return {o.pk for o in obiekty}


def zserializuj(uczelnia, rekord):
    """Zserializuj publikację w kontekście zbudowanym przez provider."""
    provider = provider_dla_setu(const.SET_PUBLICATIONS)
    obiekty, _ = provider.strona(uczelnia, rozmiar=1000)
    swiezy = next(o for o in obiekty if o.pk == rekord.pk and type(o) is type(rekord))
    kontekst = KontekstSerializacji(
        namespace=NAMESPACE,
        uczelnia=uczelnia,
        widoczne=provider.zbiory_widocznosci(uczelnia, obiekty),
    )
    return publication.serializuj(swiezy, kontekst)


# -- OSOBY: wyciek danych osobowych --------------------------------------


@pytest.mark.django_db
def test_ukryty_autor_nie_wychodzi_w_secie_persons(uczelnia, fabryka_autorow):
    widoczny = fabryka_autorow("Widoczny", pokazuj=True)
    ukryty = fabryka_autorow("Ukryty", pokazuj=False)

    obecni = pki(provider_dla_setu(const.SET_PERSONS), uczelnia)

    assert widoczny.pk in obecni
    assert ukryty.pk not in obecni, "autor z pokazuj=False trafił do eksportu"


@pytest.mark.django_db
def test_ukryty_autor_nie_wycieka_jako_id_w_publikacji(
    uczelnia, fabryka_autorow, fabryka_wydawnictw
):
    """Druga droga wycieku: encja osadzona w ``Publication/Authors``.

    Profil pozwala osadzić osobę bez identyfikatora, więc nazwisko może się
    pojawić w opisie bibliograficznym — ale ``@id`` wskazywałoby rekord,
    którego w secie ``persons`` nie ma. To i psuje integralność
    referencyjną, i publikuje powiązanie, którego autor sobie nie życzy.
    """
    ukryty = fabryka_autorow("Ukryty", pokazuj=False)
    rekord = fabryka_wydawnictw(Wydawnictwo_Ciagle, autor=ukryty)

    element = zserializuj(uczelnia, rekord)

    identyfikatory_osob = [
        el.get("id")
        for el in element.iter()
        if el.tag.endswith("}Person") or el.tag == "Person"
    ]
    assert identyfikatory_osob, "autor w ogóle nie został osadzony"
    assert all(x is None for x in identyfikatory_osob), (
        f"ukryty autor wyciekł jako @id: {identyfikatory_osob}"
    )


@pytest.mark.django_db
def test_widoczny_autor_dostaje_id_w_publikacji(
    uczelnia, fabryka_autorow, fabryka_wydawnictw
):
    """Kontrola pozytywna — inaczej test wycieku przechodziłby na pusto."""
    autor = fabryka_autorow("Widoczny", pokazuj=True)
    rekord = fabryka_wydawnictw(Wydawnictwo_Ciagle, autor=autor)

    element = zserializuj(uczelnia, rekord)

    identyfikatory_osob = [
        el.get("id")
        for el in element.iter()
        if el.tag.endswith("}Person") or el.tag == "Person"
    ]
    assert any(x and x.endswith(f"au-{autor.pk}") for x in identyfikatory_osob)


@pytest.mark.django_db
def test_autor_bez_powiazania_z_uczelnia_nie_wychodzi(uczelnia, fabryka_autorow):
    """Autor spoza uczelni nie jest „nasz" — nie eksportujemy go."""
    obcy = fabryka_autorow("Obcy", pokazuj=True, powiaz=False)

    assert obcy.pk not in pki(provider_dla_setu(const.SET_PERSONS), uczelnia)


@pytest.mark.django_db
def test_autor_innego_tenanta_nie_wychodzi(uczelnia, fabryka_autorow):
    """Wielotenantowość: autor z drugiej uczelni nie może wyjść w naszym
    eksporcie, bo identyfikatory OAI byłyby fałszywie atrybuowane."""
    from bpp.models import Autor_Jednostka

    inne_site = Site.objects.create(domain="inna.example.org", name="inna")
    inna = Uczelnia.objects.create(nazwa="Inna", skrot="INN", site=inne_site)
    jednostka_obca = Jednostka.objects.create(nazwa="Obca", skrot="OBC", uczelnia=inna)
    obcy = baker.make("bpp.Autor", nazwisko="Obcy", imiona="Jan", pokazuj=True)
    Autor_Jednostka.objects.create(autor=obcy, jednostka=jednostka_obca)

    assert obcy.pk not in pki(provider_dla_setu(const.SET_PERSONS), uczelnia)


# -- JEDNOSTKI ------------------------------------------------------------


@pytest.mark.django_db
def test_jednostka_niewidoczna_nie_wychodzi(uczelnia, jednostka):
    ukryta = Jednostka.objects.create(
        nazwa="Ukryta", skrot="UKR", uczelnia=uczelnia, widoczna=False
    )
    obecne = pki(provider_dla_setu(const.SET_ORGUNITS), uczelnia)

    assert jednostka.pk in obecne
    assert ukryta.pk not in obecne


@pytest.mark.django_db
def test_jednostka_z_opt_out_nie_wychodzi(uczelnia, jednostka):
    jednostka.nie_eksportuj_przez_api = True
    jednostka.save()

    assert jednostka.pk not in pki(provider_dla_setu(const.SET_ORGUNITS), uczelnia)


# -- PUBLIKACJE -----------------------------------------------------------


@pytest.mark.django_db
def test_wydawnictwo_z_ukrytym_statusem_nie_wychodzi(
    uczelnia, fabryka_autorow, fabryka_wydawnictw, status_ok
):
    """Kanał ``cerif`` jest niezależny od kanału ``api``."""
    autor = fabryka_autorow()
    rekord = fabryka_wydawnictw(Wydawnictwo_Ciagle, autor=autor)
    provider = provider_dla_setu(const.SET_PUBLICATIONS)

    assert rekord.pk in pki(provider, uczelnia)

    uczelnia.ukryj_status_korekty_set.create(status_korekty=status_ok, cerif=True)

    assert rekord.pk not in pki(provider, uczelnia)


@pytest.mark.django_db
def test_wydawnictwo_z_opt_out_nie_wychodzi(
    uczelnia, fabryka_autorow, fabryka_wydawnictw
):
    autor = fabryka_autorow()
    rekord = fabryka_wydawnictw(
        Wydawnictwo_Zwarte, autor=autor, nie_eksportuj_przez_api=True
    )

    assert rekord.pk not in pki(provider_dla_setu(const.SET_PUBLICATIONS), uczelnia)


@pytest.mark.django_db
def test_praca_dyplomowa_respektuje_opt_out(
    uczelnia, jednostka, fabryka_autorow, status_ok
):
    """Regresja: ``Praca_Doktorska`` MA ``nie_eksportuj_przez_api``.

    Provider początkowo tego nie filtrował, bo specyfikacja twierdziła
    (błędnie), że pole siedzi tylko na wydawnictwach i patentach. Praca
    oznaczona jako niepubliczna szła wtedy prosto do OpenAIRE.
    """
    pola = {f.name for f in Praca_Doktorska._meta.get_fields()}
    assert "nie_eksportuj_przez_api" in pola

    widoczna = baker.make(
        Praca_Doktorska,
        jednostka=jednostka,
        autor=fabryka_autorow("Doktorant"),
        status_korekty=status_ok,
        rok=2020,
        nie_eksportuj_przez_api=False,
    )
    ukryta = baker.make(
        Praca_Doktorska,
        jednostka=jednostka,
        autor=fabryka_autorow("Tajny"),
        status_korekty=status_ok,
        rok=2020,
        nie_eksportuj_przez_api=True,
    )

    obecne = pki(provider_dla_setu(const.SET_PUBLICATIONS), uczelnia)

    assert widoczna.pk in obecne
    assert ukryta.pk not in obecne


# -- SŁOWNIKI WSPÓŁDZIELONE ----------------------------------------------


@pytest.mark.django_db
def test_zrodlo_wychodzi_tylko_gdy_uzywane(
    uczelnia, fabryka_autorow, fabryka_wydawnictw
):
    """``Zrodlo`` nie ma FK do uczelni ani opt-outu.

    Bez warunku „wskazywane przez widoczną publikację" każdy tenant
    wyeksportowałby cały współdzielony słownik czasopism jako własny.
    """
    uzywane = baker.make(Zrodlo, nazwa="Uzywane", skrot="Uz.")
    nieuzywane = baker.make(Zrodlo, nazwa="Nieuzywane", skrot="Nie.")
    fabryka_wydawnictw(Wydawnictwo_Ciagle, autor=fabryka_autorow(), zrodlo=uzywane)

    obecne = pki(provider_dla_setu(const.SET_PUBLICATIONS), uczelnia)

    assert uzywane.pk in obecne
    assert nieuzywane.pk not in obecne


@pytest.mark.django_db
def test_konferencja_wychodzi_tylko_gdy_uzywana(
    uczelnia, fabryka_autorow, fabryka_wydawnictw
):
    uzywana = baker.make(Konferencja, nazwa="Uzywana", skrocona_nazwa="Uz")
    nieuzywana = baker.make(Konferencja, nazwa="Nieuzywana", skrocona_nazwa="Nie")
    fabryka_wydawnictw(Wydawnictwo_Ciagle, autor=fabryka_autorow(), konferencja=uzywana)

    obecne = pki(provider_dla_setu(const.SET_EVENTS), uczelnia)

    assert uzywana.pk in obecne
    assert nieuzywana.pk not in obecne


# -- typ COAR prac dyplomowych -------------------------------------------


@pytest.mark.django_db
def test_typ_coar_pracy_dociera_do_xml(uczelnia, jednostka, fabryka_autorow, status_ok):
    """URI COAR ze słownika musi trafić do ``Publication/Type``.

    Regresja: provider anotował wynik pod nazwą ``_cerif_coar``, a serializer
    czytał ``cerif_typ_coar``. Obie warstwy z osobna działały poprawnie, więc
    nic tego nie wykrywało — a wszystkie prace dyplomowe wychodziły jako
    ogólny ``text`` zamiast ``doctoral thesis``.
    """
    from bpp.models import Charakter_Formalny
    from cerif_export.cerif import publication

    Charakter_Formalny.objects.filter(skrot="D").delete()
    baker.make(
        Charakter_Formalny,
        nazwa="Praca doktorska",
        skrot="D",
        coar_type=coar.DOCTORAL_THESIS,
    )
    praca = baker.make(
        Praca_Doktorska,
        tytul_oryginalny="Rozprawa",
        jednostka=jednostka,
        autor=fabryka_autorow("Doktorant"),
        status_korekty=status_ok,
        rok=2020,
        nie_eksportuj_przez_api=False,
    )

    provider = provider_dla_setu(const.SET_PUBLICATIONS)
    obiekty, _ = provider.strona(uczelnia, rozmiar=100)
    kontekst = KontekstSerializacji(
        namespace=NAMESPACE,
        uczelnia=uczelnia,
        widoczne=provider.zbiory_widocznosci(uczelnia, obiekty),
    )
    swiezy = next(o for o in obiekty if o.pk == praca.pk and type(o) is Praca_Doktorska)

    xml = etree.tostring(publication.serializuj(swiezy, kontekst)).decode()

    assert coar.DOCTORAL_THESIS in xml
    assert coar.TEKST_ROOT not in xml, "typ spadł na ogólny fallback"


# -- wycieki wykryte w self-review PR-a ----------------------------------


@pytest.mark.django_db
def test_email_autora_nie_jest_eksportowany(uczelnia, fabryka_autorow):
    """``Autor.email`` to PII — ``api_v1`` usuwa je dla anonima.

    Eksport CERIF jest publiczny i nieodwracalny, więc nie może obchodzić
    tamtej decyzji tylnymi drzwiami.
    """
    from cerif_export.cerif import person as person_cerif

    autor = fabryka_autorow("Mailowy")
    autor.email = "jan.kowalski@example.org"
    autor.www = "https://example.org/~jk"
    autor.save()

    obiekty, kontekst = _kontekst(uczelnia, const.SET_PERSONS)
    xml = etree.tostring(person_cerif.serializuj(obiekty[0], kontekst)).decode()

    assert "jan.kowalski@example.org" not in xml
    assert "mailto:" not in xml
    assert "https://example.org/~jk" in xml, "adres WWW ma zostać"


@pytest.mark.django_db
def test_jednostka_obcej_uczelni_nie_wycieka_w_afiliacji(uczelnia, fabryka_autorow):
    """Autor zatrudniony w dwóch uczelniach — pokazujemy tylko naszą.

    ``autor_jednostka_set`` nie jest filtrowany po tenancie, a bramkowanie
    samego ``@id`` nie wystarczało: ``Name`` wychodził bezwarunkowo.
    """
    from bpp.models import Autor_Jednostka
    from cerif_export.cerif import person as person_cerif

    autor = fabryka_autorow("Dwuetatowy")

    obce_site = Site.objects.create(domain="obca.example.org", name="obca")
    obca = Uczelnia.objects.create(nazwa="Obca", skrot="OBC", site=obce_site)
    obca_jednostka = Jednostka.objects.create(
        nazwa="TAJNA JEDNOSTKA OBCEJ UCZELNI", skrot="TJ", uczelnia=obca
    )
    Autor_Jednostka.objects.create(autor=autor, jednostka=obca_jednostka)

    obiekty, kontekst = _kontekst(uczelnia, const.SET_PERSONS)
    xml = etree.tostring(person_cerif.serializuj(obiekty[0], kontekst)).decode()

    assert "TAJNA JEDNOSTKA OBCEJ UCZELNI" not in xml
    assert "Jednostka CERIF" in xml, "własna jednostka ma zostać"


@pytest.mark.django_db
def test_ukryta_jednostka_nie_wycieka_w_afiliacji(uczelnia, jednostka, fabryka_autorow):
    from bpp.models import Autor_Jednostka
    from cerif_export.cerif import person as person_cerif

    autor = fabryka_autorow("Zatrudniony")
    ukryta = Jednostka.objects.create(
        nazwa="UKRYTA KATEDRA", skrot="UK", uczelnia=uczelnia, widoczna=False
    )
    Autor_Jednostka.objects.create(autor=autor, jednostka=ukryta)

    obiekty, kontekst = _kontekst(uczelnia, const.SET_PERSONS)
    xml = etree.tostring(person_cerif.serializuj(obiekty[0], kontekst)).decode()

    assert "UKRYTA KATEDRA" not in xml


@pytest.mark.django_db
def test_orcid_ukrytego_autora_nie_wycieka(
    uczelnia, fabryka_autorow, fabryka_wydawnictw
):
    """Nazwisko zostaje (opis bibliograficzny), ORCID nie.

    ORCID to trwały globalny identyfikator osoby — jego publikacja wiąże
    ukrytego autora z profilem w całym ekosystemie OpenAIRE.
    """
    ukryty = fabryka_autorow("Ukryty", pokazuj=False, orcid="0000-0002-1825-0097")
    rekord = fabryka_wydawnictw(Wydawnictwo_Ciagle, autor=ukryty)

    xml = etree.tostring(zserializuj(uczelnia, rekord)).decode()

    assert "0000-0002-1825-0097" not in xml
    assert "Ukryty" in xml, "nazwisko ma zostać — inaczej lista autorów kłamie"


def _kontekst(uczelnia, set_spec):
    provider = provider_dla_setu(set_spec)
    obiekty, _ = provider.strona(uczelnia, rozmiar=100)
    return obiekty, KontekstSerializacji(
        namespace=NAMESPACE,
        uczelnia=uczelnia,
        widoczne=provider.zbiory_widocznosci(uczelnia, obiekty),
    )


# -- przełącznik eksportu osób -------------------------------------------


@pytest.mark.django_db
def test_wylaczenie_osob_oproznia_set_persons(uczelnia, fabryka_autorow):
    autor = fabryka_autorow("Kowalski")
    assert autor.pk in pki(provider_dla_setu(const.SET_PERSONS), uczelnia)

    uczelnia.eksport_cerif_osoby = False
    uczelnia.save()

    assert pki(provider_dla_setu(const.SET_PERSONS), uczelnia) == set()


@pytest.mark.django_db
def test_wylaczenie_osob_odbiera_orcid_i_identyfikator_w_publikacji(
    uczelnia, fabryka_autorow, fabryka_wydawnictw
):
    """Wyłączenie zestawu osób nie może być pozorne.

    Gdyby działało tylko na własny zestaw, dane osobowe wychodziłyby dalej
    okrężną drogą — jako encje osadzone w publikacjach.

    Granica przebiega tak: znikają dane **osoby** (własny rekord, ``@id``,
    ORCID), zostaje **atrybucja instytucjonalna**. Afiliacja przy autorstwie
    mówi, z której jednostki pochodzi praca — to jest sedno tego eksportu
    i informacja drukowana zresztą w każdym czasopiśmie. Zdjęcie jej
    zerwałoby powiązanie dorobku z uczelnią, czyli jedyny powód, dla którego
    ktokolwiek ten endpoint wystawia.
    """
    autor = fabryka_autorow("Kowalski", orcid="0000-0002-1825-0097")
    rekord = fabryka_wydawnictw(Wydawnictwo_Ciagle, autor=autor)

    uczelnia.eksport_cerif_osoby = False
    uczelnia.save()

    xml = etree.tostring(zserializuj(uczelnia, rekord)).decode()

    assert "0000-0002-1825-0097" not in xml, "ORCID to trwały identyfikator osoby"
    assert "Persons/au-" not in xml, "brak rekordu w secie = brak referencji"
    # Nazwisko zostaje — bez niego opis bibliograficzny byłby nieprawdziwy.
    assert "Kowalski" in xml
    # Afiliacja zostaje — to atrybucja pracy do uczelni, nie dana osobowa.
    assert "Jednostka CERIF" in xml


# -- JEDNOSTKI: ukryty rodzic a `PartOf` ---------------------------------


def zserializuj_jednostke(uczelnia, jednostka):
    """Zserializuj jednostkę w kontekście zbudowanym przez jej provider."""
    from cerif_export.cerif import orgunit

    provider = provider_dla_setu(const.SET_ORGUNITS)
    obiekty, _ = provider.strona(uczelnia, rozmiar=1000)
    swiezy = next(o for o in obiekty if o.pk == jednostka.pk and type(o) is Jednostka)
    kontekst = KontekstSerializacji(
        namespace=NAMESPACE,
        uczelnia=uczelnia,
        widoczne=provider.zbiory_widocznosci(uczelnia, obiekty),
    )
    return orgunit.serializuj(swiezy, kontekst)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "ukrycie",
    [
        {"widoczna": False},
        {"nie_eksportuj_przez_api": True},
    ],
    ids=["niewidoczna", "opt-out-api"],
)
def test_ukryty_rodzic_nie_zostawia_pustego_part_of(uczelnia, jednostka, ukrycie):
    """Rodzic poza eksportem nie może zostawić po sobie pustego ``PartOf``.

    ``PartOf`` wymaga w XSD dziecka (``DisplayName`` albo ``OrgUnit``), więc
    pusty kontener unieważnia **cały** rekord jednostki. Skutek jest dużo
    gorszy niż jeden zły rekord: walidator euroCRIS przerywa na nim harvest
    setu ``openaire_cris_orgunits``, przez co żadna kolejna jednostka nie
    trafia do indeksu i jej referencje z publikacji wyglądają na wiszące
    (kontrola 5a). Jeden niepoprawny element wywraca więc dwa testy naraz.
    """
    rodzic = Jednostka.objects.create(
        nazwa="Rodzic poza eksportem", skrot="RPE", uczelnia=uczelnia, **ukrycie
    )
    jednostka.parent = rodzic
    jednostka.save()

    el = zserializuj_jednostke(uczelnia, jednostka)

    part_of = el.findall(f"{{{const.NS_CERIF}}}PartOf")
    assert all(len(kontener) for kontener in part_of), (
        "pusty <PartOf/> — kontener powstał, mimo że rodzica nie wolno pokazać"
    )
    # Samo „brak pustego kontenera" spełniłoby też pominięcie ``PartOf`` w
    # ogóle (``all()`` po pustej liście jest prawdziwe), a to inne — i gorsze
    # — zachowanie: jednostka zostaje oderwanym korzeniem. Dlatego wprost
    # wymagamy zejścia na uczelnię.
    osadzony = el.find(f"{{{const.NS_CERIF}}}PartOf/{{{const.NS_CERIF}}}OrgUnit")
    assert osadzony is not None, "jednostka bez PartOf = oderwany korzeń drzewa"
    assert osadzony.get("id") == f"OrgUnits/uc-{uczelnia.pk}"
    # Nazwa ukrytego rodzica nie ma prawa wyciec także jako sam tekst.
    assert "Rodzic poza eksportem" not in etree.tostring(el).decode()


@pytest.mark.django_db
def test_rodzic_z_cudzego_tenanta_nie_wychodzi_w_part_of(uczelnia, jednostka):
    """Rodzic z innej uczelni to ten sam przypadek co rodzic ukryty.

    W instalacji multi-hosted ``Jednostka.parent`` nie jest niczym ograniczony
    do własnego tenanta, więc bez tego członu eksport uczelni A wystawiałby
    nazwę jednostki uczelni B — i to jako ``@id``, którego w tym harveście
    nie da się rozwiązać na żaden rekord (kontrola 5a walidatora).
    """
    obca_uczelnia = Uczelnia.objects.create(
        nazwa="Uczelnia obca",
        skrot="UOB",
        site=Site.objects.create(domain="obca.example.org", name="obca.example.org"),
    )
    obcy_rodzic = Jednostka.objects.create(
        nazwa="Jednostka obcej uczelni", skrot="JOU", uczelnia=obca_uczelnia
    )
    jednostka.parent = obcy_rodzic
    jednostka.save()

    el = zserializuj_jednostke(uczelnia, jednostka)

    xml = etree.tostring(el).decode()
    assert "Jednostka obcej uczelni" not in xml, (
        "wyciek nazwy jednostki z cudzego tenanta"
    )
    assert f"OrgUnits/je-{obcy_rodzic.pk}" not in xml, "referencja nie do rozwiązania"

    osadzony = el.find(f"{{{const.NS_CERIF}}}PartOf/{{{const.NS_CERIF}}}OrgUnit")
    assert osadzony.get("id") == f"OrgUnits/uc-{uczelnia.pk}"


@pytest.mark.django_db
def test_ukryty_rodzic_takze_przez_get_record(uczelnia, jednostka):
    """Ta sama reguła musi działać na ścieżce ``GetRecord``, nie tylko listowej.

    ``GetRecord`` buduje kontekst z jednoelementowej listy, więc gdyby
    prekomputacja widoczności zależała od tego, co jeszcze jest na stronie,
    pojedynczy rekord wychodziłby inaczej niż ten sam rekord w ``ListRecords``.
    """
    from cerif_export.cerif import orgunit

    rodzic = Jednostka.objects.create(
        nazwa="Rodzic poza eksportem", skrot="RPE", uczelnia=uczelnia, widoczna=False
    )
    jednostka.parent = rodzic
    jednostka.save()

    provider = provider_dla_setu(const.SET_ORGUNITS)
    obiekt = provider.pojedynczy(uczelnia, Jednostka, jednostka.pk)
    kontekst = KontekstSerializacji(
        namespace=NAMESPACE,
        uczelnia=uczelnia,
        widoczne=provider.zbiory_widocznosci(uczelnia, [obiekt]),
    )

    el = orgunit.serializuj(obiekt, kontekst)

    osadzony = el.find(f"{{{const.NS_CERIF}}}PartOf/{{{const.NS_CERIF}}}OrgUnit")
    assert osadzony is not None, "pusty albo brakujący PartOf na ścieżce GetRecord"
    assert osadzony.get("id") == f"OrgUnits/uc-{uczelnia.pk}"


@pytest.mark.django_db
def test_jednostka_z_ukrytym_rodzicem_przechodzi_xsd(uczelnia, jednostka):
    """Ten sam przypadek, ale sprawdzony tym, co orzeka walidator: XSD."""
    from cerif_export.tests.test_serializery import sprawdz, zbuduj_schemat

    rodzic = Jednostka.objects.create(
        nazwa="Rodzic poza eksportem", skrot="RPE", uczelnia=uczelnia, widoczna=False
    )
    jednostka.parent = rodzic
    jednostka.save()

    sprawdz(zbuduj_schemat(), zserializuj_jednostke(uczelnia, jednostka))


@pytest.mark.django_db
def test_widoczny_rodzic_nadal_wychodzi_w_part_of(uczelnia, jednostka):
    """Kontrola negatywna — poprawka nie może zjeść normalnego ``PartOf``."""
    rodzic = Jednostka.objects.create(
        nazwa="Rodzic widoczny", skrot="RW", uczelnia=uczelnia
    )
    jednostka.parent = rodzic
    jednostka.save()

    el = zserializuj_jednostke(uczelnia, jednostka)

    osadzony = el.find(f"{{{const.NS_CERIF}}}PartOf/{{{const.NS_CERIF}}}OrgUnit")
    assert osadzony is not None
    assert osadzony.get("id") == f"OrgUnits/je-{rodzic.pk}"


@pytest.mark.django_db
def test_korzen_podpiety_pod_uczelnie(uczelnia, jednostka):
    """Jednostka bez rodzica trafia pod uczelnię — drzewo zostaje spójne."""
    el = zserializuj_jednostke(uczelnia, jednostka)

    osadzony = el.find(f"{{{const.NS_CERIF}}}PartOf/{{{const.NS_CERIF}}}OrgUnit")
    assert osadzony is not None
    assert osadzony.get("id") == f"OrgUnits/uc-{uczelnia.pk}"


@pytest.mark.django_db
def test_set_persons_istnieje_mimo_wylaczenia(uczelnia):
    """Profil wymaga wszystkich dziewięciu zestawów, także pustych."""
    from cerif_export.oai import czasowniki

    uczelnia.eksport_cerif_osoby = False
    uczelnia.save()

    korzen = czasowniki.odpowiedz(
        czasowniki.Zadanie(uczelnia, "https://x/cerif-oai/", {"verb": "ListSets"})
    )
    specyfikacje = [el.text for el in korzen.iter() if el.tag.endswith("}setSpec")]

    assert const.SET_PERSONS in specyfikacje
