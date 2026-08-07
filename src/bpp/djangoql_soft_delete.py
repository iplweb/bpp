"""Domyślne odsiewanie kosza (soft-delete) w zapytaniach DjangoQL.

DECYZJA (2026-08-07) — ZMIANA WCZEŚNIEJSZEJ
===========================================

Przy naprawie wycieku ORM (commit ``e80d1656e``) DjangoQL zostawiono
świadomie surowy, z uzasadnieniem „język zapytań użytkownika jest
narzędziem audytowym, ma widzieć kosz". Właściciel projektu zdecydował
inaczej: **domyślnie kosz ma być niewidoczny**, a audyt ma być czynnością
JAWNĄ. Ten moduł realizuje tę decyzję.

KONTRAKT DLA UŻYTKOWNIKA — jak zobaczyć kosz
============================================

Regułą steruje sam tekst zapytania, per ŚCIEŻKA RELACJI:

* zapytanie, które przechodzi przez relację do modelu soft-delete i nie
  wspomina o ``deleted_at`` na tej relacji, dostaje domyślny predykat
  ``<relacja>.deleted_at = None`` (kosz niewidoczny)::

      autorzy_set.autor.nazwisko = "Kowalski"
      # → tylko ŻYWE autorstwa

* wystarczy w zapytaniu wymienić ``deleted_at`` na tej samej ścieżce, żeby
  BPP przestało cokolwiek dokładać — od tego momentu kosz jest w Twoich
  rękach::

      autorzy_set.autor.nazwisko = "Kowalski" and autorzy_set.deleted_at != None
      # → TYLKO kosz (skasowane autorstwa Kowalskiego)

      autorzy_set.autor.nazwisko = "Kowalski" and autorzy_set.deleted_at = None
      # → to samo, co domyślnie (predykat napisany ręcznie)

* zdjęcie predykatu jest PER PREFIKS, nie globalne: w zapytaniu mieszanym
  ``autorzy_set.deleted_at != None and wydawnictwo_zwarte_autor.autor.id = 5``
  kosz odsłania się tylko dla ``autorzy_set``;

* ``<relacja>.deleted_at != None`` znaczy „relacja MA wiersz w koszu"
  (a nie, jak wyszłoby z gołego djangoql, „relacja nie ma wiersza żywego")
  — patrz :func:`_deleted_at_pozytywne`.

DLACZEGO W SCHEMACIE, A NIE W QUERYSECIE BAZOWYM
================================================

Filtr na querysecie bazowym (``qs.filter(deleted_at__isnull=True)``)
załatwia wyłącznie model-korzeń — a ten i tak jest odsiany domyślnym
managerem (``BppSoftDeleteManager``). Problemem, który wracał w fazie 01
trzy razy, jest **JOIN przez relację**: ``filter(autorzy_set__…)`` nie pyta
managera, tylko złącza surową tabelę. Dołożenie predykatu osobnym
``.filter()`` NIE pomaga — Django zrobi wtedy DRUGI, nieskorelowany JOIN
i warunek zdegeneruje się do „istnieje jakiekolwiek żywe autorstwo".
Predykat musi trafić do TEGO SAMEGO ``Q``, które buduje warunek
użytkownika — a jedynym miejscem, gdzie to ``Q`` powstaje, jest
``DjangoQLField.get_lookup()`` zwracane przez ``schema.resolve_name()``.

Stąd wpięcie w ``resolve_name`` — jedno miejsce, które obsługuje WSZYSTKIE
punkty wejścia DjangoQL w BPP naraz: adminy (``BppDjangoQLSearchMixin``),
widok „Szukaj zapytaniem", ``/api/v1/zapytanie/*``, eksport
multiseek→DjangoQL oraz rozbicie „dlaczego 0 wyników"
(``djangoql.breakdown`` woła ``build_filter`` bezpośrednio).

ZAKRES — introspekcja, nie lista nazw
=====================================

Modele objęte odsiewaniem wykrywamy przez ``issubclass(model,
SoftDeleteModel)``. Dziś to trzy through-modele ``*_Autor``; gdy faza 02
uczyni soft-delete pięć modeli publikacji, ten moduł nie wymaga ŻADNEJ
zmiany.

ZNANE ŚLEPE PLAMY (świadome)
============================

* **M2M przez soft-delete through-model** — ``Autor.wydawnictwo_ciagle``
  idzie przez ``Wydawnictwo_Ciagle_Autor``, ale ``related_model`` tej
  relacji to ``Wydawnictwo_Ciagle`` (nie soft-delete), a Django nie
  pozwala dołożyć warunku na tabelę pośrednią w ścieżce M2M. Ekwiwalent
  z predykatem: ``wydawnictwo_ciagle_autor.rekord.…`` (through jawnie).
* **porównanie samej relacji z None** — ``autorzy_set != None`` nie
  dostaje predykatu, bo ``resolve_name()`` zwraca dla takiej ścieżki
  ``None`` (djangoql buduje wtedy pole abstrakcyjne poza naszym zasięgiem).
  Ekwiwalent z predykatem: ``autorzy_set.id != None``.
* **operatory negujące na ścieżce relacyjnej** (``autorzy_set.autor.id !=
  5``) — predykat NIE jest dokładany. Django świadomie DEKORELUJE negację
  na relacji wielowartościowej: ``~Q(A) & Q(B)`` kompiluje się do
  ``NOT (EXISTS(A) AND EXISTS(B))`` z dwoma NIEZALEŻNYMI podzapytaniami
  (udokumentowana różnica ``exclude()`` vs ``filter()`` — „Spanning
  multi-valued relationships"). Predykat wciągnięty tam pod negację nie
  zawęża wiersza, tylko dokłada osobny warunek „istnieje jakieś żywe
  autorstwo" — czyli zmienia znaczenie zapytania. Poprawne rozwiązanie
  (``exclude(rel__in=Subquery)``) wymagałoby przepisywania ``Q``
  użytkownika i nie da się go zrobić ogólnie na poziomie pola. Tryb awarii
  jest ZACHOWAWCZY: skasowany wiersz może spowodować, że publikacja NIE
  zostanie zwrócona — nigdy odwrotnie, więc treść kosza dalej nie wycieka.
  Predykat na samym modelu-korzeniu (bez JOIN-u) działa też pod negacją.
* **agregaty relacyjne** (``autorzy_set__count``) — NIE są ślepą plamą,
  ale obsługuje je inny mechanizm: podmiana managera źródłowego
  podzapytania (:func:`_agregat_bez_skasowanych`), bo agregat nie filtruje
  JOIN-em.
"""

import copy

from django.db.models import Q
from django_softdelete.models import SoftDeleteModel

#: Nazwa pola-znacznika soft-delete (``django-soft-delete``).
POLE_SOFT_DELETE = "deleted_at"

#: Operatory DjangoQL, dla których ``DjangoQLField.get_lookup()`` zwraca
#: ``~Q`` (kopia negatywnej połowy mapy z ``DjangoQLField.get_operator``).
#: Predykatu NIE dokładamy do nich na ścieżkach relacyjnych — patrz
#: „Znane ślepe plamy" w docstringu modułu.
OPERATORY_NEGUJACE = frozenset({"!=", "!~", "not in", "not startswith", "not endswith"})


def jest_modelem_soft_delete(model) -> bool:
    """Czy ``model`` jest modelem soft-delete (ma kolumnę ``deleted_at``)?"""
    return isinstance(model, type) and issubclass(model, SoftDeleteModel)


def prefiksy_z_jawnym_deleted_at(node) -> frozenset:
    """Prefiksy ścieżek, na których UŻYTKOWNIK sam wspomniał ``deleted_at``.

    Czysto składniowe — chodzi o intencję („pytam o kosz"), nie o to, czy
    pole istnieje; walidację i tak zrobi zaraz potem sam djangoql. Dzięki
    temu funkcja nie może wysypać się wcześniej niż walidator i nie musi
    znać modeli.
    """
    operator = getattr(node, "operator", None)
    if getattr(operator, "operator", None) in ("and", "or"):
        return prefiksy_z_jawnym_deleted_at(node.left) | prefiksy_z_jawnym_deleted_at(
            node.right
        )
    parts = getattr(getattr(node, "left", None), "parts", None)
    if parts and parts[-1] == POLE_SOFT_DELETE:
        return frozenset({tuple(parts[:-1])})
    return frozenset()


def _prefiksy_soft_delete(schema, parts):
    """Prefiksy ścieżki ``parts``, na których zapytanie WCHODZI w model
    soft-delete. ``()`` oznacza sam model-korzeń.

    Odwzorowuje trawersację z ``DjangoQLSchema.resolve_name()`` (łącznie z
    hakiem ``resolve_unknown`` na wirtualne pola). Przy nieznanym członie
    kończy cicho — komunikat błędu jest zadaniem ``resolve_name()``.
    """
    prefiksy = []
    if jest_modelem_soft_delete(schema.current_model):
        prefiksy.append(())

    etykieta = schema.model_label(schema.current_model)
    model_cls = schema.current_model
    poprzednia_relacja = None
    for i, czlon in enumerate(parts):
        pole = schema.models.get(etykieta, {}).get(czlon)
        if pole is None:
            pole = schema.resolve_unknown(model_cls, poprzednia_relacja, czlon)
        if pole is None:
            break
        if pole.type == "relation":
            poprzednia_relacja = pole
            etykieta = pole.relation
            model_cls = pole.related_model
            if jest_modelem_soft_delete(model_cls):
                prefiksy.append(tuple(parts[: i + 1]))
        else:
            poprzednia_relacja = None
    return prefiksy


class _ZrodloBezSkasowanych:
    """Podstawka pod ``AggregateField.related_model`` w podzapytaniu agregatu.

    ``djangoql.extras.AggregateField._subquery()`` buduje skorelowane
    podzapytanie z ``self.related_model._base_manager``. ``_base_manager``
    Django to goły ``Manager()`` — NIE nasz ``BppSoftDeleteManager`` —
    więc ``autorzy_set__count`` liczyłby również kosz. Podstawiamy obiekt,
    którego ``_base_manager`` to manager odsiewający.

    Świadomie WĄSKA atrapa: gdyby djangoql zaczął sięgać po inny atrybut
    modelu, dostaniemy głośny ``AttributeError`` zamiast cichego powrotu
    do liczenia kosza.
    """

    def __init__(self, model):
        self._base_manager = model.objects


def _deleted_at_pozytywne(pole):
    """Kopia pola ``deleted_at``, w której ``!= None`` znaczy „ma wiersz w
    koszu", a nie „nie ma wiersza żywego".

    DLACZEGO: djangoql tłumaczy ``!=`` na ``~Q(...)``, a Django kompiluje
    negację na relacji wielowartościowej jako ``NOT EXISTS(...)`` — więc
    ``autorzy_set.deleted_at != None`` znaczyłoby „publikacja NIE MA
    żadnego żywego autorstwa". Dla publikacji z jednym autorstwem
    skasowanym i drugim żywym dałoby to pustkę, choć użytkownik pytał o
    kosz. Wersja pozytywna (``deleted_at__isnull=False``) jest
    skorelowana z tym samym JOIN-em, co reszta warunków użytkownika, więc
    ``autorzy_set.autor.id = 5 and autorzy_set.deleted_at != None``
    naprawdę znajduje skasowane autorstwo autora 5.

    Odstępstwo od djangoql jest WĄSKIE: dotyczy wyłącznie pola
    ``deleted_at`` na modelu soft-delete i wyłącznie porównania z ``None``.
    """
    oryginalny_lookup = pole.get_lookup
    kopia = copy.copy(pole)

    def get_lookup(path, operator, value):
        if value is None and operator in ("=", "!="):
            klucz = "__".join((*path, POLE_SOFT_DELETE, "isnull"))
            return Q(**{klucz: operator == "="})
        return oryginalny_lookup(path, operator, value)

    kopia.get_lookup = get_lookup
    return kopia


def _jest_agregatem_po_soft_delete(pole) -> bool:
    """Czy ``pole`` to agregat relacyjny djangoql (``<rel>__count``,
    ``<rel>.<pole>__sum``) liczony po modelu soft-delete?

    Rozpoznajemy po atrybutach ``AggregateField`` (``owner_lookup`` +
    ``relation_name``), a nie po ``isinstance`` — żeby nie importować
    prywatnych klas ``djangoql.extras``.
    """
    return (
        hasattr(pole, "owner_lookup")
        and hasattr(pole, "relation_name")
        and jest_modelem_soft_delete(getattr(pole, "related_model", None))
    )


def prefiks_agregatu(pole, parts) -> tuple:
    """Ścieżka relacji, po której liczony jest agregat — do porównania z
    prefiksami, na których użytkownik jawnie pyta o kosz.

    Nazwa płaska (``autorzy_set__count``) NIE zawiera relacji w ścieżce,
    notacja z kropką (``autorzy_set.procent__sum``) — zawiera
    (``relation_hop_in_path``).
    """
    poczatek = tuple(parts[:-1])
    if getattr(pole, "relation_hop_in_path", False):
        return poczatek
    return poczatek + (pole.relation_name,)


def _agregat_bez_skasowanych(pole):
    """Kopia agregatu, którego podzapytanie liczy TYLKO żywe wiersze.

    Agregat nie filtruje JOIN-em, tylko skorelowanym podzapytaniem po
    ``related_model._base_manager`` — dokładanie predykatu do ``Q``
    dołożyłoby osobny, nieskorelowany warunek na zewnętrznym zapytaniu i
    nie zmieniłoby wartości licznika. Odsiewamy więc ŹRÓDŁO podzapytania.
    """
    kopia = copy.copy(pole)
    kopia.related_model = _ZrodloBezSkasowanych(pole.related_model)
    return kopia


def _z_predykatem_soft_delete(pole, prefiksy):
    """Kopia pola DjangoQL, której ``get_lookup()`` domyka JOIN-y predykatem
    ``deleted_at IS NULL``.

    Kopiujemy, bo instancje pól są współdzielone w ``schema.models`` między
    wywołaniami — mutacja oryginału przeciekłaby na zapytania, które o kosz
    poprosiły jawnie.
    """
    oryginalny_lookup = pole.get_lookup
    kopia = copy.copy(pole)

    predykat = Q()
    #: Osobno część „na własnej tabeli" (prefiks ``()``, czyli model-korzeń)
    #: — ta jedna jest bezpieczna także pod negacją, bo nie tworzy JOIN-u.
    predykat_korzenia = Q()
    for prefiks in prefiksy:
        klucz = "__".join((*prefiks, POLE_SOFT_DELETE, "isnull"))
        czesc = Q(**{klucz: True})
        predykat &= czesc
        if not prefiks:
            predykat_korzenia &= czesc

    def get_lookup(path, operator, value):
        q = oryginalny_lookup(path, operator, value)
        if operator in OPERATORY_NEGUJACE:
            return q & predykat_korzenia
        return q & predykat

    kopia.get_lookup = get_lookup
    return kopia


class WykluczSkasowaneMixin:
    """Domyślnie odsiewa rekordy soft-delete z zapytań DjangoQL.

    Musi stać PRZED klasą bazową schematu w MRO. Szczegóły kontraktu —
    docstring modułu.
    """

    def __init__(self, model):
        # Bezpieczny domyślny stan: „użytkownik o kosz nie prosił".
        # Ustawiane przed ``super()``, bo konstruktor bazy robi
        # introspekcję i może wołać metody schematu.
        self._jawne_prefiksy_soft_delete = frozenset()
        self._ast_zbadany = False
        super().__init__(model)

    def validate(self, node):
        """Zapamiętaj prefiksy, na których użytkownik JAWNIE pyta o kosz.

        ``apply_search()`` woła ``validate()`` z CAŁYM drzewem zanim
        zbuduje filtr, a ``djangoql.breakdown`` — z każdym podzapytaniem
        osobno; w obu wypadkach pierwszy węzeł, jaki widzimy, jest
        korzeniem tego, co zaraz zostanie wykonane. ``validate()`` rekuruje
        po sobie, więc analizę robimy tylko raz (``_ast_zbadany``).
        """
        if not self._ast_zbadany:
            self._ast_zbadany = True
            self._jawne_prefiksy_soft_delete = prefiksy_z_jawnym_deleted_at(node)
        return super().validate(node)

    def resolve_name(self, name):
        pole = super().resolve_name(name)
        if pole is None:
            return None
        if _jest_agregatem_po_soft_delete(pole):
            # Agregat obsługujemy WYŁĄCZNIE podmianą źródła podzapytania —
            # predykat na JOIN-ie nie zmieniłby wartości licznika, a dołożyłby
            # zewnętrzny warunek „istnieje żywy wiersz".
            if prefiks_agregatu(pole, name.parts) in self._jawne_prefiksy_soft_delete:
                return pole
            return _agregat_bez_skasowanych(pole)

        wszystkie = _prefiksy_soft_delete(self, name.parts)
        if name.parts[-1] == POLE_SOFT_DELETE and tuple(name.parts[:-1]) in wszystkie:
            # Samo ``deleted_at`` na modelu soft-delete: predykatu nie
            # dokładamy (to jest właśnie jawne pytanie o kosz), ale
            # naprawiamy semantykę ``!= None``.
            return _deleted_at_pozytywne(pole)

        prefiksy = [
            prefiks
            for prefiks in wszystkie
            if prefiks not in self._jawne_prefiksy_soft_delete
        ]
        if not prefiksy:
            return pole
        return _z_predykatem_soft_delete(pole, prefiksy)
