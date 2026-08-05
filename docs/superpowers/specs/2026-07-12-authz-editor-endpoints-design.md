# Centralna bramka autoryzacji dla mutujących endpointów redaktorskich

Data: 2026-07-12
Gałąź: `fix/authz-editor-endpoints` (baza: `dev`)

## Problem

W kilku modułach `login_required` / `LoginRequiredMixin` jest traktowane jak
uprawnienie redaktorskie. Zwykłe zalogowane konto (bez `is_staff`, bez grup,
bez uprawnień modelowych) może wywołać operacje modyfikujące dane globalne:

1. **Klonowanie publikacji/autorów** przez `/admin/.../toz/<pk>/` — mutacja
   już na GET; trasy wymagają tylko zalogowania
   (`src/django_bpp/urls.py`, `src/bpp/views/admin.py`).
2. **Nadpisywanie punktacji źródeł** (MNiSW, IF, SNIP, kwartyle, punktacja
   wewnętrzna) — `src/bpp/views/api/__init__.py` (`UploadPunktacjaZrodlaView`).
3. **Masowe przepinanie publikacji między źródłami, tworzenie/usuwanie źródeł,
   dodawanie do kolejki PBN** — `src/przemapuj_zrodla_pbn/views.py`.
4. **Usunięcie wszystkich `MetrykaAutora` + globalne przeliczenie** —
   `src/ewaluacja_optymalizacja/views/unpinning_analysis.py`.
5. **Toggle przypięcia rekordu po globalnym PK** —
   `src/ewaluacja_optymalizacja/views/evaluation_browser/views.py`
   (`browser_toggle_pin`).
6. **Przypinanie/odpinanie/zmiana dyscyplin** —
   `src/ewaluacja_optymalizuj_publikacje/views.py`.

Istniejący test dowodzi realności luki: zwykły użytkownik `baker.make` loguje
się i skutecznie usuwa źródło
(`src/przemapuj_zrodla_pbn/tests/test_views_actions.py`).

Właściwa kontrola już istnieje w projekcie, ale nie jest tu użyta:
`ma_pelne_uprawnienia_ewaluacji` = superuser **lub** grupa
`GR_WPROWADZANIE_DANYCH` (`src/ewaluacja_metryki/views/mixins.py`).

## Rozwiązanie

Dwie ortogonalne warstwy defektu; ten PR zamyka pierwszą (P0) oraz towarzyszący
jej problem „mutacja na GET". Scoping wielotenantowy (IDOR po globalnym PK) jest
świadomie **odroczony** do osobnego PR z fiksturami multi-uczelnia.

### 1. Wspólny prymityw autoryzacji — `src/bpp/permissions.py` (nowy plik)

Jedno źródło prawdy, domyślnie odmawiające dostępu, w trzech formach:

- `moze_wprowadzac_dane(user) -> bool` — superuser lub członek grupy
  `GR_WPROWADZANIE_DANYCH`.
- `WprowadzanieDanychRequiredMixin(LoginRequiredMixin)` — dla CBV.
  Anonim → 302 na login; zalogowany-bez-uprawnień → **403** (`PermissionDenied`).
- `wprowadzanie_danych_wymagane(view_func)` — dekorator dla FBV, ta sama
  semantyka.

`ewaluacja_metryki.views.mixins.ma_pelne_uprawnienia_ewaluacji` zostaje
przepięte, żeby delegowało do `moze_wprowadzac_dane` (bez zmiany zachowania —
zwijamy duplikat logiki do jednego helpera).

**Semantyka statusów (celowo):** anonim → login redirect (zachowuje kontrakt
istniejącego `test_usun_zrodlo_view_requires_login`); zalogowany-bez-uprawnień
→ 403 (czego wymaga review).

### 2. Zmiany w call-site'ach

| Moduł | Zmiana |
|-------|--------|
| `bpp/views/api/__init__.py` | 4 widoki: `LoginRequiredMixin` → `WprowadzanieDanychRequiredMixin` |
| `przemapuj_zrodla_pbn/views.py` | 3 FBV (`lista_skasowanych_zrodel`, `przemapuj_zrodlo`, `usun_zrodlo`): `@login_required` → `@wprowadzanie_danych_wymagane` |
| `ewaluacja_optymalizacja/.../unpinning_analysis.py` | `analyze_unpinning_opportunities`: dekorator |
| `ewaluacja_optymalizacja/.../evaluation_browser/views.py` | `browser_toggle_pin`: dekorator (zachowaj `@require_POST`) |
| `ewaluacja_optymalizuj_publikacje/views.py` | 2 CBV: mixin |

### 3. `toz`: GET → POST + CSRF

- `bpp/views/admin.py`: `TozView(RedirectView)` → `View` z metodą `post()`,
  która klonuje i zwraca `HttpResponseRedirect`, z mixinem
  `WprowadzanieDanychRequiredMixin`. Brak `get()` → GET zwraca 405
  (koniec mutacji-na-nawigacji).
- `src/django_bpp/urls.py`: usunąć owijkę `login_required(...)` (mixin
  przejmuje auth); nazwy URL bez zmian.
- 3 × `change_form.html` (ciagle/zwarte/patent): `location.href = "../../toz/"
  + pub_id` → dynamiczny `<form method="post">` z `csrfmiddlewaretoken`
  (czytany z ukrytego inputa formularza admina), `appendTo('body').submit()`.
  UX bez zmian: ten sam przycisk, to samo `confirm()`, natywny redirect.

### 4. Testy (TDD — najpierw czerwone)

- **Nowe** `src/bpp/tests/test_permissions.py`: helper + mixin + dekorator
  (anon→login, zwykły→403, grupa→pass, superuser→pass).
- **Nowe** testy 403 per-trasa: dla każdej mutującej trasy zwykły user → 403;
  członek grupy/superuser → nie-403. Plus `GET /toz/<pk>/` → 405.
- **Aktualizacja** `przemapuj_zrodla_pbn/tests/test_views_actions.py`: 4 testy
  logujące zwykłego usera dostają wspólnego usera-redaktora (happy path);
  stary test „zwykły user usuwa źródło" rozbity — happy path z grupą + nowy
  test zwykły user → 403.
- **Newsfragment** `src/bpp/newsfragments/<slug>.bugfix.rst` (PL).

### Weryfikacja

- `make tests-without-playwright` dla dotkniętych apek.
- Manualnie: przycisk „Toż" w adminie przez `run-site` (POST-klon działa).

## Poza zakresem (świadomie)

- Scoping bieżącej uczelni przy pobraniu po globalnym PK (IDOR wielotenantowy) —
  osobny PR z fiksturami multi-uczelnia.
- Zmiana grupy/roli redaktorskiej (per-model Django perms) — odrzucone na rzecz
  jednej centralnej bramki (superuser ∨ `GR_WPROWADZANIE_DANYCH`).
