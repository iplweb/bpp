# Cache'ujemy:
# - Wydawnictwo_Zwarte
# - Wydawnictwo_Ciagle
# - Patent
# - Praca_Doktorska
# - Praca_Habilitacyjna

import denorm
from django.db import connections, models, router
from django.db.models import CASCADE, ForeignKey
from django.db.models.deletion import DO_NOTHING
from django.urls import reverse
from taggit.managers import TaggableManager, _TaggableManager
from taggit.models import Tag

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
    Typ_Odpowiedzialnosci,
    Wydawnictwo_Zwarte,
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
from bpp.models.util import ModelZOpisemBibliograficznym
from bpp.util import FulltextSearchMixin


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
    kierunek_studiow = models.ForeignKey("Kierunek_Studiow", DO_NOTHING)

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
    kierunek_studiow = models.ForeignKey("Kierunek_Studiow", DO_NOTHING)

    @cached_property
    def wydawnictwo_autor_class(self):
        return (
            ContentType.objects.get(pk=self.id[0])
            .model_class()
            .autorzy_set.rel.related_model
        )

    @cached_property
    def original(self):
        return self.wydawnictwo_autor_class.objects.get(pk=self.id[1])

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

    def prace_jednostki(self, jednostka, afiliowane=None):
        if afiliowane is None:
            return self.filter(
                autorzy__jednostka__pk__in=list(
                    jednostka.get_descendants(include_self=True).values_list(
                        "pk", flat=True
                    )
                )
            ).distinct()

        return self.filter(
            autorzy__jednostka__pk__in=list(
                jednostka.get_descendants(include_self=True).values_list(
                    "pk", flat=True
                )
            ),
            autorzy__afiliuje=afiliowane,
        ).distinct()

    def prace_wydzialu(self, wydzial, afiliowane=None):
        if afiliowane is None:
            return self.filter(autorzy__jednostka__wydzial=wydzial).distinct()

        return self.filter(
            autorzy__jednostka__wydzial=wydzial, autorzy__afiliuje=afiliowane
        ).distinct()

    def redaktorzy_z_jednostki(self, jednostka):
        return self.filter(
            autorzy__jednostka=jednostka,
            autorzy__typ_odpowiedzialnosci_id=Typ_Odpowiedzialnosci.objects.get(
                skrot="red."
            ).pk,
        ).distinct()

    def get_original(self, model):
        return self.get(pk=[ContentType.objects.get_for_model(model).pk, model.pk])

    def full_refresh(self):
        """Procedura odswieza opisy bibliograficzne dla wszystkich rekordów."""
        denorm.rebuildall("bpp.Wydawnictwo_Zwarte")
        denorm.rebuildall("bpp.Wydawnictwo_Ciagle")
        denorm.rebuildall("bpp.Patent")
        denorm.rebuildall("bpp.Praca_Doktorska")
        denorm.rebuildall("bpp.Praca_Habilitacyjna")


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

    opis_bibliograficzny_cache = models.TextField()
    opis_bibliograficzny_autorzy_cache = ArrayField(models.TextField())
    opis_bibliograficzny_zapisani_autorzy_cache = models.TextField()
    slug = models.TextField()

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
    def form_post_pk(self):
        return "{%i,%i}" % (self.pk[0], self.pk[1])

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
    def ma_odpiete_dyscypliny(self):
        return (
            self.original.autorzy_set.exclude(dyscyplina_naukowa=None)
            .exclude(przypieta=True)
            .exists()
        )

    @cached_property
    def punktacja_dyscypliny(self):
        return Cache_Punktacja_Dyscypliny.objects.filter(
            rekord_id=[self.id[0], self.id[1]]
        )

    @cached_property
    def punktacja_autora(self):
        return Cache_Punktacja_Autora.objects.filter(rekord_id=[self.id[0], self.id[1]])

    @cached_property
    def pierwszy_autor_afiliowany(self):
        """Zwraca pierwszego autora, afiliującego na jednostkę uczelni z tej pracy"""
        return self.autorzy.filter(afiliuje=True).order_by("kolejnosc").first()

    @cached_property
    def pierwsza_jednostka_afiliowana(self):
        """Zwraca pierwszego autora, afiliującego na jednostkę uczelni z tej pracy"""
        res = self.pierwszy_autor_afiliowany()
        if res is not None:
            return self.pierwszy_autor_afiliowany().jednostka

    def get_absolute_url(self):
        return reverse("bpp:browse_rekord", args=(self.pk[0], self.pk[1]))


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

    def serialize(self):
        return [self.rekord_id, self.dyscyplina_id, str(self.pkd), str(self.slot)]


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

    def serialize(self):
        return [
            self.rekord_id,
            self.autor_id,
            self.jednostka_id,
            self.dyscyplina_id,
            str(self.pkdaut),
            str(self.slot),
        ]


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
