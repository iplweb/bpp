__doc__ = """W tym module znajdziemy modele, które powstają na skutek wyliczeń (punktacja slotu, zdenormalizowana
tabela wszystkich rekordów, ilość N).

Zawartość tabel tych modeli zazwyczaj musi być na przeróżne sposoby odświeżana.


Cache'ujemy za pomocą tabeli Rekord:
- Wydawnictwo_Zwarte
- Wydawnictwo_Ciagle
- Patent
- Praca_Doktorska
- Praca_Habilitacyjna
"""

from .autorzy import *  # noqa
from .liczba_n import *  # noqa
from .punktacja import *  # noqa
from .rekord import *  # noqa
from .views import *  # noqa
