# -*- encoding: utf-8 -*-

# Zaimportujmy wszystko
from bpp.models.abstract import *  # noqa
from bpp.models.autor import *  # noqa
from bpp.models.grant import *  # noqa
from bpp.models.patent import *  # noqa
from bpp.models.praca_doktorska import *  # noqa
from bpp.models.praca_habilitacyjna import *  # noqa
from bpp.models.profile import *  # noqa
from bpp.models.repozytorium import *  # noqa
from bpp.models.struktura import *  # noqa
from bpp.models.system import *  # noqa
from bpp.models.wydawnictwo_ciagle import *  # noqa
from bpp.models.wydawnictwo_zwarte import *  # noqa
from bpp.models.zrodlo import *  # noqa

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

from .multiseek import BppMultiseekVisibility  # noqa

from bpp.models.cache import *  # noqa
from bpp.models.dyscyplina_naukowa import *  # noqa
from bpp.models.konferencja import *  # noqa
from bpp.models.kronika_view import *  # noqa
from bpp.models.openaccess import *  # noqa
from bpp.models.opi_2012 import *  # noqa
from bpp.models.seria_wydawnicza import *  # noqa
from bpp.models.sumy_views import *  # noqa

TABLE_TO_MODEL = {
    "bpp_wydawnictwo_ciagle": Wydawnictwo_Ciagle,  # noqa
    "bpp_wydawnictwo_zwarte": Wydawnictwo_Zwarte,  # noqa
    "bpp_praca_doktorska": Praca_Doktorska,  # noqa
    "bpp_praca_habilitacyjna": Praca_Habilitacyjna,  # noqa
    "bpp_patent": Patent,  # noqa
}  # noqa
