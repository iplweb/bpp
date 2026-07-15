import json

from django.template import Library
from django.utils.safestring import mark_safe

register = Library()


def strip_at_end(ciag, znaki=",."):
    ciag = ciag.strip()
    while ciag:
        if ciag[-1] in znaki:
            ciag = ciag[:-1]
            continue
        break
    return ciag


def strip_at_beginning(ciag, znaki=",."):
    ciag = ciag.strip()
    while ciag:
        if ciag[0] in znaki:
            ciag = ciag[1:]
            continue
        break
    return ciag


def znak_na_koncu(ciag, znak):
    """Wymusza, aby na końcu ciągu znaków był konkretny znak, czyli przecinek
    albo kropka. Wycina wszelkie kropki i przecinki z końca ciągu i stripuje go,
    zwracając
    """
    if ciag is None:
        return

    ciag = strip_at_end(ciag)
    if ciag:
        return ciag + znak
    return ciag


register.filter(znak_na_koncu)


def znak_na_poczatku(ciag, znak):
    """Wymusza, aby na PRZED ciągiem znaków był konkretny znak ORAZ spacja,
    czyli - przykładowo - przecinek albo kropka, jeżeli ciąg jest nie-pusty;
    do tego wycina wszelkie kropki i przecinki z końca i z początku ciągu
    oraz stripuje go.

    Tag używany do uzyskiwania opisu bibliograficznego.
    """
    if ciag is None:
        return ""

    ciag = strip_at_beginning(strip_at_end(ciag))
    if ciag:
        return znak + " " + ciag
    return ciag


register.filter(znak_na_poczatku)


def ladne_numery_prac(arr):
    """Wyświetla ładne numery prac, tzn. tablicę [1, 2, 5, 6, 7, 8, 12]
    przerobi na 1-2, 5-8, 12

    Filtr wykorzystywany do wyświetlania numerków prac w Kronice Uczelni
    """

    # To może być set(), a set() jest nieposortowany
    nu = sorted(arr)

    if not nu:
        return ""

    buf = str(nu[0])
    last_elem = nu[0]
    cont = False

    for elem in nu[1:]:
        if elem == last_elem + 1:
            last_elem = elem
            cont = True
            continue

        if cont:
            buf += "-" + str(last_elem) + ", " + str(elem)
        else:
            buf += ", " + str(elem)

        last_elem = elem
        cont = False

    if cont:
        buf += "-" + str(last_elem)

    return buf


register.filter(ladne_numery_prac)


@register.filter(name="safe_streszczenie")
def safe_streszczenie(value):
    """Wyrenderuj streszczenie bezpiecznie.

    Zamiennik dla ``|safe`` przy treści streszczeń: escape'uje matematyczne
    operatory '<'/'>' wpisane w tekst (np. "<30 IU/dL"), usuwa niedozwolony
    markup (w tym JATS i ewentualny XSS) i oddaje zbalansowany HTML, którego
    minifikator HTML nie zepsuje. Bez tego goły '<' pożerał układ strony.
    """
    from bpp.util import safe_streszczenie_html

    return mark_safe(safe_streszczenie_html(value))


@register.filter(name="safe_tytul")
def safe_tytul(value):
    """Wyrenderuj tytuł publikacji bezpiecznie.

    Zamiennik dla ``|safe`` przy ``tytul``/``tytul_oryginalny``: sanityzuje
    HTML tytułu (wąska allowlista inline — kursywa, pogrubienie, sub/sup),
    usuwając XSS z tytułów pochodzących z importu/zgłoszeń. Stosować jako
    OSTATNI filtr (po ``truncatewords_html``/``znak_na_koncu``).
    """
    from bpp.util import safe_tytul_html

    return mark_safe(safe_tytul_html(value))


@register.filter(name="jsonify")
def jsonify(value):
    """Convert a value to a JSON literal for use inside a <script> JSON-LD block.

    Zwraca `mark_safe`, więc autoescaping Django NIE zamieni cudzysłowów
    JSON-a na `&quot;` — to było realnym bugiem: HTML5 nie dekoduje encji
    w treści `<script>`, więc `"headline": &quot;...&quot;` dawało
    niepoprawny JSON-LD (Google go odrzucał).

    Skoro pomijamy autoescaping, sami escapujemy znaki groźne wewnątrz
    `<script>` (`<`, `>`, `&` oraz separatory linii U+2028/U+2029) na
    sekwencje `\\uXXXX` — to wciąż poprawny JSON, a zarazem uniemożliwia
    wyłamanie się z taga przez `</script>` (ochrona przed XSS). Ta sama
    technika co `django.utils.html.json_script`.
    """
    if value is None:
        return mark_safe("null")
    # Handle Django model instances by converting them to string
    if hasattr(value, "_meta"):
        value = str(value)
    result = json.dumps(value, ensure_ascii=False)
    result = (
        result.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )
    return mark_safe(result)


@register.filter(name="link_do_pi")
def link_do_pi(praca, uczelnia=None):
    """Zwróć link do Profilu Instytucji rekordu dla danej uczelni.

    Multi-hosted (audyt uczelnia, track 7b): templejt nie umie podać argumentu
    metodzie, więc filtr przekazuje uczelnię oglądającego (z kontekstu) do
    ``praca.link_do_pi(uczelnia)`` — link wskazuje na PBN-root TEJ uczelni i
    rozwiązuje wiersz ``PublikacjaInstytucji_V2`` otagowany TĄ uczelnią.
    ``uczelnia=None`` (brak uczelni w kontekście) → brak linku (NIE ma
    „uczelni domyślnej").
    """
    method = getattr(praca, "link_do_pi", None)
    if method is None:
        return None
    return method(uczelnia=uczelnia)


@register.simple_tag
def opis_bibliograficzny_cache(pk):
    from bpp.models.cache import Rekord

    try:
        return mark_safe(Rekord.objects.get(pk=pk).opis_bibliograficzny_cache)
    except Rekord.DoesNotExist:
        pass

    return "(brak danych)"


@register.simple_tag
def generate_coins(praca, autorzy):  # noqa
    """Generate COinS (ContextObjects in Spans) metadata for bibliography managers.
    This allows Zotero, Mendeley and other tools to automatically detect and import citations.
    """
    from urllib.parse import quote

    # Build the OpenURL KEV format string
    coins_data = []

    # Context version
    coins_data.append("ctx_ver=Z39.88-2004")

    # Format - determine if it's a book or article
    if hasattr(praca, "charakter_formalny") and praca.charakter_formalny:
        if (
            "książ" in praca.charakter_formalny.nazwa.lower()
            or "book" in praca.charakter_formalny.nazwa.lower()
        ):
            coins_data.append("rft_val_fmt=info:ofi/fmt:kev:mtx:book")
            coins_data.append("rft.genre=book")
        else:
            coins_data.append("rft_val_fmt=info:ofi/fmt:kev:mtx:journal")
            coins_data.append("rft.genre=article")
    else:
        coins_data.append("rft_val_fmt=info:ofi/fmt:kev:mtx:journal")
        coins_data.append("rft.genre=article")

    # Title
    if praca.tytul_oryginalny:
        coins_data.append(f"rft.title={quote(praca.tytul_oryginalny)}")

    # Authors
    if autorzy:
        for autor in autorzy[:5]:  # Limit to first 5 authors for COinS
            if hasattr(autor, "autor"):
                full_name = f"{autor.autor.nazwisko}, {autor.autor.imiona}"
                coins_data.append(f"rft.au={quote(full_name)}")

    # Publication year
    if praca.rok:
        coins_data.append(f"rft.date={praca.rok}")

    # Journal/Source title
    if hasattr(praca, "zrodlo") and praca.zrodlo:
        coins_data.append(f"rft.jtitle={quote(str(praca.zrodlo))}")

    # Volume
    if hasattr(praca, "tom") and praca.tom:
        coins_data.append(f"rft.volume={quote(str(praca.tom))}")

    # Issue
    if hasattr(praca, "numer_zeszytu") and praca.numer_zeszytu:
        coins_data.append(f"rft.issue={quote(str(praca.numer_zeszytu))}")

    # Pages — pierwsza_strona/ostatnia_strona to metody, więc trzeba je
    # wywołać; bez () do title= wyciekał repr bound-methody (FD#420).
    if hasattr(praca, "pierwsza_strona"):
        spage = praca.pierwsza_strona()
        if spage:
            coins_data.append(f"rft.spage={quote(str(spage))}")
    if hasattr(praca, "ostatnia_strona"):
        epage = praca.ostatnia_strona()
        if epage:
            coins_data.append(f"rft.epage={quote(str(epage))}")

    # Identifiers
    if hasattr(praca, "doi") and praca.doi:
        coins_data.append(f"rft_id=info:doi/{quote(praca.doi)}")
    if hasattr(praca, "isbn") and praca.isbn:
        coins_data.append(f"rft.isbn={quote(praca.isbn)}")
    if hasattr(praca, "issn") and praca.issn:
        coins_data.append(f"rft.issn={quote(praca.issn)}")

    # Publisher
    if hasattr(praca, "wydawca") and praca.wydawca:
        coins_data.append(f"rft.pub={quote(str(praca.wydawca))}")

    # Language
    if hasattr(praca, "jezyk") and praca.jezyk:
        lang = praca.jezyk.skrot if hasattr(praca.jezyk, "skrot") else "pl"
        coins_data.append(f"rft.language={lang}")

    # Join all parts with &
    coins_string = "&".join(coins_data)

    # Return the complete COinS span
    return mark_safe(f'<span class="Z3988" title="{coins_string}"></span>')


def czy_zwijac_liste_autorow(request, uczelnia):
    """Rozstrzyga, czy zwijać długie listy autorów dla danego żądania.

    Kolejność: świadoma preferencja zalogowanego użytkownika (ZAWSZE/NIGDY)
    → ustawienie oglądanej uczelni → domyślnie ``True``. Użytkownik z
    preferencją „jak uczelnia" (oraz anonim / brak żądania) dziedziczy
    ustawienie uczelni.
    """
    from bpp.models.profile import ZwijanieAutorow

    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        pref = user.zwijaj_dlugie_listy_autorow
        if pref == ZwijanieAutorow.ZAWSZE:
            return True
        if pref == ZwijanieAutorow.NIGDY:
            return False
        # DOMYSLNE → dziedziczymy z uczelni (poniżej)
    return bool(getattr(uczelnia, "zwijaj_dlugie_listy_autorow", True))


@register.simple_tag(takes_context=True)
def autorzy_skrocony(context, praca, uczelnia=None):
    """Skrócony widok listy autorów (``autorzy_dla_opisu_skrocony``) z przekazaną
    oglądającą uczelnią, tak by wyróżnienie "naszego" autora było host-aware.

    Metoda modelu nie może dostać argumentu przez ``{% with %}``/``{{ }}``,
    więc owijamy ją w simple_tag wywoływany jako
    ``{% autorzy_skrocony praca uczelnia as box %}``. ``uczelnia`` pochodzi
    z context processora (``Uczelnia.objects.get_for_request``). Zwijanie
    długiej listy jest rozstrzygane per-żądanie (preferencja zalogowanego
    użytkownika nadpisuje ustawienie uczelni) — dlatego ``takes_context``.
    """
    zwijaj = czy_zwijac_liste_autorow(context.get("request"), uczelnia)
    return praca.autorzy_dla_opisu_skrocony(uczelnia=uczelnia, zwijaj=zwijaj)


@register.simple_tag
def autor_nazwa(autor, links="", pokaz_pozycje=False):
    """Renderuje pojedynczego autora na liście na stronie rekordu: nazwisko
    (opcjonalnie linkowane do admina/strony autora), z wyróżnieniem "naszego"
    autora oraz opcjonalnym numerem pozycji.

    Zwraca bezpieczny HTML bez otaczających białych znaków — w przeciwieństwie
    do ``{% include %}``, które (przez wymuszony przez pre-commit newline na
    końcu pliku) wstawiało spację przed przecinkiem między autorami.
    """
    from django.urls import reverse
    from django.utils.html import format_html

    klasa = "author-name"
    if not links:
        klasa += " praca-mono__author-name"
    if getattr(autor, "czy_nasz", False):
        klasa += " praca-mono__author-name--nasz"

    nazwa = format_html(
        '<span class="{}">{}</span>', klasa, (autor.zapisany_jako or "").upper()
    )

    if links == "admin":
        nazwa = format_html(
            '<a href="{}">{}</a>',
            reverse("admin:bpp_autor_change", args=[autor.autor.pk]),
            nazwa,
        )
    elif links == "normal":
        nazwa = format_html(
            '<a href="{}">{}</a>',
            reverse("bpp:browse_autor", args=[autor.autor.slug]),
            nazwa,
        )

    pozycja = getattr(autor, "pozycja", None)
    if pokaz_pozycje and pozycja:
        nazwa = format_html(
            '{} <span class="praca-mono__author-pozycja">({}.)</span>', nazwa, pozycja
        )
    return nazwa
