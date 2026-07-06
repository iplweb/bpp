# Zawężenie przeglądania jednostek do uczelni oglądającego

Data: 2026-06-30
Gałąź: `feature/multi-hosted-config`

## Problem

Strona przeglądania jednostek `/bpp/jednostki/` (`JednostkiView`) w trybie
multi-hosted pokazuje jednostki **wszystkich** uczelni w bazie, niezależnie
od tego, na której domenie/uczelni znajduje się oglądający. Powinna pokazywać
wyłącznie jednostki bieżącej uczelni (rozwiązanej z hosta przez
`Uczelnia.objects.get_for_request`).

## Decyzje (ustalone z użytkownikiem)

1. **Definicja „jednostka z uczelni"** = bezpośredni FK `Jednostka.uczelnia`
   równy bieżącej uczelni (`filter(uczelnia=biezaca_uczelnia)`).
   - NIE filtrujemy przez `wydzial__uczelnia`. Constraint w
     `Jednostka_Wydzial.clean()` i tak wymusza
     `wydzial.uczelnia == jednostka.uczelnia`, więc dla jednostek z wydziałem
     wynik jest tożsamy. Jednostki **bez** wydziału, należące do uczelni,
     pozostają widoczne.
2. **Bez `aktualna=True`** — zachowujemy dotychczasowy warunek widoczności
   `widoczna=True`. Nie zawężamy do jednostek aktualnie obecnych w strukturze
   wydziału.

## Projekt

### 1. Helper read-side: `scope_jednostki_do_uczelni`

W `src/bpp/util/uczelnia_scope.py` (dom istniejących reguł read-side:
`scope_rekord_do_uczelni`, `tylko_jedna_uczelnia`):

```python
def scope_jednostki_do_uczelni(qs, uczelnia):
    """Zawęź queryset Jednostka do uczelni oglądającego (multi-hosted).

    No-op gdy brak uczelni (brak mapowania Site→Uczelnia) albo gdy w
    systemie jest dokładnie jedna uczelnia — wynik identyczny.
    """
    if uczelnia is None or tylko_jedna_uczelnia():
        return qs
    return qs.filter(uczelnia=uczelnia)
```

Semantyka guardów identyczna jak `scope_rekord_do_uczelni` i jak
`UczelniaScopedAutocompleteMixin`:
- `uczelnia is None` (nierozwiązana uczelnia) → no-op (bezpieczny fallback),
- dokładnie jedna uczelnia w systemie → no-op (uniknięcie zbędnego `WHERE`).

### 2. Zastosowanie w `JednostkiView` (`src/bpp/views/browse.py`)

Dwa miejsca budujące queryset jednostek — oba muszą być spójne:

- `get_queryset()` — lista paginowana; filtr po `widoczna=True`.
- `get_context_data()` — `base_qry` użyte do `available_letters` (pasek A–Z).
  Bez tego samego filtra pasek liter reklamowałby litery istniejące tylko dla
  jednostek innych uczelni → kliknięcie prowadzi do pustej strony.

`uczelnia` jest w obu metodach już pobierana przez
`Uczelnia.objects.get_for_request(self.request)`.

## Zachowanie

- Multi-hosted (≥2 uczelnie), host → uczelnia X: tylko jednostki X i pasek
  liter X.
- Single-install: bez zmian (guard `tylko_jedna_uczelnia()` → no-op).
- Uczelnia nierozwiązana (`None`): bez zmian (pokazuje wszystko) — ten sam
  bezpieczny fallback co reszta read-side.

## Testy (TDD)

Wzorzec: `src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py`.

- Przy dwóch uczelniach + mapowaniu Site→Uczelnia: `JednostkiView` zwraca
  tylko jednostki uczelni oglądającego, a `available_letters` odzwierciedla
  tylko te jednostki.
- Single-install: zwraca wszystkie jednostki (guard → no-op).
- (Opcjonalnie) test jednostkowy samego `scope_jednostki_do_uczelni`.

## Zakres / poza zakresem

- W zakresie: `/bpp/jednostki/` i `/bpp/jednostki/<literka>/` (ten sam widok).
- Poza zakresem: zmiana znaczenia `aktualna`, filtrowanie przez wydział,
  inne widoki przeglądania.
