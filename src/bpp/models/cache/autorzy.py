from django.db import models
from django.db.models.deletion import DO_NOTHING

from django.contrib.contenttypes.models import ContentType

from django.utils.functional import cached_property

from bpp.models.fields import TupleField


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
    oswiadczenie_ken = models.BooleanField()
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
