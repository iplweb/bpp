# -*- encoding: utf-8 -*-

AUTOR_IMPORT_COLUMNS = {
    u"Tytuł/Stopień": "tytul_skrot",
    u"Nazwisko": "nazwisko",
    u"Imię": "imie",
    u"Nazwa jednostki": "nazwa_jednostki",
    u"PBN ID": "pbn_id"
}


AUTOR_BEZ_PBN_IMPORT_COLUMNS = {
    u"Tytuł/Stopień": "tytul_skrot",
    u"NAZWISKO": "nazwisko",
    u"IMIĘ": "imie",
    u"NAZWA JEDNOSTKI": "nazwa_jednostki",
}

def int_or_None(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


class MetkaRekorduIntegracji(models.Model):
    zanalizowano = models.BooleanField(default=False)
    moze_byc_zintegrowany_automatycznie = models.BooleanField(default=False)
    zintegrowano = models.BooleanField(default=False)
    extra_info = models.TextField()

    class Meta:
        abstract = True


class ZrodloIntegrationRecord(MetkaRekorduIntegracji, models.Model):
    parent = models.ForeignKey(IntegrationFile)

    title = models.TextField()
    www = models.TextField()
    publisher = models.TextField()
    issn = models.TextField()
    e_issn = models.TextField()
    license = models.TextField()

    matching_zrodlo = models.ForeignKey(Zrodlo, null=True)

    def sprobuj_znalezc_zrodlo(self):
        res = Zrodlo.objects.extra(
            where=["(nazwa ILIKE %s OR nazwa_alternatywna ILIKE %s)"],
            params=[self.title, self.title])

        if res.count() == 1:
            return res[0]

        if self.issn:
            res = Zrodlo.objects.filter(issn=self.issn)
            if res.count() == 1:
                return res[0]

        if self.e_issn:
            res = Zrodlo.objects.filter(e_issn=self.e_issn)
            if res.count() == 1:
                return res[0]



class AutorIntegrationRecord(MetkaRekorduIntegracji, models.Model):
    parent = models.ForeignKey(IntegrationFile)

    tytul_skrot = models.TextField()
    nazwisko = models.TextField()
    imie = models.TextField()
    nazwa_jednostki = models.TextField()
    pbn_id = models.TextField()

    matching_autor = models.ForeignKey(Autor, null=True)
    matching_jednostka = models.ForeignKey(Jednostka, null=True)

    def sprobuj_zlokalizowac_autora(self):
        strategia_1 = lambda self: Autor.objects.filter(nazwisko=self.nazwisko, imiona=self.imie)
        strategia_2 = lambda self: Autor.objects.filter(nazwisko__icontains=self.nazwisko, imiona__icontains=self.imie)
        strategia_3 = lambda self: Autor.objects.filter(
            pk=int_or_None("".join(self.nazwisko.split(",")[1:2]).strip()))
        strategia_4 = lambda self: Autor.objects.filter(
            poprzednie_nazwiska__icontains=self.nazwisko, imiona__icontains=self.imie)

        for strategia in [strategia_1, strategia_2, strategia_3, strategia_4]:
            ret = strategia(self)

            if ret.count() == 0:
                continue

            if ret.count() == 1:
                self.matching_autor = list(ret)[0]
                self.save()
                return True

            # Jest wiecej, niz jeden pasujacy autor, sprawdz wobec tego po jednostce
            for autor in ret:
                # Poszukaj ciągu self.nazwa_jednostki w jednostkach danego autora
                ret_jed = autor.jednostki.filter(nazwa=self.nazwa_jednostki)
                if ret_jed.count() == 1:
                    self.matching_autor = autor
                    self.matching_jednostka = list(ret_jed)[0]
                    self.save()
                    return True

    def sprobuj_zlokalizowac_jednostke(self):
        # Zakładamy, że wcześniej uruchomiono self.sprobuj_zlokalizowac_autora oraz, ze
        # self.matchin_autor jest nie-pusty.

        # UWAGA: autor moze byc nie-przypisany do tej jednostki

        strategia_1 = Jednostka.objects.filter(nazwa__icontains=self.nazwa_jednostki.strip())[:3]
        strategia_2 = Jednostka.objects.filter(nazwa=self.nazwa_jednostki.strip())[:3]
        strategia_3 = Jednostka.objects.filter(nazwa=self.nazwa_jednostki)[:3]
        strategia_4 = Jednostka.objects.filter(slug=slugify_function(self.nazwa_jednostki)[:50])[:3]
        strategia_5 = Jednostka.objects.filter(nazwa=unicode("%r" % self.nazwa_jednostki))[:3]
        strategia_6 = Jednostka.objects.filter(slug=slugify_function(unicode("%r" % self.nazwa_jednostki))[:50])[:3]
        strategia_7 = Jednostka.objects.filter(nazwa__icontains=self.nazwa_jednostki.strip().replace("  ", " ").replace("  ", " ").strip())[:3]

        log = [u"Ciąg: |%s|" % self.nazwa_jednostki]

        for no, strategia in enumerate([strategia_1, strategia_2, strategia_3, strategia_4, strategia_5, strategia_6, strategia_7]):
            res = list(strategia)
            log.append(u"%s: %s" % (no, len(strategia)))

            if len(strategia) == 1:
                self.matching_jednostka = strategia[0]
                self.save()
                return True

        return u", ".join(log)


class ListaMinisterialnaIntegrationRecord(MetkaRekorduIntegracji, models.Model):
    parent = models.ForeignKey(IntegrationFile)

    nazwa = models.TextField()
    issn = models.TextField()
    e_issn = models.TextField()

    matching_zrodlo = models.ForeignKey(Zrodlo, null=True)

    def sprobuj_zlokalizowac_zrodlo(self):
        raise NotImplementedError

        # 1) lokalizuj zrodlo po e-issn, potem issn, potem nazwie
        # 2) dodatkowy widok, dodatkowy formularz dodawania pliku dla list ministerialnych
        # 3) klasa importer,

        # if self.e_issn:
        #     Zrodlo.objects.get
