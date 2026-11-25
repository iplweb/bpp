from decimal import ROUND_HALF_UP, Decimal

from django.utils.functional import cached_property

from bpp.models import Autor

CZTERY_MIEJSCA = Decimal("0.0001")


def zaokraglij_do_4_miejsc(wartosc):
    """Zaokrągla wartość do czterech miejsc po przecinku, „połówki w górę”.

    § 13 ust. 6 rozporządzenia w sprawie ewaluacji jakości działalności
    naukowej (t.j. Dz.U. 2026 poz. 1346): „Wartości liczb √k/m i k/m ustala
    się z dokładnością do czterech miejsc po przecinku.” Przepis nie określa
    trybu, więc stosujemy zwykłe zaokrąglenie matematyczne (ROUND_HALF_UP)
    — tak samo zaokrągla PostgreSQL przy zapisie do pól numeric(…, 4).
    """
    return Decimal(wartosc).quantize(CZTERY_MIEJSCA, rounding=ROUND_HALF_UP)


class SlotMixin:
    """Mixin używany przez Wydawnictwo_Zwarte, Wydawnictwo_Ciagle i Patent
    do przeprowadzania kalkulacji na slotach."""

    def __init__(self, original, uczelnia=None):
        self.original = original
        self.uczelnia = uczelnia

    def _autorzy_qs(self):
        qs = self.original.autorzy_set.all()
        if self.uczelnia is not None:
            qs = qs.filter(jednostka__uczelnia=self.uczelnia)
        return qs

    def wszyscy(self):
        return self._autorzy_qs().count()

    def autorzy_z_dyscypliny(self, dyscyplina_naukowa, typ_ogolny=None):
        ret = []

        elem_kw = {}
        if typ_ogolny is not None:
            # Czy typ ogólny autora (autor, redaktor) to ten, którego poszukujemy?
            elem_kw = {"typ_odpowiedzialnosci__typ_ogolny": typ_ogolny}

        for elem in self._autorzy_qs().filter(
            afiliuje=True,
            przypieta=True,
            # explicte -- nie chcemy, aby to pole brało udział w kalkulacjach
            # mpasternak 18.03.2025
            # upowaznienie_pbn=True,
            dyscyplina_naukowa=dyscyplina_naukowa,
            **elem_kw,
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
        for wa in self._autorzy_qs():
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
        Dzieli PKd (czyli punkty MNiSW dla dyscypliny) przez liczbę k czyli
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
        """k/m zaokrąglone do 4 miejsc po przecinku (§ 13 ust. 6).

        Liczone na Decimal (bez float), żeby zaokrąglenie „połówek” było
        dokładne — np. 1/160 = 0,00625 daje 0,0063."""
        m = self.wszyscy()
        if m == 0:
            return
        return zaokraglij_do_4_miejsc(Decimal(self.liczba_k(dyscyplina)) / m)

    def pierwiastek_k_przez_m(self, dyscyplina):
        """√(k/m) zaokrąglony do 4 miejsc po przecinku (§ 13 ust. 6).

        Pierwiastek liczymy z dokładnego k/m (nie z już zaokrąglonego),
        a zaokrąglamy wynik — dopiero ta wartość jest mnożona przez punkty,
        np. 20 × √(1/6) = 20 × 0,4082 = 8,1640 (a nie 8,1650)."""
        m = self.wszyscy()
        if m == 0:
            return
        return zaokraglij_do_4_miejsc((Decimal(self.liczba_k(dyscyplina)) / m).sqrt())
