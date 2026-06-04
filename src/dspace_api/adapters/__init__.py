from dspace_api.adapters.patent import PatentDSpaceAdapter
from dspace_api.adapters.prace import (
    PracaDoktorskaDSpaceAdapter,
    PracaHabilitacyjnaDSpaceAdapter,
)
from dspace_api.adapters.wydawnictwo_ciagle import WydawnictwoCiagleDSpaceAdapter
from dspace_api.adapters.wydawnictwo_zwarte import WydawnictwoZwarteDSpaceAdapter

_REJESTR = {
    "Wydawnictwo_Ciagle": WydawnictwoCiagleDSpaceAdapter,
    "Wydawnictwo_Zwarte": WydawnictwoZwarteDSpaceAdapter,
    "Patent": PatentDSpaceAdapter,
    "Praca_Doktorska": PracaDoktorskaDSpaceAdapter,
    "Praca_Habilitacyjna": PracaHabilitacyjnaDSpaceAdapter,
}


def adapter_for(rec, domyslny_jezyk="pl"):
    klasa = _REJESTR.get(type(rec).__name__)
    if klasa is None:
        raise ValueError(f"Brak adaptera DSpace dla modelu {type(rec).__name__}")
    return klasa(rec, domyslny_jezyk=domyslny_jezyk)
