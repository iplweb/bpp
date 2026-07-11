"""Wspólny schemat DjangoQL dla BPP — auto-pickery ``<fk>__rel``.

Trzon współdzielony przez widok „Szukaj zapytaniem" (`bpp.views.zapytanie`) i
adminy z ``DjangoQLSearchMixin`` (ustawiają ``djangoql_schema = BppQLSchema``).

Idea: dla KAŻDEGO klucza obcego (FK) modelu, którego model docelowy ma
pole-etykietę (nazwa/skrot/tytuł/opis bibliograficzny…), auto-generujemy
„picker" pod nazwą ``<fk>__rel``. Wybierasz obiekt z podpowiedzi i filtruje po
jego pk (``lookup_name`` wskazuje realny FK), z fallbackiem free-text (icontains
po polach-etykietach). Notacja z kropką (``zrodlo.nazwa``) zostaje domyślna dla
FK — picker tylko ją uzupełnia.

Lookup nie podpowiada ukrytych: queryset filtruje boolowskie pola widoczności
(``widoczny``/``widoczna``/``widoczne``/``visible``/``enabled``/``pokazuj`` =
True, ``disabled``/``ukryty``… = False). FK do modeli bez pola-etykiety
(np. ``pbn_uid`` → ``Journal``) oraz rodzic ``rekord`` (cache/through) są
pomijane.
"""

from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models import Q
from django.utils.html import strip_tags
from djangoql.extras import AutocompleteField, ExtrasSchema

from bpp.models import Charakter_Formalny, Jednostka

#: Pola-etykiety wg priorytetu — czym opisać i po czym szukać obiekt w pickerze.
#: Opis bibliograficzny jako pierwszy: dla publikacji jest najczytelniejszy.
_LABEL_FIELDS = (
    "opis_bibliograficzny_cache",
    "nazwa",
    "skrot",
    "tytul_oryginalny",
    "nazwisko",
    "imiona",
    "kod",
)
#: Boolowskie pola widoczności: widoczne, gdy True.
_VISIBLE_WHEN_TRUE = (
    "widoczny",
    "widoczna",
    "widoczne",
    "visible",
    "enabled",
    "pokazuj",
)
#: Boolowskie pola „ukrycia": widoczne, gdy False.
_VISIBLE_WHEN_FALSE = ("disabled", "ukryty", "ukryta", "ukryte")
_REL_SUFFIX = "__rel"
#: FK pomijane (rodzic cache/through — pickowanie rodzica nie ma sensu).
_SKIP_FK = ("rekord",)
#: Wirtualne pole: picker po Jednostce dopasowujący rodzinę MPTT.
_SUBUNITS_FIELD = "jednostka_z_podjednostkami__rel"
#: Wirtualne pole: picker po Charakterze Formalnym dopasowujący MPTT-descendants.
_CHARAKTER_SUB_FIELD = "charakter_z_podrzednymi__rel"


def _field_names(model):
    return {f.name for f in model._meta.get_fields() if isinstance(f, models.Field)}


def _label_fields(model):
    """Pola-etykiety modelu (przecięcie z ``_LABEL_FIELDS``, wg priorytetu)."""
    names = _field_names(model)
    return [f for f in _LABEL_FIELDS if f in names]


def _is_bool_field(model, name):
    try:
        return isinstance(model._meta.get_field(name), models.BooleanField)
    except FieldDoesNotExist:
        return False


def _visible_qs(model):
    """Queryset modelu z odfiltrowanymi niewidocznymi pozycjami."""
    qs = model.objects.all()
    for name in _VISIBLE_WHEN_TRUE:
        if _is_bool_field(model, name):
            qs = qs.filter(**{name: True})
    for name in _VISIBLE_WHEN_FALSE:
        if _is_bool_field(model, name):
            qs = qs.filter(**{name: False})
    return qs


def _picker_label(model):
    """Callable ``obj -> etykieta`` dla pickera; dla publikacji preferuje opis
    bibliograficzny (bez HTML). ``None`` → AutocompleteField użyje ``str(obj)``."""
    if "opis_bibliograficzny_cache" in _field_names(model):

        def label(obj):
            return strip_tags(getattr(obj, "opis_bibliograficzny_cache", "") or "")

        return label
    return None


def _picker_fks(model):
    """FK (many_to_one) modelu nadające się na picker — model docelowy ma
    pole-etykietę i nie jest to pomijany rodzic ``rekord``."""
    out = []
    for f in model._meta.get_fields():
        if not (f.is_relation and getattr(f, "many_to_one", False)):
            continue
        if f.related_model is None or f.name in _SKIP_FK:
            continue
        if not _label_fields(f.related_model):
            continue
        out.append(f)
    return out


class JednostkaZPodjednostkamiField(AutocompleteField):
    """Picker po Jednostce: dopasowuje rekordy autorów z tej jednostki ORAZ
    wszystkich jednostek z jej rodziny MPTT (przodkowie+sama+potomkowie).

    Odwzorowuje multiseek EQUAL_PLUS_SUB_FEMALE:
        Q(autorzy__jednostka__in=value.get_family())
    """

    def get_lookup(self, path, operator, value):
        parsed = self.parse_id(value)
        if not isinstance(parsed, int):
            # free-text fallback po nazwie jednostki (best-effort), uwzględnia operator
            q = Q(autorzy__jednostka__nazwa__icontains=str(value))
            return ~q if operator in ("!=", "not in") else q
        try:
            jednostka = Jednostka.objects.get(pk=parsed)
        except Jednostka.DoesNotExist:
            # Pozytywne dopasowanie: nic nie pasuje. Negacja: pasuje wszystko.
            return Q() if operator in ("!=", "not in") else Q(pk__in=[])
        q = Q(autorzy__jednostka__in=jednostka.get_family())
        return ~q if operator in ("!=", "not in") else q


class CharakterZPodrzednymiField(AutocompleteField):
    """Picker po Charakter_Formalny: dopasowuje rekordy o tym charakterze ORAZ
    wszystkich potomkach w drzewie MPTT (sam + descendants).

    Odwzorowuje CharakterFormalnyQueryObject.real_query:
        Q(charakter_formalny__in=value.get_descendants(include_self=True))
    """

    def get_lookup(self, path, operator, value):
        parsed = self.parse_id(value)
        if not isinstance(parsed, int):
            q = Q(charakter_formalny__nazwa__icontains=str(value))
            return ~q if operator in ("!=", "not in") else q
        try:
            ch = Charakter_Formalny.objects.get(pk=parsed)
        except Charakter_Formalny.DoesNotExist:
            return Q() if operator in ("!=", "not in") else Q(pk__in=[])
        q = Q(charakter_formalny__in=ch.get_descendants(include_self=True))
        return ~q if operator in ("!=", "not in") else q


def _has_autorzy_jednostka(model):
    """True, gdy model ma odwrotną relację 'autorzy' z FK 'jednostka'
    (Rekord/cache)."""
    try:
        rel = model._meta.get_field("autorzy")
    except FieldDoesNotExist:
        return False
    related = getattr(rel, "related_model", None)
    if related is None:
        return False
    return "jednostka" in {
        f.name for f in related._meta.get_fields() if isinstance(f, models.Field)
    }


def _has_charakter_formalny(model):
    """True, gdy model ma FK 'charakter_formalny' (Rekord/cache)."""
    try:
        f = model._meta.get_field("charakter_formalny")
    except FieldDoesNotExist:
        return False
    return getattr(f, "many_to_one", False)


class RelPickerSchemaMixin:
    """Mixin auto-generujący pickery ``<fk>__rel`` (patrz docstring modułu)."""

    def get_fields(self, model):
        fields = list(super().get_fields(model))
        fields += [f.name + _REL_SUFFIX for f in _picker_fks(model)]
        if _has_autorzy_jednostka(model):
            fields.append(_SUBUNITS_FIELD)
        if _has_charakter_formalny(model):
            fields.append(_CHARAKTER_SUB_FIELD)
        return fields

    def get_field_instance(self, model, field_name):
        if field_name == _SUBUNITS_FIELD:
            return JednostkaZPodjednostkamiField(
                model=model,
                name=_SUBUNITS_FIELD,
                nullable=True,
                queryset=_visible_qs(Jednostka),
                search_fields=_label_fields(Jednostka),
            )
        if field_name == _CHARAKTER_SUB_FIELD:
            return CharakterZPodrzednymiField(
                model=model,
                name=_CHARAKTER_SUB_FIELD,
                nullable=True,
                queryset=_visible_qs(Charakter_Formalny),
                search_fields=_label_fields(Charakter_Formalny),
            )
        if field_name.endswith(_REL_SUFFIX):
            fk_name = field_name[: -len(_REL_SUFFIX)]
            try:
                fk = model._meta.get_field(fk_name)
            except FieldDoesNotExist:
                fk = None
            if fk is not None and fk.is_relation and fk.related_model is not None:
                related = fk.related_model
                return AutocompleteField(
                    model=model,
                    name=field_name,
                    lookup_name=fk_name,
                    nullable=getattr(fk, "null", False),
                    queryset=_visible_qs(related),
                    search_fields=_label_fields(related),
                    label=_picker_label(related),
                )
        return super().get_field_instance(model, field_name)


class BppQLSchema(RelPickerSchemaMixin, ExtrasSchema):
    """ExtrasSchema (agregaty + części dat) + auto-pickery ``<fk>__rel``.

    Wspólny dla widoku „Szukaj zapytaniem" i adminów (``djangoql_schema =
    BppQLSchema``). Mapa modeli jest budowana lazy per-model, więc ten sam
    schemat obsługuje dowolny model (Rekord, Autor, Wydawnictwo_*, Patent,
    Praca_Doktorska/Habilitacyjna, …).
    """


# ---------------------------------------------------------------------------
# Ograniczony schemat (allow-lista) — rdzeń bibliograficzny.
#
# Wspólny dla: widoku „Szukaj zapytaniem", walidacji eksportu
# multiseek→DjangoQL oraz eksportu schematu dla LLM. Adminy zostają na pełnym
# ``BppQLSchema``. Szczegóły i uzasadnienie doboru modeli:
# docs/superpowers/specs/2026-07-10-djangoql-schema-dla-llm-design.md
# ---------------------------------------------------------------------------

#: Allow-lista modeli DjangoQL osiągalnych z ``Rekord``: rdzeń bibliograficzny
#: + świadome „ratunki" (identyfikatory PBN, źródło informacji, zatrudnienie).
#: Trzymana jako etykiety ``app_label.Model`` (nie klasy) i rozwiązywana leniwie
#: przez ``apps.get_model`` — dzięki temu nie robimy top-level importów modeli
#: ``pbn_api``/``ewaluacja_common`` (uniknięcie cykli importów).
_SEARCH_ALLOWLIST_LABELS = (
    # rekord + typy publikacji
    "bpp.Rekord",
    "bpp.Wydawnictwo_Ciagle",
    "bpp.Wydawnictwo_Zwarte",
    "bpp.Patent",
    "bpp.Praca_Doktorska",
    "bpp.Praca_Habilitacyjna",
    # autorstwo
    "bpp.Autorzy",
    "bpp.Wydawnictwo_Ciagle_Autor",
    "bpp.Wydawnictwo_Zwarte_Autor",
    "bpp.Patent_Autor",
    "bpp.Autor",
    "bpp.Autor_Dyscyplina",
    "bpp.Autor_Jednostka",
    "bpp.Typ_Odpowiedzialnosci",
    "bpp.Funkcja_Autora",
    "bpp.Tytul",
    "bpp.Plec",
    # struktura organizacyjna
    "bpp.Jednostka",
    "bpp.Wydzial",
    "bpp.Uczelnia",
    "bpp.RodzajJednostki",
    # źródło / miejsce wydania / wydawca
    "bpp.Zrodlo",
    "bpp.Konferencja",
    "bpp.Seria_Wydawnicza",
    "bpp.Wydawca",
    "bpp.Poziom_Wydawcy",
    "bpp.Rodzaj_Zrodla",
    "bpp.Zasieg_Zrodla",
    # słowniki klasyfikacyjne
    "bpp.Charakter_Formalny",
    "bpp.Typ_KBN",
    "bpp.Jezyk",
    "bpp.Dyscyplina_Naukowa",
    "bpp.Status_Korekty",
    # open access
    "bpp.Tryb_OpenAccess_Wydawnictwo_Ciagle",
    "bpp.Tryb_OpenAccess_Wydawnictwo_Zwarte",
    "bpp.Licencja_OpenAccess",
    "bpp.Wersja_Tekstu_OpenAccess",
    "bpp.Czas_Udostepnienia_OpenAccess",
    # patenty
    "bpp.Rodzaj_Prawa_Patentowego",
    # streszczenia i tytuły obcojęzyczne
    "bpp.Wydawnictwo_Ciagle_Streszczenie",
    "bpp.Wydawnictwo_Ciagle_Tytul",
    "bpp.Wydawnictwo_Zwarte_Streszczenie",
    "bpp.Wydawnictwo_Zwarte_Tytul",
    # zewnętrzne bazy danych (widok ZewnetrzneBazyDanychView to rekordowa
    # ścieżka zapytań multiseek „Zewnętrzna baza danych": zewnetrzne_bazy.baza)
    "bpp.Zewnetrzna_Baza_Danych",
    "bpp.ZewnetrzneBazyDanychView",
    "bpp.Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych",
    "bpp.Wydawnictwo_Zwarte_Zewnetrzna_Baza_Danych",
    # słowa kluczowe
    "taggit.Tag",
    # nagrody
    "bpp.Nagroda",
    "bpp.OrganPrzyznajacyNagrody",
    # identyfikatory PBN (ratunek A) + dane dyscyplin
    "pbn_api.Publication",
    "pbn_api.Scientist",
    "pbn_api.Institution",
    "pbn_api.Language",
    "pbn_api.Conference",
    "pbn_api.Publisher",
    "pbn_api.Journal",
    "bpp.Cache_Punktacja_Autora",
    # źródło informacji (ratunek B)
    "bpp.Zrodlo_Informacji",
    # zatrudnienie (ratunek C)
    "bpp.Grupa_Pracownicza",
    "bpp.Wymiar_Etatu",
    "bpp.Kierunek_Studiow",
    # nisze (ratunek D)
    "bpp.Charakter_PBN",
    "ewaluacja_common.Rodzaj_Autora",
)


def _resolve_search_allowlist():
    """Rozwiąż etykiety allow-listy na klasy modeli (leniwie, przez rejestr)."""
    from django.apps import apps

    return tuple(apps.get_model(label) for label in _SEARCH_ALLOWLIST_LABELS)


#: Wspólne źródło prawdy dla obu ograniczonych schematów. Rozwiązywane przy
#: imporcie modułu (a ten importowany jest dopiero po zapełnieniu rejestru
#: aplikacji — z adminów/widoków, nigdy z ``models.py``).
SEARCH_ALLOWLIST = _resolve_search_allowlist()


#: Modele, dla których w schemacie wyszukiwania udostępniamy TYLKO wskazane pola.
#: Uczelnia trzyma hasła (dspace/pbn/clarivate/orcid) i dziesiątki pól-ustawień —
#: w języku zapytań sens ma jedynie identyfikujące nazwa/skrot.
_RESTRICTED_FIELDS_LABELS = {
    "bpp.Uczelnia": ("nazwa", "skrot"),
}


def _restricted_fields():
    """Mapa {klasa modelu: {dozwolone pola}} rozwiązana z etykiet (leniwie)."""
    from django.apps import apps

    return {
        apps.get_model(label): set(names)
        for label, names in _RESTRICTED_FIELDS_LABELS.items()
    }


def _field_name(field):
    """Nazwa pola z pozycji ``get_fields`` — to bywa albo string (nazwa pola),
    albo instancja DjangoQLField (np. ``CountField`` z agregatów)."""
    return field if isinstance(field, str) else getattr(field, "name", "")


def _is_deprecated_field(model, name):
    """Pole do pominięcia w schemacie: ``legacy`` w nazwie albo marker
    „o znaczeniu historycznym" / „[Przestarzałe]" w help_text/verbose_name.

    Nazwy pickerów/agregatów/części dat (``<fk>__rel``, ``<pole>__year``) nie
    mają odpowiednika w ``_meta`` → nie są tykane.
    """
    if not name:
        return False
    if "legacy" in name.lower():
        return True
    try:
        field = model._meta.get_field(name)
    except FieldDoesNotExist:
        return False
    help_text = str(getattr(field, "help_text", "") or "").lower()
    verbose = str(getattr(field, "verbose_name", "") or "").lower()
    return "znaczeniu historyczn" in help_text or "przestarzał" in verbose


class DeprecatedAndRestrictedFieldsMixin:
    """Docina wynik ``get_fields`` KAŻDEGO modelu:

    1. modele z ``_RESTRICTED_FIELDS_LABELS`` (Uczelnia) pokazują tylko wskazane
       pola — bez haseł i ustawień;
    2. pola przestarzałe / ``legacy`` / „o znaczeniu historycznym" znikają
       zewsząd.

    Musi być PIERWSZĄ bazą schematu, żeby filtrować finalną listę pól (już po
    pickerach/agregatach dokładanych przez klasy niżej w MRO). ``get_fields``
    zwraca pozycje mieszane (stringi i instancje pól) — filtrujemy po nazwie,
    zachowując oryginalną pozycję.
    """

    def get_fields(self, model):
        fields = list(super().get_fields(model))
        allowed = _restricted_fields().get(model)
        if allowed is not None:
            return [f for f in fields if _field_name(f) in allowed]
        return [f for f in fields if not _is_deprecated_field(model, _field_name(f))]


class BppQLSchemaOgraniczony(DeprecatedAndRestrictedFieldsMixin, BppQLSchema):
    """``BppQLSchema`` (pickery ``<fk>__rel`` + agregaty) zawężony allow-listą do
    rdzenia bibliograficznego.

    Używany przez widok „Szukaj zapytaniem" oraz walidację eksportu
    multiseek→DjangoQL. Autocomplete i podpowiedzi obejmują tylko modele
    bibliograficzne — bez szumu z pipeline'ów PBN/importu/dedupu/ewaluacji.
    """

    include = SEARCH_ALLOWLIST


#: Modele-słowniki, których wartości WOLNO osadzić w commitowanym artefakcie:
#: standardowe tablice referencyjne BPP — identyczne między instalacjami,
#: niewrażliwe, o wysokiej wartości dydaktycznej dla LLM (uczą dopuszczalnych
#: wartości zapytań). Wszystko poza tą listą (tytuły publikacji, abstrakty,
#: nazwiska, nazwy jednostek, encje PBN) NIE osadza wartości — inaczej do repo
#: open-source trafiłyby dane konkretnej instytucji.
_SAFE_VALUE_TARGET_LABELS = (
    "bpp.Charakter_Formalny",
    "bpp.Typ_KBN",
    "bpp.Jezyk",
    "bpp.Dyscyplina_Naukowa",
    "bpp.Status_Korekty",
    "bpp.Typ_Odpowiedzialnosci",
    "bpp.Funkcja_Autora",
    "bpp.Tytul",
    "bpp.Plec",
    "bpp.RodzajJednostki",
    "bpp.Rodzaj_Zrodla",
    "bpp.Zasieg_Zrodla",
    "bpp.Poziom_Wydawcy",
    "bpp.Rodzaj_Prawa_Patentowego",
    "bpp.Tryb_OpenAccess_Wydawnictwo_Ciagle",
    "bpp.Tryb_OpenAccess_Wydawnictwo_Zwarte",
    "bpp.Licencja_OpenAccess",
    "bpp.Wersja_Tekstu_OpenAccess",
    "bpp.Czas_Udostepnienia_OpenAccess",
    "bpp.Zewnetrzna_Baza_Danych",
    "bpp.Zrodlo_Informacji",
    "bpp.Grupa_Pracownicza",
    "bpp.Wymiar_Etatu",
    "bpp.Kierunek_Studiow",
    "bpp.Charakter_PBN",
    "ewaluacja_common.Rodzaj_Autora",
)


#: Per-relacyjny limit osadzanych wartości dla bezpiecznych słowników. Liczba
#: (a nie ``True``!) omija w djangoql-iplweb >= 0.31.1 zarówno twardy cap
#: ``MAX_SUGGESTED_VALUES`` (20 — tyle dałoby ``True``), jak i globalny próg
#: ``--max-fk-options`` (0 w komendzie). Dzięki temu do artefaktu trafiają PEŁNE
#: słowniki (np. wszystkie ~487 języków, komplet dyscyplin), a nie tylko pierwsze
#: 20 alfabetycznie. Wartość jest górnym ograniczeniem bezpieczeństwa: żaden
#: standardowy słownik referencyjny BPP nie zbliża się do tej liczności, więc
#: nic realnie nie jest ucinane; gdyby jednak tabela urosła ponad limit, djangoql
#: zwyczajnie pominie ją (zamiast wysypać ogromną listę w prompt).
_EMBED_ALL_VALUES = 10_000


def _build_llm_fk_options():
    """``fk_options`` dla eksportu LLM: dla każdego FK/​O2O w allow-liście, którego
    cel to bezpieczny słownik (:data:`_SAFE_VALUE_TARGET_LABELS`), wymuś
    osadzenie KOMPLETU wartości (``_EMBED_ALL_VALUES``). Reszta relacji przy
    ``--max-fk-options 0`` nie osadza nic → artefakt jest deterministyczny
    i wolny od danych instytucji.
    """
    from django.apps import apps

    safe = {apps.get_model(label) for label in _SAFE_VALUE_TARGET_LABELS}
    options = {}
    for owner in SEARCH_ALLOWLIST:
        for field in owner._meta.get_fields():
            is_fk = getattr(field, "many_to_one", False) or getattr(
                field, "one_to_one", False
            )
            if is_fk and not field.auto_created and field.related_model in safe:
                options.setdefault(owner, {})[field.name] = _EMBED_ALL_VALUES
    return options


class RekordLLMSchema(DeprecatedAndRestrictedFieldsMixin, ExtrasSchema):
    """Schemat dla eksportu opisu DjangoQL do promptu LLM.

    Baza ``ExtrasSchema`` (agregaty + części dat), **bez** pickerów
    ``<fk>__rel`` z ``BppQLSchema`` — te generują szum (``FieldError`` w logu,
    puste object_reference) i dla LLM są zbędne (uczymy notacji z kropką).
    Ta sama ``SEARCH_ALLOWLIST`` co widok, więc zapytania napisane wg tego
    schematu są poprawne wobec pełniejszego schematu widoku.

    ``fk_options`` wymusza osadzanie wartości tylko dla bezpiecznych słowników;
    w połączeniu z ``--max-fk-options 0`` (domyślnie w komendzie) daje
    deterministyczny, wolny od danych instytucji artefakt.
    """

    include = SEARCH_ALLOWLIST
    fk_options = _build_llm_fk_options()
    #: Twarda lista celów, których nazwy NIGDY nie trafiają do artefaktu —
    #: niezależnie od fk_options i --max-fk-options (wymaga djangoql-iplweb
    #: >= 0.30.3). Nazwy jednostek, wydziałów i uczelni to dane instytucji,
    #: nie standardowe słowniki — nie mają prawa wyciec nawet przy regeneracji
    #: z --max-fk-options > 0.
    no_value_targets = ("bpp.Jednostka", "bpp.Wydzial", "bpp.Uczelnia")
