# Bezpieczne kasowanie pustych jednostek (admin)

Data: 2026-07-07
Status: zaakceptowany (design), do implementacji

## Problem

`JednostkaAdmin` bramkuje kasowanie wyłącznie po grupie
(`RestrictDeletionToAdministracjaGroupMixin`) — każdy członek grupy
`administracja` może usunąć jednostkę. Nie ma żadnego zabezpieczenia przed
tym, CO zniknie w kaskadzie.

Większość FK wskazujących na `Jednostka` ma `on_delete=CASCADE`
(`Autor_Jednostka`, `Jednostka_Rodzic`, cache `Autorzy`/`Rekord`, MPTT
`children` przez self-FK `parent`, …). Skutek: dzisiejsze skasowanie
jednostki **po cichu kaskaduje** — kasuje powiązania autor-jednostka,
historię przypisań, wpisy cache, całe poddrzewo podjednostek. To utrata
danych bez ostrzeżenia.

## Cel

Pozwolić skasować jednostkę **tylko wtedy, gdy jest w pełni pusta**:
ściśle zero referencji przez FK/M2M i zero podjednostek. W przeciwnym razie
odrzucić operację z czytelnym komunikatem, który wymienia CO blokuje.

## Decyzje projektowe

1. **Definicja „pustej" — ściśle zero referencji.** Jakikolwiek wiersz
   wskazujący na jednostkę przez FK/M2M blokuje kasowanie: podjednostki,
   `Autor_Jednostka` (nawet puste), własna historia `Jednostka_Rodzic`,
   cache, PBN itd. Nie rozróżniamy „własnych artefaktów" od „realnych
   powiązań" — wszystko liczy się jako blokada.

2. **Mechanizm/UX — bramkuj standardowy delete + komunikat.** Zostaje zwykły
   przycisk „Usuń" Django. Gdy jednostka ma referencje, strona potwierdzenia
   wyświetla listę blokad i **nie pozwala potwierdzić**. Gdy pusta — kasuje
   normalnie. Działa też dla akcji masowej „Usuń wybrane".

3. **Bramka grupy `administracja` zostaje bez zmian.** Nowy warunek „pusta"
   jest DODATKOWY — nie zastępuje istniejącego `has_delete_permission`
   opartego o grupę. Aby skasować: trzeba być w grupie `administracja`
   ORAZ jednostka musi być pusta.

## Architektura (trzy warstwy)

### 1. Warstwa logiki — model `Jednostka`

Jedno źródło prawdy, testowalne bez admina. W `src/bpp/models/jednostka.py`:

```python
def przeszkody_w_kasowaniu(self) -> list[tuple[str, int]]:
    """Lista (etykieta, liczba) niepustych odwrotnych relacji FK/M2M
    wskazujących na tę jednostkę. Pusta lista ⇔ jednostkę można skasować."""
```

- Iteruje po `self._meta.related_objects` (odwrotne FK/O2O) oraz relacjach
  M2M `auto_created`. Dla każdej relacji z `count() > 0` zwraca krotkę
  `(etykieta, liczba)`, gdzie `etykieta` bierze się z `verbose_name_plural`
  powiązanego modelu (np. „powiązania jednostka-rodzic", „jednostki
  podrzędne").
- Podjednostki (`children`, self-FK `parent`) pojawiają się tu naturalnie
  jako jedna z relacji — NIE ma osobnej gałęzi kodu „czy ma dzieci".
- Zwraca pustą listę wtedy i tylko wtedy, gdy jednostka jest w pełni pusta.

Helper:

```python
def czy_mozna_skasowac(self) -> bool:
    return not self.przeszkody_w_kasowaniu()
```

Uwagi implementacyjne:
- Odwrotny denorm self-FK `wydzial` (`related_name="+"`, `SET_NULL`) też
  istnieje w `_meta.related_objects`; dla pustej jednostki-liścia jest
  pusty, więc nie przeszkadza. Zgodnie ze „ściśle zero" jego niepustość
  (gdyby jakaś jednostka wskazywała `wydzial` na tę) też blokuje — co jest
  poprawne (to root z poddrzewem, i tak zablokowany przez `children`).
- Etykieta dla relacji bez czytelnego `verbose_name_plural` (np. `+`)
  degraduje do sensownego fallbacku (np. `related_model._meta.verbose_name_plural`).

### 2. Warstwa admina — `JednostkaAdmin`

Override `get_deleted_objects(self, objs, request)`:

- Woła `super().get_deleted_objects(objs, request)` →
  `(deletable_objects, model_count, perms_needed, protected)`.
- Dla każdej `obj` w `objs`, jeśli `obj.przeszkody_w_kasowaniu()` nie jest
  puste, dokłada do `protected` czytelny wpis, np.:
  *„Jednostka «X» — nie można usunąć: 3× powiązania autor-jednostka,
  2× jednostki podrzędne"*.
- Zwraca zmodyfikowaną krotkę. Django renderuje `protected` na stronie
  potwierdzenia i chowa przycisk potwierdzenia. Ten sam kod obsługuje delete
  pojedynczy i akcję masową (obie ścieżki wołają `get_deleted_objects`).

Defense-in-depth — guard w `delete_model` i `delete_queryset`:
- Jeśli jakąś inną drogą (skrypt, przyszły kod) trafi tam niepusta
  jednostka, odmów (pomiń/`messages.error`) zamiast po cichu kaskadować.
  Filtruje niepuste z que/pojedynczego usuwania.

`has_delete_permission` — **bez zmian** (istniejąca bramka grupy).

### 3. Testy (TDD, pytest + `model_bakery.baker`)

Model (`przeszkody_w_kasowaniu` / `czy_mozna_skasowac`):
- Pusta jednostka → `[]`, `czy_mozna_skasowac() is True`.
- Z jednym `Autor_Jednostka` → dokładnie jeden wpis, `czy_mozna_skasowac()`
  `is False`.
- Z podjednostką (`parent=jednostka`) → wpis „jednostki podrzędne".
- Z wpisem `Jednostka_Rodzic` (własna historia) → wpis blokujący
  (potwierdza semantykę „ściśle zero").

Admin (przez `client` zalogowany jako user w grupie `administracja`):
- POST delete na PUSTEJ jednostce → znika z bazy (`DoesNotExist`).
- GET/POST delete na NIEPUSTEJ → strona potwierdzenia zawiera wpis
  `protected`; obiekt NADAL istnieje po próbie.
- Akcja masowa „Usuń wybrane" na mieszance pusta+niepusta → pusta skasowana,
  niepusta zostaje.

## Świadomie poza zakresem (YAGNI)

- Brak zmian w API i management-commands — feature dotyczy wyłącznie admin UI.
- Brak „trybu wymuszonego kaskadowego kasowania" — jeśli coś wisi, użytkownik
  musi to najpierw ręcznie odpiąć/przenieść.
- Brak luzowania bramki grupy `administracja`.

## Pliki

- `src/bpp/models/jednostka.py` — metody `przeszkody_w_kasowaniu`,
  `czy_mozna_skasowac`.
- `src/bpp/admin/jednostka.py` — override `get_deleted_objects`,
  guardy `delete_model` / `delete_queryset` (możliwe wydzielenie do mixinu
  w `src/bpp/admin/core.py`, jeśli okaże się reużywalne).
- Testy: `src/bpp/tests/` (model) + test admina obok istniejących testów
  `JednostkaAdmin`.
- Newsfragment towncriera (feature).
