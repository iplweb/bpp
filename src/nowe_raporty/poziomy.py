"""Rejestr poziomów raportu — jedyna część "raportu", która zostaje KODEM.

Każdy poziom (uczelnia/wydział/jednostka/autor) mapuje na: model obiektu, czy
URL niesie ``pk``, funkcję bazowego querysetu ``Rekord`` (logika ORM, której nie
da się wyrazić jako dana — patrz slice A), oraz pole wyboru obiektu do
formularza. Reszta definicji raportu (nazwa, slug, template, uprawnienia) jest
danymi w ``DefinicjaRaportu``.
"""

from dal import autocomplete
from django import forms

from bpp.models import Uczelnia
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.struktura import Jednostka
from bpp.util.uczelnia_scope import scope_rekord_do_uczelni

from .models import DefinicjaRaportu


def _base_autor(obiekt, tylko_afiliowane):
    if tylko_afiliowane:
        return Rekord.objects.prace_autora_z_afiliowanych_jednostek(obiekt)
    return Rekord.objects.prace_autora(obiekt)


def _base_jednostka(obiekt, tylko_afiliowane):
    if tylko_afiliowane:
        return Rekord.objects.prace_jednostki(obiekt, afiliowane=True)
    return Rekord.objects.prace_jednostki(obiekt)


def _base_wydzial(obiekt, tylko_afiliowane):
    if tylko_afiliowane:
        return Rekord.objects.prace_wydzialu(obiekt, afiliowane=True)
    return Rekord.objects.prace_wydzialu(obiekt)


def _base_uczelnia(obiekt, tylko_afiliowane):
    if tylko_afiliowane:
        qs = Rekord.objects.filter(autorzy__afiliuje=True)
    else:
        qs = Rekord.objects.all()
    return scope_rekord_do_uczelni(qs, obiekt)


def _wydzial_queryset():
    """#438: „wydział" = widoczna jednostka-korzeń (``parent IS NULL``). JEDNO
    źródło prawdy dla pola formularza ORAZ pobrania obiektu po pk
    (``get_object``/``get_initial``) — inaczej generujący URL (poza walidacją
    formularza) przyjąłby DOWOLNY pk Jednostki (stary bookmark
    ``?...=<Wydzial.pk>`` → losowa jednostka / wyciek ukrytej)."""
    return Jednostka.objects.widoczne().filter(parent__isnull=True)


def _pole(label, model, url, queryset=None):
    # ``queryset`` domyślnie = ``model.objects.all()``, ale poziom „wydział"
    # (#438) MUSI zawęzić do widocznych korzeni — inaczej ModelChoiceField
    # zwaliduje DOWOLNY pk Jednostki (widget ogranicza tylko UI), więc stary
    # bookmark ``?...=<Wydzial.pk>`` mógłby trafić w pk niepowiązanej jednostki.
    return forms.ModelChoiceField(
        label=label,
        queryset=model.objects.all() if queryset is None else queryset,
        widget=autocomplete.ModelSelect2(url=url),
    )


class PoziomConfig:
    def __init__(
        self, model, ma_pk, base_queryset, pole_factory, obiekt_queryset=None
    ):
        self.model = model
        self.ma_pk = ma_pk
        self.base_queryset = base_queryset
        self.pole_factory = pole_factory  # () -> forms.Field | None
        # () -> QuerySet: z czego wolno pobrać ``obiekt`` po pk (get_object /
        # get_initial). Domyślnie ``model.objects.all()``; poziom „wydział"
        # zawęża do widocznych korzeni (spójnie z polem formularza), żeby
        # generujący URL nie przyjął dowolnego pk Jednostki.
        self._obiekt_queryset = obiekt_queryset

    def pole_obiektu(self):
        return self.pole_factory()

    def obiekt_queryset(self):
        if self._obiekt_queryset is not None:
            return self._obiekt_queryset()
        return self.model._default_manager.all()


POZIOMY = {
    DefinicjaRaportu.POZIOM_AUTOR: PoziomConfig(
        Autor,
        True,
        _base_autor,
        lambda: _pole("Autor", Autor, "bpp:public-autor-autocomplete"),
    ),
    DefinicjaRaportu.POZIOM_JEDNOSTKA: PoziomConfig(
        Jednostka,
        True,
        _base_jednostka,
        lambda: _pole("Jednostka", Jednostka, "bpp:public-jednostka-autocomplete"),
    ),
    # Faza B (#438): „wydział" = jednostka-korzeń (parent IS NULL). Picker i
    # obiekt raportu to teraz Jednostka top-level, nie Wydzial.
    DefinicjaRaportu.POZIOM_WYDZIAL: PoziomConfig(
        Jednostka,
        True,
        _base_wydzial,
        lambda: _pole(
            "Wydział",
            Jednostka,
            "bpp:public-jednostka-toplevel-autocomplete",
            queryset=_wydzial_queryset(),
        ),
        obiekt_queryset=_wydzial_queryset,
    ),
    DefinicjaRaportu.POZIOM_UCZELNIA: PoziomConfig(
        Uczelnia,
        False,
        _base_uczelnia,
        lambda: None,
    ),
}
