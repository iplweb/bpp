"""Fail-closed guard na placeholder ``SECRET_KEY`` (używany w ``production.py``).

``SECRET_KEY`` podpisuje sesje i tokeny resetu hasła — start produkcji z
publicznie znanym placeholderem = ryzyko forgowania sesji/tokenów (przejęcie
konta). ``production.py`` jest importowany w KAŻDYM procesie produkcyjnym
(web/celery/migrate), inaczej niż system-checki, które nie odpalają się na
daphne — dlatego twardy ``raise`` tutaj realnie fail-closuje serwowanie.

Predykat jest czystą funkcją (bez importu ``settings``), żeby był testowalny
bez pełnego środowiska produkcyjnego.
"""

#: Wartość SECRET_KEY używana przez ``collectstatic`` w buildzie obrazu
#: (docker/bpp_base/Dockerfile). Świadomie BEZPIECZNA: artefakt buildu nigdy
#: nie obsługuje ruchu, a jej blokada wywaliłaby build (dlatego istniejący
#: check ALTCHA jest tylko Warning). Nie flagujemy jej.
SECRET_KEY_BUILD_DUMMY = "build-time-only-not-used"


def secret_key_niebezpieczny_placeholder(key, *, unset_sentinel):
    """Czy ``key`` to placeholder, którego NIE wolno użyć w produkcji.

    :param key: wartość ``SECRET_KEY``.
    :param unset_sentinel: default z ``base.py`` (``SECRET_KEY_UNSET``) —
        wpada, gdy env ``DJANGO_BPP_SECRET_KEY`` w ogóle nie jest ustawiony.

    Łapiemy realne misdeploye: pusty klucz, nieustawiony env (sentinel) oraz
    ``.env.docker`` zostawiony bez zmian (``ZMIEN_KONIECZNIE_...``). Wartość
    build-owa jest jawnie przepuszczana.
    """
    if key == SECRET_KEY_BUILD_DUMMY:
        return False
    if not key:
        return True
    if key == unset_sentinel:
        return True
    return "ZMIEN" in key
