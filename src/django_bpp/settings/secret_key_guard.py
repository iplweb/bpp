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
#: (docker/bpp_base/Dockerfile). Jest publicznie znana, więc poza buildem
#: traktujemy ją jak każdy inny placeholder. W samym buildzie przepuszczamy ją
#: tylko przy jawnym ``DJANGO_BPP_BUILD_STAGE=1`` (ustawianym INLINE w RUN-ie
#: collectstatic, nie przez ``ENV`` — nie trafia do działającego kontenera).
SECRET_KEY_BUILD_DUMMY = "build-time-only-not-used"

#: Zmienna środowiskowa włączająca wyjątek dla wartości build-owej.
BUILD_STAGE_ENV = "DJANGO_BPP_BUILD_STAGE"


def tryb_buildu(environ):
    """Czy proces działa w kroku buildu obrazu (``DJANGO_BPP_BUILD_STAGE=1``)."""
    return environ.get(BUILD_STAGE_ENV, "") == "1"


def secret_key_niebezpieczny_placeholder(key, *, unset_sentinel, build_stage=False):
    """Czy ``key`` to placeholder, którego NIE wolno użyć w produkcji.

    :param key: wartość ``SECRET_KEY``.
    :param unset_sentinel: default z ``base.py`` (``SECRET_KEY_UNSET``) —
        wpada, gdy env ``DJANGO_BPP_SECRET_KEY`` w ogóle nie jest ustawiony.
    :param build_stage: ``True`` tylko w kroku buildu obrazu — wtedy (i tylko
        wtedy) wartość build-owa jest przepuszczana.

    Łapiemy realne misdeploye: pusty klucz, nieustawiony env (sentinel),
    ``.env.docker`` zostawiony bez zmian (``ZMIEN_KONIECZNIE_...``) oraz
    wartość build-ową z Dockerfile użytą poza buildem.
    """
    if key == SECRET_KEY_BUILD_DUMMY:
        return not build_stage
    if not key:
        return True
    if key == unset_sentinel:
        return True
    return "ZMIEN" in key
