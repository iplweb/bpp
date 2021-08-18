# -*- encoding: utf-8 -*-

# Cache'ujemy:
# - Wydawnictwo_Zwarte
# - Wydawnictwo_Ciagle
# - Patent
# - Praca_Doktorska
# - Praca_Habilitacyjna
from contextlib import contextmanager

from django.core.exceptions import ObjectDoesNotExist
from django.db import connections, models, router, transaction
from django.db.models import CASCADE, ForeignKey, Func
from django.db.models.deletion import DO_NOTHING
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from taggit.managers import TaggableManager, _TaggableManager
from taggit.models import Tag

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields.array import ArrayField
from django.contrib.postgres.search import SearchVectorField as VectorField

from django.utils.functional import cached_property

from bpp.models import (
    Autor,
    Dyscyplina_Naukowa,
    Jednostka,
    ModelZDOI,
    ModelZeStatusem,
    ModelZISBN,
    ModelZPBN_UID,
    Patent,
    Patent_Autor,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Typ_Odpowiedzialnosci,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
    Zrodlo,
)
from bpp.models.abstract import (
    ModelPunktowanyBaza,
    ModelRecenzowany,
    ModelTypowany,
    ModelZCharakterem,
    ModelZeSzczegolami,
    ModelZeZnakamiWydawniczymi,
    ModelZKonferencja,
    ModelZOpenAccess,
    ModelZRokiem,
    ModelZWWW,
)
from bpp.models.system import Charakter_Formalny, Jezyk
from bpp.models.util import ModelZOpisemBibliograficznym
from bpp.util import FulltextSearchMixin

# zmiana CACHED_MODELS powoduje zmiane opisu bibliograficznego wszystkich rekordow
CACHED_MODELS = [
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Patent,
]

# zmiana DEPENDEND_REKORD_MODELS powoduje zmiane opisu bibliograficznego rekordu z pola z ich .rekord
DEPENDENT_REKORD_MODELS = [
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
    Patent_Autor,
]

# Other dependent -- czyli skasowanie tych obiektów pociąga za sobą odbudowanie tabeli cache
OTHER_DEPENDENT_MODELS = [Typ_Odpowiedzialnosci, Jezyk, Charakter_Formalny, Zrodlo]


def defer_zaktualizuj_opis(instance, *args, **kw):
    """Obiekt typu Wydawnictwo_..., Patent, Praca_... został zapisany.
    Zaktualizuj jego opis bibliograficzny."""
    flds = kw.get("update_fields", [])

    if flds:
        flds = list(flds)
        for elem in [
            "opis_bibliograficzny_cache",
            "opis_bibliograficzny_autorzy_cache",
            "opis_bibliograficzny_zapisani_autorzy_cache",
        ]:
            try:
                flds.remove(elem)
            except ValueError:
                pass

        if not flds:
            # uniknij loopa w przypadku zapisywania obiektu z metody
            # models.util.ModelZOpisemBibliograficznym.zaktualizuj_opis
            return

    # transaction.on_commit(
    #     lambda: zaktualizuj_opis.delay(
    #         app_label=instance._meta.app_label,
    #         model_name=instance._meta.model_name,
    #         pk=instance.pk))

    CacheQueue.objects.add(instance)
    # transaction.on_commit(
    #    lambda instance=instance:
    #


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
        instance._BPP_CHANGED_FIELDS = [
            "skrot",
        ]


def zrodlo_post_save(instance, *args, **kw):
    """Źródło zostało zapisane (post_save)"""

    changed = getattr(instance, "_BPP_CHANGED_FIELDS", [])
    if not changed:
        changed = kw.get("update_fields") or []

    if "skrot" in changed:
        from bpp.tasks import zaktualizuj_zrodlo

        zaktualizuj_zrodlo.delay(instance.pk)


def zrodlo_pre_delete(instance, *args, **kw):
    # TODO: moze byc memory-consuming, lepiej byloby to wrzucic do bazy danych - moze?
    instance._PRACE = list(
        Rekord.objects.filter(zrodlo__id=instance.pk).values_list("id", flat=True)
    )


def zrodlo_post_delete(instance, *args, **kw):
    for pk in instance._PRACE:
        try:
            rekord = Rekord.objects.get(pk=pk)
        except Rekord.DoesNotExist:
            continue
        defer_zaktualizuj_opis(rekord.original)


_CACHE_ENABLED = False


class AlreadyEnabledException(Exception):
    pass


class AlreadyDisabledException(Exception):
    pass


def enable():
    global _CACHE_ENABLED

    if _CACHE_ENABLED:
        raise AlreadyEnabledException()

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


@contextmanager
def cache_enabled():
    if not enabled():
        enable()
    try:
        yield
    finally:
        disable()


class TupleField(ArrayField):
    def from_db_value(self, value, expression, connection):
        return tuple(value)


class AutorzyManager(models.Manager):
    def filter_rekord(self, rekord):
        return self.filter(rekord_id=rekord.pk)


class AutorzyBase(models.Model):
    id = TupleField(models.IntegerField(), size=2, primary_key=True)

    autor = models.ForeignKey("Autor", DO_NOTHING)
    jednostka = models.ForeignKey("Jednostka", DO_NOTHING)
    kolejnosc = models.IntegerField()
    typ_odpowiedzialnosci = models.ForeignKey("Typ_Odpowiedzialnosci", DO_NOTHING)
    zapisany_jako = models.TextField()
    dyscyplina_naukowa = models.ForeignKey("Dyscyplina_Naukowa", DO_NOTHING)

    afiliuje = models.BooleanField()
    zatrudniony = models.BooleanField()
    upowaznienie_pbn = models.BooleanField()
    profil_orcid = models.BooleanField()

    objects = AutorzyManager()

    class Meta:
        abstract = True


class Autorzy(AutorzyBase):
    rekord = models.ForeignKey(
        "bpp.Rekord",
        related_name="autorzy",
        # tak na prawdę w bazie danych jest constraint dla ON_DELETE, ale
        # dajemy to tutaj, żeby django się nie awanturowało i nie próbowało
        # tego ręcznie kasować
        on_delete=DO_NOTHING,
    )

    # To poniżej musi być, bo się django-admin.py sqlflush nie uda
    typ_odpowiedzialnosci = models.ForeignKey("Typ_Odpowiedzialnosci", DO_NOTHING)
    autor = models.ForeignKey("Autor", DO_NOTHING)
    dyscyplina_naukowa = models.ForeignKey("Dyscyplina_Naukowa", DO_NOTHING)

    class Meta:
        managed = False
        db_table = "bpp_autorzy_mat"


class AutorzyView(AutorzyBase):
    rekord = models.ForeignKey(
        "bpp.RekordView",
        related_name="autorzy",
        # tak na prawdę w bazie danych jest constraint dla ON_DELETE, ale
        # dajemy to tutaj, żeby django się nie awanturowało i nie próbowało
        # tego ręcznie kasować
        on_delete=DO_NOTHING,
    )

    class Meta:
        managed = False
        db_table = "bpp_autorzy"


class SlowaKluczoweView(models.Model):
    id = ArrayField(base_field=models.IntegerField(), size=3, primary_key=True)

    rekord = models.ForeignKey(
        "bpp.Rekord", related_name="slowa_kluczowe_set", on_delete=DO_NOTHING
    )
    tag = models.ForeignKey(Tag, on_delete=DO_NOTHING)

    @classmethod
    def tag_relname(cls):
        field = cls._meta.get_field("tag")
        return field.remote_field.related_name

    @classmethod
    def tags_for(cls, model, instance=None, **kwargs):
        if model != Rekord:
            raise NotImplementedError
        if instance is not None:
            return cls.objects.filter(rekord_id=(instance.pk,))
        return cls.objects.all()

    class Meta:
        managed = False
        db_table = "bpp_slowa_kluczowe_view"


class ZewnetrzneBazyDanychView(models.Model):
    rekord = models.ForeignKey(
        "bpp.Rekord", related_name="zewnetrzne_bazy", on_delete=DO_NOTHING
    )

    baza = models.ForeignKey("bpp.Zewnetrzna_Baza_Danych", on_delete=DO_NOTHING)

    info = models.TextField()

    class Meta:
        managed = False
        db_table = "bpp_zewnetrzne_bazy_view"


class RekordManager(FulltextSearchMixin, models.Manager):
    fts_field = "search_index"

    def get_for_model(self, model):
        pk = (ContentType.objects.get_for_model(model).pk, model.pk)
        return self.get(pk=pk)

    def prace_autora(self, autor):
        return self.filter(autorzy__autor=autor).distinct()

    def prace_autora_z_afiliowanych_jednostek(self, autor):
        """
        Funkcja zwraca prace danego autora, należące tylko i wyłącznie
        do jednostek skupiających pracowników, gdzie autor jest zaznaczony jako
        afiliowany.
        """
        return (
            self.prace_autora(autor)
            .filter(
                autorzy__autor=autor,
                autorzy__jednostka__skupia_pracownikow=True,
                autorzy__afiliuje=True,
            )
            .distinct()
        )

    def prace_autor_i_typ(self, autor, skrot):
        return (
            self.prace_autora(autor)
            .filter(
                autorzy__typ_odpowiedzialnosci_id=Typ_Odpowiedzialnosci.objects.get(
                    skrot=skrot
                ).pk
            )
            .distinct()
        )

    def prace_jednostki(self, jednostka):
        return self.filter(
            autorzy__jednostka__pk__in=list(
                jednostka.get_descendants(include_self=True).values_list(
                    "pk", flat=True
                )
            )
        ).distinct()

    def prace_wydzialu(self, wydzial):
        return self.filter(autorzy__jednostka__wydzial=wydzial).distinct()

    def redaktorzy_z_jednostki(self, jednostka):
        return self.filter(
            autorzy__jednostka=jednostka,
            autorzy__typ_odpowiedzialnosci_id=Typ_Odpowiedzialnosci.objects.get(
                skrot="red."
            ).pk,
        ).distinct()

    def get_original(self, model):
        return self.get(pk=[ContentType.objects.get_for_model(model).pk, model.pk])

    @transaction.atomic
    def full_refresh(self):
        """Procedura odswieza opisy bibliograficzne dla wszystkich rekordów."""

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


class _MyTaggableManager(_TaggableManager):
    def get_prefetch_queryset(self, instances, queryset=None):
        if queryset is not None:
            raise ValueError("Custom queryset can't be used for this lookup.")

        instance = instances[0]
        db = self._db or router.db_for_read(type(instance), instance=instance)

        fieldname = "rekord_id"
        fk = self.through._meta.get_field(fieldname)
        query = {
            "%s__%s__in"
            % (self.through.tag_relname(), fk.name): {
                obj._get_pk_val() for obj in instances
            }
        }
        join_table = self.through._meta.db_table
        source_col = fk.column
        connection = connections[db]
        qn = connection.ops.quote_name
        qs = (
            self.get_queryset(query)
            .using(db)
            .extra(
                select={
                    "_prefetch_related_val": "{}.{}".format(
                        qn(join_table), qn(source_col)
                    )
                }
            )
        )
        from operator import attrgetter

        rel_obj_attr = attrgetter("_prefetch_related_val")

        return (
            qs,
            rel_obj_attr,
            lambda obj: obj._get_pk_val(),
            False,
            self.prefetch_cache_name,
            False,
        )


class RekordBase(
    ModelPunktowanyBaza,
    ModelZOpisemBibliograficznym,
    ModelZRokiem,
    ModelZWWW,
    ModelZDOI,
    ModelZPBN_UID,
    ModelZeSzczegolami,
    ModelRecenzowany,
    ModelZeZnakamiWydawniczymi,
    ModelZOpenAccess,
    ModelTypowany,
    ModelZCharakterem,
    ModelZKonferencja,
    ModelZISBN,
    ModelZeStatusem,
    models.Model,
):
    id = TupleField(models.IntegerField(), size=2, primary_key=True)

    tekst_przed_pierwszym_autorem = None
    tekst_po_ostatnim_autorze = None

    tytul_oryginalny = models.TextField()
    tytul = models.TextField()
    search_index = VectorField()

    zrodlo = models.ForeignKey(Zrodlo, null=True, on_delete=DO_NOTHING)
    wydawnictwo_nadrzedne = models.ForeignKey(
        Wydawnictwo_Zwarte, null=True, on_delete=DO_NOTHING
    )
    slowa_kluczowe = TaggableManager(
        "Słowa kluczowe",
        through=SlowaKluczoweView,
        blank=True,
        manager=_MyTaggableManager,
    )

    wydawnictwo = models.TextField()

    adnotacje = models.TextField()
    ostatnio_zmieniony = models.DateTimeField()

    tytul_oryginalny_sort = models.TextField()

    liczba_autorow = models.SmallIntegerField()

    liczba_cytowan = models.SmallIntegerField()

    objects = RekordManager()

    strony = None
    nr_zeszytu = None
    tom = None

    jezyk_alt = None
    jezyk_orig = None

    # Skróty dla django-dsl

    django_dsl_shortcuts = {
        "charakter": "charakter_formalny__skrot",
        "typ_kbn": "typ_kbn__skrot",
        "typ_odpowiedzialnosci": "autorzy__typ_odpowiedzialnosci__skrot",
        "autor": "autorzy__autor_id",
        "jednostka": "autorzy__jednostka__pk",
        "wydzial": "autorzy__jednostka__wydzial__pk",
    }

    class Meta:
        abstract = True

    def __str__(self):
        return self.tytul_oryginalny

    @cached_property
    def content_type(self):
        return ContentType.objects.get(pk=self.id[0])

    @cached_property
    def describe_content_type(self):
        return ContentType.objects.get(pk=self.id[0]).model_class()._meta.verbose_name

    @cached_property
    def object_id(self):
        return self.id[1]

    @cached_property
    def original(self):
        return self.content_type.get_object_for_this_type(pk=self.object_id)

    @cached_property
    def js_safe_pk(self):
        return "%i_%i" % (self.pk[0], self.pk[1])

    @cached_property
    def ma_punktacje_sloty(self):
        return (
            Cache_Punktacja_Autora.objects.filter(
                rekord_id=[self.id[0], self.id[1]]
            ).exists()
            or Cache_Punktacja_Dyscypliny.objects.filter(
                rekord_id=[self.id[0], self.id[1]]
            ).exists()
        )

    @cached_property
    def punktacja_dyscypliny(self):
        return Cache_Punktacja_Dyscypliny.objects.filter(
            rekord_id=[self.id[0], self.id[1]]
        )

    @cached_property
    def punktacja_autora(self):
        return Cache_Punktacja_Autora.objects.filter(rekord_id=[self.id[0], self.id[1]])


class Rekord(RekordBase):
    class Meta:
        managed = False
        ordering = ["tytul_oryginalny_sort"]
        db_table = "bpp_rekord_mat"

    @cached_property
    def autorzy_set(self):
        return self.autorzy


class RekordView(RekordBase):
    class Meta:
        managed = False
        db_table = "bpp_rekord"


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
                raise Exception(
                    "Enable failure, trace enable function, there was a bug there..."
                )

    return _wrapped


class CacheManager(models.Manager):
    def add(self, obj):
        from bpp.tasks import aktualizuj_cache

        obj, created = self.get_or_create(
            created_on=Func(function="NOW"),
            object_id=obj.pk,
            content_type=ContentType.objects.get_for_model(obj._meta.model),
        )
        if created:
            transaction.on_commit(lambda: aktualizuj_cache.delay())

        return obj

    def ready(self):
        return self.filter(started_on=None)


class CacheQueue(models.Model):
    # Pole created_on dostanie po stronie SQL defaultową wartość "NOW()";
    # niestety na ten moment zrobienie tego w Django nie jest trywialne, więc
    # temat zostaje załatwiony po stronie migracji przez RunSQL
    created_on = models.DateTimeField(blank=True)
    last_updated_on = models.DateTimeField(auto_now=True)

    completed_on = models.DateTimeField(null=True, blank=True)
    started_on = models.DateTimeField(null=True, blank=True)

    error = models.BooleanField(default=False)
    info = models.TextField(blank=True, null=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    rekord = GenericForeignKey("content_type", "object_id")

    objects = CacheManager()

    class Meta:
        ordering = ("-created_on",)


class Cache_Punktacja_Dyscypliny(models.Model):
    rekord_id = TupleField(models.IntegerField(), size=2, db_index=True)
    # rekord = ForeignKey('bpp.Rekord', CASCADE)
    dyscyplina = ForeignKey(Dyscyplina_Naukowa, CASCADE)
    pkd = models.DecimalField(max_digits=20, decimal_places=4)
    slot = models.DecimalField(max_digits=20, decimal_places=4)

    autorzy_z_dyscypliny = ArrayField(
        models.PositiveIntegerField(), blank=True, null=True
    )
    zapisani_autorzy_z_dyscypliny = ArrayField(
        models.TextField(), blank=True, null=True
    )

    class Meta:
        ordering = ("dyscyplina__nazwa",)


class Cache_Punktacja_Autora_Base(models.Model):
    autor = ForeignKey(Autor, CASCADE)
    jednostka = ForeignKey(Jednostka, CASCADE)
    dyscyplina = ForeignKey(Dyscyplina_Naukowa, CASCADE)
    pkdaut = models.DecimalField(max_digits=20, decimal_places=4)
    slot = models.DecimalField(max_digits=20, decimal_places=4)

    class Meta:
        ordering = ("autor__nazwisko", "dyscyplina__nazwa")
        abstract = True


class Cache_Punktacja_Autora(Cache_Punktacja_Autora_Base):
    rekord_id = TupleField(models.IntegerField(), size=2, db_index=True)

    class Meta:
        ordering = ("autor__nazwisko", "dyscyplina__nazwa")


class Cache_Punktacja_Autora_Query(Cache_Punktacja_Autora_Base):
    rekord = ForeignKey("bpp.Rekord", DO_NOTHING)

    class Meta:
        db_table = "bpp_cache_punktacja_autora"
        managed = False


class Cache_Punktacja_Autora_Query_View(models.Model):
    """W porównaniu do Cache_Punktacja_Autora, mam jeszcze listę zapisanych
    autorów z dyscypliny. A skąd? A z widoku bazodanowego, który bierze
    też pod uwagę Cache_Punktacja_Dyscypliny.
    """

    rekord = ForeignKey("bpp.Rekord", DO_NOTHING)
    autor = ForeignKey(Autor, DO_NOTHING)
    jednostka = ForeignKey(Jednostka, DO_NOTHING)
    dyscyplina = ForeignKey(Dyscyplina_Naukowa, DO_NOTHING)
    pkdaut = models.DecimalField(max_digits=20, decimal_places=4)
    slot = models.DecimalField(max_digits=20, decimal_places=4)
    zapisani_autorzy_z_dyscypliny = ArrayField(models.TextField())

    class Meta:
        ordering = ("rekord__tytul_oryginalny", "dyscyplina__nazwa")
        db_table = "bpp_cache_punktacja_autora_view"
        managed = False


class Cache_Punktacja_Autora_Sum(Cache_Punktacja_Autora_Base):
    rekord = ForeignKey("bpp.Rekord", DO_NOTHING)
    autor = ForeignKey(Autor, DO_NOTHING)
    jednostka = ForeignKey(Jednostka, DO_NOTHING)
    dyscyplina = ForeignKey(Dyscyplina_Naukowa, DO_NOTHING)
    pkdautslot = models.FloatField()
    pkdautsum = models.FloatField()
    pkdautslotsum = models.FloatField()

    class Meta:
        db_table = "bpp_temporary_cpaq"
        managed = False
        ordering = (
            "autor",
            "dyscyplina",
            "-pkdautslot",
        )


class Cache_Punktacja_Autora_Sum_Ponizej(Cache_Punktacja_Autora_Base):
    rekord = ForeignKey("bpp.Rekord", DO_NOTHING)
    autor = ForeignKey(Autor, DO_NOTHING)
    jednostka = ForeignKey(Jednostka, DO_NOTHING)
    dyscyplina = ForeignKey(Dyscyplina_Naukowa, DO_NOTHING)
    pkdautslot = models.FloatField()
    pkdautsum = models.FloatField()
    pkdautslotsum = models.FloatField()

    class Meta:
        db_table = "bpp_temporary_cpaq_2"
        managed = False
        ordering = (
            "autor",
            "dyscyplina",
            "pkdautslot",
        )


class Cache_Punktacja_Autora_Sum_Group_Ponizej(models.Model):
    autor = models.OneToOneField(Autor, DO_NOTHING, primary_key=True)
    jednostka = ForeignKey(Jednostka, DO_NOTHING)
    dyscyplina = ForeignKey(Dyscyplina_Naukowa, DO_NOTHING)
    pkdautsum = models.FloatField()
    pkdautslotsum = models.FloatField()

    class Meta:
        db_table = "bpp_temporary_cpasg_2"
        managed = False
        ordering = (
            "autor",
            "dyscyplina",
        )


class Cache_Punktacja_Autora_Sum_Gruop(models.Model):
    autor = models.OneToOneField(Autor, DO_NOTHING, primary_key=True)
    jednostka = ForeignKey(Jednostka, DO_NOTHING)
    dyscyplina = ForeignKey(Dyscyplina_Naukowa, DO_NOTHING)
    pkdautsum = models.FloatField()
    pkdautslotsum = models.FloatField()

    class Meta:
        db_table = "bpp_temporary_cpasg"
        managed = False
        ordering = (
            "autor",
            "dyscyplina",
        )


#
# Rebuilder
#


def rebuild(klass, offset=None, limit=None, extra_flds=None, extra_tables=None):
    if extra_flds is None:
        extra_flds = ()

    if extra_tables is None:
        extra_tables = ()

    ids = klass.objects.all().values_list("pk").order_by("pk")[offset:limit]

    query = (
        klass.objects.filter(pk__in=ids)
        .select_related(*extra_tables)
        .only(
            "tytul_oryginalny",
            "informacje",
            "szczegoly",
            "uwagi",
            "tekst_przed_pierwszym_autorem",
            "tekst_po_ostatnim_autorze",
            "opis_bibliograficzny_cache",
            "opis_bibliograficzny_autorzy_cache",
            "opis_bibliograficzny_zapisani_autorzy_cache",
            "slug",
            "rok",
            "punkty_kbn",
            "status_korekty_id",
            *extra_flds
        )
    )

    from bpp.tasks import aktualizuj_cache_rekordu

    for r in query:
        aktualizuj_cache_rekordu(r, uczelnia=Uczelnia.objects.default)


def rebuild_zwarte(offset=None, limit=None):
    return rebuild(
        Wydawnictwo_Zwarte,
        offset=offset,
        limit=limit,
        extra_tables=[
            "wydawca",
            "charakter_formalny",
            "typ_kbn",
        ],
        extra_flds=[
            "tytul",
            "doi",
            "miejsce_i_rok",
            "wydawca__nazwa",
            "wydawca_opis",
            "isbn",
            "typ_kbn__nazwa",
            "typ_kbn__skrot",
            "charakter_formalny__skrot",
            "charakter_formalny__charakter_sloty",
            "charakter_formalny__charakter_ogolny",
            "oznaczenie_wydania",
        ],
    )


def rebuild_ciagle(offset=None, limit=None):
    return rebuild(
        Wydawnictwo_Ciagle,
        offset=offset,
        limit=limit,
        extra_tables=[
            "zrodlo",
            "charakter_formalny",
            "typ_kbn",
        ],
        extra_flds=[
            "tytul",
            "doi",
            "zrodlo__nazwa",
            "zrodlo__skrot",
            "typ_kbn__nazwa",
            "typ_kbn__skrot",
            "charakter_formalny__skrot",
            "charakter_formalny__charakter_sloty",
            "charakter_formalny__charakter_ogolny",
        ],
    )


def rebuild_patent(offset=None, limit=None):
    return rebuild(
        Patent,
        offset=offset,
        limit=limit,
    )


def rebuild_praca_doktorska(offset=None, limit=None):
    return rebuild(
        Praca_Doktorska,
        offset=offset,
        limit=limit,
    )


def rebuild_praca_habilitacyjna(offset=None, limit=None):
    return rebuild(
        Praca_Habilitacyjna,
        offset=offset,
        limit=limit,
    )
