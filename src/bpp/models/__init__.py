# -*- encoding: utf-8 -*-

# Zaimportujmy wszystko
from bpp.models.abstract import *
from bpp.models.struktura import *
from bpp.models.autor import *
from bpp.models.profile import *
from bpp.models.system import *
from bpp.models.wydawnictwo_ciagle import *
from bpp.models.wydawnictwo_zwarte import *
from bpp.models.zrodlo import *
from bpp.models.praca_doktorska import *
from bpp.models.praca_habilitacyjna import *
from bpp.models.patent import *


# W tej tablicy znajdują się wszystkie modele dziedziczące z ModelPunktowany
MODELE_PUNKTOWANE = [
    Wydawnictwo_Zwarte,
    Wydawnictwo_Ciagle,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Patent,
]

# W tej tablicy znajdują się wszystkie modele będące powiązaniem rekordu
# z rekordem Autora
MODELE_AUTORSKIE = [Wydawnictwo_Zwarte_Autor, Wydawnictwo_Ciagle_Autor, Patent_Autor]

from bpp.models.cache import *
from bpp.models.sumy_views import *
from bpp.models.kronika_view import *

from bpp.models.opi_2012 import *

from bpp.models.openaccess import *

from bpp.models.dyscyplina_naukowa import *

from bpp.models.seria_wydawnicza import *

from bpp.models.konferencja import *

from bpp.models.repozytorium import Element_Repozytorium

from bpp.models.grant import Grant, Grant_Rekordu

TABLE_TO_MODEL = {
    "bpp_wydawnictwo_ciagle": Wydawnictwo_Ciagle,
    "bpp_wydawnictwo_zwarte": Wydawnictwo_Zwarte,
    "bpp_praca_doktorska": Praca_Doktorska,
    "bpp_praca_habilitacyjna": Praca_Habilitacyjna,
    "bpp_patent": Patent,
}
