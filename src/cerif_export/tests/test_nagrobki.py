"""Faza 05b soft-delete: nagrobki dla konsumentów przyrostowych.

Nagrobek = rekord, który NALEŻY do tenanta, ale nie jest już wystawiany.
Dopełniamy ekspozycję, nigdy przynależność — dopełnienie przynależności
wystawiłoby w multi-hosted rekordy cudzych uczelni.
"""

from cerif_export.oai.czasowniki import rejestr_providerow


def test_kazdy_provider_deklaruje_przynaleznosc():
    """Kontrakt musi być kompletny, inaczej nagrobki milkną w losowym secie.

    Provider bez ``przynaleznosc`` wywaliłby się dopiero przy harveście
    akurat tego setu — czyli u konsumenta, nie w testach.
    """
    for set_spec, provider in rejestr_providerow().items():
        assert hasattr(provider, "przynaleznosc"), (
            f"Provider setu {set_spec} nie deklaruje przynaleznosc()"
        )
