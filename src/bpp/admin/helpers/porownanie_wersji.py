"""Czytelne porównanie dwóch wersji rekordu (FD#587).

Zastępuje domyślny diff reversion-compare (różnice znak po znaku, surowe
``repr``, każde pole w osobnym bloku) tabelą „pole | wersja starsza |
zmiana | wersja nowsza”:

* tylko pola, które się zmieniły, z etykietami jak w formularzu,
* kolumny boczne — pełne wartości z obu wersji (bez skreśleń), wartości po
  ludzku: nazwy ze słowników zamiast numerów, „tak/nie”, daty po polsku,
  „—” dla pustych,
* kolumna „zmiana” — sama różnica: w tekstach usunięte słowa w ``del``
  i dodane w ``ins``, w pozostałych polach „stare → nowe”,
* listy śledzone razem z rekordem (autorzy, granty, pliki…): po bokach
  pełne listy z obu wersji, w środku pozycje usunięte (−), dodane (+)
  i zmienione z konkretnymi polami, np. „Afiliuje: tak → nie”.
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


#: Słowa i odstępy jako osobne tokeny.
_SLOWA = re.compile(r"\S+|\s+")


def _kawalki(stary, nowy):
    """Lista (wspólne, usunięte, dodane) kawałków tekstu. Sam odstęp między
    dwiema zmianami jest doklejany do zmiany — zamiana kilku słów daje
    jeden blok ``del``/``ins``, a nie osobny na każde słowo."""
    a, b = _SLOWA.findall(stary), _SLOWA.findall(nowy)
    surowe = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, a, b, autojunk=False
    ).get_opcodes():
        surowe.append((op == "equal", "".join(a[i1:i2]), "".join(b[j1:j2])))
    wynik = []
    for nr, (rowne, tekst_a, tekst_b) in enumerate(surowe):
        odstep_miedzy_zmianami = (
            rowne
            and not tekst_a.strip()
            and 0 < nr < len(surowe) - 1
            and not surowe[nr - 1][0]
            and not surowe[nr + 1][0]
        )
        if odstep_miedzy_zmianami:
            rowne = False
        if wynik and not rowne and not wynik[-1][0]:
            _, poprz_a, poprz_b = wynik[-1]
            wynik[-1] = (False, poprz_a + tekst_a, poprz_b + tekst_b)
        else:
            wynik.append((rowne, tekst_a, tekst_b))
    return wynik


def diff_slow(stary, nowy):
    """Jeden tekst z różnicami: słowa usunięte w ``del``, dodane w ``ins``,
    wspólne bez zmian — do środkowej kolumny „zmiana”."""
    wynik = []
    for rowne, tekst_a, tekst_b in _kawalki(stary, nowy):
        if rowne:
            wynik.append(escape(tekst_a))
            continue
        if tekst_a.strip():
            wynik.append(f"<del>{escape(tekst_a)}</del>")
        if tekst_b.strip():
            wynik.append(f"<ins>{escape(tekst_b)}</ins>")
        if not tekst_a.strip() and not tekst_b.strip():
            wynik.append(escape(tekst_b))
    return mark_safe("".join(wynik))


def _tekstowe(pole):
    return (
        isinstance(pole, (models.CharField, models.TextField))
        and not pole.is_relation
        and not getattr(pole, "choices", None)
    )


def _zmiana(pole, stary, nowy):
    """Środkowa kolumna dla zwykłego pola: w tekstach diff słów, w
    wartościach ze słowników, liczbach, datach, tak/nie — „stare → nowe”."""
    if _tekstowe(pole) and stary != "—" and nowy != "—":
        return diff_slow(stary, nowy)
    if stary == "—":
        return format_html(
            '<ins>{}</ins> <span class="bpp-przygaszony">(dodano)</span>', nowy
        )
    if nowy == "—":
        return format_html(
            '<del>{}</del> <span class="bpp-przygaszony">(usunięto)</span>', stary
        )
    return format_html("<del>{}</del> → <ins>{}</ins>", stary, nowy)


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
        yield {
            "etykieta": _etykieta(pole),
            "stare": stary,
            "zmiana": _zmiana(pole, stary, nowy),
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
        zmiana = [
            *(
                format_html("<li><del>− {}</del></li>", w.object_repr)
                for w in sorted(usuniete, key=lambda v: v.object_repr)
            ),
            *(
                format_html("<li><ins>+ {}</ins></li>", w.object_repr)
                for w in sorted(dodane, key=lambda v: v.object_repr)
            ),
            *(
                format_html(
                    "<li>{}<ul>{}</ul></li>",
                    w2.object_repr,
                    format_html_join(
                        "",
                        "<li>{}: <del>{}</del> → <ins>{}</ins></li>",
                        pola,
                    ),
                )
                for _w1, w2, pola in sorted(zmienione, key=lambda z: z[1].object_repr)
            ),
        ]
        if bez_zmian:
            zmiana.append(
                format_html(
                    '<li class="bpp-bez-zmian">pozostałe bez zmian: {}</li>',
                    bez_zmian,
                )
            )
        nazwa = str(powiazany._meta.verbose_name_plural)
        yield {
            "etykieta": nazwa[:1].upper() + nazwa[1:],
            "stare": _lista(e1),
            "zmiana": format_html("<ul>{}</ul>", mark_safe("".join(zmiana))),
            "nowe": _lista(e2),
            "lista": True,
        }


def _lista(elementy):
    """Pełna lista pozycji z jednej wersji (kolumny boczne)."""
    if not elementy:
        return "—"
    return format_html(
        "<ul>{}</ul>",
        format_html_join(
            "",
            "<li>{}</li>",
            (
                (v.object_repr,)
                for v in sorted(elementy.values(), key=lambda v: v.object_repr)
            ),
        ),
    )


def porownaj_wersje(model, obj, wersja1, wersja2, pomijane):
    """Wiersze porównania ``wersja1`` (starsza) z ``wersja2`` (nowsza)."""
    fmt = Formatowanie()
    return [
        *_wiersze_pol(model, wersja1, wersja2, set(pomijane), fmt),
        *_wiersze_list(model, obj, wersja1, wersja2, fmt),
    ]
