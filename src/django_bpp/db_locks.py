"""
Deterministyczne klucze Postgresowych advisory locków.

Advisory locki w PostgreSQL identyfikuje się LICZBĄ, nie nazwą. Klucz musi
więc być wyprowadzony z jakiejś nazwy — i **musi wyjść identyczny w każdym
procesie**, inaczej wzajemne wykluczanie nie zachodzi w ogóle.

Nie wolno do tego używać wbudowanego `hash()`: dla `str` (i `bytes`) jest on
solony `PYTHONHASHSEED`-em, losowanym per proces od Pythona 3.3. `hash("x")`
daje INNĄ wartość w każdym uruchomieniu interpretera, więc każdy worker
Celery i każdy proces gunicorna zakładałby lock na własnym, prywatnym
numerze — dokładnie w wielo-procesowym deploymencie, dla którego locki
powstały. Do niedawna dwa miejsca w repo robiły `abs(hash(nazwa)) % 2**31`
i przez to nie chroniły niczego.

Zamiast tego liczymy klucz `blake2s`-em (niesolony, stabilny między
procesami i wersjami Pythona).

PRZESTRZEŃ NAZW: jedno-argumentowy wariant (`pg_advisory_xact_lock(bigint)`)
ma JEDNĄ globalną przestrzeń na cały klaster — kolizja klucza między dwoma
niepowiązanymi podsystemami oznacza, że niepotrzebnie się blokują.
Dwu-argumentowy wariant (`pg_advisory_xact_lock(int, int)`) ma przestrzeń
osobną, więc locki z migracji `0421`/`0428`/`0429`/`0432` (kluczowane
`(classid, objid)`) NIE kolidują z niczym tutaj.

Żeby zminimalizować ryzyko kolizji w przestrzeni jedno-argumentowej:

* nazwy przekazywane tu są w pełni kwalifikowane (`app.funkcja.obiekt`),
* wynik ma 63 bity entropii, więc przy kilku kluczach w systemie
  prawdopodobieństwo kolizji jest astronomicznie małe.
"""

import hashlib

__all__ = ["advisory_lock_id"]


def advisory_lock_id(nazwa: str) -> int:
    """
    Zwróć deterministyczny klucz advisory locka dla podanej nazwy.

    Wynik mieści się w zakresie dodatnich `bigint`-ów (63 bity), czyli w
    dziedzinie jedno-argumentowego `pg_advisory_xact_lock(bigint)`.

    Ta sama nazwa daje tę samą liczbę w KAŻDYM procesie Pythona — na tym
    polega przydatność tej funkcji (patrz docstring modułu).
    """
    digest = hashlib.blake2s(nazwa.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") & (2**63 - 1)
