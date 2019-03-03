# -*- encoding: utf-8 -*-

import os

from django.conf import settings
from django.db import models
from django.db.models import CASCADE

from bpp.models.profile import BppUser

STATUSY = [
    (0, "dodany"),
    (1, "w trakcie analizy"),
    (2, "przetworzony"),
    (3, "przetworzony z błędami")
]


class BaseIntegration(models.Model):
    """
    Import danch z zewnętrznych plików wejściowych w trybie wsadowym odbywa się w 3 etapach:

    1) otwarcie pliku wejściowego i wprowadzenie danych z pliku wejściowego do bazy
        - procedura input_file_to_dict_stream oraz dict_stream_to_db
        - na tym etapie dane są walidowane pod kątem kompletności (czy np wszystkie pola wypełnione),

    2) zmatchowanie rekordów w bazie danych
        - rekordy wprowadzone do bazy danych w punkcie 1 są uzupełniane o informacje z systemu,
        - najczęściej polega to na dopasowaniu ID rekordu w systemie z danymi z rekordu wprowadzonego

    3) zintegrowanie danch do bazy danych
        - procedura integrate_data

    Import powinien też odbywać się w trybie interaktywnym, wówczas użytkownik może np. zobaczyć
    na WWW listę rekordów np. po przejściu punktu 2 - tylko rekordy które "nie weszły", poprawić je ręcznie
    i wywołać ponownie punkt 3. Ta funkcjonalność obecnie jest jedynie planowana, ale kod importera
    powinien umożliwiać tego typu zachowanie.

    """

    name = models.CharField("Nazwa pliku", max_length=255)

    file = models.FileField(verbose_name="Plik", upload_to="integrator2")
    owner = models.ForeignKey(BppUser, CASCADE)

    uploaded_on = models.DateTimeField(auto_now_add=True)
    last_updated_on = models.DateTimeField(auto_now=True)

    status = models.IntegerField(choices=STATUSY, default=STATUSY[0][0])
    extra_info = models.TextField()  # ekstra informacje dla statusu

    klass = None  # zobacz self.records()

    class Meta:
        verbose_name = "Plik integracji danych"
        ordering = ['-last_updated_on']
        abstract = True

    def model_name(self):
        """Na potrzeby tworzenia linku URL w template."""
        return self._meta.model_name

    def verbose_name(self):
        """Na potrzeby pokazania ładnej nazwy w template."""
        return self._meta.verbose_name

    def filename(self):
        "Zwróć ładną nazwę pliku - na potrzeby GUI"
        return os.path.basename(self.file.name)

    def records(self):
        "Zwraca rekordy podrzędne dla tej integracji. Zaimplementuj w klasach dziedziczących. "
        return self.klass.objects.filter(parent=self)

    def integrated(self):
        return self.records().filter(zintegrowano=True)

    def not_integrated(self):
        return self.records().exclude(zintegrowano=True).order_by('extra_info')

    def input_file_to_dict_stream(self):
        """Otwiera plik wejściowy, wyszukuje nagłówek, a następnie zaczyna
        zwracać kolejne rekordy w formie słowników. """
        raise NotImplementedError

    def dict_stream_to_db(self, dict_stream):
        """Przyjmuje jako parametr wejściowy strumień słowników, a następnie
        dodaje je do bazy dancyh."""
        raise NotImplementedError

    def match_single_record(self, elem):
        """Matchuj jeden rekord. Zobacz komentarz do :function:`integrator2.models.base.BaseIntegration.match_records`."""
        raise NotImplementedError

    def match_records(self):
        """Dopasowuje zaimportowane rekordy do informacji zawartej w bazie danych. Najczęściej
        polega to na uzupełnieniu ID powiązanego rekordu w systemie, dopasowanego do zaimportowanych
        informacji."""
        for elem in self.records():
            self.match_single_record(elem)
            elem.zanalizowano = True
            elem.save()

    def integrate(self):
        """Integruje wszystkie dane."""
        for elem in self.records().filter(
                zanalizowano=True,
                moze_byc_zintegrowany_automatycznie=True,
                zintegrowano=False):
            self.integrate_single_record(elem)
            elem.zintegrowano = True
            elem.save()


class BaseIntegrationElement(models.Model):
    """Pojedynczy element zbioru integrowanych danych.

    Po dodaniu do bazy danych, domyślnie model nie jest zanalizowany, nie jest zintegrowany,
    a jego status jest nieokreślony.

    zanalizowany - system przyjrzał się na ten element,

    może byc zintegrowany automatycznie - wszystko OK, można wkładać dane z tego elementu do systemu,

    zintegrowano - dane z tego elementu zostały dodane.
    """

    zanalizowano = models.BooleanField(default=False)
    moze_byc_zintegrowany_automatycznie = models.NullBooleanField(default=None)
    extra_info = models.TextField()

    zintegrowano = models.BooleanField(default=False)

    # parent!

    class Meta:
        abstract = True

# INTEGRATOR_DOI = 0
# INTEGRATOR_ATOZ = 1
# INTEGRATOR_AUTOR = 2
# INTEGRATOR_AUTOR_BEZ_PBN = 3
# INTEGRATOR_LISTA_MINISTERIALNA = 4
#
# RODZAJE = [
#     (INTEGRATOR_DOI, "lista DOI"),
#     (INTEGRATOR_ATOZ, "lista AtoZ"),
#     (INTEGRATOR_AUTOR, "integracja autorów"),
#     (INTEGRATOR_AUTOR_BEZ_PBN, "integracja autorów bez PBN ID"),
#     (INTEGRATOR_LISTA_MINISTERIALNA, "import punktów z list ministerialnych")
# ]
