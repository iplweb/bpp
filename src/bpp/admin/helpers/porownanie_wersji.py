"""Czytelne porównanie dwóch wersji rekordu (FD#587).

Zastępuje domyślny diff reversion-compare (różnice znak po znaku, surowe
``repr``, każde pole w osobnym bloku) tabelą „pole | wersja starsza |
wersja nowsza”:

* tylko pola, które się zmieniły, z etykietami jak w formularzu,
* wartości po ludzku: nazwy ze słowników zamiast numerów, „tak/nie”,
  daty po polsku, „—” dla pustych,
* w tekstach podświetlone całe słowa usunięte (lewa kolumna) i dodane
  (prawa),
* listy śledzone razem z rekordem (autorzy, granty, pliki…): pozycje
  usunięte, dodane i zmienione — dla zmienionych konkretne pola,
  np. „Afiliuje: tak → nie”.
"""

import difflib
import json
import re
from datetime import date, datetime

from django.db import models
from django.utils import formats, timezone
from django.utils.html import escape, format_html, format_html_join
from django.utils.safestring import mark_safe

from bpp.wersjonowanie import FOLLOW_REVERSION

BRAK = object()

#: Pola pomijane w szczegółach zmienionych pozycji list (techniczne).
POLA_TECHNICZNE_POZYCJI = {
    "id",
    "ostatnio_zmieniony",
    "utworzono",
    "content_type",
    "object_id",
    "rekord",
}


def _etykieta(pole):
    nazwa = getattr(pole, "verbose_name", None) or pole.name
    return str(nazwa)[:1].upper() + str(nazwa)[1:]


class Formatowanie:
    """Zamiana surowych wartości z wersji na tekst dla człowieka (z pamięcią
    podręczną nazw obiektów powiązanych)."""

    def __init__(self):
        self._obiekty = {}

    def obiekt(self, model, pk):
        klucz = (model, pk)
        if klucz not in self._obiekty:
            obj = model._base_manager.filter(pk=pk).first()
            self._obiekty[klucz] = (
                str(obj) if obj is not None else f"(usunięty, id {pk})"
            )
        return self._obiekty[klucz]

    def wartosc(self, pole, wartosc):
        if wartosc is BRAK or wartosc is None or wartosc == "" or wartosc == []:
            return "—"
        if getattr(pole, "flatchoices", None):
            wybory = dict(pole.flatchoices)
            if wartosc in wybory:
                return str(wybory[wartosc])
        if isinstance(pole, models.BooleanField) or isinstance(wartosc, bool):
            return "tak" if wartosc else "nie"
        if pole.is_relation and pole.related_model is not None:
            return self._powiazane(pole, wartosc)
        return self._prosta(wartosc)

    def _powiazane(self, pole, wartosc):
        if isinstance(pole, models.ManyToManyField):
            return ", ".join(
                sorted(self.obiekt(pole.related_model, pk) for pk in wartosc)
            )
        return self.obiekt(pole.related_model, wartosc)

    @staticmethod
    def _prosta(wartosc):
        if isinstance(wartosc, datetime):
            return formats.date_format(timezone.localtime(wartosc), "j E Y, H:i")
        if isinstance(wartosc, date):
            return formats.date_format(wartosc, "j E Y")
        if isinstance(wartosc, (list, tuple)):
            return ", ".join(str(x) for x in wartosc)
        if isinstance(wartosc, dict):
            return json.dumps(wartosc, ensure_ascii=False, sort_keys=True, indent=1)
        return str(wartosc)


#: Słowo razem ze spacjami za nim — zamiana kilku słów daje jeden blok
#: ``del``/``ins``, a nie osobny na każde słowo.
_SLOWA = re.compile(r"\s*\S+\s*|\s+")


def diff_slow(stary, nowy):
    """(html_stary, html_nowy) z podświetlonymi słowami usuniętymi (``del``)
    w starym i dodanymi (``ins``) w nowym tekście."""
    a, b = _SLOWA.findall(stary), _SLOWA.findall(nowy)
    lewa, prawa = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, a, b, autojunk=False
    ).get_opcodes():
        kawalek_a, kawalek_b = escape("".join(a[i1:i2])), escape("".join(b[j1:j2]))
        if op == "equal":
            lewa.append(kawalek_a)
            prawa.append(kawalek_b)
            continue
        if kawalek_a:
            lewa.append(f"<del>{kawalek_a}</del>")
        if kawalek_b:
            prawa.append(f"<ins>{kawalek_b}</ins>")
    return mark_safe("".join(lewa)), mark_safe("".join(prawa))


def _tekstowe(pole):
    return (
        isinstance(pole, (models.CharField, models.TextField))
        and not pole.is_relation
        and not getattr(pole, "choices", None)
    )


def _para(pole, stary, nowy):
    """Para HTML dla zwykłego pola: teksty — diff słów, wartości ze
    słowników, liczby, daty, tak/nie — całe, podświetlone."""
    if _tekstowe(pole) and stary != "—" and nowy != "—":
        return diff_slow(stary, nowy)
    return (
        format_html("<del>{}</del>", stary) if stary != "—" else stary,
        format_html("<ins>{}</ins>", nowy) if nowy != "—" else nowy,
    )


def _pola_modelu(model, pomijane):
    opts = model._meta
    for pole in [*opts.concrete_fields, *opts.many_to_many]:
        if pole.name in pomijane or pole.primary_key:
            continue
        through = getattr(pole.remote_field, "through", None)
        if isinstance(pole, models.ManyToManyField) and not through._meta.auto_created:
            continue
        yield pole


def _wiersze_pol(model, wersja1, wersja2, pomijane, fmt):
    d1, d2 = wersja1.field_dict, wersja2.field_dict
    for pole in _pola_modelu(model, pomijane):
        a, b = d1.get(pole.attname, BRAK), d2.get(pole.attname, BRAK)
        if a is BRAK and b is BRAK or a == b:
            continue
        stary, nowy = fmt.wartosc(pole, a), fmt.wartosc(pole, b)
        if stary == nowy:
            continue  # różnica tylko techniczna (np. NULL a pusty tekst)
        stary, nowy = _para(pole, stary, nowy)
        yield {
            "etykieta": _etykieta(pole),
            "stare": stary,
            "nowe": nowy,
            "lista": False,
        }


def _nalezy(wersja, obj, menedzer):
    from .wersje import _nalezy_do

    return _nalezy_do(wersja, obj, menedzer)


def _elementy(rewizja, model_powiazany, obj, menedzer):
    return {
        v.object_id: v
        for v in rewizja.version_set.all()
        if v.content_type.model_class() is model_powiazany and _nalezy(v, obj, menedzer)
    }


def _zmienione_pola(model, w1, w2, fmt):
    pomijane = POLA_TECHNICZNE_POZYCJI
    zmiany = []
    for pole in _pola_modelu(model, pomijane):
        a, b = (
            w1.field_dict.get(pole.attname, BRAK),
            w2.field_dict.get(pole.attname, BRAK),
        )
        if a != b and fmt.wartosc(pole, a) != fmt.wartosc(pole, b):
            zmiany.append((_etykieta(pole), fmt.wartosc(pole, a), fmt.wartosc(pole, b)))
    return zmiany


def _wiersze_list(model, obj, wersja1, wersja2, fmt):
    for akcesor in FOLLOW_REVERSION.get(model, ()):
        menedzer = getattr(obj, akcesor)
        powiazany = menedzer.model
        e1 = _elementy(wersja1.revision, powiazany, obj, menedzer)
        e2 = _elementy(wersja2.revision, powiazany, obj, menedzer)
        usuniete = [e1[k] for k in e1.keys() - e2.keys()]
        dodane = [e2[k] for k in e2.keys() - e1.keys()]
        zmienione = [
            (e1[k], e2[k], _zmienione_pola(powiazany, e1[k], e2[k], fmt))
            for k in e1.keys() & e2.keys()
            if e1[k].field_dict != e2[k].field_dict
        ]
        zmienione = [z for z in zmienione if z[2]]
        if not (usuniete or dodane or zmienione):
            continue
        bez_zmian = len(e1.keys() & e2.keys()) - len(zmienione)
        lewa, prawa = [], []
        for w in sorted(usuniete, key=lambda v: v.object_repr):
            lewa.append(format_html("<li><del>{}</del></li>", w.object_repr))
        for w in sorted(dodane, key=lambda v: v.object_repr):
            prawa.append(format_html("<li><ins>{}</ins></li>", w.object_repr))
        for w1, w2, pola in sorted(zmienione, key=lambda z: z[1].object_repr):
            lewa.append(
                format_html(
                    "<li>{}<ul>{}</ul></li>",
                    w1.object_repr,
                    format_html_join(
                        "", "<li>{}: <del>{}</del></li>", ((e, s) for e, s, _ in pola)
                    ),
                )
            )
            prawa.append(
                format_html(
                    "<li>{}<ul>{}</ul></li>",
                    w2.object_repr,
                    format_html_join(
                        "", "<li>{}: <ins>{}</ins></li>", ((e, n) for e, _, n in pola)
                    ),
                )
            )
        stopka = (
            format_html(
                '<p class="bpp-bez-zmian">pozostałe bez zmian: {}</p>', bez_zmian
            )
            if bez_zmian
            else ""
        )
        yield {
            "etykieta": str(powiazany._meta.verbose_name_plural)[:1].upper()
            + str(powiazany._meta.verbose_name_plural)[1:],
            "stare": format_html("<ul>{}</ul>{}", mark_safe("".join(lewa)), stopka),
            "nowe": format_html("<ul>{}</ul>{}", mark_safe("".join(prawa)), stopka),
            "lista": True,
        }


def porownaj_wersje(model, obj, wersja1, wersja2, pomijane):
    """Wiersze porównania ``wersja1`` (starsza) z ``wersja2`` (nowsza)."""
    fmt = Formatowanie()
    return [
        *_wiersze_pol(model, wersja1, wersja2, set(pomijane), fmt),
        *_wiersze_list(model, obj, wersja1, wersja2, fmt),
    ]
