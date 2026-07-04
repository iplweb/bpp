# Kolumny i filtry w adminie Źródeł: mniswID + liczba publikacji

Data: 2026-07-04
Gałąź: `feature/zrodlo-admin-mnisw-publikacje`

## Cel

Ułatwić redaktorowi w adminie Django (`Zrodlo`) porządkowanie źródeł:
odnalezienie i hurtowe usunięcie źródeł, które **nie mają publikacji**
oraz **nie mają mniswID** (ministerialnego identyfikatora z PBN).

## Kontekst kodu

- Model: `src/bpp/models/zrodlo.py:133` — `Zrodlo`. Relacja do PBN przez
  `pbn_uid` FK → `pbn_api.Journal` (nullable, `SET_NULL`).
- `mniswId`: `src/pbn_api/models/journal.py:21` — `IntegerField(null=True,
  db_index=True)` na `Journal`. Dostęp: `zrodlo.pbn_uid.mniswId`.
- Publikacje → źródło: **tylko** `Wydawnictwo_Ciagle.zrodlo`
  (`src/bpp/models/wydawnictwo_ciagle.py:139`, nullable `SET_NULL`, brak
  `related_name` → reverse `wydawnictwo_ciagle`). To jedyny realny model z FK
  do `Zrodlo`, więc autorytatywne źródło odpowiedzi „czy ma publikacje".
- Admin: `src/bpp/admin/zrodlo.py:111` — `ZrodloAdmin`. `list_display`
  pokazuje już `pbn_uid_id`. `BaseBppAdminMixin` **nie** nadpisuje
  `ModelAdmin.get_queryset(self, request)`.
- Filtry: `src/bpp/admin/filters.py` — bazy `SimpleNotNullFilter` (brak/jest)
  i `SimpleListFilter`. Istnieje `PBN_UID_IDObecnyFilter` (obecność `pbn_uid`).

## Rozróżnienie mniswID vs pbn_uid

Istniejący `PBN_UID_IDObecnyFilter` sprawdza obecność **`pbn_uid`**
(powiązanie z `Journal`). To NIE to samo co obecność `mniswId`: źródło może
mieć `pbn_uid`, ale powiązany `Journal` może mieć `mniswId = NULL`. Dlatego
potrzebny osobny filtr i osobna kolumna po `pbn_uid__mniswId`.

## Zmiany

Zero migracji, zero zmian w modelach. Dwa pliki:

### `src/bpp/admin/filters.py`

1. `MniswIdObecnyFilter(SimpleNotNullFilter)` — `db_field_name =
   "pbn_uid__mniswId"`, `parameter_name = "mnisw_id"`, tytuł „mniswID",
   etykiety „nie ma mniswID" / „ma mniswID".
2. `MaPublikacjeFilter(SimpleListFilter)` — `parameter_name =
   "ma_publikacje"`, tytuł „ma publikacje". Filtruje po annotacji
   `_liczba_prac` (dostarczanej przez `ZrodloAdmin.get_queryset`):
   - `"nie"` → `.filter(_liczba_prac=0)`
   - `"tak"` → `.filter(_liczba_prac__gt=0)`

### `src/bpp/admin/zrodlo.py`

1. `get_queryset(self, request)` — `super().get_queryset(request).annotate(
   _liczba_prac=Count("wydawnictwo_ciagle"))`.
2. Metoda `mnisw_id_display` — `@admin.display(description="mniswID",
   ordering="pbn_uid__mniswId")`, zwraca `obj.pbn_uid.mniswId if
   obj.pbn_uid_id else None`.
3. Metoda `liczba_prac_display` — `@admin.display(description="Publikacje",
   ordering="_liczba_prac")`, zwraca `obj._liczba_prac`.
4. `list_display` += `"mnisw_id_display"`, `"liczba_prac_display"`.
5. `list_filter` += `MniswIdObecnyFilter`, `MaPublikacjeFilter`.
6. `list_select_related` += `"pbn_uid"` (uniknięcie N+1 przy kolumnie
   mniswID).

## Workflow usuwania

Filtr „ma publikacje = nie ma" + „mniswID = nie ma mniswID" → zaznacz
wszystko → akcja „Usuń wybrane źródła".

## Testy (`src/bpp/tests/`)

TDD, pytest + `model_bakery.baker`, `@pytest.mark.django_db`:

- annotacja/kolumna liczby prac: źródło z N wydawnictwami ciągłymi → N;
  źródło bez prac → 0.
- kolumna mniswID: źródło z `pbn_uid`→`Journal(mniswId=123)` → 123; źródło
  bez `pbn_uid` → None; źródło z `pbn_uid`, ale `mniswId=None` → None.
- `MaPublikacjeFilter`: „nie" zwraca tylko źródła bez prac; „tak" tylko z
  pracami.
- `MniswIdObecnyFilter`: „brak" zwraca źródła bez mniswID (w tym te z
  `pbn_uid` ale `mniswId=None`); „jest" tylko z mniswID.

## Poza zakresem (YAGNI)

- Liczenie z cache `Rekord` (wszystkie typy rekordów) — źródła referuje tylko
  `Wydawnictwo_Ciagle`, więc niepotrzebne.
- Nowa akcja adminowa do usuwania — wbudowana akcja „Usuń wybrane" wystarcza.
