from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models import DO_NOTHING, CASCADE


class Bib(models.Model):
    idt = models.IntegerField(primary_key=True)
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
    import_field = models.TextField(
        db_column="import", blank=True, null=True
    )  # Field renamed because it was a Python reserved word.
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
    punkty_kbn = models.TextField(db_column="pk", blank=True, null=True)
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
    zaznacz_field = models.TextField(
        db_column="zaznacz_", blank=True, null=True
    )  # Field renamed because it ended with '_'.
    idt2 = models.ForeignKey("self", CASCADE, db_column="idt2", blank=True, null=True)
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

    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_type = models.ForeignKey(ContentType, DO_NOTHING, null=True, blank=True)
    object = GenericForeignKey()

    analyzed = models.BooleanField(default=False)

    class Meta:
        db_table = "import_dbf_bib"
        verbose_name = "zaimportowany rekord bibliografi"
        verbose_name_plural = "zaimportowane rekordy bibliografi"

    def __str__(self):
        return self.tytul_or_s


class Bib_Desc(models.Model):
    idt = models.ForeignKey(Bib, CASCADE)
    elem_id = models.PositiveSmallIntegerField(db_index=True)
    value = JSONField()
    source = models.CharField(max_length=10)

    class Meta:
        ordering = ("idt", "source")


class Aut(models.Model):
    idt_aut = models.TextField(primary_key=True)
    imiona = models.TextField(blank=True, null=True)
    nazwisko = models.TextField(blank=True, null=True)
    # 'ref' to odnośnik do sposobu zapisania danego autora w publikacji (myśl: b_a)
    ref = models.ForeignKey(
        "import_dbf.Aut",
        blank=True,
        null=True,
        db_column="ref",
        on_delete=DO_NOTHING,
        related_name="aut_ref",
    )
    idt_jed = models.ForeignKey(
        "import_dbf.Jed",
        blank=True,
        null=True,
        db_column="idt_jed",
        on_delete=DO_NOTHING,
    )
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
    # exp_id to autor "nadrzędny"(?)
    exp_id = models.ForeignKey(
        "import_dbf.Aut",
        blank=True,
        null=True,
        db_column="exp_id",
        on_delete=DO_NOTHING,
        related_name="aut_exp",
    )
    polon_id = models.TextField(blank=True, null=True)
    usos_id = models.TextField(blank=True, null=True)
    udf_id = models.TextField(blank=True, null=True)
    control = models.TextField(blank=True, null=True)
    uwagi = models.TextField(blank=True, null=True)
    graf = models.TextField(blank=True, null=True)

    bpp_autor = models.ForeignKey(
        "bpp.Autor", null=True, blank=True, on_delete=DO_NOTHING
    )

    class Meta:
        managed = False
        db_table = "import_dbf_aut"
        verbose_name = "zaimportowany autor"
        verbose_name_plural = "zaimportowani autorzy"
        ordering = ("nazwisko", "imiona")

    def __str__(self):
        ret = f"{self.nazwisko} {self.imiona}"
        if self.tytul:
            ret += f", {self.tytul}"
        return ret

    def get_bpp(self):
        return self.bpp_autor


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

    bpp_jednostka = models.ForeignKey(
        "bpp.Jednostka", DO_NOTHING, blank=True, null=True
    )

    def get_bpp(self):
        return self.bpp_jednostka

    class Meta:
        managed = False
        db_table = "import_dbf_jed"

    def __str__(self):
        return self.nazwa


class B_A(models.Model):
    id = models.IntegerField(primary_key=True)
    idt = models.ForeignKey("import_dbf.Bib", db_column="idt", on_delete=DO_NOTHING)
    lp = models.TextField(blank=True, null=True)
    idt_aut = models.ForeignKey(
        "import_dbf.Aut", db_column="idt_aut", on_delete=DO_NOTHING
    )
    idt_jed = models.ForeignKey(
        "import_dbf.Jed", db_column="idt_jed", on_delete=DO_NOTHING
    )
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

    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_type = models.ForeignKey(ContentType, DO_NOTHING, null=True, blank=True)
    object = GenericForeignKey()

    def __str__(self):
        return f"Przypisanie autora {self.idt_aut} w jednostce {self.idt_jed} do rekordu {self.idt}"

    class Meta:
        managed = False
        ordering = ("idt__tytul_or_s", "lp")
        db_table = "import_dbf_b_a"


class PozManager(models.Manager):
    def get_for_model(self, idt, rec_type):
        ret = ""
        for elem in self.filter(idt=idt, kod_opisu=rec_type):
            ret += elem.tresc
        return ret


class Poz(models.Model):
    id = models.IntegerField(primary_key=True)
    idt = models.ForeignKey("import_dbf.Bib", db_column="idt", on_delete=DO_NOTHING)
    kod_opisu = models.TextField(blank=True, null=True)
    lp = models.PositiveSmallIntegerField()
    tresc = models.TextField(blank=True, null=True)

    objects = PozManager()

    class Meta:
        managed = False
        ordering = ("idt", "kod_opisu", "lp")
        db_table = "import_dbf_poz"
        verbose_name = "zaimportowany opis rekordu"
        verbose_name_plural = "zaimportowane opisy rekordow"


class B_U(models.Model):
    idt = models.ForeignKey("import_dbf.Bib", DO_NOTHING, db_column="idt")
    idt_usi = models.ForeignKey("import_dbf.Usi", DO_NOTHING, db_column="idt_usi")
    comm = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        verbose_name_plural = "zaimportowane dane OA rekordow"
        verbose_name = "zaimportowane dane OA rekordu"
        db_table = "import_dbf_b_u"
        ordering = (
            "idt",
            "comm",
        )


class Usi(models.Model):
    idt_usi = models.IntegerField(primary_key=True)
    usm_f = models.TextField(blank=True, null=True)
    usm_sf = models.TextField(blank=True, null=True)
    skrot = models.TextField(blank=True, null=True)
    nazwa = models.TextField(blank=True, null=True)
    bpp_id = models.ForeignKey("bpp.Zrodlo", DO_NOTHING, db_column="bpp_id", null=True)
    bpp_wydawca_id = models.ForeignKey(
        "bpp.Wydawca", DO_NOTHING, db_column="bpp_wydawca_id", null=True
    )
    bpp_seria_wydawnicza_id = models.ForeignKey(
        "bpp.Seria_Wydawnicza",
        DO_NOTHING,
        db_column="bpp_seria_wydawnicza_id",
        null=True,
    )

    class Meta:
        managed = False
        verbose_name_plural = "zaimportowane źródła"
        verbose_name = "zaimportowane źródło"
        db_table = "import_dbf_usi"

    def __str__(self):
        return self.nazwa


class Ses(models.Model):
    redaktor = models.TextField(blank=True, null=True)
    file = models.TextField(blank=True, null=True)
    login_t = models.TextField(blank=True, null=True)
    logout_t = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_ses"


class Wx2(models.Model):
    idt_wsx = models.TextField(primary_key=True)
    skrot = models.TextField(blank=True, null=True)
    nazwa = models.TextField(blank=True, null=True)
    wsp = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_wx2"


class Ixn(models.Model):
    idt_pbn = models.TextField(blank=True, primary_key=True)
    pbn = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        verbose_name = "zaimportowany identyfikator PBN"
        verbose_name_plural = "zaimportowane identyfikatory PBN"
        db_table = "import_dbf_ixn"


class B_B(models.Model):
    idt = models.TextField(primary_key=True)
    lp = models.TextField(blank=True, null=True)
    idt_bazy = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_b_b"


class B_N(models.Model):
    idt = models.TextField(primary_key=True)
    lp = models.TextField(blank=True, null=True)
    idt_pbn = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_b_n"


class Dys(models.Model):
    orcid_id = models.TextField(primary_key=True)
    a_n = models.TextField(blank=True, null=True)
    a_w_etatu = models.TextField(blank=True, null=True)
    a_dysc_1 = models.TextField(blank=True, null=True)
    a_dysc_2 = models.TextField(blank=True, null=True)
    a_dysc_1_e = models.TextField(blank=True, null=True)
    a_dysc_2_e = models.TextField(blank=True, null=True)
    b_n = models.TextField(blank=True, null=True)
    b_w_etatu = models.TextField(blank=True, null=True)
    b_dysc_1 = models.TextField(blank=True, null=True)
    b_dysc_2 = models.TextField(blank=True, null=True)
    b_dysc_1_e = models.TextField(blank=True, null=True)
    b_dysc_2_e = models.TextField(blank=True, null=True)
    c_n = models.TextField(blank=True, null=True)
    c_w_etatu = models.TextField(blank=True, null=True)
    c_dysc_1 = models.TextField(blank=True, null=True)
    c_dysc_2 = models.TextField(blank=True, null=True)
    c_dysc_1_e = models.TextField(blank=True, null=True)
    c_dysc_2_e = models.TextField(blank=True, null=True)
    d_n = models.TextField(blank=True, null=True)
    d_w_etatu = models.TextField(blank=True, null=True)
    d_dysc_1 = models.TextField(blank=True, null=True)
    d_dysc_2 = models.TextField(blank=True, null=True)
    d_dysc_1_e = models.TextField(blank=True, null=True)
    d_dysc_2_e = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        verbose_name = "zaimportowana dyscyplina pracownika"
        verbose_name_plural = "zaimportowane dyscypliny pracowników"
        db_table = "import_dbf_dys"


class Ixe(models.Model):
    idt_eng = models.TextField(primary_key=True)
    haslo = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.haslo

    class Meta:
        managed = False
        verbose_name = "zaimportowane hasło naukowe"
        verbose_name_plural = "zaimportowane hasła naukowe"
        db_table = "import_dbf_ixe"


class Jer(models.Model):
    nr = models.TextField(primary_key=True)
    od_roku = models.TextField(blank=True, null=True)
    skrot = models.TextField(blank=True, null=True)
    nazwa = models.TextField(blank=True, null=True)
    wyd_skrot = models.TextField(blank=True, null=True)
    id_u = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_jer"


class Kad(models.Model):
    nr = models.TextField(primary_key=True)
    na = models.TextField(blank=True, null=True)
    im1 = models.TextField(blank=True, null=True)
    im2 = models.TextField(blank=True, null=True)
    s_jed = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_kad"


class Loc(models.Model):
    ident = models.TextField(primary_key=True)
    ext = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_loc"


class Pbc(models.Model):
    idt = models.TextField(primary_key=True)
    wyd_skrot = models.TextField(blank=True, null=True)
    date = models.TextField(blank=True, null=True)
    category = models.TextField(blank=True, null=True)
    details = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_pbc"


class Pub(models.Model):
    idt_pub = models.TextField(primary_key=True)
    skrot = models.TextField(blank=True, null=True)
    nazwa = models.TextField(blank=True, null=True)
    to_print = models.TextField(blank=True, null=True)
    to_print2 = models.TextField(blank=True, null=True)
    to_print3 = models.TextField(blank=True, null=True)
    to_print4 = models.TextField(blank=True, null=True)
    to_print5 = models.TextField(blank=True, null=True)
    bpp_id = models.ForeignKey(
        "bpp.Charakter_Formalny", DO_NOTHING, db_column="bpp_id", null=True
    )

    class Meta:
        managed = False
        verbose_name = "zaimportowany charakter publikacji"
        verbose_name_plural = "zaimportowane charaktery publikacji"
        db_table = "import_dbf_pub"


class Sci(models.Model):
    idt_sci = models.TextField(primary_key=True)
    au = models.TextField(blank=True, null=True)
    ti = models.TextField(blank=True, null=True)
    src = models.TextField(blank=True, null=True)
    ye = models.TextField(blank=True, null=True)
    cont = models.TextField(blank=True, null=True)
    ut = models.TextField(blank=True, null=True)
    field_ignore_me = models.TextField(
        db_column="_ignore_me", blank=True, null=True
    )  # Field renamed because it started with '_'.

    class Meta:
        managed = False
        db_table = "import_dbf_sci"


class Sys(models.Model):
    ver = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_sys"
        verbose_name = "zaimportowana wersja bazy"
        verbose_name_plural = "zaimportowane wersje bazy"

    def __str__(self):
        return self.ver


class Wsx(models.Model):
    idt_wsx = models.TextField(primary_key=True)
    skrot = models.TextField(blank=True, null=True)
    nazwa = models.TextField(blank=True, null=True)
    wsp = models.TextField(blank=True, null=True)
    field_ignore_me = models.TextField(
        db_column="_ignore_me", blank=True, null=True
    )  # Field renamed because it started with '_'.

    class Meta:
        managed = False
        db_table = "import_dbf_wsx"


class Wyd(models.Model):
    idt_wyd = models.TextField(primary_key=True)
    skrot = models.TextField(blank=True, null=True)
    nazwa = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_wyd"
        verbose_name = "zaimportowany wydział"
        verbose_name_plural = "zaimportowane wydzialy"

    def __str__(self):
        return self.nazwa


class Ldy(models.Model):
    id = models.TextField(primary_key=True)
    dziedzina = models.TextField(blank=True, null=True)
    dyscyplina = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_ldy"
        verbose_name = "zaimportowana dziedzina"
        verbose_name_plural = "zaimportowane dziedziny"

    def __str__(self):
        return f"{self.dziedzina} / {self.dyscyplina}"


class B_E(models.Model):
    idt = models.IntegerField()
    lp = models.TextField(blank=True, null=True)
    idt_eng = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_b_e"


class B_P(models.Model):
    idt = (
        models.IntegerField()
    )  # ForeignKey("import_dbf.Bib", db_column='idt', on_delete=DO_NOTHING)
    lp = models.TextField(blank=True, null=True)
    idt_pol = models.ForeignKey(
        "import_dbf.Ixp", db_column="idt_pol", on_delete=DO_NOTHING
    )

    class Meta:
        managed = False
        db_table = "import_dbf_b_p"

    def __str__(self):
        return "powiązanie B_P dla %s" % self.idt


class Ixp(models.Model):
    idt_pol = models.TextField(primary_key=True)
    haslo = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_ixp"

    def __str__(self):
        return self.haslo


class Jez(models.Model):
    skrot = models.TextField(primary_key=True)
    nazwa = models.TextField(blank=True, null=True)
    bpp_id = models.ForeignKey("bpp.Jezyk", DO_NOTHING, db_column="bpp_id", null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_jez"
        verbose_name = "zaimportowany język"
        verbose_name_plural = "zaimportowane języki"

    def __str__(self):
        return self.nazwa


class Kbn(models.Model):
    idt_kbn = models.TextField(primary_key=True)
    skrot = models.TextField(blank=True, null=True)
    nazwa = models.TextField(blank=True, null=True)
    to_print = models.TextField(blank=True, null=True)
    to_print2 = models.TextField(blank=True, null=True)
    to_print3 = models.TextField(blank=True, null=True)
    to_print4 = models.TextField(blank=True, null=True)
    to_print5 = models.TextField(blank=True, null=True)

    bpp_id = models.ForeignKey("bpp.Typ_KBN", DO_NOTHING, db_column="bpp_id", null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_kbn"
        verbose_name = "zaimportowany typ KBN"
        verbose_name_plural = "zaimportowane typy KBN"

    def __str__(self):
        return self.nazwa


class Pba(models.Model):
    idt = models.TextField(blank=True, null=True)
    idt_pbn = models.TextField(blank=True, null=True)
    wyd_skrot = models.TextField(blank=True, null=True)
    date = models.TextField(blank=True, null=True)
    category = models.TextField(blank=True, null=True)
    details = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_pba"


class Pbd(models.Model):
    rep_f_name = models.TextField(blank=True, null=True)
    field_ignore_me = models.TextField(
        db_column="_ignore_me", blank=True, null=True
    )  # Field renamed because it started with '_'.

    class Meta:
        managed = False
        db_table = "import_dbf_pbd"


class Rtf(models.Model):
    idt = models.TextField(blank=True, null=True)
    lp = models.TextField(blank=True, null=True)
    len = models.TextField(blank=True, null=True)
    rtf = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_rtf"


class S_B(models.Model):
    idt_sci = models.TextField(blank=True, null=True)
    idt = models.ForeignKey("import_dbf.Bib", db_column="idt", on_delete=DO_NOTHING)
    cit = models.TextField(blank=True, null=True)
    doi = models.TextField(blank=True, null=True)
    del_field = models.TextField(
        db_column="del", blank=True, null=True
    )  # Field renamed because it was a Python reserved word.
    redaktor = models.TextField(blank=True, null=True)
    dat_akt = models.TextField(blank=True, null=True)
    autocyt = models.TextField(blank=True, null=True)
    ut = models.TextField(blank=True, null=True)
    ut0 = models.TextField(blank=True, null=True)
    uwagi = models.TextField(blank=True, null=True)
    field_ignore_me = models.TextField(
        db_column="_ignore_me", blank=True, null=True
    )  # Field renamed because it started with '_'.

    class Meta:
        managed = False
        db_table = "import_dbf_s_b"


class Wsy(models.Model):
    idt_wsy = models.TextField(primary_key=True)
    skrot = models.TextField(blank=True, null=True)
    nazwa = models.TextField(blank=True, null=True)
    wsp = models.TextField(blank=True, null=True)
    field_ignore_me = models.TextField(
        db_column="_ignore_me", blank=True, null=True
    )  # Field renamed because it started with '_'.

    class Meta:
        managed = False
        db_table = "import_dbf_wsy"


class Ixb(models.Model):
    idt_bazy = models.TextField(primary_key=True)
    baza = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_ixb"
        verbose_name = "zaimportowana baza"
        verbose_name_plural = "zaimportowane bazy"

    def __str__(self):
        return self.baza


class Lis(models.Model):
    rok = models.TextField(blank=True, null=True)
    kategoria = models.TextField(blank=True, null=True)
    numer = models.TextField(blank=True, null=True)
    tytul = models.TextField(blank=True, null=True)
    issn = models.TextField(blank=True, null=True)
    eissn = models.TextField(blank=True, null=True)
    punkty = models.TextField(blank=True, null=True)
    sobowtor = models.TextField(blank=True, null=True)
    errissn = models.TextField(blank=True, null=True)
    dblissn = models.TextField(blank=True, null=True)
    dbltitul = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_lis"
        verbose_name = "zaimportowana lista wydawców"
        verbose_name_plural = "zaimportowane listy wydawców"


class B_L(models.Model):
    idt = (
        models.IntegerField()
    )  # ForeignKey("import_dbf.Bib", on_delete=DO_NOTHING, db_column='idt')
    idt_l = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_b_l"


class Ext(models.Model):
    cont = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_ext"


class J_H(models.Model):
    idt_jed_f = models.ForeignKey(
        "import_dbf.Jed",
        on_delete=DO_NOTHING,
        db_column="idt_jed_f",
        related_name="jed_f",
    )
    idt_jed_t = models.ForeignKey(
        "import_dbf.Jed",
        on_delete=DO_NOTHING,
        db_column="idt_jed_t",
        related_name="jed_t",
    )
    rok = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_j_h"
        verbose_name = "zaimportowany rekord historii jednostek"
        verbose_name_plural = "zaimportowane rekordy historii jednostek"


class Kbr(models.Model):
    idt_kbr = models.TextField(primary_key=True)
    skrot = models.TextField(blank=True, null=True)
    nazwa = models.TextField(blank=True, null=True)
    to_print = models.TextField(blank=True, null=True)
    to_print2 = models.TextField(blank=True, null=True)
    to_print3 = models.TextField(blank=True, null=True)
    to_print4 = models.TextField(blank=True, null=True)
    to_print5 = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_kbr"
        verbose_name = "zaimportowany rekord KBR"
        verbose_name_plural = "zaimportowane rekordy KBR"

    def __str__(self):
        return self.nazwa


class Pbb(models.Model):
    rep_f_name = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "import_dbf_pbb"


__all__ = [
    "Bib",
    "Aut",
    "Jed",
    "B_A",
    "Poz",
    "B_U",
    "Usi",
    "Ses",
    "Wx2",
    "Ixn",
    "B_B",
    "B_N",
    "Dys",
    "Ixe",
    "Jer",
    "Kad",
    "Loc",
    "Pbc",
    "Pub",
    "Sci",
    "Sys",
    "Wsx",
    "Wyd",
    "Ldy",
    "B_E",
    "B_P",
    "Ixp",
    "Jez",
    "Kbn",
    "Pba",
    "Pbd",
    "Rtf",
    "S_B",
    "Wsy",
    "Ixb",
    "Lis",
    "B_L",
    "Ext",
    "J_H",
    "Kbr",
    "Pbb",
]
