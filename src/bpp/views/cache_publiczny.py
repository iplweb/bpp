"""Cache HTTP publicznych stron przeglądania — wyłącznie dla anonimów.

DLACZEGO NIE ``django.views.decorators.cache.cache_page``
=========================================================

BPP jest systemem WIELO-UCZELNIANYM (multi-hosted): jeden proces Django
obsługuje wiele domen. ``bpp.middleware.SiteResolutionMiddleware``
rozstrzyga ``Host`` → ``Site`` → ``Uczelnia`` i ustawia
``request._uczelnia``, a każdy publiczny widok przeglądania filtruje
dane przez tę uczelnię (``scope_rekord_do_uczelni``,
``scope_jednostki_do_uczelni``). Innymi słowy: TA SAMA ścieżka URL daje
RÓŻNE treści pod różnymi domenami.

Klucz ``cache_page`` powstaje z metody, pełnej ścieżki URL i nagłówków
wymienionych w ``Vary``. ``Host`` NIE trafia tam domyślnie. Bez jawnego
``Vary: Host`` cache zaserwowałby treść uczelni A pod domeną uczelni B —
wyciek danych między instytucjami.

Ten dekorator wstawia hosta do klucza JAWNIE (patrz ``_klucz``), a nie
przez ``Vary``. Dzięki temu izolacja nie zależy od tego, czy jakiś inny
dekorator, middleware albo reverse proxy po drodze nadpisze ``Vary``.

DLACZEGO NIE ``Vary: Cookie``
=============================

Standardowa recepta na „nie serwuj zalogowanemu cache'a anonima" to
``Vary: Cookie``. W BPP byłaby bezużyteczna: praktycznie każdy
odwiedzający dostaje jakieś ciasteczko (``cookielaw``, sesja,
``csrftoken``), więc każdy miałby własny klucz i hit-rate spadłby do
zera. Zamiast tego bramkujemy JAWNIE na ``request.user.is_anonymous`` —
zalogowany nigdy z tego cache'a nie czyta i nigdy do niego nie pisze.

BEZPIECZNIKI
============

* tylko ``GET``/``HEAD``, tylko odpowiedzi ``200``, tylko nie-streaming,
* nie zapisujemy odpowiedzi ustawiającej ciasteczka — zamrożony w
  cache'u ``Set-Cookie`` byłby współdzielony przez wszystkich,
* nie zapisujemy treści zawierającej token CSRF (``_ZAWIERA_CSRF``);
  współdzielony token to realna dziura. Strony ``browse/autor.html``,
  ``browse/jednostka.html``, ``browse/zrodlo.html`` i
  ``browse/uczelnia.html`` SĄ objęte cache'em — ich formularz „szukaj
  publikacji" celuje w ``BuildSearch``, który jest ``@csrf_exempt``
  (zapisuje tylko do własnej sesji requestującego — patrz jego
  docstring), więc szablony nie renderują już ``{% csrf_token %}`` i nie
  niosą sekretu. Bezpiecznik zostaje jako defense-in-depth: gdyby ktoś
  dodał do któregoś cache'owanego szablonu formularz stanowego widoku z
  tokenem, ta strona po cichu wypadnie z cache'a zamiast współdzielić
  cudzy sekret,
* ``Cache-Control: private, no-cache`` na wyjściu, żeby nginx/CDN nie
  zrobiły drugiej, niebramkowanej kopii.

INWALIDACJA I TTL
=================

Klucz zawiera numer generacji (``_generacja``) trzymany w cache'u.
``bpp.apps.BppConfig.ready`` podpina ``uniewaznij_cache_publiczny`` pod
``post_save``/``post_delete`` modeli redagowanych w adminie, więc zapis
publikacji unieważnia cache NATYCHMIAST (bez enumerowania kluczy).

``DOMYSLNY_TTL`` jest tylko siatką bezpieczeństwa na zmiany, których
sygnały nie łapią: ``QuerySet.update()``, ``bulk_create``, importery
masowe i triggery SQL. Stąd 10 minut, a nie doba z
``CACHE_MIDDLEWARE_SECONDS``.
"""

import hashlib
import logging
from functools import wraps
from uuid import uuid4

from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse, HttpResponseNotModified
from django.utils.cache import patch_cache_control
from django.utils.translation import get_language

logger = logging.getLogger(__name__)

#: Górna granica nieświeżości dla zmian, których sygnały nie widzą
#: (``QuerySet.update``, ``bulk_create``, importery, triggery SQL).
DOMYSLNY_TTL = 600

PREFIKS = "bpp-pub-cache:v1"

_KLUCZ_GENERACJI = f"{PREFIKS}:generacja"

#: Nagłówki, których nigdy nie zapamiętujemy ani nie odtwarzamy.
_NAGLOWKI_POMIJANE = frozenset({"set-cookie", "vary", "cache-control", "expires"})

#: Obecność tego ciągu (bez rozróżniania wielkości liter) oznacza token
#: CSRF związany z sekretem JEDNEGO odwiedzającego — takiej odpowiedzi nie
#: wolno współdzielić. Celowo szukamy samego „csrf", a nie
#: ``csrfmiddlewaretoken``: gołe ``{{ csrf_token }}`` (``<meta
#: name="csrf-token">``, globalna zmienna JS, atrybut ``data-``) nie
#: zawiera nazwy pola formularza, a jest równie wrażliwe. Wolimy fałszywie
#: odmówić zapisu stronie, która tylko wspomina o CSRF, niż współdzielić
#: cudzy token — bezpiecznik ma zawodzić w stronę bezpieczną.
_ZAWIERA_CSRF = b"csrf"


def _generacja():
    """Bieżący znacznik generacji cache'a (część klucza).

    Znacznik jest LOSOWY, nie licznikiem. Licznik dałoby się COFNĄĆ:
    seed z zegara plus ``incr`` na każdy zapis sprawia, że masowy import
    (>1 zapis/s) wyprzedza zegar, a eksmisja klucza przez ``maxmemory``
    Redisa cofnęłaby generację do ``int(time.time())`` — czyli PONIŻEJ
    ostatnio używanej wartości, wskrzeszając każdy wpis z okna TTL.
    Losowy znacznik nie ma porządku, więc nie ma czego cofać.
    """
    wartosc = cache.get(_KLUCZ_GENERACJI)
    if wartosc is None:
        wartosc = uuid4().hex
        cache.set(_KLUCZ_GENERACJI, wartosc, None)
    return wartosc


def _wykonaj_bump():
    """Ustaw nową, nigdy wcześniej nieużytą generację."""
    cache.set(_KLUCZ_GENERACJI, uuid4().hex, None)


def _bump_juz_zaplanowany(polaczenie):
    """Czy w tej transakcji zaplanowano już unieważnienie?

    Skanujemy ``run_on_commit`` zamiast trzymać własną flagę, bo tę listę
    Django czyści przy rollbacku. Własna flaga przetrwałaby wycofaną
    transakcję i wyciszyła wszystkie kolejne unieważnienia.
    """
    return any(_wykonaj_bump in wpis for wpis in polaczenie.run_on_commit)


def uniewaznij_cache_publiczny(sender=None, **kwargs):
    """Unieważnij CAŁY publiczny cache HTTP (nowa generacja).

    Receiver ``post_save``/``post_delete``. Stare wpisy zostają w
    backendzie, ale ich klucz zawiera poprzednią generację, więc nikt ich
    już nie trafi; wygasną same po TTL.

    Unieważniamy dopiero PO zatwierdzeniu transakcji i tylko raz na
    transakcję. Dwa powody:

    * poprawność — ``post_save`` leci przed ``COMMIT``, więc równoległe
      żądanie mogłoby jeszcze nie widzieć nowych danych, zapamiętać stan
      sprzed zapisu już pod NOWĄ generacją i utrwalić go na cały TTL;
    * koszt — importer zapisujący 100 tys. wierszy w jednym bloku
      ``atomic`` robi jedno unieważnienie, a nie 100 tys. round-tripów.
    """
    polaczenie = transaction.get_connection()
    if _bump_juz_zaplanowany(polaczenie):
        return
    # Poza blokiem ``atomic`` ``on_commit`` wykonuje się natychmiast.
    transaction.on_commit(_wykonaj_bump)


#: Nazwa ciasteczka zgody na ciasteczka (pakiet ``cookielaw``).
_CIASTECZKO_ZGODY = "cookielaw_accepted"


def _stan_zgody(request):
    """Stan zgody na ciasteczka, sprowadzony do TRZECH wartości.

    ``base.html`` renderuje baner cookielaw i snippet Google Analytics
    warunkowo, na podstawie ``request.COOKIES['cookielaw_accepted']``
    (patrz ``cookielaw.context_processors``). Treść strony ZALEŻY więc od
    tego ciasteczka, mimo że wszystkie trzy warianty są anonimowe —
    bramkowanie na ``is_anonymous`` nic tu nie daje. Bez tego składnika
    klucza strona rozgrzana przez osobę, która wyraziła zgodę, niosłaby
    znacznik Google Analytics do WSZYSTKICH, także do tych, którzy zgody
    odmówili (i odwrotnie: analityka znikałaby akceptującym na czas TTL).

    NORMALIZACJA JEST OBOWIĄZKOWA. Wartość ciasteczka pochodzi od
    klienta, więc wpuszczenie jej surowej do klucza pozwoliłoby zalać
    cache nieograniczoną liczbą wariantów tej samej strony — trywialny
    DoS na pamięć Redisa. Mapujemy na trzy kubełki i nic poza nimi.

    Koszt dla ruchu, który ten cache ma odciążyć, jest bliski zeru:
    roboty indeksujące nie wykonują JavaScriptu i nigdy nie ustawiają
    tego ciasteczka, więc wszystkie lądują w kubełku „brak".

    KUBEŁKI ODWZOROWUJĄ RENDEROWANIE, NIE SUROWE WARTOŚCI. Context
    processor rozróżnia cztery stany surowe (``None`` / ``"1"`` / ``"0"``
    / wartość nieznana), ale ``base.html`` czyta wyłącznie
    ``cookielaw.notset`` (baner) i ``cookielaw.accepted`` (snippet GA) —
    ``cookielaw.rejected`` nie jest używane nigdzie w szablonach. Wartość
    NIEZNANA renderuje się więc identycznie jak ``"0"``: bez banera i bez
    GA. Musi trafiać do kubełka „odmowa", nie „brak". Wrzucenie jej do
    „brak" pozwalało spreparowanym ciasteczkiem rozgrzać cache stroną BEZ
    banera zgody i podawać ją świeżym odwiedzającym, tłumiąc im komunikat
    prawny na czas TTL.
    """
    wartosc = request.COOKIES.get(_CIASTECZKO_ZGODY)
    if wartosc is None:
        return "brak"
    if wartosc == "1":
        return "zgoda"
    # Każda inna wartość, także śmieciowa, renderuje się jak ``"0"``.
    return "odmowa"


def _klucz(request):
    """Klucz cache'a: generacja + HOST + zgoda + język + metoda + ścieżka.

    ``request.get_host()`` jest tu składnikiem KRYTYCZNYM — to on
    izoluje uczelnie od siebie (patrz docstring modułu). Nie usuwaj go
    bez przeczytania ``test_izolacja_multi_host_*``.

    ``_stan_zgody`` jest krytyczny z innego powodu — patrz
    ``test_cache_nie_przenosi_zgody_miedzy_odwiedzajacymi``.
    """
    surowy = "|".join(
        [
            str(_generacja()),
            # Nazwy hostów są case-insensitive — bez ``lower()``
            # ``Uczelnia1.localhost`` i ``uczelnia1.localhost`` robiłyby
            # dwa wpisy na tę samą stronę (marnotrawstwo, nie wyciek).
            request.get_host().lower(),
            _stan_zgody(request),
            get_language() or "",
            request.method,
            request.get_full_path(),
        ]
    )
    return f"{PREFIKS}:{hashlib.sha256(surowy.encode('utf-8')).hexdigest()}"


def _mozna_cachowac_zadanie(request):
    uzytkownik = getattr(request, "user", None)
    if uzytkownik is None:
        # Brak ``AuthenticationMiddleware`` (np. surowy RequestFactory) —
        # nie wiemy, kto pyta, więc nie ryzykujemy.
        return False
    if not uzytkownik.is_anonymous:
        return False
    return request.method in ("GET", "HEAD")


def _mozna_cachowac_odpowiedz(odpowiedz):
    if odpowiedz.status_code != 200:
        return False
    if getattr(odpowiedz, "streaming", False):
        return False
    if odpowiedz.cookies:
        # UWAGA przy ewentualnym usuwaniu tego warunku: chroni on nie tylko
        # przed zamrożeniem cudzego ``Set-Cookie``. Wyrenderowanie
        # komunikatu ``django.contrib.messages`` modyfikuje sesję, ta
        # ustawia ``sessionid`` — i właśnie ten warunek sprawia, że
        # komunikat zaadresowany do jednego anonima nie trafia do cache'a
        # i nie wyświetla się wszystkim pozostałym.
        logger.debug("cache_publiczny: pomijam odpowiedź ustawiającą ciasteczka")
        return False
    # ``lower()`` bo ``window.CSRF``/``X-CSRFToken`` też są tokenami —
    # dopasowanie z rozróżnianiem wielkości liter przepuściłoby je.
    if _ZAWIERA_CSRF in odpowiedz.content.lower():
        logger.warning(
            "cache_publiczny: odpowiedź zawiera token CSRF — NIE zapamiętuję. "
            "Ten widok nie nadaje się do współdzielonego cache'a."
        )
        return False
    return True


def _zapisz(klucz, odpowiedz, ttl):
    if not _mozna_cachowac_odpowiedz(odpowiedz):
        return
    naglowki = {
        nazwa: wartosc
        for nazwa, wartosc in odpowiedz.items()
        if nazwa.lower() not in _NAGLOWKI_POMIJANE
    }
    cache.set(klucz, (odpowiedz.status_code, naglowki, odpowiedz.content), ttl)


def _etag(tresc):
    """Słaby ETag z treści — pozwala odpowiedzieć 304 zamiast całym ciałem."""
    return f'W/"{hashlib.sha256(tresc).hexdigest()[:32]}"'


def _odtworz(request, zapamietane):
    status, naglowki, tresc = zapamietane
    etag = _etag(tresc)

    if request.headers.get("If-None-Match") == etag:
        # Przeglądarka ma już tę wersję — oszczędzamy całe ciało odpowiedzi.
        niezmieniona = HttpResponseNotModified()
        niezmieniona["ETag"] = etag
        niezmieniona["X-BPP-Cache"] = "HIT"
        return niezmieniona

    odpowiedz = HttpResponse(tresc, status=status)
    for nazwa, wartosc in naglowki.items():
        odpowiedz[nazwa] = wartosc
    odpowiedz["ETag"] = etag
    odpowiedz["X-BPP-Cache"] = "HIT"
    return odpowiedz


def cache_publiczny(ttl=DOMYSLNY_TTL):
    """Zapamiętaj odpowiedź publicznego widoku przeglądania dla anonima.

    Używaj TYLKO na widokach, których wyrenderowana dla anonima treść
    zależy wyłącznie od (host, ścieżka, query string, język) — czyli na
    deterministycznych stronach przeglądania. Zalogowani przechodzą obok
    cache'a w obie strony.

    Na widokach klasowych::

        @method_decorator(cache_publiczny(), name="dispatch")
        class RokView(ListView):
            ...
    """

    def dekorator(view_func):
        @wraps(view_func)
        def _opakowany(request, *args, **kwargs):
            if not _mozna_cachowac_zadanie(request):
                return view_func(request, *args, **kwargs)

            klucz = _klucz(request)
            zapamietane = cache.get(klucz)
            if zapamietane is not None:
                odpowiedz = _odtworz(request, zapamietane)
                patch_cache_control(
                    odpowiedz, private=True, max_age=0, must_revalidate=True
                )
                return odpowiedz

            odpowiedz = view_func(request, *args, **kwargs)
            odpowiedz["X-BPP-Cache"] = "MISS"

            def _po_renderze(wyrenderowana):
                _zapisz(klucz, wyrenderowana, ttl)
                if _mozna_cachowac_odpowiedz(wyrenderowana):
                    # Ten sam ETag, który wyliczy ``_odtworz`` — dzięki temu
                    # kolejna wizyta może dostać 304 zamiast całego ciała.
                    wyrenderowana["ETag"] = _etag(wyrenderowana.content)

            if hasattr(odpowiedz, "render") and callable(odpowiedz.render):
                # ``TemplateResponse`` nie ma jeszcze ``content`` — zapis
                # musi poczekać na wyrenderowanie.
                odpowiedz.add_post_render_callback(_po_renderze)
            else:
                _po_renderze(odpowiedz)

            patch_cache_control(
                odpowiedz, private=True, max_age=0, must_revalidate=True
            )
            return odpowiedz

        return _opakowany

    return dekorator
