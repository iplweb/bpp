"""Funkcje pomocnicze dla klas w bpp.models"""

from django.core.exceptions import ObjectDoesNotExist, ValidationError

from bpp.models.szablondlaopisubibliograficznego import SzablonDlaOpisuBibliograficznego

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from django.db import models
from django.db.models import Max
from django.template.loader import get_template
from django.utils import safestring

# Skrócony widok listy autorów na stronie rekordu (patrz
# ModelZOpisemBibliograficznym.autorzy_dla_opisu_skrocony):
LICZBA_PIERWSZYCH_AUTOROW = 5
PROG_SKRACANIA_AUTOROW = 25


def dodaj_autora(
    klass,
    rekord,
    autor,
    jednostka,
    zapisany_jako=None,
    typ_odpowiedzialnosci_skrot="aut.",
    kolejnosc=None,
    dyscyplina_naukowa=None,
    afiliuje=True,
):
    """
    Utility function, dodająca autora do danego rodzaju klasy (Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte, Patent); funkcja używana przez te klasy, niejako
    wewnętrzna dla całego API; nie powinna być używana bezpośrednio nigdzie,
    jedynie API tych klas winno być używane.

    :param klass:
    :param rekord:
    :param autor:
    :param jednostka:
    :param zapisany_jako:
    :param typ_odpowiedzialnosci_skrot:
    :param kolejnosc:
    :return:
    """

    from bpp.models import Typ_Odpowiedzialnosci

    typ_odpowiedzialnosci = Typ_Odpowiedzialnosci.objects.get(
        skrot=typ_odpowiedzialnosci_skrot
    )

    if zapisany_jako is None:
        zapisany_jako = f"{autor.nazwisko} {autor.imiona}"

    if kolejnosc is None:
        kolejnosc = klass.objects.filter(rekord=rekord).aggregate(Max("kolejnosc"))[
            "kolejnosc__max"
        ]
        if kolejnosc is None:
            kolejnosc = 0
        else:
            kolejnosc += 1

    inst = klass(
        rekord=rekord,
        autor=autor,
        jednostka=jednostka,
        typ_odpowiedzialnosci=typ_odpowiedzialnosci,
        kolejnosc=kolejnosc,
        zapisany_jako=zapisany_jako,
        dyscyplina_naukowa=dyscyplina_naukowa,
        afiliuje=afiliuje,
    )
    inst.full_clean()
    inst.save()
    return inst


class ModelZOpisemBibliograficznym(models.Model):
    """Mixin, umożliwiający renderowanie opisu bibliograficznego dla danego
    obiektu przy pomocy template."""

    # noqa: DJ001 - pre-existing null=True na TextField (sprzed naszego brancha).
    tekst_przed_pierwszym_autorem = models.TextField(blank=True, null=True)  # noqa: DJ001
    tekst_po_ostatnim_autorze = models.TextField(blank=True, null=True)  # noqa: DJ001

    def opis_bibliograficzny(self, links=None):
        """Renderuje opis bibliograficzny dla danej klasy, używając:
        * w pierwszej kolejności zadeklarowanej Template dla danego typu rekordu (lub ogólnego Template),
        * w trzeciej kolejności templatki z dysku "opis_bibliograficzny/opis_bibliograficzny.html"

        :param links: "normal" lub "admin" jeżeli chcemy, aby autorzy prowadzili gdzieś (do stron browse/
        lub do admina).
        """

        template_name = SzablonDlaOpisuBibliograficznego.objects.get_for_model(self)
        if template_name is None:
            template_name = "opis_bibliograficzny.html"

        template = get_template(template_name)

        ret = (
            template.render(dict(praca=self, links=links))
            .replace("\r\n", "")
            .replace("\n", "")
        )
        while ret.find("  ") != -1:
            ret = ret.replace("  ", " ")

        ret = (
            ret.replace(" , ", ", ")
            .replace(" . ", ". ")
            .replace(". . ", ". ")
            .replace(". , ", ". ")
            .replace(" .", ".")
            .replace(".</b>[", ".</b> [")
        )

        # Opis powstaje m.in. z (niezaufanego) tytułu i jest renderowany |safe
        # oraz cache'owany w opis_bibliograficzny_cache. Sanityzujemy złożenie,
        # żeby żaden <script> z tytułu nie przeżył (obrona w głębi obok
        # sanityzacji tytułu u źródła), zachowując kursywę, sub/sup i linki
        # autorów.
        from bpp.util import safe_opis_bibliograficzny_html

        return safe_opis_bibliograficzny_html(ret)

    #: Atrybut, pod którym ``prefetch_autorzy_dla_opisu`` podstawia gotową
    #: listę autorów. Ustawiany JAWNIE przez widok na czas renderowania jednej
    #: strony — dzięki temu nie ma ryzyka, że pamięć podręczna przeżyje zapis
    #: autorów na tej samej instancji (jak zrobiłaby to ``cached_property``).
    PREFETCH_AUTORZY_ATTR = "_autorzy_dla_opisu_prefetch"

    def autorzy_dla_opisu(self):
        # Takie 'autorzy_set.all()' ale na potrzeby opisu bibliograficznego -- zaciąga
        # rekordy zależne za pomocą .select_related:

        prefetched = getattr(self, self.PREFETCH_AUTORZY_ATTR, None)
        if prefetched is not None:
            return prefetched

        if not self.pk:
            return []

        return self.autorzy_set.select_related(
            "autor", "typ_odpowiedzialnosci"
        ).order_by("kolejnosc")

    def autorzy_dla_opisu_skrocony(self, uczelnia=None, zwijaj=True):
        """Dane dla skróconego widoku listy autorów na stronie rekordu.

        Materializuje listę autorów raz i dokleja każdemu wpisowi atrybuty
        ``pozycja`` (1-based numer na liście) oraz ``czy_nasz`` (autor z
        jednostki skupiającej pracowników oglądającej uczelni). Zwraca słownik:

        - ``skrocony``   -- czy włączyć widok zwinięty (``zwijaj`` włączone
          ORAZ autorów > próg); ``zwijaj=False`` wymusza pełną listę,
        - ``wszyscy``    -- pełna lista (z ``pozycja``/``czy_nasz``),
        - ``pierwsi``    -- pierwszych ``LICZBA_PIERWSZYCH_AUTOROW``,
        - ``nasi_dalej`` -- "nasi" autorzy spoza pierwszej piątki,
        - ``liczba``     -- liczba autorów.

        ``uczelnia`` to oglądająca uczelnia (rozwiązana per-host przez
        ``Uczelnia.objects.get_for_request``). Gdy podana (ma ``pk``), autor
        jest "nasz" tylko jeśli jego jednostka należy do TEJ uczelni — bez
        tego, w konfiguracji multi-hosted ta sama praca pokazywałaby tego
        samego autora jako "naszego" na każdym hoście. Gdy ``uczelnia`` jest
        ``None`` (lub niezdefiniowana, ``pk=None``), filtrowanie po uczelni
        nie zachodzi i flaga zależy wyłącznie od ``skupia_pracownikow``
        (wstecz-kompatybilność z callerami bez kontekstu uczelni).
        """
        autorzy = self.autorzy_dla_opisu()
        # autorzy_dla_opisu() zwraca [] (zamiast QuerySetu) dla niezapisanego
        # rekordu (pk=None) — wtedy nie ma do czego doczepić select_related.
        if hasattr(autorzy, "select_related"):
            autorzy = autorzy.select_related("jednostka")
        wszyscy = list(autorzy)
        uczelnia_pk = getattr(uczelnia, "pk", None)
        for pozycja, wpis in enumerate(wszyscy, start=1):
            wpis.pozycja = pozycja
            czy_nasz = bool(wpis.jednostka.skupia_pracownikow)
            if czy_nasz and uczelnia_pk is not None:
                # ``uczelnia_id`` to FK-id na już-select_related-owanej
                # jednostce — porównanie nie generuje dodatkowego zapytania.
                czy_nasz = wpis.jednostka.uczelnia_id == uczelnia_pk
            wpis.czy_nasz = czy_nasz

        return {
            "skrocony": zwijaj and len(wszyscy) > PROG_SKRACANIA_AUTOROW,
            "wszyscy": wszyscy,
            "pierwsi": wszyscy[:LICZBA_PIERWSZYCH_AUTOROW],
            "nasi_dalej": [
                wpis for wpis in wszyscy[LICZBA_PIERWSZYCH_AUTOROW:] if wpis.czy_nasz
            ],
            "liczba": len(wszyscy),
        }

    def get_slug(self):
        if self.pk is None:
            return

        from bpp.util import slugify_function

        slug_tytul_oryginalny = slugify_function(self.tytul_oryginalny)

        slug_trzech_pierwszych_autorow = []
        for wyd_autor in self.autorzy_set.all().select_related("autor")[:3]:
            slug_trzech_pierwszych_autorow.append(
                f"{wyd_autor.autor.nazwisko} {wyd_autor.autor.imiona[:1]}"
            )
        slug_trzech_pierwszych_autorow = " ".join(slug_trzech_pierwszych_autorow)

        if hasattr(self, "zrodlo_id") and self.zrodlo_id is not None:
            slug_zrodla = slugify_function(self.zrodlo.nazwa)
        elif (
            hasattr(self, "wydawnictwo_nadrzedne")
            and self.wydawnictwo_nadrzedne_id is not None
        ):
            slug_zrodla = slugify_function(self.wydawnictwo_nadrzedne.tytul_oryginalny)
        else:
            slug_zrodla = ""

        lt, la, lz = (
            len(slug_tytul_oryginalny),
            len(slug_trzech_pierwszych_autorow),
            len(slug_zrodla),
        )

        if lt + la + lz >= 350:
            if lt > 200:
                lt = 200

            if lt + la + lz >= 350:
                if lz > 100:
                    lz = 100

                if lt + la + lz >= 350:
                    la = 50

        from django.contrib.contenttypes.models import ContentType

        ret = "-".join(
            [
                slug_tytul_oryginalny[:lt],
                slug_zrodla[:lz],
                slug_trzech_pierwszych_autorow[:la],
                str(ContentType.objects.get_for_model(self).pk),
                str(self.pk),
            ]
        )

        return slugify_function(ret)

    # Ten obiekt stanowi bazę do późniejszego zapełniania pól w podklasach. Pola,
    # które powinna podklasa definiować to:
    #
    # opis_bibliograficzny_cache = models.TextField(default="")
    # - generowane przez self.opis_bibliograficzny()
    #
    # opis_bibliograficzny_autorzy_cache = ArrayField(TextField(), blank=True, null=True)
    # -  To pole używane jest na ten moment jedynie przez moduł OAI, do szybkiego
    #    produkowania pola "Creator" dla formatu Dublin Core, vide moduł bpp.oai .
    #    To pole zawiera listę autorów, w kolejności, nazwisko i imię, bez
    #    tytułu
    #
    # slug = models.SlugField(max_length=400, unique=True, db_index=True, null=True, blank=True)
    # - skrót dla rekordu, dla SEO, zależy od m.in. tytułu, autorów, wydawnictwa nadrzędnego, źródła
    #
    # opis_bibliograficzny_zapisani_autorzy_cache = models.TextField(default="")
    # - zależy od klas autorów; to pole używane jest przez Raport autorów oraz Raport
    #   jednostek do szybkiego wypluwania listy zapisanych nazwisk
    #
    # def zaktualizuj_opis_bibliograficzny_cache(self, tylko_opis=False):
    #     autorzy = self.autorzy_dla_opisu()
    #     self.opis_bibliograficzny_cache = self.opis_bibliograficzny()
    #     self.slug = self._get_slug()
    #
    #     if hasattr(self, "autor"):
    #         zapisani = ["%s %s" % (autorzy[0].autor.nazwisko, autorzy[0].autor.imiona)]
    #     else:
    #         zapisani = [x.zapisany_jako for x in autorzy]
    #
    #     oac = ["%s %s" % (x.autor.nazwisko, x.autor.imiona) for x in autorzy]
    #     self.opis_bibliograficzny_autorzy_cache = oac
    #
    #     ozac = ", ".join(zapisani)
    #     self.opis_bibliograficzny_zapisani_autorzy_cache = ozac

    class Meta:  # noqa: DJ012 - kolejność zastana (sprzed naszego brancha).
        abstract = True


def prefetch_dane_strony_rekordu(praca):
    """Materializuje — jednym zapytaniem na zestaw — dane, po które szablon
    strony rekordu sięga wielokrotnie: autorów opisu i streszczenia.

    Wywoływane JAWNIE przez widok strony rekordu, tuż przed renderowaniem.
    Nie jest to ``cached_property`` na modelu: pamięć podręczna ma żyć tylko
    tyle, co jeden render, a nie tyle, co instancja modelu (inaczej kod,
    który zapisuje autorów i od razu odświeża opis bibliograficzny na tej
    samej instancji, zobaczyłby nieaktualne dane).
    """
    if praca is None:
        return

    from django.db.models import Prefetch, prefetch_related_objects
    from django.db.models.fields.related_descriptors import (
        ReverseManyToOneDescriptor,
    )

    descriptor = getattr(type(praca), "autorzy_set", None)
    attr = getattr(praca, "PREFETCH_AUTORZY_ATTR", None)
    if attr is not None and isinstance(descriptor, ReverseManyToOneDescriptor):
        # Praca_Doktorska/Habilitacyjna mają 'autorzy_set' jako property
        # zwracającą sztuczną listę — tam prefetch nie ma sensu i by się wywalił.
        autorzy = praca.autorzy_set.model.objects.select_related(
            "autor", "typ_odpowiedzialnosci"
        ).order_by("kolejnosc")
        prefetch_related_objects(
            [praca],
            Prefetch(
                "autorzy_set",
                queryset=autorzy,
                to_attr=attr,
            ),
        )

    try:
        prefetch_related_objects([praca], "streszczenia")
    except AttributeError:
        # Patent, doktorat, habilitacja: brak relacji 'streszczenia'.
        pass


class ZapobiegajNiewlasciwymCharakterom(models.Model):
    class Meta:
        abstract = True

    def clean_fields(self, *args, **kw):
        try:
            cf = self.charakter_formalny
        except ObjectDoesNotExist:
            cf = None

        if cf is not None:
            if self.charakter_formalny.skrot in ["D", "H", "PAT"]:
                raise ValidationError(
                    {
                        "charakter_formalny": [
                            safestring.mark_safe(
                                'Jeżeli chcesz dodać rekord o typie "{}"'
                                ', <a href="{}">kliknij tutaj</a>.'.format(
                                    self.charakter_formalny.nazwa,
                                    reverse(
                                        "admin:bpp_{}_add".format(
                                            self.charakter_formalny.nazwa.lower().replace(
                                                " ", "_"
                                            )
                                        )
                                    ),
                                )
                            )
                        ]
                    }
                )
