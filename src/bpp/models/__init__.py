# Zaimportujmy wszystko
from .abstract import *  # noqa
from .autor import *  # noqa
from .cache import *  # noqa
from .dyscyplina_naukowa import *  # noqa
from .grant import *  # noqa
from .kierunek_studiow import Kierunek_Studiow  # noqa
from .konferencja import *  # noqa
from .multiseek import BppMultiseekVisibility  # noqa
from .openaccess import *  # noqa
from .patent import *  # noqa
from .praca_doktorska import *  # noqa
from .praca_habilitacyjna import *  # noqa
from .profile import *  # noqa
from .repozytorium import *  # noqa
from .rzeczownik import *  # noqa
from .seria_wydawnicza import *  # noqa
from .struktura import *  # noqa
from .sumy_views import *  # noqa
from .system import *  # noqa
from .wydawnictwo_ciagle import *  # noqa
from .wydawnictwo_zwarte import *  # noqa
from .zrodlo import *  # noqa

# W tej tablicy znajdują się wszystkie modele dziedziczące z ModelPunktowany
MODELE_PUNKTOWANE = [
    Wydawnictwo_Zwarte,  # noqa
    Wydawnictwo_Ciagle,  # noqa
    Praca_Doktorska,  # noqa
    Praca_Habilitacyjna,  # noqa
    Patent,  # noqa
]  # noqa

# W tej tablicy znajdują się wszystkie modele będące powiązaniem rekordu
# z rekordem Autora
MODELE_AUTORSKIE = [
    Wydawnictwo_Zwarte_Autor,  # noqa
    Wydawnictwo_Ciagle_Autor,  # noqa
    Patent_Autor,  # noqa
]  # noqa

TABLE_TO_MODEL = {
    "bpp_wydawnictwo_ciagle": Wydawnictwo_Ciagle,  # noqa
    "bpp_wydawnictwo_zwarte": Wydawnictwo_Zwarte,  # noqa
    "bpp_praca_doktorska": Praca_Doktorska,  # noqa
    "bpp_praca_habilitacyjna": Praca_Habilitacyjna,  # noqa
    "bpp_patent": Patent,  # noqa
}  # noqa


from .opi_2012 import *  # noqa
