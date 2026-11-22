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


#: Pola autorstwa pokazywane bez etykiety, zaraz po nazwisku autora.
POLA_OPISU_AUTORA = ("jednostka", "typ_odpowiedzialnosci")


def _opis_pozycji(model, wersja, fmt, pelny=True):
    """Czytelny opis pozycji listy. Dla autorstw (model z polem ``autor``):
    nazwisko autora, a w pełnym opisie także jednostka, typ
    odpowiedzialności i WSZYSTKIE pozostałe dane autorstwa (dyscyplina,
    afiliacja, zatrudnienie, procent…) — zamiast ``__str__`` wiersza
    („autor - skrót jednostki”). Dla pozostałych — nazwa obiektu."""
    pola = {f.name: f for f in model._meta.concrete_fields}
    if "autor" not in pola:
        return wersja.object_repr
    stan = wersja.field_dict

    def wartosc(nazwa):
        return fmt.wartosc(pola[nazwa], stan.get(pola[nazwa].attname))

    autor = wartosc("autor")
    if not pelny:
        return autor
    glowne = [wartosc(n) for n in POLA_OPISU_AUTORA if n in pola and wartosc(n) != "—"]
    pomijane = POLA_TECHNICZNE_POZYCJI | {"autor", "kolejnosc", *POLA_OPISU_AUTORA}
    reszta = [
        f"{_etykieta(pole)}: {fmt.wartosc(pole, stan.get(pole.attname))}"
        for pole in _pola_modelu(model, pomijane)
        if fmt.wartosc(pole, stan.get(pole.attname)) != "—"
    ]
    opis = autor + (f" — {', '.join(glowne)}" if glowne else "")
    if reszta:
        opis += f" ({'; '.join(reszta)})"
    return opis


def _zmienione_pola(model, w1, w2, fmt):
    pomijane = POLA_TECHNICZNE_POZYCJI | {"kolejnosc"}
    zmiany = []
    for pole in _pola_modelu(model, pomijane):
        a, b = (
            w1.field_dict.get(pole.attname, BRAK),
            w2.field_dict.get(pole.attname, BRAK),
        )
        if a != b and fmt.wartosc(pole, a) != fmt.wartosc(pole, b):
            zmiany.append((_etykieta(pole), fmt.wartosc(pole, a), fmt.wartosc(pole, b)))
    return zmiany


def _pozycje(elementy, klucz):
    """Numer pozycji (od 1) każdej pozycji listy w kolejności modelu."""
    return {
        v.object_id: nr
        for nr, v in enumerate(sorted(elementy.values(), key=klucz), start=1)
    }


def _wiersze_list(model, obj, wersja1, wersja2, fmt):
    for akcesor in FOLLOW_REVERSION.get(model, ()):
        menedzer = getattr(obj, akcesor)
        powiazany = menedzer.model
        e1 = _elementy(wersja1.revision, powiazany, obj, menedzer)
        e2 = _elementy(wersja2.revision, powiazany, obj, menedzer)
        klucz = _klucz_kolejnosci(powiazany)
        poz1, poz2 = _pozycje(e1, klucz), _pozycje(e2, klucz)
        usuniete = [e1[k] for k in e1.keys() - e2.keys()]
        dodane = [e2[k] for k in e2.keys() - e1.keys()]
        zmienione = []
        for k in e1.keys() & e2.keys():
            pola = _zmienione_pola(powiazany, e1[k], e2[k], fmt)
            if poz1[k] != poz2[k]:
                pola.insert(0, ("Pozycja na liście", str(poz1[k]), str(poz2[k])))
            if pola:
                zmienione.append((e2[k], pola))
        etykiety_zmian = {w.object_id: {e for e, _a, _b in p} for w, p in zmienione}
        if not (usuniete or dodane or zmienione):
            continue
        bez_zmian = len(e1.keys() & e2.keys()) - len(zmienione)

        def krotki(w, model=powiazany):
            return _opis_pozycji(model, w, fmt, pelny=False)

        zmiana = [
            *(
                format_html("<li><del>− {}</del></li>", krotki(w))
                for w in sorted(usuniete, key=klucz)
            ),
            *(
                format_html("<li><ins>+ {}</ins></li>", krotki(w))
                for w in sorted(dodane, key=klucz)
            ),
            *(
                format_html(
                    "<li>{}<ul>{}</ul></li>",
                    krotki(w2),
                    format_html_join(
                        "",
                        "<li>{}: <del>{}</del> → <ins>{}</ins></li>",
                        pola,
                    ),
                )
                for w2, pola in sorted(zmienione, key=lambda z: klucz(z[0]))
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
            "stare": _lista(e1, e2, klucz, powiazany, fmt, etykiety_zmian, "stara"),
            "zmiana": format_html("<ul>{}</ul>", mark_safe("".join(zmiana))),
            "nowe": _lista(e2, e1, klucz, powiazany, fmt, etykiety_zmian, "nowa"),
            "lista": True,
        }


def _klucz_kolejnosci(model):
    """Klucz sortowania pozycji z wersji wg domyślnego porządku modelu
    (``Meta.ordering`` — u autorów ``kolejnosc``), a nie alfabetycznie:
    zmiana kolejności autorów musi być widać w porównaniu."""
    pola = []
    for nazwa in model._meta.ordering or ():
        if not isinstance(nazwa, str) or "__" in nazwa or nazwa == "?":
            continue
        try:
            pola.append(model._meta.get_field(nazwa.lstrip("-")).attname)
        except LookupError:
            continue

    def klucz(wersja):
        wartosci = tuple(
            (wartosc is None, wartosc if wartosc is not None else 0)
            for wartosc in (wersja.field_dict.get(p) for p in pola)
        )
        return (wartosci, wersja.object_repr)

    return klucz


def _nazwa_pozycji(model, wersja, fmt):
    """Nagłówek pozycji listy: nazwisko autora (autorstwa) albo nazwa."""
    pole = next((f for f in model._meta.concrete_fields if f.name == "autor"), None)
    if pole is None:
        return wersja.object_repr
    return fmt.wartosc(pole, wersja.field_dict.get(pole.attname))


def _pola_pozycji(model, wersja, fmt, zmienione):
    """(etykieta, wartość, czy_zmienione) — wszystkie dane pozycji listy
    z etykietami, bez pól technicznych i bez tego, co jest w nagłówku."""
    pomijane = POLA_TECHNICZNE_POZYCJI | {"autor", "kolejnosc"}
    for pole in _pola_modelu(model, pomijane):
        wartosc = fmt.wartosc(pole, wersja.field_dict.get(pole.attname))
        etykieta = _etykieta(pole)
        if wartosc == "—" and etykieta not in zmienione:
            continue
        yield etykieta, wartosc, etykieta in zmienione


def _lista(elementy, inne, klucz, model, fmt, zmienione, strona):
    """Numerowana lista pozycji z jednej wersji (kolumna boczna), w kolejności
    modelu. Pozycje dodane/usunięte i zmienione — z danymi z etykietami
    (zmienione pola podświetlone), pozostałe — sama nazwa „bez zmian”.

    ``inne`` — pozycje z drugiej wersji; ``zmienione`` — {object_id:
    zbiór etykiet zmienionych pól}; ``strona`` — "stara" albo "nowa"."""
    if not elementy:
        return "—"
    wiersze = []
    for wersja in sorted(elementy.values(), key=klucz):
        nazwa = _nazwa_pozycji(model, wersja, fmt)
        tylko_tu = wersja.object_id not in inne
        etykiety = zmienione.get(wersja.object_id, set())
        if not tylko_tu and not etykiety:
            wiersze.append(
                format_html(
                    '<li>{} <span class="bpp-przygaszony">— bez zmian</span></li>',
                    nazwa,
                )
            )
            continue
        if tylko_tu:
            znacznik = (
                '<span class="bpp-znacznik-usunieta">usunięty w nowszej wersji</span>'
                if strona == "stara"
                else '<span class="bpp-znacznik-dodana">dodany w nowszej wersji</span>'
            )
        else:
            znacznik = '<span class="bpp-znacznik-zmiana">zmieniony</span>'
        pola = format_html_join(
            "",
            '<li{}><span class="bpp-etykieta-pola">{}:</span> {}</li>',
            (
                (mark_safe(' class="bpp-pole-zmienione"') if zm else "", e, w)
                for e, w, zm in _pola_pozycji(model, wersja, fmt, etykiety)
            ),
        )
        wiersze.append(
            format_html(
                '<li class="bpp-pozycja"><strong>{}</strong> {}'
                '<ul class="bpp-pola-pozycji">{}</ul></li>',
                nazwa,
                mark_safe(znacznik),
                pola,
            )
        )
    return format_html("<ol>{}</ol>", mark_safe("".join(wiersze)))


def porownaj_wersje(model, obj, wersja1, wersja2, pomijane):
    """Wiersze porównania ``wersja1`` (starsza) z ``wersja2`` (nowsza)."""
    fmt = Formatowanie()
    return [
        *_wiersze_pol(model, wersja1, wersja2, set(pomijane), fmt),
        *_wiersze_list(model, obj, wersja1, wersja2, fmt),
    ]
