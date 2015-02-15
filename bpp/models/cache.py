# -*- encoding: utf-8 -*-
import warnings

from django.contrib.contenttypes.models import ContentType
from django.db.models.deletion import DO_NOTHING
from django.db import models, transaction
from django.db.models.signals import post_save, pre_save, post_delete
from djorm_pgfulltext.fields import VectorField

from filtered_contenttypes.fields import FilteredGenericForeignKey
from bpp.models import Patent, \
    Praca_Doktorska, Praca_Habilitacyjna, \
    Typ_Odpowiedzialnosci, Wydawnictwo_Zwarte, \
    Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor, Patent_Autor, Zrodlo



# Cache'ujemy:
# - Wydawnictwo_Zwarte
# - Wydawnictwo_Ciagle
# - Patent
# - Praca_Doktorska
# - Praca_Habilitacyjna
from django.core.exceptions import ObjectDoesNotExist
from bpp.models.abstract import ModelPunktowanyBaza, \
    ModelZRokiem, ModelZeSzczegolami, ModelAfiliowanyRecenzowany, \
    ModelZCharakterem, ModelZWWW
from bpp.models.system import Charakter_Formalny, Jezyk
from bpp.models.util import ModelZOpisemBibliograficznym
from bpp.tasks import refresh_rekord, refresh_autorzy
from bpp.util import FulltextSearchMixin

CACHED_MODELS = [Wydawnictwo_Ciagle, Wydawnictwo_Zwarte, Praca_Doktorska,
                 Praca_Habilitacyjna, Patent]

DEPENDENT_REKORD_MODELS = [Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor,
                           Patent_Autor]

# Other dependent -- czyli skasowanie tych obiektów pociąga za sobą odbudowanie
# tabeli cache
OTHER_DEPENDENT_MODELS = [Typ_Odpowiedzialnosci, Jezyk, Charakter_Formalny]


def defer_zaktualizuj_opis(instance, *args, **kw):
    """Obiekt typu Wydawnictwo_..., Patent, Praca_... został zapisany.
    Zaktualizuj jego opis bibliograficzny."""
    from bpp.tasks import zaktualizuj_opis

    flds = kw.get('update_fields', [])

    if flds:
        flds = list(flds)
        for elem in ['opis_bibliograficzny_cache',
                     'opis_bibliograficzny_autorzy_cache']:
            try:
                flds.remove(elem)
            except ValueError:
                pass

        if not flds:
            # uniknij loopa w przypadku zapisywania obiektu z metody
            # models.util.ModelZOpisemBibliograficznym.zaktualizuj_opis
            return

    zaktualizuj_opis.delay(instance.__class__, instance.pk)

def defer_odswiez_rekordy(*args, **kw):
    refresh_rekord()
    refresh_autorzy()

def defer_zaktualizuj_opis_rekordu(instance, *args, **kw):
    """Obiekt typy Wydawnictwo..._Autor został zapisany (post_save) LUB
    został skasowany (post_delete). Zaktualizuj rekordy."""
    try:
        rekord = instance.rekord
    except ObjectDoesNotExist:
        # W sytuacji, gdyby rekord nadrzędny również został skasowany...
        return
    return defer_zaktualizuj_opis(rekord)


def defer_zaktualizuj_zrodlo(instance, *args, **kw):
    """Źródło za chwilę zostanie zapisane (pre_save).

    Jeżeli jego tytuł uległ zmianie, zaktualizuj wszystkie publikacje zapisane
    w tym źródle."""

    # Nowy obiekt -- wyjdź
    if instance.pk is None:
        return

    try:
        old = Zrodlo.objects.get(pk=instance.pk)
    except Zrodlo.DoesNotExist:
        return

    if old.nazwa != instance.nazwa:
        from bpp.tasks import zaktualizuj_opis, zaktualizuj_zrodlo
        zaktualizuj_zrodlo.delay(instance.pk)


_CACHE_ENABLED = False

class AlreadyEnabledException(Exception):
    pass

class AlreadyDisabledException(Exception):
    pass


def enable():

    global _CACHE_ENABLED

    if _CACHE_ENABLED: raise AlreadyEnabledException()

    pre_save.connect(defer_zaktualizuj_zrodlo, sender=Zrodlo)

    for model in DEPENDENT_REKORD_MODELS:
        post_save.connect(defer_zaktualizuj_opis_rekordu, sender=model)
        post_delete.connect(defer_zaktualizuj_opis_rekordu, sender=model)

    for model in CACHED_MODELS:
        post_save.connect(defer_zaktualizuj_opis, sender=model)
        post_delete.connect(defer_odswiez_rekordy, sender=model)

    for model in OTHER_DEPENDENT_MODELS:
        post_delete.connect(defer_odswiez_rekordy, sender=model)

    _CACHE_ENABLED = True

def disable():
    global _CACHE_ENABLED

    if not _CACHE_ENABLED:
        raise AlreadyDisabledException

    pre_save.disconnect(defer_zaktualizuj_zrodlo, sender=Zrodlo)

    for model in DEPENDENT_REKORD_MODELS:
        post_save.disconnect(defer_zaktualizuj_opis_rekordu, sender=model)
        post_delete.disconnect(defer_zaktualizuj_opis_rekordu, sender=model)

    for model in CACHED_MODELS:
        post_save.disconnect(defer_zaktualizuj_opis, sender=model)
        post_delete.disconnect(defer_odswiez_rekordy, sender=model)

    for model in OTHER_DEPENDENT_MODELS:
        post_delete.disconnect(defer_odswiez_rekordy, sender=model)

    _CACHE_ENABLED = False


class AutorzyManager(models.Manager):
    def refresh_materialized_view(self):
        warnings.warn("Ta procedura NIC nie robi", DeprecationWarning)


class AutorzyBase(models.Model):
    fake_id = models.TextField(primary_key=True)

    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    rekord = FilteredGenericForeignKey('content_type', 'object_id')

    autor = models.ForeignKey('Autor', on_delete=DO_NOTHING)
    jednostka = models.ForeignKey('Jednostka', on_delete=DO_NOTHING)
    kolejnosc = models.IntegerField()
    typ_odpowiedzialnosci = models.ForeignKey('Typ_Odpowiedzialnosci', on_delete=DO_NOTHING)
    zapisany_jako = models.TextField()

    objects = AutorzyManager()

    class Meta:
        abstract = True


class Autorzy(AutorzyBase):
    class Meta:
        managed = False
        db_table = 'bpp_autorzy_mat'


class AutorzyView(AutorzyBase):
    class Meta:
        managed = False
        db_table = 'bpp_autorzy'

# class RekordCountQuery(Query):
#
#     def add_count_column(self):
#         """
#         Converts the query to do count(...) or count(distinct(pk)) in order to
#         get its size.
#         """
#         xxx tu skon
#
#         if not self.distinct:
#             if not self.select:
#                 count = self.aggregates_module.Count('*', is_summary=True)
#             else:
#                 assert len(self.select) == 1, \
#                     "Cannot add count col with multiple cols in 'select': %r" % self.select
#                 count = self.aggregates_module.Count("LOL")
#         else:
#             opts = self.get_meta()
#             if not self.select:
#                 count = self.aggregates_module.Count(
#                     Rekord.original,
#                     is_summary=True, distinct=True)
#             else:
#                 # Because of SQL portability issues, multi-column, distinct
#                 # counts need a sub-query -- see get_count() for details.
#                 assert len(self.select) == 1, \
#                     "Cannot add count col with multiple cols in 'select'."
#
#                 count = self.aggregates_module.Count(
#                     "WTF", distinct=True)
#             # Distinct handling is done in Count(), so don't do it at this
#             # level.
#             self.distinct = False
#
#         # Set only aggregate to be the count column.
#         # Clear out the select cache to reflect the new unmasked aggregates.
#         self._aggregates = {None: count}
#         self.set_aggregate_mask(None)
#         self.group_by = None

class RekordManager(FulltextSearchMixin, models.Manager):
    fts_field = 'search_index'

    def prace_autora(self, autor):
        return self.filter(original__in_raw=Autorzy.objects.filter(autor=autor)).distinct()

    def prace_autor_i_typ(self, autor, skrot):
        return self.filter(
            original__in_raw=Autorzy.objects.filter(
                autor_id=autor.pk,
                typ_odpowiedzialnosci_id=Typ_Odpowiedzialnosci.objects.get(skrot=skrot).pk
            )).distinct()


    def prace_jednostki(self, jednostka):
        return self.filter(
            original__in_raw=Autorzy.objects.filter(jednostka=jednostka)).distinct()

    def redaktorzy_z_jednostki(self, jednostka):
        return self.filter(
            original__in_raw=Autorzy.objects.filter(
                jednostka=jednostka,
                typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot='red.')
            )).distinct()

    def refresh_materialized_view(self):
        warnings.warn("ta procedura nic nie robi", DeprecationWarning)

    def refresh(self):
        """Procedura używana przez testy w sytuacji wyłączonego cache
        """
        warnings.warn("ta procedura nic nie robi", DeprecationWarning)

    @transaction.atomic
    def full_refresh(self):
        """Procedura odswieza opisy bibliograficzne dla wszystkich rekordów.
        """

        global _CACHE_ENABLED

        was_enabled = False

        try:
            if _CACHE_ENABLED:
                was_enabled = True
                disable()

            for elem in self.all():
                elem.original.zaktualizuj_cache()

        finally:
            if was_enabled:
                enable()

    #
    # def get_queryset(self):
    #     """
    #     Returns a new QuerySet object.  Subclasses can override this method to
    #     easily customize the behavior of the Manager.
    #     """
    #     return QuerySet(model=self.model, query=RekordCountQuery(self.model),
    #                     using=self._db, hints=self._hints)
    #

class Rekord(ModelPunktowanyBaza, ModelZOpisemBibliograficznym,
             ModelZRokiem, ModelZeSzczegolami, ModelAfiliowanyRecenzowany,
             models.Model):
    # XXX TODO: gdy będą compound keys w Django, można pozbyć się fake_id
    fake_id = models.TextField(primary_key=True)

    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    original = FilteredGenericForeignKey('content_type', 'object_id')

    tytul_oryginalny = models.TextField()
    tytul = models.TextField()
    search_index = VectorField()

    jezyk = models.ForeignKey('Jezyk', on_delete=DO_NOTHING)
    typ_kbn = models.ForeignKey('Typ_KBN', on_delete=DO_NOTHING)
    charakter_formalny = models.ForeignKey('Charakter_Formalny', on_delete=DO_NOTHING)

    zrodlo = models.ForeignKey(Zrodlo, on_delete=DO_NOTHING)

    wydawnictwo = models.TextField()

    adnotacje = models.TextField()
    ostatnio_zmieniony = models.DateTimeField()

    tytul_oryginalny_sort = models.TextField()

    liczba_znakow_wydawniczych = models.IntegerField()

    # nie dziedziczymy z ModelZWWW, poniewaz tam jest pole dostep_dnia,
    # ktore to obecnie nie jest potrzebne w Cache, wiec:
    www = models.URLField("Adres WWW", max_length=1024, blank=True, null=True)

    objects = RekordManager()

    class Meta:
        managed = False
        ordering = ['tytul_oryginalny_sort']
        db_table = 'bpp_rekord_mat'


    def __unicode__(self):
        return self.tytul_oryginalny


def with_cache(fun):
    """Użyj jako dekorator do funkcji testujących"""
    def _wrapped(*args, **kw):
        enable_failure = None
        try:
            enable_failure = True
            enable()
            enable_failure = False
            fun(*args, **kw)
        finally:
            if not enable_failure:
                disable()
            else:
                raise Exception("Enable failure, trace enable function, there was a bug there...")

    return _wrapped