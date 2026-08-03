"""Resumption tokeny OAI-PMH — keyset, podpisane, z TTL.

**Keyset, nie offset.** Przy ``[offset:offset+n]`` edycja albo skasowanie
rekordu w trakcie wielogodzinnego harvestu przesuwa okno i po cichu gubi
albo dubluje pozycje; keyset ma dodatkowo stały koszt strony niezależnie od
głębokości.

**Podpis jest wymagany.** Token wraca do nas z zewnątrz i steruje zapytaniem
do bazy — bez podpisu byłby zwykłym wektorem wstrzykiwania parametrów
(dowolny ``set``, dowolny ``slug``, obejście filtrów zakresu). Podpisujemy
``django.core.signing`` z solą ``const.TOKEN_SALT`` i sprawdzamy wiek wobec
``const.TOKEN_TTL``.

``slug`` jest **obowiązkowy** — set ``openaire_cris_publications`` łączy pięć
modeli o kolidujących kluczach głównych, więc sama para ``(ts, pk)`` jest
wieloznaczna i produkuje duplikaty albo gubi rekordy na granicy strony.

Pole ``set`` niesie **żądany** set (albo ``None``, gdy harvest idzie po
wszystkich setach), a nie ten, w którym akurat stoi kursor — tę informację
niesie ``slug``, bo każdy slug należy do dokładnie jednego setu.
"""

from django.core import signing

from cerif_export import const
from cerif_export.kontekst import Kursor
from cerif_export.oai.bledy import BlednyResumptionToken

#: Komplet kluczy ładunku. Token z innym zestawem jest odrzucany — pochodzi
#: albo z innej wersji kodu, albo z próby ręcznego majstrowania.
KLUCZE = ("set", "prefix", "od", "do", "slug", "ts", "pk")

_KLUCZE_TEKSTOWE_OPCJONALNE = ("set", "od", "do")


def zakoduj(kursor, set_spec, prefix, od=None, do=None) -> str:
    """Zapakuj pozycję keyset w podpisany resumption token.

    ``od``/``do`` to datestampy w formacie ``const.FORMAT_DATESTAMP`` albo
    ``None``; ``set_spec`` to ``setSpec`` z żądania albo ``None``.
    """
    if kursor is None:
        raise ValueError("Nie ma czego kodować — kursor jest pusty")
    if not kursor.slug:
        raise ValueError(
            "Kursor bez sluga jest wieloznaczny w secie łączącym kilka modeli"
        )

    ladunek = {
        "set": set_spec or None,
        "prefix": prefix,
        "od": od,
        "do": do,
        "slug": kursor.slug,
        "ts": kursor.ts,
        "pk": int(kursor.pk),
    }
    return signing.dumps(ladunek, salt=const.TOKEN_SALT, compress=True)


def odkoduj(token) -> dict:
    """Rozpakuj i zweryfikuj token.

    Token wygasły, z zerwanym podpisem albo z niekompletnym ładunkiem daje
    ``BlednyResumptionToken`` — warstwa czasowników mapuje go na kod
    protokołu ``badResumptionToken``.
    """
    if not isinstance(token, str) or not token:
        raise BlednyResumptionToken("Pusty resumption token")

    try:
        dane = signing.loads(token, salt=const.TOKEN_SALT, max_age=const.TOKEN_TTL)
    except signing.SignatureExpired as wyjatek:
        raise BlednyResumptionToken("Resumption token wygasł") from wyjatek
    except signing.BadSignature as wyjatek:
        raise BlednyResumptionToken(
            "Resumption token ma niepoprawny podpis"
        ) from wyjatek

    _sprawdz_ladunek(dane)
    return dane


def kursor_z(dane: dict) -> Kursor:
    """Zbuduj ``Kursor`` z rozpakowanego ładunku tokenu."""
    return Kursor(slug=dane["slug"], ts=dane["ts"], pk=dane["pk"])


def _sprawdz_ladunek(dane):
    if not isinstance(dane, dict):
        raise BlednyResumptionToken("Ładunek resumption tokenu nie jest mapą")

    brakujace = [klucz for klucz in KLUCZE if klucz not in dane]
    if brakujace:
        raise BlednyResumptionToken(
            "Resumption token bez pól: " + ", ".join(brakujace)
        )

    nadmiarowe = sorted(set(dane) - set(KLUCZE))
    if nadmiarowe:
        raise BlednyResumptionToken(
            "Resumption token z nieznanymi polami: " + ", ".join(nadmiarowe)
        )

    for klucz in ("prefix", "slug", "ts"):
        wartosc = dane[klucz]
        if not isinstance(wartosc, str) or not wartosc:
            raise BlednyResumptionToken(
                f"Pole {klucz} resumption tokenu musi być niepustym łańcuchem"
            )

    for klucz in _KLUCZE_TEKSTOWE_OPCJONALNE:
        wartosc = dane[klucz]
        if wartosc is not None and not isinstance(wartosc, str):
            raise BlednyResumptionToken(
                f"Pole {klucz} resumption tokenu musi być łańcuchem albo None"
            )

    # ``bool`` jest podklasą ``int`` — bez jawnego wykluczenia ``True``
    # przeszłoby jako pk == 1.
    if isinstance(dane["pk"], bool) or not isinstance(dane["pk"], int):
        raise BlednyResumptionToken("Pole pk resumption tokenu musi być liczbą")
    if dane["pk"] < 0:
        raise BlednyResumptionToken("Pole pk resumption tokenu nie może być ujemne")
