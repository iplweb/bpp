from django.utils.functional import cached_property

from django.utils.functional import cached_property

from bpp.models import TO_AUTOR, TO_REDAKTOR, Autor


class SlotMixin:
    """Mixin używany przez Wydawnictwo_Zwarte, Wydawnictwo_Ciagle i Patent
    do przeprowadzania kalkulacji na slotach. """

    def __init__(self, original):
        self.original = original

    def wszyscy(self):
        return self.original.autorzy_set.count()

    def autorzy_z_dyscypliny(self, dyscyplina_naukowa, typ_ogolny=None):
        qset = self.original.autorzy_set.filter(
            dyscyplina_naukowa=dyscyplina_naukowa
        )

        if typ_ogolny is not None:
            qset = qset.filter(typ_odpowiedzialnosci__typ_ogolny=typ_ogolny)

        return qset

    def wszyscy_autorzy(self, typ_ogolny=None):
        # TODO: czy wszyscy, czy wszyscy redaktorzy, czy ... ?

        if hasattr(self.original, 'calkowita_liczba_autorow'):
            if self.original.calkowita_liczba_autorow is not None and (typ_ogolny is None or typ_ogolny == TO_AUTOR):
                return self.original.calkowita_liczba_autorow

        if hasattr(self.original, 'calkowita_liczba_redaktorow'):
            if typ_ogolny is TO_REDAKTOR and self.original.calkowita_liczba_redaktorow is not None:
                return self.original.calkowita_liczba_redaktorow

        if typ_ogolny is None:
            return self.wszyscy()

        return self.original.autorzy_set.filter(
            typ_odpowiedzialnosci__typ_ogolny=typ_ogolny
        ).count()

    @cached_property
    def dyscypliny(self):
        return self.original.autorzy_set.exclude(dyscyplina_naukowa=None).values(
            "dyscyplina_naukowa").distinct().values_list('dyscyplina_naukowa', flat=True)

    def ma_dyscypline(self, dyscyplina):
        return dyscyplina.pk in self.dyscypliny

    def ensure_autor_rekordu_klass(self, a):
        """
        Jeżeli parametr 'a' to self.original.autor_rekordu_klass, zwraca parametr
        a. Jeżeli parametr 'a' to bpp.models.Autor, znajdź odpowiedni autor_rekordu_klass
        (czyli Wydawnictwo_Ciagle_Autor lub Wydawnictwo_Zwarte_Autor), gdzie ten
        autor występuje.
        """

        if isinstance(a, Autor):
            return self.original.autor_rekordu_klass.objects.get(
                rekord=self.original,
                autor=a
            )
        return a

    def pkd_dla_autora(self, wca):
        """
        Dzieli PKd (czyli punkty PK dla dyscypliny) przez liczbę k czyli
        przez liczbę wszystkich autorów/redaktorów dla artykułu/książki/rozdziału
        z danej dyscypliny.

        :type wca: bpp.models.WydawnictwoCiagleAutor
        """
        wca = self.ensure_autor_rekordu_klass(wca)

        dyscyplina = wca.okresl_dyscypline()
        azd = self.autorzy_z_dyscypliny(dyscyplina).count()
        if azd == 0:
            return

        pkd = self.punkty_pkd(dyscyplina)
        if pkd is None:
            return

        return pkd / azd

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

