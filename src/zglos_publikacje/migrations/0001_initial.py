# Generated by Django 3.2.14 on 2022-07-10 20:13

import django.db.models.deletion
from django.db import migrations, models

import bpp.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("bpp", "0325_nullbooleanfield"),
    ]

    operations = [
        migrations.CreateModel(
            name="Zgloszenie_Publikacji",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "tytul_oryginalny",
                    models.TextField(db_index=True, verbose_name="Tytuł oryginalny"),
                ),
                (
                    "tytul",
                    models.TextField(
                        blank=True, db_index=True, null=True, verbose_name="Tytuł"
                    ),
                ),
                (
                    "www",
                    models.URLField(
                        blank=True,
                        max_length=1024,
                        null=True,
                        verbose_name="Adres WWW (płatny dostęp)",
                    ),
                ),
                (
                    "dostep_dnia",
                    models.DateField(
                        blank=True,
                        help_text="Data dostępu do strony WWW.",
                        null=True,
                        verbose_name="Dostęp dnia (płatny dostęp)",
                    ),
                ),
                (
                    "public_www",
                    models.URLField(
                        blank=True,
                        max_length=2048,
                        null=True,
                        verbose_name="Adres WWW (wolny dostęp)",
                    ),
                ),
                (
                    "public_dostep_dnia",
                    models.DateField(
                        blank=True,
                        help_text="Data wolnego dostępu do strony WWW.",
                        null=True,
                        verbose_name="Dostęp dnia (wolny dostęp)",
                    ),
                ),
                (
                    "doi",
                    bpp.fields.DOIField(
                        blank=True,
                        db_index=True,
                        help_text="Digital Object Identifier (DOI)",
                        max_length=2048,
                        null=True,
                        verbose_name="DOI",
                    ),
                ),
                (
                    "opl_pub_cost_free",
                    models.BooleanField(
                        null=True, verbose_name="Publikacja bezkosztowa"
                    ),
                ),
                (
                    "opl_pub_research_potential",
                    models.BooleanField(
                        help_text="Środki finansowe, o których mowa w art. 365 pkt 2 ustawy",
                        null=True,
                        verbose_name="Środki finansowe art. 365 pkt 2 ustawy",
                    ),
                ),
                (
                    "opl_pub_research_or_development_projects",
                    models.BooleanField(
                        help_text="Środki finansowe przyznane na realizację projektu w zakresie badań naukowych "
                        "lub prac rozwojowych",
                        null=True,
                        verbose_name="Środki finansowe na realizację projektu",
                    ),
                ),
                (
                    "opl_pub_other",
                    models.BooleanField(
                        blank=True,
                        default=None,
                        null=True,
                        verbose_name="Inne środki finansowe",
                    ),
                ),
                (
                    "opl_pub_amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=20,
                        null=True,
                        verbose_name="Kwota (zł)",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Zgloszenie_Publikacji_Autor",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("kolejnosc", models.IntegerField(default=0, verbose_name="Kolejność")),
                ("zapisany_jako", models.CharField(max_length=512)),
                (
                    "afiliuje",
                    models.BooleanField(
                        default=True,
                        help_text="Afiliuje\n    się do jednostki podanej w przypisaniu. Jednostka nie może być obcą. ",
                    ),
                ),
                (
                    "zatrudniony",
                    models.BooleanField(
                        default=False,
                        help_text="Pracownik\n    jednostki podanej w przypisaniu",
                    ),
                ),
                (
                    "procent",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=5,
                        null=True,
                        verbose_name="Udział w opracowaniu (procent)",
                    ),
                ),
                (
                    "przypieta",
                    models.BooleanField(
                        db_index=True,
                        default=True,
                        help_text='Możesz odznaczyć, żeby "odpiąć" dyscyplinę od tego autora. Dyscyplina "odpięta" '
                        "nie będzie\n        wykazywana do PBN oraz nie będzie używana do liczenia punktów "
                        "dla danej pracy.",
                    ),
                ),
                (
                    "upowaznienie_pbn",
                    models.BooleanField(
                        default=False,
                        help_text='Tik w polu "upoważnienie PBN" oznacza, że dany autor upoważnił Uczelnię do '
                        "sprawozdania tej publikacji w ocenie parametrycznej Uczelni",
                        verbose_name="Upoważnienie PBN",
                    ),
                ),
                (
                    "profil_orcid",
                    models.BooleanField(
                        default=False,
                        help_text="Zaznacz, jeżeli praca znajdje się na profilu ORCID autora",
                        verbose_name="Praca w profilu ORCID autora",
                    ),
                ),
                (
                    "data_oswiadczenia",
                    models.DateField(
                        blank=True,
                        help_text="Informacja eksportowana do PBN, gdy uzupełniono",
                        null=True,
                        verbose_name="Data oświadczenia",
                    ),
                ),
                (
                    "autor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="bpp.autor"
                    ),
                ),
                (
                    "dyscyplina_naukowa",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="bpp.dyscyplina_naukowa",
                    ),
                ),
                (
                    "jednostka",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="bpp.jednostka"
                    ),
                ),
                (
                    "rekord",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="zglos_publikacje.zgloszenie_publikacji",
                    ),
                ),
                (
                    "typ_odpowiedzialnosci",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="bpp.typ_odpowiedzialnosci",
                        verbose_name="Typ odpowiedzialności",
                    ),
                ),
            ],
            options={
                "ordering": ("kolejnosc", "typ_odpowiedzialnosci__skrot"),
                "abstract": False,
            },
        ),
    ]