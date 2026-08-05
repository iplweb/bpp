"""Wspólne zawężanie querysetu ``Rekord`` do polityki widoczności API.

Jedno źródło reguły dla ``/api/v1/szukaj/`` i ``/api/v1/zapytanie/rekord/`` —
oba endpointy MUSZĄ egzekwować ten sam zestaw ograniczeń. Wcześniejszy dryf
(``szukaj`` egzekwował, ``zapytanie`` nie) był luką bezpieczeństwa (uwaga #1
reviewera): token redaktora widział rekordy innej uczelni, ukryte statusy oraz
rekordy oznaczone ``nie_eksportuj_przez_api``.
"""

from django.contrib.contenttypes.models import ContentType

from bpp.util.uczelnia_scope import scope_rekord_do_uczelni


def scope_rekord_api(qs, uczelnia, modele_zrodlowe):
    """Zawęź queryset ``Rekord`` do widoczności API dla danej uczelni.

    Trzy warstwy (identyczne jak frontowa wyszukiwarka „/"):

    1. ``scope_rekord_do_uczelni`` — multi-host: tylko rekordy tej uczelni
       (no-op przy jednej uczelni / braku mapowania Site→Uczelnia),
    2. wykluczenie ``ukryte_statusy("api")`` uczelni (statusy korekty ukryte
       dla API),
    3. wykluczenie rekordów źródłowych z ``nie_eksportuj_przez_api=True``
       (per-content-type na TupleField ``id`` mat-view ``Rekord``).

    ``modele_zrodlowe`` — iterowalne modeli źródłowych (klucze
    ``MODELE_DETAIL_VIEWNAME``); przekazywane, by uniknąć importu cyklicznego.
    """
    qs = scope_rekord_do_uczelni(qs, uczelnia)
    if uczelnia is not None:
        qs = qs.exclude(status_korekty_id__in=uczelnia.ukryte_statusy("api"))
    for model in modele_zrodlowe:
        ct_pk = ContentType.objects.get_for_model(model).pk
        oflagowane = model.objects.filter(nie_eksportuj_przez_api=True).values("pk")
        qs = qs.exclude(id__0=ct_pk, id__1__in=oflagowane)
    return qs
