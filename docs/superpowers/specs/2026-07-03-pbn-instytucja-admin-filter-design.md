# Filtr i kolumna „Instytucja PBN” w adminach PBN API (multi-hosted)

Data: 2026-07-03
Gałąź: `feature/multi-hosted-config`

## Cel

W instalacji multi-hosted (wiele `Uczelnia` w jednej bazie) superuser widzi
w adminie PBN API wiersze ze **wszystkich** uczelni naraz
(`SiteFilteredAdminMixin` filtruje po `uczelnia` tylko nie-superuserów).
Brakuje sposobu, żeby **odfiltrować po instytucji** i — w tabeli — **zobaczyć,
z której instytucji jest dany wiersz**.

Dotyczy trzech adminów:

- `PublikacjaInstytucji` (V1) — `src/pbn_api/admin/publikacjainstytucji_v1.py`
- `PublikacjaInstytucji_V2` — `src/pbn_api/admin/publikacjainstytucji_v2.py`
- `OswiadczenieInstytucji` — `src/pbn_api/admin/oswiadczenieinstytucji.py`

## Zakres — i czego NIE robimy

To zmiana **wyłącznie w warstwie admina**. Nie ruszamy modeli, migracji,
importu (`pbn_import`) ani write-side tagowania `uczelnia`.

Uzasadnienie: obowiązuje niezmiennik

```
Uczelnia.pbn_uid_id  ==  PublikacjaInstytucji.institutionId_id
                     ==  OswiadczenieInstytucji.institutionId_id
```

`institutionId` to FK do `pbn_api.Institution`, którego PK jest surowym UUID-em
instytucji z PBN — czyli dokładnie ta sama wartość co `uczelnia.pbn_uid_id`.
Filtrujemy więc po `institutionId` i nigdy nie dotykamy pola `uczelnia`.
(Pomysł „ustawiać uczelnia przy imporcie / dodać pole Uczelnia ID do V2”
został świadomie odrzucony — V2 i tak ma już tagowane `uczelnia`, a dla V1 /
Oświadczeń `institutionId` zawsze jest wypełnione, więc jest pewniejszym
źródłem filtra niż potencjalnie NULL-owy `uczelnia`.)

## Rozwiązanie

### 1. Współdzielona klasa filtra w `src/pbn_api/admin/filters.py`

Nowy `SimpleListFilter` (ta sama baza co istniejąca rodzina
`OdpowiednikWBPPFilter`):

```python
class InstytucjaPBNFilter(SimpleListFilter):
    title = "Instytucja PBN"
    parameter_name = "instytucja_pbn"
    field_name = "institutionId_id"  # V1 / Oświadczenia

    def lookups(self, request, model_admin):
        from bpp.models import Uczelnia

        choices = list(
            Uczelnia.objects.exclude(pbn_uid_id=None)
            .values_list("pbn_uid_id", "nazwa")
            .order_by("nazwa")
        )
        # ≤1 uczelnia → pusta lista → Django nie renderuje filtra
        # (has_output()). To jest bramka „tylko gdy >1 uczelnia”.
        if len(choices) <= 1:
            return []
        return choices

    def queryset(self, request, queryset):
        v = self.value()
        if v:
            return queryset.filter(**{self.field_name: v})
        return queryset


class InstytucjaPBNFilterV2(InstytucjaPBNFilter):
    # V2 nie ma institutionId — filtrujemy przez otagowaną uczelnia.
    field_name = "uczelnia__pbn_uid_id"
```

Właściwości:

- **Etykiety czytelne** (nazwa uczelni), ale wartość filtra to `pbn_uid_id`
  (UUID instytucji PBN) — ta sama dla obu wariantów `field_name`.
- **Auto-ukrywanie na single-tenant**: `lookups()` zwraca `[]` przy ≤1
  uczelni, więc na zwykłej instalacji filtr w ogóle się nie pokazuje.
- Zero ryzyka „mega-dropdownu” — nie listujemy `pbn_api.Institution`
  (tysiące obcych instytucji współautorów), tylko wiersze `Uczelnia`.

### 2. Warunkowa kolumna „Instytucja PBN” (`get_list_display`)

W każdym z trzech adminów override, który dokłada kolumnę **tylko gdy
`Uczelnia.objects.count() > 1`**:

```python
def get_list_display(self, request):
    ld = list(super().get_list_display(request))
    from bpp.models import Uczelnia

    if Uczelnia.objects.count() > 1:
        ld = ld + ["instytucja_pbn"]
    return ld

def instytucja_pbn(self, obj):
    return obj.institutionId  # V2: return obj.uczelnia

instytucja_pbn.short_description = "Instytucja PBN"
```

- V1 / Oświadczenia → `obj.institutionId` (zawsze wypełnione;
  `list_select_related` już obejmuje `institutionId` → zero dodatkowych
  zapytań na wiersz).
- V2 → `obj.uczelnia` (jego otagowane pole; V2 nie ma `institutionId`).

Na instalacji z jedną uczelnią: brak kolumny, brak filtra — bez zmian.

### 3. Podpięcie w adminach

Dla każdego z trzech adminów:

- dodać odpowiedni filtr do `list_filter`
  (`InstytucjaPBNFilter` dla V1 i Oświadczeń, `InstytucjaPBNFilterV2` dla V2),
- dodać override `get_list_display` + metodę `instytucja_pbn`.

## Uwaga projektowa (do decyzji przy review)

Bramką jest `Uczelnia.objects.count() > 1` (zgodnie z prośbą). Nie-superuser
i tak jest zawężony przez `SiteFilteredAdminMixin` do własnej uczelni, więc
filtr/kolumna są realnie użyteczne tylko dla superusera. Można — opcjonalnie —
dodatkowo zawęzić widoczność do `request.user.is_superuser`, ale nie jest to
konieczne (dla nie-superusera kolumna ma jedną wartość, a filtr zwróci pusty
zbiór dla obcej uczelni — nieszkodliwe). Domyślnie zostawiamy sam warunek
`count() > 1`.

## Testy

Pytest (konwencje projektu — funkcje, `@pytest.mark.django_db`, `baker.make`):

1. **Filtr — >1 uczelnia**: dwie `Uczelnia` z różnymi `pbn_uid`, po
   `PublikacjaInstytucji` / `OswiadczenieInstytucji` na każdą; wywołanie
   changelist z `?instytucja_pbn=<pbn_uid_1>` zwraca tylko wiersze tej
   instytucji.
2. **Filtr — V2**: analogicznie, filtr po `uczelnia__pbn_uid_id`.
3. **Auto-ukrywanie**: przy 1 uczelni `lookups()` zwraca `[]` (filtr się nie
   renderuje) i `get_list_display` nie zawiera `instytucja_pbn`.
4. **Kolumna — >1 uczelnia**: `get_list_display` zawiera `instytucja_pbn`,
   a metoda zwraca poprawną instytucję/uczelnię.

## Pliki

- `src/pbn_api/admin/filters.py` — nowe klasy `InstytucjaPBNFilter`,
  `InstytucjaPBNFilterV2`.
- `src/pbn_api/admin/publikacjainstytucji_v1.py` — `list_filter`,
  `get_list_display`, `instytucja_pbn`.
- `src/pbn_api/admin/publikacjainstytucji_v2.py` — j.w. (wariant V2).
- `src/pbn_api/admin/oswiadczenieinstytucji.py` — j.w.
- Test: `src/pbn_api/tests/` (np. `test_admin_instytucja_filter.py`).

Newsfragment towncriera (jeśli wymagane w tym repo dla zmian widocznych
w adminie).
