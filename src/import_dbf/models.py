from django.db import models
from django.db.models import DO_NOTHING


class Bib(models.Model):
    idt = models.TextField(primary_key=True)
    tytul_or = models.TextField(blank=True, null=True)
    title = models.TextField(blank=True, null=True)
    zrodlo = models.TextField(blank=True, null=True)
    szczegoly = models.TextField(blank=True, null=True)
    uwagi = models.TextField(blank=True, null=True)
    charakter = models.TextField(blank=True, null=True)
    impact = models.TextField(blank=True, null=True)
    redakcja = models.TextField(blank=True, null=True)
    status = models.TextField(blank=True, null=True)
    rok = models.TextField(blank=True, null=True)
    sort = models.TextField(blank=True, null=True)
    sort2 = models.TextField(blank=True, null=True)
    export = models.TextField(blank=True, null=True)
    import_field = models.TextField(db_column='import', blank=True,
                                    null=True)  # Field renamed because it was a Python reserved word.
    naz_imie = models.TextField(blank=True, null=True)
    redaktor = models.TextField(blank=True, null=True)
    redaktor0 = models.TextField(blank=True, null=True)
    tytul_or_s = models.TextField(blank=True, null=True)
    title_s = models.TextField(blank=True, null=True)
    zrodlo_s = models.TextField(blank=True, null=True)
    szczegol_s = models.TextField(blank=True, null=True)
    mem_fi_ext = models.TextField(blank=True, null=True)
    dat_akt = models.TextField(blank=True, null=True)
    kbn = models.TextField(blank=True, null=True)
    kbr = models.TextField(blank=True, null=True)
    afiliowana = models.TextField(blank=True, null=True)
    recenzowan = models.TextField(blank=True, null=True)
    jezyk = models.TextField(blank=True, null=True)
    jezyk2 = models.TextField(blank=True, null=True)
    punkty_kbn = models.TextField(db_column='pk', blank=True, null=True)
    x_skrot = models.TextField(blank=True, null=True)
    wspx = models.TextField(blank=True, null=True)
    x2_skrot = models.TextField(blank=True, null=True)
    wspx2 = models.TextField(blank=True, null=True)
    y_skrot = models.TextField(blank=True, null=True)
    wspy = models.TextField(blank=True, null=True)
    wspq = models.TextField(blank=True, null=True)
    ic = models.TextField(blank=True, null=True)
    rok_inv = models.TextField(blank=True, null=True)
    link = models.TextField(blank=True, null=True)
    lf = models.TextField(blank=True, null=True)
    rok_punkt = models.TextField(blank=True, null=True)
    form = models.TextField(blank=True, null=True)
    k_z = models.TextField(blank=True, null=True)
    uwagi2 = models.TextField(blank=True, null=True)
    dat_utw = models.TextField(blank=True, null=True)
    pun_wl = models.TextField(blank=True, null=True)
    study_gr = models.TextField(blank=True, null=True)
    sort_fixed = models.TextField(blank=True, null=True)
    zaznacz_field = models.TextField(db_column='zaznacz_', blank=True,
                                     null=True)  # Field renamed because it ended with '_'.
    idt2 = models.TextField(blank=True, null=True)
    pun_max = models.TextField(blank=True, null=True)
    pun_erih = models.TextField(blank=True, null=True)
    kwartyl = models.TextField(blank=True, null=True)
    issn = models.TextField(blank=True, null=True)
    eissn = models.TextField(blank=True, null=True)
    wok_id = models.TextField(blank=True, null=True)
    sco_id = models.TextField(blank=True, null=True)
    mnsw_fixed = models.TextField(blank=True, null=True)
    liczba_aut = models.TextField(blank=True, null=True)
    pro_p_wydz = models.TextField(blank=True, null=True)
    snip = models.TextField(blank=True, null=True)
    sjr = models.TextField(blank=True, null=True)
    cites = models.TextField(blank=True, null=True)
    if5 = models.TextField(blank=True, null=True)
    lis_numer = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'bib'


class Aut(models.Model):
    idt_aut = models.TextField(primary_key=True)
    imiona = models.TextField(blank=True, null=True)
    nazwisko = models.TextField(blank=True, null=True)
    ref = models.TextField(blank=True, null=True)
    idt_jed = models.TextField(blank=True, null=True)
    kad_nr = models.TextField(blank=True, null=True)
    tel = models.TextField(blank=True, null=True)
    email = models.TextField(blank=True, null=True)
    www = models.TextField(blank=True, null=True)
    imiona_bz = models.TextField(blank=True, null=True)
    nazwisk_bz = models.TextField(blank=True, null=True)
    tytul = models.TextField(blank=True, null=True)
    stanowisko = models.TextField(blank=True, null=True)
    prac_od = models.TextField(blank=True, null=True)
    dat_zwol = models.TextField(blank=True, null=True)
    fg = models.TextField(blank=True, null=True)
    dop = models.TextField(blank=True, null=True)
    nr_ewid = models.TextField(blank=True, null=True)
    kad_s_jed = models.TextField(blank=True, null=True)
    pbn_id = models.TextField(blank=True, null=True)
    res_id = models.TextField(blank=True, null=True)
    scop_id = models.TextField(blank=True, null=True)
    orcid_id = models.TextField(blank=True, null=True)
    exp_id = models.TextField(blank=True, null=True)
    polon_id = models.TextField(blank=True, null=True)
    usos_id = models.TextField(blank=True, null=True)
    udf_id = models.TextField(blank=True, null=True)
    control = models.TextField(blank=True, null=True)
    uwagi = models.TextField(blank=True, null=True)
    graf = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'aut'


class Jed(models.Model):
    idt_jed = models.TextField(primary_key=True)
    nr = models.TextField(blank=True, null=True)
    skrot = models.TextField(blank=True, null=True)
    nazwa = models.TextField(blank=True, null=True)
    wyd_skrot = models.TextField(blank=True, null=True)
    sort = models.TextField(blank=True, null=True)
    to_print = models.TextField(blank=True, null=True)
    to_print2 = models.TextField(blank=True, null=True)
    to_print3 = models.TextField(blank=True, null=True)
    to_print4 = models.TextField(blank=True, null=True)
    to_print5 = models.TextField(blank=True, null=True)
    email = models.TextField(blank=True, null=True)
    www = models.TextField(blank=True, null=True)
    id_u = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'jed'


class B_A(models.Model):
    id = models.IntegerField(primary_key=True)
    idt = models.ForeignKey("import_dbf.Bib", db_column="idt", on_delete=DO_NOTHING)
    lp = models.TextField(blank=True, null=True)
    idt_aut = models.ForeignKey("import_dbf.Aut", db_column="idt_aut", on_delete=DO_NOTHING)
    idt_jed = models.ForeignKey("import_dbf.Jed", db_column="idt_jed", on_delete=DO_NOTHING)
    wspz = models.TextField(blank=True, null=True)
    pkt_dod = models.TextField(blank=True, null=True)
    wspz2 = models.TextField(blank=True, null=True)
    pkt2_dod = models.TextField(blank=True, null=True)
    afiliacja = models.TextField(blank=True, null=True)
    odp = models.TextField(blank=True, null=True)
    study_ga = models.TextField(blank=True, null=True)
    tytul = models.TextField(blank=True, null=True)
    stanowisko = models.TextField(blank=True, null=True)
    uwagi = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'b_a'


class Poz(models.Model):
    idt = models.TextField(blank=True, null=True)
    kod_opisu = models.TextField(blank=True, null=True)
    lp = models.TextField(blank=True, null=True)
    tresc = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'poz'


class BU(models.Model):
    idt = models.TextField(blank=True, null=True)
    idt_usi = models.TextField(blank=True, null=True)
    comm = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'b_u'


class Usi(models.Model):
    idt_usi = models.TextField(blank=True, null=True)
    usm_f = models.TextField(blank=True, null=True)
    usm_sf = models.TextField(blank=True, null=True)
    skrot = models.TextField(blank=True, null=True)
    nazwa = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'usi'


class Ses(models.Model):
    redaktor = models.TextField(blank=True, null=True)
    file = models.TextField(blank=True, null=True)
    login_t = models.TextField(blank=True, null=True)
    logout_t = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'ses'
