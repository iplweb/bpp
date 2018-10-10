# -*- encoding: utf-8 -*-

# Cache'ujemy:
# - Wydawnictwo_Zwarte
# - Wydawnictwo_Ciagle
# - Patent
# - Praca_Doktorska
# - Praca_Habilitacyjna
import traceback

from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields.array import ArrayField
from django.contrib.postgres.search import SearchVectorField as VectorField
from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
from django.db.models.deletion import DO_NOTHING
from django.db.models.lookups import In
from django.db.models.signals import post_save, post_delete, pre_save, \
    pre_delete
from django.utils import six
from django.utils.functional import cached_property

from bpp.models import Patent, \
    Praca_Doktorska, Praca_Habilitacyjna, \
    Typ_Odpowiedzialnosci, Wydawnictwo_Zwarte, \
    Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor, \
    Patent_Autor, Zrodlo
from bpp.models.abstract import ModelPunktowanyBaza, \
    ModelZRokiem, ModelZeSzczegolami, ModelRecenzowany, \
    ModelZeZnakamiWydawniczymi, ModelZOpenAccess, ModelZKonferencja, \
    ModelTypowany, ModelZCharakterem
from bpp.models.system import Charakter_Formalny, Jezyk
from bpp.models.util import ModelZOpisemBibliograficznym
from bpp.util import FulltextSearchMixin

# zmiana CACHED_MODELS powoduje zmiane opisu bibliograficznego wszystkich rekordow
CACHED_MODELS = [Wydawnictwo_Ciagle, Wydawnictwo_Zwarte, Praca_Doktorska,
                 Praca_Habilitacyjna, Patent]

# zmiana DEPENDEND_REKORD_MODELS powoduje zmiane opisu bibliograficznego rekordu z pola z ich .rekord
DEPENDENT_REKORD_MODELS = [Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor,
                           Patent_Autor]

# Other dependent -- czyli skasowanie tych obiektów pociąga za sobą odbudowanie tabeli cache
OTHER_DEPENDENT_MODELS = [Typ_Odpowiedzialnosci, Jezyk, Charakter_Formalny, Zrodlo]


def defer_zaktualizuj_opis(instance, *args, **kw):
    """Obiekt typu Wydawnictwo_..., Patent, Praca_... został zapisany.
    Zaktualizuj jego opis bibliograficzny."""
    from bpp.tasks import zaktualizuj_opis

    flds = kw.get('update_fields', [])

    if flds:
        flds = list(flds)
        for elem in ['opis_bibliograficzny_cache',
                     'opis_bibliograficzny_autorzy_cache',
                     'opis_bibliograficzny_zapisani_autorzy_cache']:
            try:
                flds.remove(elem)
            except ValueError:
                pass

        if not flds:
            # uniknij loopa w przypadku zapisywania obiektu z metody
            # models.util.ModelZOpisemBibliograficznym.zaktualizuj_opis
            return

    called_by = "X".join(traceback.format_stack())

    transaction.on_commit(
        lambda: zaktualizuj_opis.delay(
            app_label=instance._meta.app_label,
            model_name=instance._meta.model_name,
            pk=instance.pk,
            called_by=called_by))


def defer_zaktualizuj_opis_rekordu(instance, *args, **kw):
    """Obiekt typy Wydawnictwo..._Autor został zapisany (post_save) LUB
    został skasowany (post_delete). Zaktualizuj rekordy."""

    try:
        rekord = instance.rekord
    except ObjectDoesNotExist:
        # W sytuacji, gdyby rekord nadrzędny również został skasowany...
        return
    return defer_zaktualizuj_opis(rekord)


def zrodlo_pre_save(instance, *args, **kw):
    if instance.pk is None:
        return

    changed = kw.get("update_fields", [])
    if changed:
        instance._BPP_CHANGED_FIELDS = changed
        return

    try:
        old = Zrodlo.objects.get(pk=instance.pk)
    except Zrodlo.DoesNotExist:
        return

    if old.skrot != instance.skrot:  # sprawdz skrot, bo on idzie do opisu
        instance._BPP_CHANGED_FIELDS = ['skrot', ]


def zrodlo_post_save(instance, *args, **kw):
    """Źródło zostało zapisane (post_save)
    """

    changed = getattr(instance, "_BPP_CHANGED_FIELDS", [])
    if not changed:
        changed = kw.get('update_fields') or []

    if 'skrot' in changed:
        from bpp.tasks import zaktualizuj_zrodlo
        zaktualizuj_zrodlo.delay(instance.pk)


def zrodlo_pre_delete(instance, *args, **kw):
    # TODO: moze byc memory-consuming, lepiej byloby to wrzucic do bazy danych - moze?
    instance._PRACE = list(Rekord.objects.filter(zrodlo__id=instance.pk).values_list("id", flat=True))


def zrodlo_post_delete(instance, *args, **kw):
    for pk in instance._PRACE:
        try:
            rekord = Rekord.objects.get(pk=pk)
        except Rekord.DoesNotExist:
            continue
        defer_zaktualizuj_opis(rekord.original)

    pass


_CACHE_ENABLED = False


class AlreadyEnabledException(Exception):
    pass


class AlreadyDisabledException(Exception):
    pass


def enable():
    global _CACHE_ENABLED

    if _CACHE_ENABLED: raise AlreadyEnabledException()

    pre_save.connect(zrodlo_pre_save, sender=Zrodlo)
    post_save.connect(zrodlo_post_save, sender=Zrodlo)
    pre_delete.connect(zrodlo_pre_delete, sender=Zrodlo)
    post_delete.connect(zrodlo_post_delete, sender=Zrodlo)

    for model in DEPENDENT_REKORD_MODELS:
        post_save.connect(defer_zaktualizuj_opis_rekordu, sender=model)
        post_delete.connect(defer_zaktualizuj_opis_rekordu, sender=model)

    for model in CACHED_MODELS:
        post_save.connect(defer_zaktualizuj_opis, sender=model)

    _CACHE_ENABLED = True


def enabled():
    global _CACHE_ENABLED
    return _CACHE_ENABLED

def disable():
    global _CACHE_ENABLED

    if not _CACHE_ENABLED:
        raise AlreadyDisabledException

    pre_save.disconnect(zrodlo_pre_save, sender=Zrodlo)
    post_save.disconnect(zrodlo_post_save, sender=Zrodlo)
    pre_delete.disconnect(zrodlo_pre_delete, sender=Zrodlo)
    post_delete.disconnect(zrodlo_post_delete, sender=Zrodlo)

    for model in DEPENDENT_REKORD_MODELS:
        post_save.disconnect(defer_zaktualizuj_opis_rekordu, sender=model)
        post_delete.disconnect(defer_zaktualizuj_opis_rekordu, sender=model)

    for model in CACHED_MODELS:
        post_save.disconnect(defer_zaktualizuj_opis, sender=model)

    _CACHE_ENABLED = False


class TupleField(ArrayField):
    def from_db_value(self, value, expression, connection, context):
        return tuple(value)


@TupleField.register_lookup
class TupleInLookup(In):
    def get_prep_lookup(self):
        values = super(TupleInLookup, self).get_prep_lookup()
        if hasattr(self.rhs, '_prepare'):
            return values
        prepared_values = []
        for value in values:
            if hasattr(value, 'resolve_expression'):
                prepared_values.append(value)
            else:
                prepared_values.append(tuple(value))
        return prepared_values


class AutorzyManager(models.Manager):
    def filter_rekord(self, rekord):
        return self.filter(rekord_id=rekord.pk)


class AutorzyBase(models.Model):
    id = TupleField(
        models.IntegerField(),
        size=2,
        primary_key=True)

    autor = models.ForeignKey('Autor', on_delete=DO_NOTHING)
    jednostka = models.ForeignKey('Jednostka', on_delete=DO_NOTHING)
    kolejnosc = models.IntegerField()
    typ_odpowiedzialnosci = models.ForeignKey('Typ_Odpowiedzialnosci', on_delete=DO_NOTHING)
    zapisany_jako = models.TextField()

    afiliuje = models.BooleanField()
    zatrudniony = models.BooleanField()

    objects = AutorzyManager()

    class Meta:
        abstract = True


class Autorzy(AutorzyBase):
    rekord = models.ForeignKey(
        'bpp.Rekord',
        related_name="autorzy",
        # tak na prawdę w bazie danych jest constraint dla ON_DELETE, ale
        # dajemy to tutaj, żeby django się nie awanturowało i nie próbowało
        # tego ręcznie kasować
        on_delete=DO_NOTHING
    )

    class Meta:
        managed = False
        db_table = 'bpp_autorzy_mat'


class AutorzyView(AutorzyBase):
    rekord = models.ForeignKey(
        'bpp.RekordView',
        related_name="autorzy",
        # tak na prawdę w bazie danych jest constraint dla ON_DELETE, ale
        # dajemy to tutaj, żeby django się nie awanturowało i nie próbowało
        # tego ręcznie kasować
        on_delete=DO_NOTHING
    )

    class Meta:
        managed = False
        db_table = 'bpp_autorzy'


class ZewnetrzneBazyDanychView(models.Model):
    rekord = models.ForeignKey(
        'bpp.Rekord',
        related_name='zewnetrzne_bazy',
        on_delete=DO_NOTHING)

    baza = models.ForeignKey(
        'bpp.Zewnetrzna_Baza_Danych',
        on_delete=DO_NOTHING
    )

    info = models.TextField()

    class Meta:
        managed = False
        db_table = "bpp_zewnetrzne_bazy_view"


class RekordManager(FulltextSearchMixin, models.Manager):
    fts_field = 'search_index'

    def prace_autora(self, autor):
        return self.filter(autorzy__autor=autor).distinct()

    def prace_autora_z_afiliowanych_jednostek(self, autor):
        """
        Funkcja zwraca prace danego autora, należące tylko i wyłącznie
        do jednostek skupiających pracowników, gdzie autor jest zaznaczony jako
        afiliowany.
        """
        return self.prace_autora(autor).filter(
            autorzy__autor=autor,
            autorzy__jednostka__skupia_pracownikow=True,
            autorzy__afiliuje=True
        ).distinct()

    def prace_autor_i_typ(self, autor, skrot):
        return self.prace_autora(autor).filter(
            autorzy__typ_odpowiedzialnosci_id=Typ_Odpowiedzialnosci.objects.get(skrot=skrot).pk
        ).distinct()

    def prace_jednostki(self, jednostka):
        return self.filter(
            autorzy__jednostka=jednostka
        ).distinct()

    def prace_wydzialu(self, wydzial):
        return self.filter(
            autorzy__jednostka__wydzial=wydzial
        ).distinct()

    def redaktorzy_z_jednostki(self, jednostka):
        return self.filter(
            autorzy__jednostka=jednostka,
            autorzy__typ_odpowiedzialnosci_id=Typ_Odpowiedzialnosci.objects.get(
                skrot='red.').pk
        ).distinct()

    def get_original(self, model):
        return self.get(pk=[
            ContentType.objects.get_for_model(model).pk,
            model.pk
        ])

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


@six.python_2_unicode_compatible
class RekordBase(ModelPunktowanyBaza, ModelZOpisemBibliograficznym,
                 ModelZRokiem, ModelZeSzczegolami, ModelRecenzowany,
                 ModelZeZnakamiWydawniczymi, ModelZOpenAccess,
                 ModelTypowany, ModelZCharakterem,
                 ModelZKonferencja,
                 models.Model):
    id = TupleField(
        models.IntegerField(),
        size=2,
        primary_key=True)

    tytul_oryginalny = models.TextField()
    tytul = models.TextField()
    search_index = VectorField()

    zrodlo = models.ForeignKey(Zrodlo, on_delete=DO_NOTHING)

    wydawnictwo = models.TextField()

    adnotacje = models.TextField()
    ostatnio_zmieniony = models.DateTimeField()
    ostatnio_zmieniony_dla_pbn = models.DateTimeField()

    tytul_oryginalny_sort = models.TextField()

    liczba_autorow = models.SmallIntegerField()

    liczba_cytowan = models.SmallIntegerField()

    # nie dziedziczymy z ModelZWWW, poniewaz tam jest pole dostep_dnia,
    # ktore to obecnie nie jest potrzebne w Cache, wiec:
    www = models.URLField("Adres WWW", max_length=1024, blank=True, null=True)

    objects = RekordManager()

    strony = None
    nr_zeszytu = None
    tom = None

    # Skróty dla django-dsl

    django_dsl_shortcuts = {
        "charakter": "charakter_formalny__skrot",
        "typ_kbn": "typ_kbn__skrot",
        "typ_odpowiedzialnosci": "autorzy__typ_odpowiedzialnosci__skrot",
        "autor": "autorzy__autor_id",
        "jednostka": "autorzy__jednostka__pk",
        "wydzial": "autorzy__jednostka__wydzial__pk"
    }

    class Meta:
        abstract = True

    def __str__(self):
        return self.tytul_oryginalny

    @cached_property
    def content_type(self):
        return ContentType.objects.get(pk=self.id[0])

    @cached_property
    def object_id(self):
        return self.id[1]

    @cached_property
    def original(self):
        return self.content_type.get_object_for_this_type(pk=self.object_id)

    @cached_property
    def js_safe_pk(self):
        return "%i_%i" % (self.pk[0], self.pk[1])


class Rekord(RekordBase):
    class Meta:
        managed = False
        ordering = ['tytul_oryginalny_sort']
        db_table = 'bpp_rekord_mat'


class RekordView(RekordBase):
    class Meta:
        managed = False
        db_table = 'bpp_rekord'


def with_cache(fun):
    """Użyj jako dekorator do funkcji testujących"""

    def _wrapped(*args, **kw):
        enable_failure = None

        # Cache było włączone, uruchom owiniętą funkcję
        if enabled():
            return fun(*args, **kw)

        # Cache było wyłączone, włącz, uruchom owiniętą funkcję,
        # wyłącz cache.
        try:
            enable_failure = True
            enable()
            enable_failure = False
            return fun(*args, **kw)
        finally:
            if not enable_failure:
                disable()
            else:
                raise Exception("Enable failure, trace enable function, there was a bug there...")

    return _wrapped
