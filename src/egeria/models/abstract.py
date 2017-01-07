# -*- encoding: utf-8 -*-


from django.db import models

class Diff_Base(models.Model):
    parent = models.ForeignKey('EgeriaImport')

    # opcjonalny odnośnik do wiersza, gdzie znajdują się informacje
    row = models.ForeignKey('EgeriaRow', blank=True, null=True)

    def commit(self):
        self.delete()

    class Meta:
        abstract = True


class Diff_Create(Diff_Base):
    nazwa_skrot = models.CharField(max_length=512)

    def __unicode__(self):
        return self.nazwa_skrot

    def commit(self):
        self.klass.objects.create(nazwa=self.nazwa_skrot, skrot=self.nazwa_skrot)
        super(Diff_Create, self).commit()

    class Meta:
        abstract = True


class Diff_Delete(Diff_Base):
    # reference = models.ForeignKey(base_klass)

    def __unicode__(self):
        return self.reference.nazwa

    def commit(self):
        self.reference.delete()
        self.delete()

    @classmethod
    def check_if_needed(cls, parent, reference):
        """
        Ta metoda sprawdza, czy potrzebne jest tworzenie tego rodzaju obiektu,
        odpowiada na pytanie "Czy potrzebne jest skasowanie obiektu do którego
        odnosi się 'reference'".

        powinna być wywoływana przed jego utworzeniem w oprogramowaniu importującym
        na etapie tworzenia diff'a.

        Przykładowo, możemy chcieć "skasować" wydział, który już jest oznaczony
        jako niewidoczny. W takiej sytuacji, tworzenie tego obiektu będzie zbędne.

        :return:
        """
        raise NotImplementedError

    class Meta:
        abstract = True

