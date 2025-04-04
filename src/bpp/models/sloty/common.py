import math
from decimal import Decimal

from django.utils.functional import cached_property

from bpp.models import Autor


class SlotMixin:
    """Mixin używany przez Wydawnictwo_Zwarte, Wydawnictwo_Ciagle i Patent
    do przeprowadzania kalkulacji na slotach."""

    def __init__(self, original):
        self.original = original

    def wszyscy(self):
        return self.original.autorzy_set.count()

    def autorzy_z_dyscypliny(self, dyscyplina_naukowa, typ_ogolny=None):
        ret = []

        elem_kw = {}
        if typ_ogolny is not None:
            # Czy typ ogólny autora (autor, redaktor) to ten, którego poszukujemy?
            elem_kw = {"typ_odpowiedzialnosci__typ_ogolny": typ_ogolny}

        for elem in self.original.autorzy_set.filter(
            afiliuje=True,
            przypieta=True,
            # explicte -- nie chcemy, aby to pole brało udział w kalkulacjach
            # mpasternak 18.03.2025
            # upowaznienie_pbn=True,
            dyscyplina_naukowa=dyscyplina_naukowa,
            **elem_kw
        ):
            # Upewnij się, ze za ten rok ten konkretny autor ma rodzaj "jest w N"
            # lub jest doktorantem:
            if not elem.rodzaj_autora_uwzgledniany_w_kalkulacjach_slotow():
                continue

            ret.append(elem)
        return ret

    @cached_property
    def dyscypliny(self):
        if not self.original.pk:
            return set()

        ret = set()
        for wa in self.original.autorzy_set.all():
            d = wa.okresl_dyscypline()
            if d is None:
                continue
            ret.add(d)
        return ret

    def ma_dyscypline(self, dyscyplina):
        return dyscyplina in self.dyscypliny

    def ensure_autor_rekordu_klass(self, a):
        """
        Jeżeli parametr 'a' to self.original.autor_rekordu_klass, zwraca parametr
        a. Jeżeli parametr 'a' to bpp.models.Autor, znajdź odpowiedni autor_rekordu_klass
        (czyli Wydawnictwo_Ciagle_Autor lub Wydawnictwo_Zwarte_Autor), gdzie ten
        autor występuje.
        """

        if isinstance(a, Autor):
            return self.original.autor_rekordu_klass.objects.get(
                rekord=self.original, autor=a
            )
        return a

    def pkd_dla_autora(self, wca):
        """
        Dzieli PKd (czyli punkty MNiSW/MEiN dla dyscypliny) przez liczbę k czyli
        przez liczbę wszystkich autorów/redaktorów dla artykułu/książki/rozdziału
        z danej dyscypliny.

        :type wca: bpp.models.WydawnictwoCiagleAutor
        """
        wca = self.ensure_autor_rekordu_klass(wca)

        dyscyplina = wca.okresl_dyscypline()
        azd = len(self.autorzy_z_dyscypliny(dyscyplina))
        if azd == 0:
            return

        pkd = self.punkty_pkd(dyscyplina)
        if pkd is None:
            return
        return Decimal(pkd) / Decimal(azd)

    def slot_dla_autora(self, wca):
        """Normalnie punktację 'slot dla autora z danej dyscypliny' dostajemy w ten
        sposób, że korzystać będziemy z funckji slot_dla_autora_z_dyscypliny.
        Ta funkcja przyjmuje dyscyplinę jako parametr.

        Niekiedy jednak będziemy mieli dostępny obiekt typu Wydawnictwo_Ciagle_Autor,
        niekiedy będziemy mieli samego autora. Żeby uprościć API, funkcja
        'slot_dla_autora' przyjąć może obydwa te parametry (potem upewniając się,
        za pomocą ensure_autor_rekordu_klass, że ma jednak obiekt typu
        Wydawnictwo_Ciagle_Autor). Następnie funkcja określi przypisaną temu
        autorowi dyscyplinę, za pomocą Wydawnictwo_Ciagle_Autor.okresl_dyscypline.
        Następnie, wywoła funkcję slot_dla_autora_z_danej_dyscypliny, podając
        tutaj już dyscyplinę jako parametr.
        """
        wca = self.ensure_autor_rekordu_klass(wca)
        dyscyplina = wca.okresl_dyscypline()
        return self.slot_dla_autora_z_dyscypliny(dyscyplina)

    def liczba_k(self, dyscyplina):
        """Liczba k czyli liczba autorów z dyscypliny (z afiliacją=tak)"""
        if hasattr(self, "_liczba_k_cache"):
            v = self._liczba_k_cache.get(dyscyplina)
            if v is not None:
                return v
        else:
            self._liczba_k_cache = {}

        v = len(self.autorzy_z_dyscypliny(dyscyplina))
        self._liczba_k_cache[dyscyplina] = v
        return v

    def k_przez_m(self, dyscyplina):
        if self.wszyscy() == 0:
            return
        return Decimal(self.liczba_k(dyscyplina) / self.wszyscy())

    def pierwiastek_k_przez_m(self, dyscyplina):
        k_przez_m = self.k_przez_m(dyscyplina)
        if k_przez_m is None:
            return
        return Decimal(math.sqrt(k_przez_m))

    def jeden_przez_wszyscy(self):
        w = self.wszyscy()
        if w == 0:
            return
        return 1 / w
